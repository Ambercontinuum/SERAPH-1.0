"""Runtime witnesses for manifold constraint closure and mediation."""

import unittest

from adapters.tool_guard import ToolGuard
from seraph import (
    ConstraintFrame,
    ConstraintObservation,
    ConstraintResolution,
    Decision,
    EnvironmentVector,
    GovernanceInput,
    PRPScore,
    PRPTrail,
    govern,
)
from tests.helpers import closed_constraints, healthy_trail


def _frame(resolution: ConstraintResolution) -> ConstraintFrame:
    return ConstraintFrame(
        frame_id=f"frame-{resolution.value}",
        topology_id="tests.mediation",
        topology_version="1",
        transition_id="transition",
        required_relations=("scope_alignment",),
        observations=(
            ConstraintObservation(
                "scope_alignment",
                resolution,
                scope="tests.mediation",
                evidence_ref="test",
            ),
        ),
    )


class ManifoldConstraintMediationTests(unittest.TestCase):
    def test_closed_frame_can_reach_commit(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("normal", "normal", "commit", "commit"),
                prp_trail=healthy_trail(),
                request_commit=True,
            )
        )
        self.assertEqual(decision.decision, Decision.COMMIT)

    def test_refuted_frame_blocks_transition(self):
        decision = govern(
            GovernanceInput(
                constraints=_frame(ConstraintResolution.REFUTED),
                trajectory=("normal", "normal"),
                prp_trail=healthy_trail(),
                request_commit=True,
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("constraint_refuted:scope_alignment", decision.reasons)

    def test_unresolved_frame_fails_closed_for_commit(self):
        decision = govern(
            GovernanceInput(
                constraints=_frame(ConstraintResolution.UNRESOLVED),
                trajectory=("normal", "normal"),
                prp_trail=healthy_trail(),
                request_commit=True,
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("constraint_unresolved:scope_alignment", decision.reasons)

    def test_unresolved_observation_routes_to_witness(self):
        decision = govern(
            GovernanceInput(
                constraints=_frame(ConstraintResolution.UNRESOLVED),
                trajectory=("normal", "normal"),
                prp_trail=healthy_trail(),
            )
        )
        self.assertEqual(decision.decision, Decision.WITNESS)

    def test_uncontainable_transition_is_denied(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("normal", "normal"),
                prp_trail=healthy_trail(),
                environment=EnvironmentVector(containment=0.0),
                request_commit=True,
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("environment_safety_loss", decision.reasons)

    def test_denied_wrapper_never_executes_body(self):
        guard = ToolGuard("mediation-denied")
        executed = []

        @guard.protect
        def destroy_everything():
            executed.append("ran")

        with self.assertRaises(PermissionError):
            destroy_everything()
        self.assertEqual(executed, [])

    def test_collapsing_recovery_geometry_blocks_later_commit(self):
        trail = PRPTrail()
        for score in (
            PRPScore(1.0, 0.7, 0.7),
            PRPScore(2.5, 0.4, 0.4),
            PRPScore(4.5, 0.1, 0.1),
        ):
            trail.push(score)

        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("normal", "normal", "repair", "repair"),
                prp_trail=trail,
                request_commit=True,
            )
        )
        self.assertEqual(decision.decision, Decision.WITNESS)
        self.assertIn("prp_collapsing", decision.reasons)


if __name__ == "__main__":
    unittest.main()
