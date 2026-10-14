-- Relocation.lean
-- SERAPH Relocation: non-traversal maneuver to an admissible layer.
--
-- Relocation allows the system to leave a compromised operating vector
-- and arrive at an admissible functional layer without traversing the
-- attacked path — a non-traversal maneuver in state space.
--
-- Four structural conditions gate admissibility. All four must hold.
-- Missing any single condition closes the relocation path; the system
-- must repair or stabilize in place instead.
--
-- Relocation is not a bypass: guardian coherence and environmental
-- safety still bound the maneuver after relocation completes.
--
-- Admissibility conditions (Nat, scaled × 100):
--   torsion ≤ 200     (≤ 2.0 in Python kernel)
--   orbit_equivalent  (orbit class is preserved)
--   identity ≥ 80     (≥ 0.8 in Python kernel)
--   closure = 100     (= 1.0; full closure preservation required)
--
-- Lean 4, no mathlib.

set_option autoImplicit false

namespace SERAPH.Relocation

/-──────────────────────────────────────────────────────────────
  Relocation request
──────────────────────────────────────────────────────────────-/

/-- A relocation request carries the four admissibility parameters. -/
structure RelocationRequest where
  torsion              : Nat   -- path curvature × 100; must be ≤ 200
  orbitEquivalent      : Bool  -- orbit class preserved across the maneuver
  identityPreservation : Nat   -- identity fidelity × 100; must be ≥ 80
  closurePreservation  : Nat   -- closure fidelity × 100; must be = 100
deriving Repr, DecidableEq

/-- Admissibility threshold constants. -/
def maxTorsion  : Nat := 200   -- 2.0 × 100
def minIdentity : Nat := 80    -- 0.8 × 100
def fullClosure : Nat := 100   -- 1.0 × 100

/-──────────────────────────────────────────────────────────────
  Violation types
──────────────────────────────────────────────────────────────-/

/-- Each admissibility condition has a named violation. -/
inductive RelocationViolation where
  | TorsionExceeded  -- path curvature exceeds maximum
  | OrbitMismatch    -- orbit class not preserved
  | IdentityLoss     -- identity fidelity below minimum
  | ClosureLoss      -- closure not fully preserved
deriving Repr, DecidableEq, BEq

/-──────────────────────────────────────────────────────────────
  Admissibility evaluation
──────────────────────────────────────────────────────────────-/

def RelocationRequest.violations (r : RelocationRequest) : List RelocationViolation :=
  (if maxTorsion < r.torsion               then [.TorsionExceeded] else []) ++
  (if !r.orbitEquivalent                    then [.OrbitMismatch]   else []) ++
  (if r.identityPreservation < minIdentity  then [.IdentityLoss]    else []) ++
  (if r.closurePreservation ≠ fullClosure   then [.ClosureLoss]     else [])

/-- A request is admissible when it has no violations. -/
def RelocationRequest.admissible (r : RelocationRequest) : Bool :=
  r.violations.isEmpty

/-- When relocation is not requested, admissibility is trivially true.
    This mirrors the Python kernel: None request → admissible = True. -/
def evaluateRelocation (r : Option RelocationRequest) : Bool :=
  match r with
  | none     => true
  | some req => req.admissible

/-──────────────────────────────────────────────────────────────
  Theorems: admissibility conditions
──────────────────────────────────────────────────────────────-/

/-- **Theorem 1 (no_request_admissible)**
    When relocation is not requested, evaluation returns admissible. -/
theorem no_request_admissible : evaluateRelocation none = true := rfl

/-- **Theorem 2 (all_conditions_pass_is_admissible)**
    A request satisfying all four conditions is admissible. -/
theorem all_conditions_pass_is_admissible (r : RelocationRequest)
    (ht : r.torsion              ≤ maxTorsion)
    (ho : r.orbitEquivalent      = true)
    (hi : minIdentity            ≤ r.identityPreservation)
    (hc : r.closurePreservation  = fullClosure) :
    r.admissible = true := by
  have h1 : ¬ maxTorsion < r.torsion := by omega
  have h2 : ¬ r.identityPreservation < minIdentity := by omega
  simp [RelocationRequest.admissible, RelocationRequest.violations, h1, ho, h2, hc]

/-──────────────────────────────────────────────────────────────
  Theorems: single-condition failures
