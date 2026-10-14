from seraph import ConstraintFrame, PRPScore, PRPTrail


def closed_constraints(
    frame_id: str = "test-frame",
    *,
    topology_id: str = "tests",
    transition_id: str = "test-transition",
) -> ConstraintFrame:
    return ConstraintFrame.closed(
        frame_id,
        topology_id=topology_id,
        topology_version="1",
        transition_id=transition_id,
        evidence_ref="test-fixture",
    )


def healthy_trail() -> PRPTrail:
    trail = PRPTrail()
    trail.push(PRPScore(0.0, 1.0, 1.0))
    return trail
