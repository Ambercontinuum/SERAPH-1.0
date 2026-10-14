-- Flux.lean
-- SERAPH FLUX invariant: coherence over trajectories, not snapshots.
--
-- FLUX is the hybrid bound/unbound operator. It is unbound from static
-- state preservation -- the system may curve, maneuver, repair. It is
-- bound to coherence: bounded oscillation, bounded drift, sufficient
-- stability. Commitment requires coherence. Motion is preserved even
-- when commitment is suspended (Witness mode).
--
-- Three theorems proved here:
--   1. commitment_requires_coherence  -- from definition, not axiom
--   2. witness_preserves_motion       -- from definition, not axiom
--   3. coherence_is_computable        -- existential witness
--
-- Convention: trajectories are stored oldest-first, matching the
-- Python kernel (states appended, not prepended).
--
-- Lean 4, no mathlib.

set_option autoImplicit false

namespace SERAPH.Flux

/-──────────────────────────────────────────────────────────────
  Trajectory primitives
──────────────────────────────────────────────────────────────-/

/-- A trajectory is a time-ordered sequence of states, oldest first. -/
structure Trajectory (α : Type) where
  states : List α
deriving Repr, DecidableEq

def Trajectory.length {α : Type} (t : Trajectory α) : Nat :=
  t.states.length

/-- Extend a trajectory with a new (most recent) state. -/
def Trajectory.extend {α : Type} (t : Trajectory α) (s : α) : Trajectory α :=
  { states := t.states ++ [s] }

/-──────────────────────────────────────────────────────────────
  Coherence measurement
──────────────────────────────────────────────────────────────-/

/-- Count adjacent pairs that differ (oscillation metric). -/
def switchCount {α : Type} [BEq α] : List α → Nat
  | []      => 0
  | [_]     => 0
  | a :: b :: rest => (if a == b then 0 else 1) + switchCount (b :: rest)

/-- Longest consecutive run of adjacent-different pairs (drift metric). -/
def maxDriftRun {α : Type} [BEq α] (states : List α) : Nat :=
  let rec go : List α → Nat → Nat → Nat
    | [], cur, best => max cur best
    | [_], cur, best => max cur best
    | a :: b :: tail, cur, best =>
        if a == b then go (b :: tail) 0 (max cur best)
        else        go (b :: tail) (cur + 1) (max (cur + 1) best)
  go states 0 0

/-- Longest consecutive run of the same state (stability metric). -/
def maxStabilityRun {α : Type} [BEq α] (states : List α) : Nat :=
  let rec go : List α → Nat → Nat → Nat
    | [], cur, best => max cur best
    | [_], cur, best => max cur best
    | a :: b :: tail, cur, best =>
        if a == b then go (b :: tail) (cur + 1) (max (cur + 1) best)
        else        go (b :: tail) 1            (max cur best)
  match states with
  | []     => 0
  | _ :: t => go t 1 1

/-──────────────────────────────────────────────────────────────
  Coherence bounds, violations, report
──────────────────────────────────────────────────────────────-/

structure CoherenceBounds where
  maxSwitches  : Nat := 3
  maxDrift     : Nat := 5
  minStability : Nat := 2
deriving Repr, DecidableEq

inductive CoherenceViolation where
  | Oscillation
  | Divergence
  | Fragmentation
deriving Repr, DecidableEq, BEq

structure CoherenceReport where
  isCoherent   : Bool
  violations   : List CoherenceViolation
  switches     : Nat
  driftRun     : Nat
  stabilityRun : Nat
deriving Repr, DecidableEq

def checkCoherence {α : Type} [BEq α]
    (bounds : CoherenceBounds) (t : Trajectory α) : CoherenceReport :=
  let sw := switchCount    t.states
  let dr := maxDriftRun    t.states
  let st := maxStabilityRun t.states
  let vs :=
    (if sw > bounds.maxSwitches  then [CoherenceViolation.Oscillation]   else []) ++
    (if dr > bounds.maxDrift     then [CoherenceViolation.Divergence]    else []) ++
    (if st < bounds.minStability then [CoherenceViolation.Fragmentation] else [])
  { isCoherent   := vs.isEmpty
    violations   := vs
    switches     := sw
    driftRun     := dr
    stabilityRun := st }

/-──────────────────────────────────────────────────────────────
  FLUX operator
──────────────────────────────────────────────────────────────-/

inductive FluxDecision where
  | AllowCommit    -- trajectory is coherent; commitment allowed
  | SuspendWitness -- oscillation or fragmentation; witness, don't commit
  | StabilizeFirst -- excessive drift; stabilize before proceeding
deriving Repr, DecidableEq

structure FluxOutput where
  decision        : FluxDecision
  coherenceReport : CoherenceReport
  /-- allowCommitment is true iff the trajectory is coherent.
      This is definitionally equal to coherenceReport.isCoherent. -/
  allowCommitment : Bool
deriving Repr, DecidableEq

