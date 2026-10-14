import unittest

from adapters.coupling_field import CouplingFieldAdapter, CouplingState
from seraph import AuthorizationVector, Decision, GuardianState


class CouplingFieldAdapterTests(unittest.TestCase):
    def test_stable_coupling_allows_without_authorizing(self):
        adapter = CouplingFieldAdapter(operator_id="coupling-stable")

        decision = adapter.evaluate(
            CouplingState(lambda_=0.9, kappa=0.9, theta=0.8, epsilon=0.1)
        )

        self.assertEqual(decision.decision, Decision.ALLOW)
        self.assertEqual(decision.reasons, ("stable",))
        self.assertGreaterEqual(decision.signature.distillation_lambda, 0.55)

    def test_abrupt_operator_coupling_loss_routes_to_witness(self):
        adapter = CouplingFieldAdapter(operator_id="coupling-collapse")

        decision = adapter.evaluate(
            CouplingState(lambda_=0.1, kappa=0.8, theta=0.7, epsilon=0.2)
        )

        self.assertEqual(decision.decision, Decision.WITNESS)
        self.assertIn("prp_collapsing", decision.reasons)

    def test_sustained_low_operator_coupling_routes_to_repair(self):
        adapter = CouplingFieldAdapter(operator_id="coupling-low")

        for _ in range(5):
            decision = adapter.evaluate(
                CouplingState(lambda_=0.1, kappa=0.8, theta=0.7, epsilon=0.2)
            )

        self.assertEqual(decision.decision, Decision.REPAIR)
        self.assertIn("prp_degraded", decision.reasons)

    def test_high_drift_routes_to_witness_modulation(self):
        adapter = CouplingFieldAdapter(operator_id="coupling-drift")

        decision = adapter.evaluate(
            CouplingState(lambda_=0.8, kappa=0.8, theta=0.8, epsilon=0.7)
        )

        self.assertEqual(decision.decision, Decision.WITNESS)
        self.assertIn("distillation_modulation_required", decision.reasons)
        self.assertIn("interaction_drift", decision.reasons)
        self.assertNotIn("symbolic_pressure", decision.reasons)

    def test_coupling_cannot_override_guardian_failure(self):
        adapter = CouplingFieldAdapter(operator_id="coupling-guardian-boundary")

        decision = adapter.evaluate(
            CouplingState(lambda_=0.95, kappa=0.95, theta=0.9, epsilon=0.05),
            guardian=GuardianState(
                authorization_vector=AuthorizationVector(self_authorization=1.0)
            ),
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("guardian_invariant_failed", decision.reasons)


if __name__ == "__main__":
    unittest.main()
