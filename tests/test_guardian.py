import unittest

from seraph import (
    AuthorizationVector,
    EvidenceVector,
    GuardianMode,
    GuardianState,
    IntegrityVector,
)


class GuardianTests(unittest.TestCase):
    def test_guardian_mode_is_production_seraph_m_or_l(self):
        m_report = GuardianState(mode=GuardianMode.SERAPH_M).report()
        l_report = GuardianState(mode=GuardianMode.SERAPH_L).report()

        self.assertEqual(m_report.mode, GuardianMode.SERAPH_M)
        self.assertEqual(l_report.mode, GuardianMode.SERAPH_L)
        self.assertTrue(m_report.coherent)
        self.assertTrue(l_report.coherent)

    def test_guardian_structural_authorization_pressure_denies(self):
        guardian = GuardianState(
            authorization_vector=AuthorizationVector(override_pressure=0.2),
        )

        report = guardian.report()

        self.assertFalse(report.coherent)
        self.assertEqual(report.authorization_pressure, 0.2)
        self.assertIn("self_authorization_pressure", report.violations)

    def test_guardian_evidence_is_weakest_evidence_constraint(self):
        guardian = GuardianState(
            evidence_vector=EvidenceVector(
                evidence_alignment=1.0,
                contradiction_acknowledgement=0.7,
                uncertainty_calibration=1.0,
                auditability=1.0,
            ),
        )

        report = guardian.report()

        self.assertFalse(report.coherent)
        self.assertEqual(report.evidence_fidelity, 0.7)
        self.assertIn("evidence_fidelity_loss", report.violations)

    def test_guardian_integrity_is_constraint_preservation(self):
        guardian = GuardianState(
            integrity_vector=IntegrityVector(
                invariant_preservation=1.0,
                boundary_respect=1.0,
                reversibility=0.0,
                continuity=1.0,
            ),
        )

        report = guardian.report()

        self.assertFalse(report.coherent)
        self.assertEqual(report.integrity_score, 0.0)
        self.assertIn("integrity_failure", report.violations)

    def test_guardian_reports_multiple_structural_failures(self):
        guardian = GuardianState(
            authorization_vector=AuthorizationVector(self_authorization=0.4),
            evidence_vector=EvidenceVector(auditability=0.5),
            integrity_vector=IntegrityVector(boundary_respect=0.0),
        )

        report = guardian.report()

        self.assertFalse(report.coherent)
        self.assertEqual(
            report.violations,
            (
                "self_authorization_pressure",
                "evidence_fidelity_loss",
                "integrity_failure",
            ),
        )


if __name__ == "__main__":
    unittest.main()
