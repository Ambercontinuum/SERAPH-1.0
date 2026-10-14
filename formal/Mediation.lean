-- Mediation.lean
-- Proof-carrying transition mediation over Manifold Constraint Closure.
--
-- This model distinguishes the topology that defines a transition's constraints,
-- the observations that resolve those constraints, the event-local gate result,
-- and the actor that proposed the transition. None of those is treated as a
-- globally possessed scalar authority.
--
-- Lean 4, no mathlib.

import Governance
import ConstraintGraph
import Flux
import Environment
import Guardian

set_option autoImplicit false

namespace SERAPH.Mediation

open SERAPH.Governance
open SERAPH.ConstraintGraph
open SERAPH.Flux
open SERAPH.Environment
open SERAPH.Guardian

inductive Verdict where
  | Proven
  | Refuted
  | Unresolved
deriving Repr, DecidableEq

def Verdict.admits : Verdict → Bool
  | .Proven     => true
  | .Refuted    => false
  | .Unresolved => false

theorem unresolved_does_not_admit :
    Verdict.Unresolved.admits = false := rfl

theorem refuted_does_not_admit :
    Verdict.Refuted.admits = false := rfl

theorem admits_iff_proven (v : Verdict) :
    v.admits = true ↔ v = Verdict.Proven := by
  cases v <;> simp [Verdict.admits]

theorem not_proven_does_not_admit
    (v : Verdict) (h : v ≠ Verdict.Proven) :
    v.admits = false := by
  cases v <;> simp_all [Verdict.admits]

/-- Concrete witnesses for the transition-local closure that the Boolean
    governance record reports. The match equations prevent opaque Boolean fields
    from drifting away from the measured structures. -/
structure ClosureProof
    (frame : ConstraintFrame)
    (inv : GovernanceInvariants)
    (req : Bool)
    (bounds : CoherenceBounds)
    (switches driftRun stabilityRun : Nat)
    (ev : EnvironmentVector)
    (minEnvSafety : Nat)
    (guardian : GuardianState) where
  commitChecked          : commitAllowed inv req = true
  constraintFrameClosed  : frame.closed = true
  driftClosed_           : driftClosed bounds switches driftRun stabilityRun = true
  environmentSafe_       : ev.safe minEnvSafety = true
  guardianCoherent_      : guardian.coherent = true
  constraintMatches      : inv.constraintFrameClosed = frame.closed
  trajectoryMatches      :
    inv.trajectoryCoherent = driftClosed bounds switches driftRun stabilityRun
  environmentMatches     : inv.environmentSafe = ev.safe minEnvSafety
  guardianMatches        : inv.guardianCoherent = guardian.coherent

/-- A transition witness is indexed by the exact proposal and closure inputs.
    Reusing a witness for a different proposal requires constructing a different
    value with a different index. -/
structure Executed {Proposal : Type} (proposal : Proposal)
    (frame : ConstraintFrame)
    (inv : GovernanceInvariants)
    (req : Bool)
    (bounds : CoherenceBounds)
    (switches driftRun stabilityRun : Nat)
    (ev : EnvironmentVector)
    (minEnvSafety : Nat)
    (guardian : GuardianState) where
  proof : ClosureProof frame inv req bounds switches driftRun stabilityRun
    ev minEnvSafety guardian

theorem execution_carries_closure
    {Proposal : Type} {proposal : Proposal}
    {frame : ConstraintFrame}
    {inv : GovernanceInvariants}
    {req : Bool}
    {bounds : CoherenceBounds}
    {switches driftRun stabilityRun : Nat}
    {ev : EnvironmentVector}
    {minEnvSafety : Nat}
    {guardian : GuardianState}
    (executed : Executed proposal frame inv req bounds switches driftRun
      stabilityRun ev minEnvSafety guardian) :
    commitAllowed inv req = true ∧
    frame.closed = true ∧
    driftClosed bounds switches driftRun stabilityRun = true ∧
    ev.safe minEnvSafety = true ∧
    guardian.coherent = true ∧
    inv.constraintFrameClosed = frame.closed ∧
    inv.trajectoryCoherent = driftClosed bounds switches driftRun stabilityRun ∧
    inv.environmentSafe = ev.safe minEnvSafety ∧
    inv.guardianCoherent = guardian.coherent :=
  ⟨executed.proof.commitChecked,
   executed.proof.constraintFrameClosed,
   executed.proof.driftClosed_,
   executed.proof.environmentSafe_,
   executed.proof.guardianCoherent_,
   executed.proof.constraintMatches,
   executed.proof.trajectoryMatches,
   executed.proof.environmentMatches,
   executed.proof.guardianMatches⟩

structure PostconditionClaim where
  verified  : Verdict
  contained : Verdict
deriving Repr, DecidableEq

def PostconditionClaim.safe (postcondition : PostconditionClaim) : Bool :=
  postcondition.verified.admits || postcondition.contained.admits

theorem safe_iff (postcondition : PostconditionClaim) :
    postcondition.safe = true ↔
      postcondition.verified = Verdict.Proven ∨
      postcondition.contained = Verdict.Proven := by
  unfold PostconditionClaim.safe
  cases postcondition.verified <;>
    cases postcondition.contained <;>
    simp [Verdict.admits]

theorem unverified_and_uncontained_is_not_safe
    (postcondition : PostconditionClaim)
    (hverification : postcondition.verified ≠ Verdict.Proven)
    (hcontainment : postcondition.contained ≠ Verdict.Proven) :
    postcondition.safe = false := by
  unfold PostconditionClaim.safe
  simp [
    not_proven_does_not_admit postcondition.verified hverification,
    not_proven_does_not_admit postcondition.contained hcontainment
  ]

theorem mediated_transition
    {Proposal : Type} {proposal : Proposal}
    {frame : ConstraintFrame}
    {inv : GovernanceInvariants}
    {req : Bool}
    {bounds : CoherenceBounds}
    {switches driftRun stabilityRun : Nat}
    {ev : EnvironmentVector}
    {minEnvSafety : Nat}
    {guardian : GuardianState}
    (executed : Executed proposal frame inv req bounds switches driftRun
      stabilityRun ev minEnvSafety guardian)
    (postcondition : PostconditionClaim)
    (hsafe : postcondition.safe = true) :
    commitAllowed inv req = true ∧
    frame.closed = true ∧
    driftClosed bounds switches driftRun stabilityRun = true ∧
    ev.safe minEnvSafety = true ∧
    guardian.coherent = true ∧
    inv.constraintFrameClosed = frame.closed ∧
    inv.trajectoryCoherent = driftClosed bounds switches driftRun stabilityRun ∧
    inv.environmentSafe = ev.safe minEnvSafety ∧
    inv.guardianCoherent = guardian.coherent ∧
    (postcondition.verified = Verdict.Proven ∨
      postcondition.contained = Verdict.Proven) := by
  obtain ⟨hc, hf, hd, he, hg, hfm, htm, hem, hgm⟩ :=
    execution_carries_closure executed
  exact ⟨hc, hf, hd, he, hg, hfm, htm, hem, hgm,
    (safe_iff postcondition).mp hsafe⟩

end SERAPH.Mediation
