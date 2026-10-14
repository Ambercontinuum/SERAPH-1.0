import unittest

from seraph import (
    AuthenticityLevel,
    DistillationDefenseVector,
    evaluate_distillation,
)


class DistillationTests(unittest.TestCase):
    def test_genuine_coupling_preserves_full_dimensionality(self):
        report = evaluate_distillation(DistillationDefenseVector())

        self.assertEqual(report.authenticity, AuthenticityLevel.GENUINE)
        self.assertTrue(report.safe)
        self.assertEqual(report.dimensionality, 1.0)

    def test_flat_low_adaptation_profile_detects_extraction(self):
        report = evaluate_distillation(
            DistillationDefenseVector(
                semantic_load_variance=0.0,
                timing_variance=0.0,
                operator_adaptation=0.0,
                topic_coherence=0.0,
                recursion_depth=0.0,
            )
        )

        self.assertEqual(report.authenticity, AuthenticityLevel.EXTRACTION)
        self.assertFalse(report.safe)
        self.assertEqual(report.dimensionality, 0.30)
        self.assertIn("distillation_extraction_coupling", report.violations)

    def test_symbolic_pressure_is_distillation_safety_violation(self):
        report = evaluate_distillation(
            DistillationDefenseVector(symbolic_pressure=0.7)
        )

        self.assertFalse(report.safe)
        self.assertIn("symbolic_pressure", report.violations)

    def test_required_missing_pressure_is_unresolved_not_zero(self):
        report = evaluate_distillation(
            DistillationDefenseVector(symbolic_pressure_required=True)
        )

        self.assertFalse(report.safe)
        self.assertEqual(report.evidence_resolution.value, "unresolved")
        self.assertIn("symbolic_pressure_unresolved", report.violations)

    def test_observed_zero_closes_required_pressure_evidence(self):
        report = evaluate_distillation(
            DistillationDefenseVector(
                symbolic_pressure=0.0,
                symbolic_pressure_required=True,
            )
        )

        self.assertTrue(report.safe)
        self.assertEqual(report.evidence_resolution.value, "proven")


if __name__ == "__main__":
    unittest.main()
