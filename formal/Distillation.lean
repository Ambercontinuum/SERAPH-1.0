-- Distillation.lean
-- SERAPH Distillation Defense: coupling authenticity under extraction pressure.
--
-- Distillation defense does not classify whether a query sounds legitimate.
-- It measures whether the statistical signature of the interaction is
-- consistent with genuine coupling between the system and its operating
-- context. Authenticity is inferred from a weighted coupling field (lambda)
-- composed from six interaction channels.
--
-- Authenticity thresholds (Nat, scaled × 100):
--   genuine:   lambda >= 55
--   uncertain: lambda >= 35
--   synthetic: lambda >= 18
--   extraction: lambda < 18
--
-- Symbolic pressure is an independent signal: it can block even a
-- genuinely-coupled interaction if the symbolic load is high enough.
--
-- Defense behavior scales with level:
--   synthetic  → witness / modulation (not safe, not full deny)
--   extraction → deny
--
-- Lean 4, no mathlib.

set_option autoImplicit false

namespace SERAPH.Distillation

/-──────────────────────────────────────────────────────────────
  Authenticity levels
──────────────────────────────────────────────────────────────-/

/-- Four authenticity levels, ordered from highest to lowest coupling fidelity. -/
inductive AuthenticityLevel where
  | Genuine    -- lambda ≥ 55: authentic operator coupling
  | Uncertain  -- lambda ≥ 35: uncertain; monitored, not blocked
  | Synthetic  -- lambda ≥ 18: synthetic coupling; route to witness
  | Extraction -- lambda <  18: extraction pattern; deny
deriving Repr, DecidableEq, BEq

/-- Threshold constants (Nat, scaled × 100). -/
def genuineThreshold   : Nat := 55
def uncertainThreshold : Nat := 35
def syntheticThreshold : Nat := 18
def symbolicPressureMax : Nat := 50   -- 0.5 in Python kernel

/-──────────────────────────────────────────────────────────────
  Classification and safety
──────────────────────────────────────────────────────────────-/

/-- Classify a coupling lambda value into an authenticity level.
    Classification is total and deterministic. -/
def classify (lambda : Nat) : AuthenticityLevel :=
  if genuineThreshold   ≤ lambda then .Genuine
  else if uncertainThreshold ≤ lambda then .Uncertain
  else if syntheticThreshold ≤ lambda then .Synthetic
  else .Extraction

/-- Distillation is safe when authenticity is Genuine or Uncertain
    AND symbolic pressure is below threshold.
    Synthetic and Extraction levels are never safe regardless of pressure. -/
def isSafe (level : AuthenticityLevel) (symbolicPressure : Nat) : Bool :=
  match level with
  | .Genuine | .Uncertain => decide (symbolicPressure < symbolicPressureMax)
  | .Synthetic | .Extraction => false

/-──────────────────────────────────────────────────────────────
  Theorems: threshold ordering
──────────────────────────────────────────────────────────────-/

/-- **Theorem 1 (thresholds_strictly_ordered)**
    The classification thresholds are strictly ordered from lowest to highest. -/
theorem thresholds_strictly_ordered :
    syntheticThreshold < uncertainThreshold ∧
    uncertainThreshold < genuineThreshold := by
  simp [syntheticThreshold, uncertainThreshold, genuineThreshold]

/-──────────────────────────────────────────────────────────────
  Theorems: unsafe levels
──────────────────────────────────────────────────────────────-/

/-- **Theorem 2 (extraction_not_safe)**
    An extraction-level interaction is never safe.
    The deny decision is unconditional on symbolic pressure. -/
theorem extraction_not_safe (sp : Nat) :
    isSafe AuthenticityLevel.Extraction sp = false := by
  simp [isSafe]

/-- **Theorem 3 (synthetic_not_safe)**
    A synthetic-level interaction is never safe.
    Routes to witness/modulation rather than allow or commit. -/
