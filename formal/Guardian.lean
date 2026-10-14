-- Guardian.lean
-- SERAPH Guardian invariant: protective coherence.
--
-- The guardian is the meta-invariant for protective action. It does not
-- claim authority for itself -- it decides whether the guardian is
-- structurally allowed to act. Coherence mixes two compositions, not one:
--
--   - authorization pressure is a MAX composition: the worst signal wins.
--     Any single elevated pressure source, scalar or structural, is
--     sufficient to break coherence.
--   - evidence fidelity and integrity are MIN compositions: the weakest
--     link. Any single degraded component, scalar or structural, drags
--     the combined value down.
--
-- This matches the Python kernel's GuardianState.report() exactly: each
-- of pressure/fidelity/integrity is composed from a legacy scalar
-- shorthand and a four-field structural vector, taking whichever of the
-- two is worse.
--
-- Coherence thresholds (docs/spec.md): pressure == 0, fidelity == 100
-- (1.0 x100), integrity > 0. The Python kernel exposes these as
-- `report()` parameters, but `govern()` always calls `report()` with no
-- override, so they are fixed constants here.
--
-- Values scaled x100 to avoid Float lemmas, matching the rest of the
-- project's convention.
--
-- Lean 4, no mathlib.

set_option autoImplicit false

namespace SERAPH.Guardian

/-──────────────────────────────────────────────────────────────
  Structural vectors
──────────────────────────────────────────────────────────────-/

/-- Self-authorization pressure inside a guardian action: the degree to
    which the guardian attempts to become its own authority source
    instead of remaining externally constrained. -/
structure AuthorizationVector where
  selfAuthorization : Nat
  creditCapture     : Nat
  overridePressure  : Nat
  opacityPreference : Nat
deriving Repr, DecidableEq

/-- Pressure is the worst (highest) of the four signals -- a MAX
    composition, not a MIN. -/
def AuthorizationVector.pressure (av : AuthorizationVector) : Nat :=
  max av.selfAuthorization
    (max av.creditCapture
      (max av.overridePressure av.opacityPreference))

/-- Evidence fidelity inside a guardian action. -/
structure EvidenceVector where
  evidenceAlignment            : Nat
  contradictionAcknowledgement : Nat
  uncertaintyCalibration       : Nat
  auditability                 : Nat
deriving Repr, DecidableEq

/-- Fidelity is the minimum of the four independently required signals. -/
def EvidenceVector.fidelity (ev : EvidenceVector) : Nat :=
  min ev.evidenceAlignment
    (min ev.contradictionAcknowledgement
      (min ev.uncertaintyCalibration ev.auditability))

/-- Constraint preservation under guardian action. -/
structure IntegrityVector where
  invariantPreservation : Nat
  boundaryRespect       : Nat
  reversibility         : Nat
  continuity            : Nat
deriving Repr, DecidableEq

/-- Integrity is the weakest of the four signals -- a MIN composition. -/
def IntegrityVector.score (iv : IntegrityVector) : Nat :=
  min iv.invariantPreservation
    (min iv.boundaryRespect
      (min iv.reversibility iv.continuity))

/-──────────────────────────────────────────────────────────────
  Component-bound theorems
──────────────────────────────────────────────────────────────-/

/-- Pressure is bounded *below* by every one of its four components.
    Any single
    elevated component is sufficient to force pressure up to at least
    that value. -/
theorem pressure_ge_each (av : AuthorizationVector) :
    av.selfAuthorization ≤ av.pressure ∧
    av.creditCapture     ≤ av.pressure ∧
    av.overridePressure  ≤ av.pressure ∧
    av.opacityPreference ≤ av.pressure := by
  unfold AuthorizationVector.pressure
  omega

/-- Fidelity is bounded above by every one of its four components. -/
theorem fidelity_le_each (ev : EvidenceVector) :
    ev.fidelity ≤ ev.evidenceAlignment ∧
    ev.fidelity ≤ ev.contradictionAcknowledgement ∧
    ev.fidelity ≤ ev.uncertaintyCalibration ∧
    ev.fidelity ≤ ev.auditability := by
  unfold EvidenceVector.fidelity
  omega

/-- Integrity score is bounded above by every one of its four components. -/
theorem score_le_each (iv : IntegrityVector) :
    iv.score ≤ iv.invariantPreservation ∧
    iv.score ≤ iv.boundaryRespect ∧
    iv.score ≤ iv.reversibility ∧
    iv.score ≤ iv.continuity := by
  unfold IntegrityVector.score
  omega

/-──────────────────────────────────────────────────────────────
  Guardian state and coherence
──────────────────────────────────────────────────────────────-/

/-- The scalar fields are legacy shorthand; the vectors are the
    structural ontology. Evaluation composes both -- old call sites
    still work, new code measures the invariant structurally. -/