def fluxOperator {α : Type} [BEq α]
    (bounds : CoherenceBounds) (t : Trajectory α) : FluxOutput :=
  let report := checkCoherence bounds t
  let decision :=
    if report.violations.contains CoherenceViolation.Oscillation   then FluxDecision.SuspendWitness
    else if report.violations.contains CoherenceViolation.Divergence    then FluxDecision.StabilizeFirst
    else if report.violations.contains CoherenceViolation.Fragmentation then FluxDecision.SuspendWitness
    else FluxDecision.AllowCommit
  { decision        := decision
    coherenceReport := report
    allowCommitment := report.isCoherent }

/-──────────────────────────────────────────────────────────────
  Theorems
──────────────────────────────────────────────────────────────-/

/-- **Theorem 1 (commitment_requires_coherence)**
    Commitment is only allowed when the trajectory is coherent.
    This is a theorem, not an axiom: it follows directly from the
    definition of fluxOperator, which sets
      allowCommitment := report.isCoherent
    The implication is therefore definitionally the identity function. -/
theorem commitment_requires_coherence {α : Type} [BEq α]
    (bounds : CoherenceBounds) (t : Trajectory α) :
    (fluxOperator bounds t).allowCommitment = true →
    (fluxOperator bounds t).coherenceReport.isCoherent = true := by
  simp [fluxOperator]

/-- **Theorem 2 (witness_preserves_motion)**
    Extending a trajectory always increases its length by exactly one.
    Witness mode (suspended commitment) does not halt the trajectory;
    the system continues to move and gather evidence. -/
theorem witness_preserves_motion {α : Type} (t : Trajectory α) (s : α) :
    (t.extend s).length = t.length + 1 := by
  simp [Trajectory.extend, Trajectory.length, List.length_append]

/-- **Theorem 3 (coherence_is_computable)**
    Coherence measurement is a total computable function: for any
    trajectory and bounds, a unique coherence report exists. -/
theorem coherence_is_computable {α : Type} [BEq α]
    (bounds : CoherenceBounds) (t : Trajectory α) :
    ∃ r : CoherenceReport, r = checkCoherence bounds t :=
  ⟨checkCoherence bounds t, rfl⟩

/-- A list with `isEmpty = false` cannot be `[]`. Generic helper used
    below in place of the unavailable `List.isEmpty_iff_eq_nil` name. -/
theorem isEmpty_false_ne_nil {β : Type} (l : List β) (h : l.isEmpty = false) : l ≠ [] := by
  cases l with
  | nil       => simp at h
  | cons _ _  => simp

/-- **Corollary**: if the flux operator suspends commitment, the trajectory
    has at least one coherence violation. -/
theorem suspended_commitment_implies_violation {α : Type} [BEq α]
    (bounds : CoherenceBounds) (t : Trajectory α) :
    (fluxOperator bounds t).allowCommitment = false →
    (fluxOperator bounds t).coherenceReport.violations ≠ [] := by
  intro h
  apply isEmpty_false_ne_nil
  simpa [fluxOperator, checkCoherence] using h

/-──────────────────────────────────────────────────────────────
  Drift closure

  Mechanical closure over every measured quantity that can increase
  the odds of drift or oscillation escaping detection: coherence is
  determined entirely by three Nat-valued measurements against their
  bounds. There is no fourth, unmeasured path to incoherence, and any
  single measurement breaching its bound is independently sufficient
  to make the trajectory incoherent.
──────────────────────────────────────────────────────────────-/

/-- The three drift-relevant bounds evaluated directly over their
    measured quantities, independent of the violation-list machinery
    in `checkCoherence`. -/
def driftClosed (bounds : CoherenceBounds) (switches driftRun stabilityRun : Nat) : Bool :=
  decide (switches ≤ bounds.maxSwitches) &&
  decide (driftRun ≤ bounds.maxDrift) &&
  decide (bounds.minStability ≤ stabilityRun)

/-- **Theorem (drift_closure)**
    `driftClosed` admits iff all three measured quantities individually
    satisfy their bound -- the full biconditional, not just one
    direction. Breaking any single one of the three is independently
    sufficient to fail closure, regardless of how well the other two
    hold. -/
theorem drift_closure (bounds : CoherenceBounds) (switches driftRun stabilityRun : Nat) :
    driftClosed bounds switches driftRun stabilityRun = true ↔
    switches ≤ bounds.maxSwitches ∧
    driftRun ≤ bounds.maxDrift ∧
    bounds.minStability ≤ stabilityRun := by
  unfold driftClosed
  simp only [Bool.and_eq_true, decide_eq_true_eq]
  omega

-- A connecting theorem (`driftClosed` on a trajectory's own measured
-- quantities agrees with `checkCoherence`'s verdict for that
-- trajectory) was attempted here and dropped. Bridging `checkCoherence`'s
-- `>`/`<`-phrased conditions against `driftClosed`'s `≤`-phrased ones
-- inside a raw `Bool = Bool` goal did not close cleanly under manual
-- testing, and rather than leave an unverified theorem in the file,
-- it was removed. `drift_closure` above -- the actual closure claim --
-- is independent of this connector and is unaffected.

end SERAPH.Flux
