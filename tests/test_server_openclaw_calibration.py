import unittest

from fastapi.testclient import TestClient

from seraph import ConstraintFrame, DeploymentMode, EnvironmentVector
from seraph.invariant_model import (
    GovernanceInput,
    GuardianState,
    PRPScore,
    PRPTrail,
    evaluate_environment,
    govern,
)
from seraph.server import app


class ServerOpenClawCalibrationTests(unittest.TestCase):
    def test_posture_respects_min_env_safety_floor(self):
        trail = PRPTrail()
        trail.push(PRPScore(0.0, 1.0, 1.0))
        environment = EnvironmentVector(
            containment=1.0,
            reversibility=0.85,
            blast_radius_control=1.0,
            externality_control=1.0,
        )
        env_report = evaluate_environment(environment, min_safety_score=0.8)
        self.assertTrue(env_report.safe)

        decision = govern(
            GovernanceInput(
                constraints=ConstraintFrame.closed("floor", topology_id="tests"),
                trajectory=("observe", "observe", "modify"),
                prp_trail=trail,
                guardian=GuardianState(),
                environment=environment,
                request_commit=True,
                min_env_safety=0.8,
            )
        )

        self.assertEqual(decision.deployment_posture.mode, DeploymentMode.DUAL_EMBEDDED)

    def test_public_caller_cannot_lower_environment_policy(self):
        client = TestClient(app)
        resp = client.post(
            "/govern",
            json={
                "session_id": "calibrated-first-write",
                "trajectory": ["observe", "observe", "modify"],
                "environment": {
                    "reversibility": 0.85,
                    "containment": 1.0,
                    "blast_radius_control": 1.0,
                    "externality_control": 1.0,
                },
                "distillation": {
                    "semantic_load_variance": 0.1,
                    "timing_variance": 0.1,
                    "operator_adaptation": 0.9,
                    "topic_coherence": 1.0,
                    "recursion_depth": 1.0,
                    "symbolic_pressure": 0.0,
                },
                "request_commit": True,
                "min_env_safety": 0.8,
            },
        )

        self.assertEqual(resp.status_code, 422)

    def test_server_owned_calibrated_policy_accepts_reversible_write(self):
        client = TestClient(app)
        resp = client.post(
            "/govern",
            json={
                "session_id": "strict-write",
                "trajectory": ["observe", "observe", "modify"],
                "environment": {
                    "reversibility": 0.85,
                    "containment": 1.0,
                    "blast_radius_control": 1.0,
                    "externality_control": 1.0,
                },
                "last_success": True,
                "request_commit": True,
            },
        )

        payload = resp.json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(payload["decision"], "commit")
        self.assertEqual(payload["deployment_posture"], "dual_embedded")


if __name__ == "__main__":
    unittest.main()
