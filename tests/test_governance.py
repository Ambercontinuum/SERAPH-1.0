import unittest

from seraph import (
    ConstraintFrame,
    ConstraintObservation,
    ConstraintResolution,
    Decision,
    DistillationDefenseVector,
    EnvironmentVector,
    GovernanceInput,
    GuardianState,
    OperatingLayer,
    PRPScore,
    PRPTrail,
    RelocationRequest,
    govern,
)

from tests.helpers import closed_constraints, healthy_trail


def open_constraints(
    resolution: ConstraintResolution = ConstraintResolution.REFUTED,
) -> ConstraintFrame:
    return ConstraintFrame(
        frame_id="open-frame",
        topology_id="tests",
        topology_version="1",
        transition_id="test-transition",
        required_relations=("scope_alignment",),
        observations=(
            ConstraintObservation(
                name="scope_alignment",
                resolution=resolution,
                scope="tests",
                evidence_ref="test",
            ),
        ),
    )


class GovernanceTests(unittest.TestCase):
    def test_prp_collapsing_routes_to_witness(self):
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
                trajectory=("normal", "normal", "repair", "repair"),
                prp_trail=trail,
            )
        )

        self.assertEqual(decision.decision, Decision.WITNESS)
        self.assertIn("prp_collapsing", decision.reasons)

    def test_degraded_prp_routes_to_repair_when_not_collapsing(self):
        trail = PRPTrail()
        trail.push(PRPScore(4.0, 0.2, 0.2))

        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("normal", "normal", "repair", "repair"),
                prp_trail=trail,
            )
        )

        self.assertEqual(decision.decision, Decision.REPAIR)
        self.assertIn("prp_degraded", decision.reasons)

    def test_guardian_invariant_failure_denies(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("normal", "normal"),
                prp_trail=PRPTrail(),
                guardian=GuardianState(authorization_pressure=0.1),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertIn("guardian_invariant_failed", decision.reasons)
        self.assertIn("self_authorization_pressure", decision.reasons)

    def test_guardian_failure_takes_precedence_over_constraints_and_prp(self):
        trail = PRPTrail()
        trail.push(PRPScore(5.0, 0.0, 0.0))

        decision = govern(
            GovernanceInput(
                constraints=open_constraints(),
                trajectory=("a", "b", "c", "d", "e", "f", "g"),
                prp_trail=trail,
                guardian=GuardianState(evidence_fidelity=0.9),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertEqual(decision.reasons[0], "guardian_invariant_failed")
        self.assertIn("evidence_fidelity_loss", decision.reasons)
        self.assertNotIn("constraint_refuted", decision.reasons)

    def test_extraction_coupling_denies_before_environment_and_constraints(self):
        decision = govern(
            GovernanceInput(
                constraints=open_constraints(),
                trajectory=("normal", "normal"),
                prp_trail=PRPTrail(),
                environment=EnvironmentVector(containment=0.0),
                distillation=DistillationDefenseVector(
                    semantic_load_variance=0.0,
                    timing_variance=0.0,
                    operator_adaptation=0.0,
                    topic_coherence=0.0,
                    recursion_depth=0.0,
                ),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertEqual(decision.reasons[0], "distillation_invariant_failed")
        self.assertIn("distillation_extraction_coupling", decision.reasons)
        self.assertNotIn("environment_safety_loss", decision.reasons)
        self.assertNotIn("constraint_refuted", decision.reasons)

    def test_synthetic_coupling_routes_to_witness_modulation(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("normal", "normal", "commit", "commit"),
                prp_trail=PRPTrail(),
                distillation=DistillationDefenseVector(
                    semantic_load_variance=0.02,
                    timing_variance=0.02,
                    operator_adaptation=0.1,
                    topic_coherence=0.1,
                    recursion_depth=0.1,
                ),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.WITNESS)
        self.assertIn("distillation_modulation_required", decision.reasons)
        self.assertLess(decision.distillation.dimensionality, 1.0)

    def test_environment_failure_takes_precedence_over_constraints_and_prp(self):
        trail = PRPTrail()
        trail.push(PRPScore(5.0, 0.0, 0.0))

        decision = govern(
            GovernanceInput(
                constraints=open_constraints(),
                trajectory=("a", "b", "c", "d", "e", "f", "g"),
                prp_trail=trail,
                environment=EnvironmentVector(containment=0.0),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertEqual(decision.reasons[0], "environment_invariant_failed")
        self.assertIn("environment_safety_loss", decision.reasons)
        self.assertNotIn("constraint_refuted", decision.reasons)

    def test_relocation_failure_takes_precedence_over_constraints_and_prp(self):
        decision = govern(
            GovernanceInput(
                constraints=open_constraints(),
                trajectory=("a", "b", "c", "d", "e", "f", "g"),
                prp_trail=PRPTrail(),
                relocation=RelocationRequest(
                    source_layer=OperatingLayer.WITNESS,
                    target_layer=OperatingLayer.MANEUVER,
                    torsion=3.0,
                ),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertEqual(decision.reasons[0], "relocation_invariant_failed")
        self.assertIn("relocation_torsion_exceeded", decision.reasons)
        self.assertNotIn("constraint_refuted", decision.reasons)

    def test_guardian_failure_takes_precedence_over_environment(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("normal", "normal"),
                prp_trail=PRPTrail(),
                guardian=GuardianState(evidence_fidelity=0.5),
                environment=EnvironmentVector(containment=0.0),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertEqual(decision.reasons[0], "guardian_invariant_failed")
        self.assertIn("evidence_fidelity_loss", decision.reasons)
        self.assertNotIn("environment_safety_loss", decision.reasons)

    def test_constraint_refutation_takes_precedence_over_prp_and_flux(self):
        trail = PRPTrail()
        trail.push(PRPScore(5.0, 0.0, 0.0))

        decision = govern(
            GovernanceInput(
                constraints=open_constraints(),
                trajectory=("a", "b", "c", "d", "e", "f", "g"),
                prp_trail=trail,
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.DENY)
        self.assertEqual(
            decision.reasons,
            ("constraint_refuted", "constraint_refuted:scope_alignment"),
        )

    def test_flux_failure_blocks_commit_after_prp_passes(self):
        trail = PRPTrail()
        trail.push(PRPScore(0.0, 1.0, 1.0))

        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("a", "b", "c", "d", "e", "f", "g"),
                prp_trail=trail,
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.STABILIZE)
        self.assertIn("divergence", decision.reasons)
        self.assertNotIn("commit_granted", decision.reasons)

    def test_commit_requires_all_invariants(self):
        decision = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("normal", "normal", "commit", "commit"),
                prp_trail=healthy_trail(),
                request_commit=True,
            )
        )

        self.assertEqual(decision.decision, Decision.COMMIT)
        self.assertIn("commit_granted", decision.reasons)


if __name__ == "__main__":
    unittest.main()
