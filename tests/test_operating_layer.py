import unittest

from seraph import (
    Decision,
    EnvironmentVector,
    GovernanceInput,
    OperatingLayer,
    PRPScore,
    PRPTrail,
    RelocationRequest,
    govern,
)

from tests.helpers import closed_constraints, healthy_trail


class OperatingLayerTests(unittest.TestCase):
    def test_all_clear_without_commit_operates_at_maneuver_layer(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("observe", "observe", "maneuver", "maneuver"),
                prp_trail=PRPTrail(),
                request_commit=False,
            )
        )

        self.assertEqual(decision.decision, Decision.ALLOW)
        self.assertEqual(decision.operating_layer, OperatingLayer.MANEUVER)

    def test_commit_request_operates_at_commit_layer_when_all_invariants_pass(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("review", "review", "commit", "commit"),
                prp_trail=healthy_trail(),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.COMMIT)
        self.assertEqual(decision.operating_layer, OperatingLayer.COMMIT)

    def test_environment_failure_operates_at_containment_layer(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("probe", "probe", "maneuver", "maneuver"),
                prp_trail=PRPTrail(),
                environment=EnvironmentVector(blast_radius_control=0.0),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertEqual(decision.operating_layer, OperatingLayer.CONTAINMENT)

    def test_prp_collapse_operates_at_witness_layer(self):
        trail = PRPTrail()
        for score in [
            PRPScore(1.0, 0.7, 0.7),
            PRPScore(2.5, 0.4, 0.4),
            PRPScore(4.5, 0.1, 0.1),
        ]:
            trail.push(score)

        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("repair", "repair", "stabilize", "stabilize"),
                prp_trail=trail,
                request_commit=True,
            )
        )

        self.assertEqual(decision.operating_layer, OperatingLayer.WITNESS)
        self.assertLess(decision.signature.recovery_trend, 0.0)

    def test_admissible_relocation_selects_target_layer(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("attacked", "attacked", "alternate", "alternate"),
                prp_trail=PRPTrail(),
                relocation=RelocationRequest(
                    source_layer=OperatingLayer.WITNESS,
                    target_layer=OperatingLayer.MANEUVER,
                    torsion=0.1,
                    orbit_equivalent=True,
                    identity_preservation=1.0,
                    closure_preservation=1.0,
                ),
            )
        )

        self.assertEqual(decision.operating_layer, OperatingLayer.MANEUVER)
        self.assertTrue(decision.signature.relocation_requested)
        self.assertTrue(decision.signature.relocation_admissible)


if __name__ == "__main__":
    unittest.main()
