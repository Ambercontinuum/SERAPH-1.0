-- PRP.lean
-- SERAPH SENTINEL/PRP invariant: recovery geometry under perturbation.
--
-- A system that looks healthy at rest is not governance-ready if its
-- recovery geometry is degraded. SENTINEL evaluates three dimensions:
-- detection latency, recovery fidelity, and coupling preservation.
-- The PRP score is a weighted composition with weights summing to 100%.
--
-- The derivative of PRP over a sliding window detects collapse: a
-- system actively losing recovery capacity is structurally different
-- from one that is merely already low. A lower score with an improving
-- trend routes toward repair, not collapse.
--
-- All values are Nat scaled × 100 to avoid Float lemmas.
-- Python kernel weights: latency 30%, fidelity 40%, coupling 30%.
--
-- Lean 4, no mathlib.

set_option autoImplicit false

namespace SERAPH.PRP

/-──────────────────────────────────────────────────────────────
  PRP score
──────────────────────────────────────────────────────────────-/

/-- Three recovery dimensions, each scored 0–100. -/
structure PRPScore where
  latencyScore         : Nat  -- 100 * max(0, 1 − detection_latency / 5)
  recoveryFidelity     : Nat  -- 100 * fidelity
  couplingPreservation : Nat  -- 100 * coupling
deriving Repr, DecidableEq

/-- Component weights (sum to 100). -/
def wLatency  : Nat := 30
def wFidelity : Nat := 40
def wCoupling : Nat := 30

/-- Weighted PRP score.
    Division by 100 maps the numerator back to the 0–100 scale. -/
def PRPScore.overall (s : PRPScore) : Nat :=
  (wLatency  * s.latencyScore       +
   wFidelity * s.recoveryFidelity   +
   wCoupling * s.couplingPreservation) / 100

/-- Degradation threshold (= 0.40 in the Python kernel). -/
def degradedThreshold : Nat := 40

def PRPScore.degraded (s : PRPScore) : Bool :=
  decide (s.overall < degradedThreshold)

/-──────────────────────────────────────────────────────────────
  Theorems: score composition
──────────────────────────────────────────────────────────────-/

/-- **Theorem 1 (prp_weights_sum)**
    The three component weights sum to 100, representing 100%. -/
theorem prp_weights_sum : wLatency + wFidelity + wCoupling = 100 := by
  simp [wLatency, wFidelity, wCoupling]

/-- **Theorem 2 (prp_overall_bounded)**
    With all inputs in 0–100, the overall score is also in 0–100. -/
theorem prp_overall_bounded (s : PRPScore)
    (h1 : s.latencyScore       ≤ 100)
    (h2 : s.recoveryFidelity   ≤ 100)
    (h3 : s.couplingPreservation ≤ 100) :
    s.overall ≤ 100 := by
  simp only [PRPScore.overall, wLatency, wFidelity, wCoupling]
  omega

/-- **Theorem 3 (perfect_score_not_degraded)**
    Maximum scores on all three dimensions are not degraded. -/
theorem perfect_score_not_degraded :
    (PRPScore.mk 100 100 100).degraded = false := by
  decide

/-- **Theorem 4 (zero_score_degraded)**
    Zero recovery on all dimensions is degraded. -/
theorem zero_score_degraded :
    (PRPScore.mk 0 0 0).degraded = true := by
  decide

/-- **Theorem 5 (fidelity_and_coupling_sustain_prp)**
    Even with zero latency score, maximum fidelity and coupling together
    lift the overall score above the degradation threshold. -/
theorem fidelity_and_coupling_sustain_prp :
    ¬ (PRPScore.mk 0 100 100).degraded = true := by
  decide

/-──────────────────────────────────────────────────────────────
  PRP trail: trend direction
──────────────────────────────────────────────────────────────-/

/-- Trend direction over a PRP history window.
    The Python kernel computes a linear regression slope over a
    sliding window of up to four scores.  Here we model the structural
    property that matters for governance: positive trend routes repair,
    negative trend signals collapse. -/
inductive TrendDirection where
  | Positive  -- PRP improving
  | Flat      -- PRP stable
  | Negative  -- PRP declining
deriving Repr, DecidableEq

/-- A trail state captures the latest score and the current trend. -/
structure PRPTrailState where
  latest : PRPScore
  trend  : TrendDirection
deriving Repr, DecidableEq

/-- A trail is collapsing when latest is degraded AND trend is negative.
    Degraded with an improving trend routes toward repair instead. -/
def PRPTrailState.collapsing (trail : PRPTrailState) : Bool :=
  trail.latest.degraded && decide (trail.trend = TrendDirection.Negative)

/-──────────────────────────────────────────────────────────────
  Theorems: collapse detection
──────────────────────────────────────────────────────────────-/

/-- **Theorem 6 (collapsing_implies_degraded)**
    A collapsing trail necessarily has a degraded latest score.
    Collapse is strictly stronger than degradation. -/
theorem collapsing_implies_degraded (trail : PRPTrailState)
    (h : trail.collapsing = true) :
    trail.latest.degraded = true := by
  simp [PRPTrailState.collapsing] at h
  exact h.1

/-- **Theorem 7 (improving_trend_not_collapsing)**
    An improving trend cannot produce collapse, even if the latest
    score is below the degradation threshold. -/
theorem improving_trend_not_collapsing (trail : PRPTrailState)
    (h : trail.trend = TrendDirection.Positive) :
    trail.collapsing = false := by
  simp [PRPTrailState.collapsing, h]

/-- **Theorem 8 (flat_trend_not_collapsing)**
    A flat trend cannot produce collapse. -/
theorem flat_trend_not_collapsing (trail : PRPTrailState)
    (h : trail.trend = TrendDirection.Flat) :
    trail.collapsing = false := by
  simp [PRPTrailState.collapsing, h]

/-- **Theorem 9 (not_degraded_not_collapsing)**
    A trail whose latest score is not degraded cannot be collapsing. -/
theorem not_degraded_not_collapsing (trail : PRPTrailState)
    (h : trail.latest.degraded = false) :
    trail.collapsing = false := by
  simp [PRPTrailState.collapsing, h]

end SERAPH.PRP
