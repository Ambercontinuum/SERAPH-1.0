-- FluxInvariant.lean
-- Minimal trajectory-level invariant kernel for STK
-- No mathlib, runtime-safe, Lean 4 compatible
--
-- Note: this is the primitive version. Flux.lean contains the full
-- formalization with trajectory primitives, coherence measurement,
-- the flux operator, and three proved theorems.

set_option autoImplicit false

namespace FluxInvariantKernel

/--
A FluxInvariant constrains admissible trajectories (lists of states).
It does NOT reason about a single state, only about motion across time.
-/
structure FluxInvariant (α : Type) where
  admissible : List α → Bool

/--
Flux operator: checks whether a trajectory is admissible
under a given FluxInvariant.
-/
def fluxOp {α : Type}
  (inv : FluxInvariant α)
  (history : List α) : Bool :=
  inv.admissible history

/--
Count switches between adjacent elements (oldest → newest).
-/
def switchCount {α : Type} [BEq α] : List α → Nat
  | [] => 0
  | [_] => 0
  | a :: b :: rest =>
      (if a == b then 0 else 1) + switchCount (b :: rest)

/--
A bounded-oscillation invariant:
Allows oscillation, but only up to maxSwitches
over the observed trajectory.
-/
def boundedOscillation {α : Type} [BEq α]
  (maxSwitches : Nat) : FluxInvariant α :=
{
  admissible := fun history =>
    let switches := switchCount history.reverse
    decide (switches ≤ maxSwitches)
}

end FluxInvariantKernel