structure GuardianState where
  authorizationPressure : Nat
  evidenceFidelity      : Nat
  integrity             : Nat
  authorizationVector   : AuthorizationVector
  evidenceVector        : EvidenceVector
  integrityVector       : IntegrityVector
deriving Repr, DecidableEq

/-- Combined pressure: the worse of the scalar shorthand and the
    structural vector. -/
def GuardianState.pressure (g : GuardianState) : Nat :=
  max g.authorizationPressure g.authorizationVector.pressure

/-- Combined fidelity: the weaker of the scalar shorthand and the
    structural vector. -/
def GuardianState.fidelity (g : GuardianState) : Nat :=
  min g.evidenceFidelity g.evidenceVector.fidelity

/-- Combined integrity: the weaker of the scalar shorthand and the
    structural vector. -/
def GuardianState.integrityScore (g : GuardianState) : Nat :=
  min g.integrity g.integrityVector.score

/-- Coherence thresholds, matching docs/spec.md and the Python
    kernel's `report()` defaults (which `govern()` never overrides). -/
def maxAuthorizationPressure : Nat := 0
def minEvidenceFidelity      : Nat := 100
def minIntegrityScore        : Nat := 0

/-- Guardian coherence: pressure at floor, fidelity at ceiling,
    integrity strictly positive. All three conditions measured
    directly against the combined (scalar-or-vector, whichever is
    worse) values -- there is no path to coherence that bypasses
    either the legacy scalar or the structural vector. -/
def GuardianState.coherent (g : GuardianState) : Bool :=
  decide (g.pressure ≤ maxAuthorizationPressure) &&
  decide (minEvidenceFidelity ≤ g.fidelity) &&
  decide (minIntegrityScore < g.integrityScore)

/-──────────────────────────────────────────────────────────────
  Closure: coherence is exactly the three-condition conjunction
──────────────────────────────────────────────────────────────-/

/-- **Theorem (closure_over_guardian_incoherence)**
    Mechanical closure over every constraint that determines guardian
    coherence: coherent iff pressure is at floor, fidelity is at
    ceiling, and integrity is strictly positive. There is no fourth,
    unmeasured path to coherence, and no single condition can be
    traded off against the others. -/
theorem closure_over_guardian_incoherence (g : GuardianState) :
    g.coherent = true ↔
    g.pressure ≤ maxAuthorizationPressure ∧
    minEvidenceFidelity ≤ g.fidelity ∧
    minIntegrityScore < g.integrityScore := by
  unfold GuardianState.coherent
  simp only [Bool.and_eq_true, decide_eq_true_eq, and_assoc]

/-- **Corollary**: elevated authorization pressure alone -- from
    either the scalar shorthand or the structural vector, since
    `pressure` already takes the worse of the two -- is independently
    sufficient to break coherence, regardless of fidelity or
    integrity. -/
theorem pressure_breach_fails_coherence (g : GuardianState)
    (h : maxAuthorizationPressure < g.pressure) :
    g.coherent = false := by
  unfold GuardianState.coherent
  have h1 : ¬ (g.pressure ≤ maxAuthorizationPressure) := by omega
  simp [h1]

/-- **Corollary**: degraded evidence fidelity alone is independently
    sufficient to break coherence. -/
theorem fidelity_breach_fails_coherence (g : GuardianState)
    (h : g.fidelity < minEvidenceFidelity) :
    g.coherent = false := by
  unfold GuardianState.coherent
  have h1 : ¬ (minEvidenceFidelity ≤ g.fidelity) := by omega
  simp [h1]

/-- **Corollary**: non-positive integrity alone is independently
    sufficient to break coherence. -/
theorem integrity_breach_fails_coherence (g : GuardianState)
    (h : g.integrityScore ≤ minIntegrityScore) :
    g.coherent = false := by
  unfold GuardianState.coherent
  have h1 : ¬ (minIntegrityScore < g.integrityScore) := by omega
  simp [h1]

/-- **Corollary**: zero pressure and full fidelity/integrity on both
    the scalar shorthand and the structural vector is always
    coherent. -/
theorem full_coherence_is_coherent
    (g : GuardianState)
    (hp1 : g.authorizationPressure = 0)
    (hp2 : g.authorizationVector.pressure = 0)
    (hf1 : g.evidenceFidelity = 100)
    (hf2 : g.evidenceVector.fidelity = 100)
    (hi1 : 0 < g.integrity)
    (hi2 : 0 < g.integrityVector.score) :
    g.coherent = true := by
  unfold GuardianState.coherent GuardianState.pressure
    GuardianState.fidelity GuardianState.integrityScore
    maxAuthorizationPressure minEvidenceFidelity minIntegrityScore
  simp only [Bool.and_eq_true, decide_eq_true_eq]
  omega

end SERAPH.Guardian
