-- ConstraintGraph.lean
-- Manifold Constraint Closure for scoped transition constraints.
--
-- Constraints are named, scoped relations with explicit resolution. The graph
-- does not assign a scalar authority strength and does not identify a global
-- authority holder. A frame closes only when every required node is proven.
--
-- Lean 4, no mathlib.

set_option autoImplicit false

namespace SERAPH.ConstraintGraph

inductive Resolution where
  | proven
  | refuted
  | unresolved
deriving Repr, DecidableEq

structure ConstraintNode where
  name       : String
  scope      : String
  horizon    : String
  required   : Bool
  resolution : Resolution
deriving Repr, DecidableEq

def ConstraintNode.closed (node : ConstraintNode) : Bool :=
  !node.required || decide (node.resolution = Resolution.proven)

structure ConstraintFrame where
  frameId         : String
  topologyId      : String
  topologyVersion : String
  transitionId    : String
  nodes           : List ConstraintNode
deriving Repr, DecidableEq

def ConstraintFrame.closed (frame : ConstraintFrame) : Bool :=
  frame.nodes.any (fun node => node.required) &&
  frame.nodes.all ConstraintNode.closed

theorem empty_frame_is_open :
    (ConstraintFrame.mk "frame" "topology" "1" "transition" []).closed = false := by
  simp [ConstraintFrame.closed]

theorem singleton_required_proven_frame_is_closed
    (name scope horizon : String) :
    (ConstraintFrame.mk "frame" "topology" "1" "transition"
      [ConstraintNode.mk name scope horizon true Resolution.proven]).closed = true := by
  simp [ConstraintFrame.closed, ConstraintNode.closed]

theorem required_proven_is_closed
    (name scope horizon : String) :
    (ConstraintNode.mk name scope horizon true Resolution.proven).closed = true := by
  simp [ConstraintNode.closed]

theorem required_refuted_is_open
    (name scope horizon : String) :
    (ConstraintNode.mk name scope horizon true Resolution.refuted).closed = false := by
  simp [ConstraintNode.closed]

theorem required_unresolved_is_open
    (name scope horizon : String) :
    (ConstraintNode.mk name scope horizon true Resolution.unresolved).closed = false := by
  simp [ConstraintNode.closed]

theorem optional_node_does_not_block
    (name scope horizon : String) (resolution : Resolution) :
    (ConstraintNode.mk name scope horizon false resolution).closed = true := by
  simp [ConstraintNode.closed]

theorem open_required_node_opens_frame
    (beforeNodes afterNodes : List ConstraintNode)
    (node : ConstraintNode)
    (hrequired : node.required = true)
    (hunproven : node.resolution ≠ Resolution.proven) :
    (ConstraintFrame.mk "frame" "topology" "1" "transition"
      (beforeNodes ++ node :: afterNodes)).closed = false := by
  simp [ConstraintFrame.closed, ConstraintNode.closed, hrequired, hunproven]

end SERAPH.ConstraintGraph
