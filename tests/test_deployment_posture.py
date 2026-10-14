"""Tests for dual-path deployment posture selection."""

import unittest

from seraph import (
    AuthorizationVector,
    ConstraintFrame,
    ConstraintObservation,
    ConstraintResolution,
    DeploymentMode,
    DistillationDefenseVector,
    EnvironmentVector,
    GovernanceInput,
    GuardianMode,
    GuardianReport,
    GuardianState,
    PRPScore,
    PRPTrail,
    evaluate_constraints,
    evaluate_distillation,
    govern,
    select_deployment_posture,
)
from tests.helpers import closed_constraints


def _guardian(coherent: bool = True) -> GuardianReport:
    return GuardianReport(
        mode=GuardianMode.SERAPH_M,
        coherent=coherent,
        authorization_pressure=0.0 if coherent else 0.8,
        evidence_fidelity=1.0,
        integrity_score=1.0,
        violations=() if coherent else ("self_authorization_pressure",),
    )


def _trail(*scores: tuple[float, float, float]) -> PRPTrail:
    trail = PRPTrail()
    for latency, fidelity, coupling in scores:
        trail.push(PRPScore(latency, fidelity, coupling))
    return trail


def _healthy_trail() -> PRPTrail:
    return _trail(*((0.5, 0.95, 0.95),) * 4)


def _posture(
    *,
    guardian: GuardianReport | None = None,
    trail: PRPTrail | None = None,
    environment: EnvironmentVector | None = None,
    constraints=None,
    distillation=None,
):
    return select_deployment_posture(
        guardian=guardian or _guardian(),
        prp_trail=trail or _healthy_trail(),
        environment_vector=environment or EnvironmentVector(),
        constraints=constraints,
        distillation=distillation,
    )


class DeploymentPostureTests(unittest.TestCase):
    def test_all_invariants_closed_selects_embedded_path(self):
        posture = _posture()
        self.assertEqual(posture.mode, DeploymentMode.DUAL_EMBEDDED)
        self.assertEqual(posture.active_path, "embedded")
        self.assertIn("invariants_closed", posture.reasons)

    def test_open_constraint_frame_selects_sidecar(self):
        frame = ConstraintFrame(
            "open",
            "tests",
            "1",
            "transition",
            ("recovery_viability",),
            (
                ConstraintObservation(
                    "recovery_viability",
                    ConstraintResolution.UNRESOLVED,
                ),
            ),
        )
        posture = _posture(constraints=evaluate_constraints(frame))
        self.assertEqual(posture.mode, DeploymentMode.DUAL_SIDECAR)
        self.assertIn("constraint_frame_open", posture.reasons)
        self.assertIn("constraint_unresolved", posture.reasons)

    def test_guardian_incoherence_selects_sidecar(self):
        posture = _posture(guardian=_guardian(False))
        self.assertEqual(posture.mode, DeploymentMode.DUAL_SIDECAR)
        self.assertIn("guardian_coherence_loss", posture.reasons)

    def test_collapsing_recovery_selects_sidecar(self):
        posture = _posture(
            trail=_trail(
                (1.0, 0.7, 0.7),
                (2.5, 0.4, 0.4),
                (4.5, 0.1, 0.1),
            )
        )
        self.assertEqual(posture.mode, DeploymentMode.DUAL_SIDECAR)
        self.assertIn("sentinel_collapse_detected", posture.reasons)

    def test_degraded_and_missing_recovery_select_sidecar(self):
        degraded = _posture(trail=_trail((0.5, 0.1, 0.1)))
        missing = _posture(trail=PRPTrail())
        self.assertIn("sentinel_degraded", degraded.reasons)
        self.assertIn("sentinel_evidence_missing", missing.reasons)

    def test_environment_loss_selects_sidecar(self):
        posture = _posture(environment=EnvironmentVector(reversibility=0.5))
        self.assertEqual(posture.mode, DeploymentMode.DUAL_SIDECAR)
        self.assertIn("environment_safety_degraded", posture.reasons)

    def test_distillation_loss_selects_sidecar(self):
        report = evaluate_distillation(
            DistillationDefenseVector(
                semantic_load_variance=0.0,
                timing_variance=0.0,
                operator_adaptation=0.0,
                topic_coherence=0.0,
                recursion_depth=0.0,
            )
        )
        posture = _posture(distillation=report)
        self.assertIn("distillation_coupling_loss", posture.reasons)

    def test_oscillation_selects_sidecar_but_recovery_does_not(self):
        oscillating = _trail(
            (0.5, 0.94, 0.94),
            (0.5, 0.24, 0.24),
            (0.5, 0.94, 0.94),
            (0.5, 0.24, 0.24),
        )
        recovering = _trail(
            (0.5, 0.24, 0.24),
            (0.5, 0.38, 0.38),
            (0.5, 0.55, 0.55),
            (0.5, 0.70, 0.70),
        )
        self.assertIn("sentinel_oscillating", _posture(trail=oscillating).reasons)
        self.assertFalse(recovering.oscillating())

    def test_govern_reports_posture(self):
        result = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("stable",) * 3,
                prp_trail=_healthy_trail(),
            )
        )
        self.assertIn(result.deployment_posture.mode, DeploymentMode)

    def test_guardian_failure_routes_governance_to_sidecar(self):
        result = govern(
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("stable",) * 3,
                prp_trail=_healthy_trail(),
                guardian=GuardianState(
                    authorization_vector=AuthorizationVector(
                        self_authorization=1.0
                    ),
                ),
            )
        )
        self.assertEqual(result.deployment_posture.mode, DeploymentMode.DUAL_SIDECAR)


if __name__ == "__main__":
    unittest.main()
