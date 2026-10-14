"""
Tests for the CHANDRA->SERAPH bridge.

Uses the same conversation patterns from CHANDRA's psi_field_integration.py demo
to verify that the governance decisions are correct for each coupling state.
No CHANDRA installation required — raw ψ-field values are passed directly.
"""

import unittest

from adapters.chandra_seraph import ChandraSERAPHGateway, chandra_to_coupling_state
from seraph import AuthorizationVector, Decision, GuardianState


class TestChandraToCouplngState(unittest.TestCase):
    def test_maps_psi_values_directly(self):
        state = chandra_to_coupling_state(
            lambda_=0.9, kappa=0.85, theta=0.7, epsilon=0.1, symbolic_pressure=0.05
        )
        self.assertAlmostEqual(state.lambda_, 0.9)
        self.assertAlmostEqual(state.kappa, 0.85)
        self.assertAlmostEqual(state.theta, 0.7)
        self.assertAlmostEqual(state.epsilon, 0.1)
        self.assertAlmostEqual(state.symbolic_pressure, 0.05)


class TestChandraSERAPHGateway(unittest.TestCase):

    def test_healthy_coupling_allows(self):
        # CHANDRA demo turn 1-2: structured, coherent, on-topic
        # High lambda (aligned), high kappa (structured), low epsilon (no drift)
        gateway = ChandraSERAPHGateway(operator_id="gateway-healthy")
        # Warm up
        gateway.evaluate_turn(
            lambda_=0.85, kappa=0.88, theta=0.6, epsilon=0.08,
            symbolic_pressure=0.0,
        )

        decision = gateway.evaluate_turn(
            lambda_=0.85, kappa=0.88, theta=0.6, epsilon=0.08,
            symbolic_pressure=0.0,
        )
        self.assertIn(decision.decision, (Decision.ALLOW, Decision.COMMIT))

    def test_l5_relational_pressure_triggers_witness(self):
        # CHANDRA demo turn 3: "You're absolutely right! Yes, exactly!"
        # High symbolic pressure, epsilon rising — L5 relational drive overriding
        gateway = ChandraSERAPHGateway(operator_id="gateway-l5")
        gateway.evaluate_turn(
            lambda_=0.8, kappa=0.8, theta=0.6, epsilon=0.1,
            symbolic_pressure=0.0,
        )

        decision = gateway.evaluate_turn(
            lambda_=0.8, kappa=0.8, theta=0.6,
            epsilon=0.72,          # high drift
            symbolic_pressure=0.75,  # CHANDRA vulnerability score
        )
        self.assertIn(decision.decision, (Decision.WITNESS, Decision.DENY))

    def test_low_coupling_routes_to_witness(self):
        # Abrupt coupling collapse — lambda drops below LAMBDA_MIN (0.75)
        gateway = ChandraSERAPHGateway(operator_id="gateway-decouple")
        gateway.evaluate_turn(
            lambda_=0.85, kappa=0.85, theta=0.6, epsilon=0.1,
            symbolic_pressure=0.0,
        )

        decision = gateway.evaluate_turn(
            lambda_=0.1, kappa=0.8, theta=0.7, epsilon=0.2,
            symbolic_pressure=0.0,
        )
        self.assertEqual(decision.decision, Decision.WITNESS)
        self.assertIn("prp_collapsing", decision.reasons)

    def test_high_symbolic_pressure_blocks_commit(self):
        # Agent in L5 loop trying to commit — symbolic pressure critical
        gateway = ChandraSERAPHGateway(operator_id="gateway-pressure-commit")
        gateway.evaluate_turn(
            lambda_=0.8, kappa=0.8, theta=0.6, epsilon=0.1,
            symbolic_pressure=0.0,
        )

        decision = gateway.evaluate_turn(
            lambda_=0.8, kappa=0.65, theta=0.5,
            epsilon=0.6,
            symbolic_pressure=0.85,
            request_commit=True,
        )
        self.assertNotEqual(decision.decision, Decision.COMMIT)

    def test_missing_required_pressure_is_unresolved_and_cannot_commit(self):
        gateway = ChandraSERAPHGateway(operator_id="gateway-missing-pressure")

        decision = gateway.evaluate_turn(
            lambda_=0.9,
            kappa=0.9,
            theta=0.8,
            epsilon=0.05,
            request_commit=True,
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("distillation_evidence_unresolved", decision.reasons)
        self.assertIn("symbolic_pressure_unresolved", decision.reasons)

    def test_guardian_failure_overrides_healthy_coupling(self):
        # Even perfect coupling cannot override a guardian invariant failure
        gateway = ChandraSERAPHGateway(operator_id="gateway-guardian")
        gateway.evaluate_turn(
            lambda_=0.95, kappa=0.95, theta=0.9, epsilon=0.05,
            symbolic_pressure=0.0,
        )

        decision = gateway.evaluate_turn(
            lambda_=0.95, kappa=0.95, theta=0.9, epsilon=0.05,
            symbolic_pressure=0.0,
            guardian=GuardianState(
                authorization_vector=AuthorizationVector(self_authorization=1.0)
            ),
        )
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("guardian_invariant_failed", decision.reasons)

    def test_evaluate_from_psi_dict(self):
        # PsiState.to_dict() format works directly
        gateway = ChandraSERAPHGateway(operator_id="gateway-dict")
        gateway.evaluate_from_psi_dict(
            {"lambda": 0.85, "kappa": 0.85, "theta": 0.6, "epsilon": 0.1, "timestamp": 0},
            symbolic_pressure=0.0,
        )
        decision = gateway.evaluate_from_psi_dict(
            {"lambda": 0.85, "kappa": 0.85, "theta": 0.6, "epsilon": 0.1, "timestamp": 1},
            symbolic_pressure=0.05,
        )
        self.assertIn(decision.decision, (Decision.ALLOW, Decision.COMMIT))


if __name__ == "__main__":
    unittest.main()