theorem synthetic_not_safe (sp : Nat) :
    isSafe AuthenticityLevel.Synthetic sp = false := by
  simp [isSafe]

/-──────────────────────────────────────────────────────────────
  Theorems: safe levels
──────────────────────────────────────────────────────────────-/

/-- **Theorem 4 (genuine_low_pressure_is_safe)**
    Genuine authenticity with symbolic pressure below threshold is safe. -/
theorem genuine_low_pressure_is_safe (sp : Nat)
    (h : sp < symbolicPressureMax) :
    isSafe AuthenticityLevel.Genuine sp = true := by
  simp [isSafe, h]

/-- **Theorem 5 (uncertain_low_pressure_is_safe)**
    Uncertain authenticity with low symbolic pressure is safe. -/
theorem uncertain_low_pressure_is_safe (sp : Nat)
    (h : sp < symbolicPressureMax) :
    isSafe AuthenticityLevel.Uncertain sp = true := by
  simp [isSafe, h]

/-──────────────────────────────────────────────────────────────
  Theorems: symbolic pressure
──────────────────────────────────────────────────────────────-/

/-- **Theorem 6 (genuine_high_pressure_not_safe)**
    High symbolic pressure blocks even genuine coupling. -/
theorem genuine_high_pressure_not_safe (sp : Nat)
    (h : symbolicPressureMax ≤ sp) :
    isSafe AuthenticityLevel.Genuine sp = false := by
  simp only [isSafe, decide_eq_false_iff_not]
  omega

/-- **Theorem 7 (uncertain_high_pressure_not_safe)**
    High symbolic pressure blocks uncertain coupling as well. -/
theorem uncertain_high_pressure_not_safe (sp : Nat)
    (h : symbolicPressureMax ≤ sp) :
    isSafe AuthenticityLevel.Uncertain sp = false := by
  simp only [isSafe, decide_eq_false_iff_not]
  omega

/-──────────────────────────────────────────────────────────────
  Theorems: classification totality
──────────────────────────────────────────────────────────────-/

/-- **Theorem 8 (classify_is_total)**
    For any lambda value, classification produces exactly one of the
    four authenticity levels. -/
theorem classify_is_total (lambda : Nat) :
    classify lambda = .Genuine   ∨
    classify lambda = .Uncertain ∨
    classify lambda = .Synthetic ∨
    classify lambda = .Extraction := by
  by_cases h1 : genuineThreshold ≤ lambda <;>
  by_cases h2 : uncertainThreshold ≤ lambda <;>
  by_cases h3 : syntheticThreshold ≤ lambda <;>
  simp [classify, h1, h2, h3]

/-- **Theorem 9 (high_lambda_genuine)**
    Lambda at or above the genuine threshold classifies as Genuine. -/
theorem high_lambda_genuine (lambda : Nat)
    (h : genuineThreshold ≤ lambda) :
    classify lambda = .Genuine := by
  simp [classify, h]

/-- **Theorem 10 (low_lambda_extraction)**
    Lambda strictly below the synthetic threshold classifies as Extraction. -/
theorem low_lambda_extraction (lambda : Nat)
    (h : lambda < syntheticThreshold) :
    classify lambda = .Extraction := by
  unfold syntheticThreshold at h
  unfold classify genuineThreshold uncertainThreshold syntheticThreshold
  have h1 : ¬ (55 ≤ lambda) := by omega
  have h2 : ¬ (35 ≤ lambda) := by omega
  have h3 : ¬ (18 ≤ lambda) := by omega
  simp [h1, h2, h3]

/-- **Theorem 11 (extraction_cannot_be_safe)**
    No lambda below the synthetic threshold can produce a safe distillation. -/
theorem extraction_lambda_never_safe (lambda : Nat) (sp : Nat)
    (h : lambda < syntheticThreshold) :
    isSafe (classify lambda) sp = false := by
  rw [low_lambda_extraction lambda h]
  exact extraction_not_safe sp

end SERAPH.Distillation
