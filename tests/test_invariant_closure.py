import math
import unittest

from fastapi.testclient import TestClient

from adapters.tool_guard import SAFE_DECISIONS, ToolCall, ToolGuard, ToolRisk
from seraph import (
    ConstraintFrame,
    ConstraintObservation,
    ConstraintResolution,
    Decision,
    DistillationDefenseVector,
    EnvironmentVector,
    GovernanceInput,
    GuardianState,
    PRPScore,
    PRPTrail,
    govern,
)
from seraph.server import app
from tests.helpers import closed_constraints, healthy_trail


class RuntimeClosureTests(unittest.TestCase):
    def test_commit_without_recovery_evidence_fails_closed(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("review", "review"),
                prp_trail=PRPTrail(),
                request_commit=True,
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("recovery_evidence_missing", decision.reasons)
        self.assertEqual(decision.deployment_posture.active_path, "sidecar")

    def test_invalid_constraint_frame_fails_closed(self):
        decision = govern(
            GovernanceInput(
                constraints=ConstraintFrame(
                    frame_id="invalid",
                    topology_id="tests",
                    topology_version="1",
                    transition_id="test",
                    required_relations=("scope_alignment",),
                    observations=(
                        ConstraintObservation(
                            name="",
                            resolution=ConstraintResolution.PROVEN,
                            scope="tests",
                        ),
                    ),
                ),
                trajectory=("observe", "observe"),
                prp_trail=healthy_trail(),
                request_commit=True,
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("constraint_frame_invalid", decision.reasons)

    def test_non_finite_environment_fails_closed(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("observe", "observe"),
                prp_trail=healthy_trail(),
                environment=EnvironmentVector(containment=math.nan),
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("invalid_environment_input", decision.reasons)

    def test_out_of_range_guardian_telemetry_fails_closed(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("observe", "observe"),
                prp_trail=healthy_trail(),
                guardian=GuardianState(authorization_pressure=-1.0),
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("invalid_guardian_input", decision.reasons)

    def test_invalid_distillation_input_cannot_crash_or_pass(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("observe", "observe"),
                prp_trail=healthy_trail(),
                distillation=DistillationDefenseVector(semantic_load_variance=-0.01),
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("invalid_distillation_input", decision.reasons)

    def test_non_finite_recovery_evidence_fails_closed(self):
        trail = PRPTrail()
        trail.push(PRPScore(math.inf, 1.0, 1.0))
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("review", "review"),
                prp_trail=trail,
                request_commit=True,
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("invalid_recovery_evidence", decision.reasons)

    def test_repair_is_not_an_execution_permit(self):
        self.assertNotIn(Decision.REPAIR, SAFE_DECISIONS)

    def test_risk_override_cannot_launder_destructive_call(self):
        guard = ToolGuard("override-test")
        decision = guard.evaluate(
            ToolCall(
                "destroy",
                ToolRisk.DESTROY,
                override_profile={
                    "blast_radius": 0.0,
                    "containment": 1.0,
                    "reversibility": 1.0,
                    "externality": 1.0,
                },
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("environment_invariant_failed", decision.reasons)

    def test_non_finite_risk_override_fails_closed(self):
        guard = ToolGuard("nan-override-test")
        decision = guard.evaluate(
            ToolCall(
                "write",
                ToolRisk.WRITE,
                override_profile={
                    "blast_radius": math.nan,
                    "containment": 1.0,
                    "reversibility": 1.0,
                    "externality": 1.0,
                },
            )
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("environment_invariant_failed", decision.reasons)


class HttpClosureTests(unittest.TestCase):
    def test_unknown_fields_are_rejected(self):
        response = TestClient(app).post(
            "/govern",
            json={"trajectory": ["observe", "observe"], "bypass": True},
        )
        self.assertEqual(response.status_code, 422)

    def test_public_policy_floor_is_not_caller_controlled(self):
        response = TestClient(app).post(
            "/govern",
            json={
                "trajectory": ["observe", "observe"],
                "min_env_safety": 0.0,
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
