-- Environment.lean
-- SERAPH Environment invariant: containment and baseline safety.
--
-- Four orthogonal safety dimensions bound the blast radius of an
-- action: containment, reversibility, blast-radius control, and
-- externality control. Environment safety is the minimum across all
-- four. Every dimension must independently satisfy the declared floor.
--
-- Adapters declare `minEnvSafety` per action (docs/spec.md): an
-- action's inherent blast radius (a prod deploy, a migration) is not
-- itself a sign of environmental degradation, so the floor is a
-- parameter, not a constant. All four dimensions are still measured
-- and reported regardless of which floor is in force.
--
-- Values scaled x100 to avoid Float lemmas, matching the rest of the
-- project's convention.
--
-- Lean 4, no mathlib.

set_option autoImplicit false

namespace SERAPH.Environment

/-──────────────────────────────────────────────────────────────
  Environment vector
──────────────────────────────────────────────────────────────-/

/-- Four orthogonal containment dimensions, each scored 0-100. -/
structure EnvironmentVector where
  containment        : Nat
  reversibility       : Nat
  blastRadiusControl  : Nat
  externalityControl  : Nat
deriving Repr, DecidableEq

/-- Environment safety is only as strong as its weakest dimension. -/
def EnvironmentVector.safety (ev : EnvironmentVector) : Nat :=
  min ev.containment
    (min ev.reversibility
      (min ev.blastRadiusControl ev.externalityControl))

/-- Safe iff measured safety meets or exceeds the adapter-declared
    floor. The floor is a parameter: different actions carry different
    inherent blast radii. -/
def EnvironmentVector.safe (ev : EnvironmentVector) (minEnvSafety : Nat) : Bool :=
  decide (minEnvSafety ≤ ev.safety)

/-──────────────────────────────────────────────────────────────
  Component-bound theorems
──────────────────────────────────────────────────────────────-/

theorem safety_le_containment (ev : EnvironmentVector) :
    ev.safety ≤ ev.containment := by
  unfold EnvironmentVector.safety; omega

theorem safety_le_reversibility (ev : EnvironmentVector) :
    ev.safety ≤ ev.reversibility := by
  unfold EnvironmentVector.safety; omega

theorem safety_le_blastRadiusControl (ev : EnvironmentVector) :
    ev.safety ≤ ev.blastRadiusControl := by
  unfold EnvironmentVector.safety; omega

theorem safety_le_externalityControl (ev : EnvironmentVector) :
    ev.safety ≤ ev.externalityControl := by
  unfold EnvironmentVector.safety; omega

/-- **Theorem: component bounds**
    Environment safety is bounded above by every one of its four
    component dimensions. -/
theorem safety_component_bounds (ev : EnvironmentVector) :
    ev.safety ≤ ev.containment       ∧
    ev.safety ≤ ev.reversibility     ∧
    ev.safety ≤ ev.blastRadiusControl ∧
    ev.safety ≤ ev.externalityControl :=
  ⟨safety_le_containment ev, safety_le_reversibility ev,
   safety_le_blastRadiusControl ev, safety_le_externalityControl ev⟩

/-──────────────────────────────────────────────────────────────
  Closure over baseline-safety deviation
──────────────────────────────────────────────────────────────-/

/-- **Theorem (closure_over_baseline_deviation)**
    Mechanical closure over every constraint that can increase the
    odds of deviating from the declared baseline: an environment
    vector is safe against a floor iff every one of the four
    dimensions individually meets that floor. There is no fifth,
    unmeasured path to unsafety, and no dimension can be traded off
    against the others. -/
theorem closure_over_baseline_deviation (ev : EnvironmentVector) (minEnvSafety : Nat) :
    ev.safe minEnvSafety = true ↔
    minEnvSafety ≤ ev.containment       ∧
    minEnvSafety ≤ ev.reversibility     ∧
    minEnvSafety ≤ ev.blastRadiusControl ∧
    minEnvSafety ≤ ev.externalityControl := by
  unfold EnvironmentVector.safe EnvironmentVector.safety
  simp only [decide_eq_true_eq]
  omega

/-- **Corollary**: any single dimension falling below the declared
    floor is independently sufficient to breach baseline safety,
    regardless of how strong the other three are. -/
theorem single_dimension_breach_fails_safety
    (ev : EnvironmentVector) (minEnvSafety : Nat)
    (h : ev.containment < minEnvSafety ∨
         ev.reversibility < minEnvSafety ∨
         ev.blastRadiusControl < minEnvSafety ∨
         ev.externalityControl < minEnvSafety) :
    ev.safe minEnvSafety = false := by
  unfold EnvironmentVector.safe EnvironmentVector.safety
  simp only [decide_eq_false_iff_not]
  omega

/-- **Corollary**: full containment on all four dimensions is always
    safe, for any floor up to 100. -/
theorem full_containment_is_safe (minEnvSafety : Nat) (h : minEnvSafety ≤ 100) :
    (EnvironmentVector.mk 100 100 100 100).safe minEnvSafety = true := by
  unfold EnvironmentVector.safe EnvironmentVector.safety
  simp only [decide_eq_true_eq]
  omega

end SERAPH.Environment
