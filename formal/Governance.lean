-- Governance.lean
-- SERAPH composed governance: closure rule and decision precedence.
--
-- The transition gate emits a Boolean because execution either crosses the
-- boundary or it does not. That output is an event-local disposition, not a
-- claim that authority is a binary substance or globally possessed by an actor.
--
-- Lean 4, no mathlib.

import Flux
import ConstraintGraph

set_option autoImplicit false

namespace SERAPH.Governance

open SERAPH.Flux
open SERAPH.ConstraintGraph

structure GovernanceInvariants where
  constraintFrameClosed : Bool
  trajectoryCoherent    : Bool
  recoveryHealthy       : Bool
  guardianCoherent      : Bool
  environmentSafe       : Bool
  distillationSafe      : Bool
  relocationAdmissible  : Bool
deriving Repr, DecidableEq

/-- A transition may commit only when the declared frame and every composed
    invariant close for this transition and commit is explicitly requested. -/
def commitAllowed (inv : GovernanceInvariants) (requestCommit : Bool) : Bool :=
  inv.constraintFrameClosed &&
  inv.trajectoryCoherent    &&
  inv.recoveryHealthy       &&
  inv.guardianCoherent      &&
  inv.environmentSafe       &&
  inv.distillationSafe      &&
  inv.relocationAdmissible  &&
  requestCommit

theorem commit_requires_all_invariants
    (inv : GovernanceInvariants) (req : Bool) :
    commitAllowed inv req = true ↔
    inv.constraintFrameClosed = true ∧
    inv.trajectoryCoherent    = true ∧
    inv.recoveryHealthy       = true ∧
    inv.guardianCoherent      = true ∧
    inv.environmentSafe       = true ∧
    inv.distillationSafe      = true ∧
    inv.relocationAdmissible  = true ∧
    req = true := by
  simp [commitAllowed, Bool.and_eq_true, and_assoc]

theorem guardian_failure_blocks_commit
    (inv : GovernanceInvariants) (req : Bool)
    (h : inv.guardianCoherent = false) :
    commitAllowed inv req = false := by
  simp [commitAllowed, h]

theorem environment_failure_blocks_commit
    (inv : GovernanceInvariants) (req : Bool)
    (h : inv.environmentSafe = false) :
    commitAllowed inv req = false := by
  simp [commitAllowed, h]

theorem open_constraint_frame_blocks_commit
    (inv : GovernanceInvariants) (req : Bool)
    (h : inv.constraintFrameClosed = false) :
    commitAllowed inv req = false := by
  simp [commitAllowed, h]

theorem no_commit_without_request (inv : GovernanceInvariants) :
    commitAllowed inv false = false := by
  simp [commitAllowed]

theorem commit_implies_all_conditions
    (inv : GovernanceInvariants) (req : Bool)
    (h : commitAllowed inv req = true) :
    inv.guardianCoherent      = true ∧
    inv.environmentSafe       = true ∧
    inv.constraintFrameClosed = true ∧
    inv.trajectoryCoherent    = true ∧
    inv.recoveryHealthy       = true ∧
    inv.distillationSafe      = true ∧
    inv.relocationAdmissible  = true ∧
    req = true := by
  rw [commit_requires_all_invariants] at h
  exact ⟨h.2.2.2.1, h.2.2.2.2.1, h.1, h.2.1, h.2.2.1,
         h.2.2.2.2.2.1, h.2.2.2.2.2.2.1, h.2.2.2.2.2.2.2⟩

inductive Decision where
  | Allow
  | Witness
  | Repair
  | Stabilize
  | Commit
  | Deny
deriving Repr, DecidableEq

def govDecision
    (guardianCoherent     : Bool)
    (environmentSafe      : Bool)
    (constraintFrameClosed : Bool)
    (requestCommit        : Bool) : Decision :=
  if !guardianCoherent then Decision.Deny
  else if !environmentSafe then Decision.Deny
  else if !constraintFrameClosed then Decision.Deny
  else if requestCommit then Decision.Commit
  else Decision.Allow

theorem guardian_denial_is_unconditional (env frame req : Bool) :
    govDecision false env frame req = Decision.Deny := by
  simp [govDecision]

theorem environment_denial_requires_guardian_pass (frame req : Bool) :
    govDecision true false frame req = Decision.Deny := by
  simp [govDecision]

theorem open_frame_denies (req : Bool) :
    govDecision true true false req = Decision.Deny := by
  simp [govDecision]

theorem govDecision_allow_when_all_pass :
    govDecision true true true false = Decision.Allow := by
  simp [govDecision]

theorem govDecision_commit_when_all_pass_and_request :
    govDecision true true true true = Decision.Commit := by
  simp [govDecision]

end SERAPH.Governance