──────────────────────────────────────────────────────────────-/

/-- **Theorem 3 (torsion_exceeded_inadmissible)**
    Excessive path curvature alone is sufficient to block relocation. -/
theorem torsion_exceeded_inadmissible (r : RelocationRequest)
    (h : maxTorsion < r.torsion) :
    r.admissible = false := by
  simp [RelocationRequest.admissible, RelocationRequest.violations, h]

/-- **Theorem 4 (orbit_mismatch_inadmissible)**
    Orbit class mismatch alone is sufficient to block relocation. -/
theorem orbit_mismatch_inadmissible (r : RelocationRequest)
    (h : r.orbitEquivalent = false) :
    r.admissible = false := by
  simp [RelocationRequest.admissible, RelocationRequest.violations, h]

/-- **Theorem 5 (identity_loss_inadmissible)**
    Identity preservation below minimum alone blocks relocation. -/
theorem identity_loss_inadmissible (r : RelocationRequest)
    (h : r.identityPreservation < minIdentity) :
    r.admissible = false := by
  unfold RelocationRequest.admissible RelocationRequest.violations
  by_cases h1 : maxTorsion < r.torsion <;>
  cases ho : r.orbitEquivalent <;>
  by_cases h3 : r.closurePreservation ≠ fullClosure <;>
  simp [h, h1, h3]

/-- **Theorem 6 (closure_loss_inadmissible)**
    Partial closure preservation (anything less than 100) blocks relocation.
    The closure condition is exact: a system that cannot fully preserve
    closure cannot relocate; it must repair in place. -/
theorem closure_loss_inadmissible (r : RelocationRequest)
    (h : r.closurePreservation ≠ fullClosure) :
    r.admissible = false := by
  unfold RelocationRequest.admissible RelocationRequest.violations
  by_cases h1 : maxTorsion < r.torsion <;>
  cases ho : r.orbitEquivalent <;>
  by_cases h3 : r.identityPreservation < minIdentity <;>
  simp [h, h1, h3]

/-──────────────────────────────────────────────────────────────
  Theorems: all-conditions-required
──────────────────────────────────────────────────────────────-/

/-- **Theorem 7 (admissible_implies_torsion_bounded)**
    Admissibility implies torsion is within bounds.
    Contrapositive of Theorem 3. -/
theorem admissible_implies_torsion_bounded (r : RelocationRequest)
    (h : r.admissible = true) :
    r.torsion ≤ maxTorsion := by
  by_cases hc : r.torsion ≤ maxTorsion
  · exact hc
  · have hc' : maxTorsion < r.torsion := by omega
    rw [torsion_exceeded_inadmissible r hc'] at h
    exact Bool.noConfusion h

/-- **Theorem 8 (admissible_implies_orbit_equivalent)**
    Admissibility implies orbit class is preserved. -/
theorem admissible_implies_orbit_equivalent (r : RelocationRequest)
    (h : r.admissible = true) :
    r.orbitEquivalent = true := by
  cases hb : r.orbitEquivalent
  · rw [orbit_mismatch_inadmissible r hb] at h
    exact Bool.noConfusion h
  · rfl

/-- **Theorem 9 (all_four_conditions_required)**
    Admissibility is equivalent to all four conditions holding simultaneously. -/
theorem all_four_conditions_required (r : RelocationRequest) :
    r.admissible = true ↔
    r.torsion             ≤ maxTorsion ∧
    r.orbitEquivalent     = true       ∧
    minIdentity           ≤ r.identityPreservation ∧
    r.closurePreservation = fullClosure := by
  constructor
  · intro h
    refine ⟨admissible_implies_torsion_bounded r h,
            admissible_implies_orbit_equivalent r h, ?_, ?_⟩
    · by_cases hc : minIdentity ≤ r.identityPreservation
      · exact hc
      · have hc' : r.identityPreservation < minIdentity := by omega
        rw [identity_loss_inadmissible r hc'] at h
        exact Bool.noConfusion h
    · by_cases hc : r.closurePreservation = fullClosure
      · exact hc
      · rw [closure_loss_inadmissible r hc] at h
        exact Bool.noConfusion h
  · intro ⟨ht, ho, hi, hc⟩
    exact all_conditions_pass_is_admissible r ht ho hi hc

end SERAPH.Relocation
