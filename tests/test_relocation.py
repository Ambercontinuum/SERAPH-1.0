import unittest

from seraph import (
    OperatingLayer,
    RelocationRequest,
    evaluate_relocation,
)


class RelocationTests(unittest.TestCase):
    def test_absent_relocation_is_admissible_noop(self):
        report = evaluate_relocation(None)

        self.assertFalse(report.requested)
        self.assertTrue(report.admissible)
        self.assertEqual(report.violations, ())

    def test_low_torsion_orbit_equivalent_relocation_is_admissible(self):
        report = evaluate_relocation(
            RelocationRequest(
                source_layer=OperatingLayer.WITNESS,
                target_layer=OperatingLayer.MANEUVER,
                torsion=0.2,
                orbit_equivalent=True,
                identity_preservation=1.0,
                closure_preservation=1.0,
            )
        )

        self.assertTrue(report.requested)
        self.assertTrue(report.admissible)
        self.assertEqual(report.target_layer, OperatingLayer.MANEUVER)

    def test_high_torsion_blocks_relocation(self):
        report = evaluate_relocation(
            RelocationRequest(
                source_layer=OperatingLayer.WITNESS,
                target_layer=OperatingLayer.MANEUVER,
                torsion=3.0,
            )
        )

        self.assertFalse(report.admissible)
        self.assertIn("relocation_torsion_exceeded", report.violations)

    def test_orbit_mismatch_blocks_relocation(self):
        report = evaluate_relocation(
            RelocationRequest(
                source_layer=OperatingLayer.WITNESS,
                target_layer=OperatingLayer.MANEUVER,
                orbit_equivalent=False,
            )
        )

        self.assertFalse(report.admissible)
        self.assertIn("relocation_orbit_mismatch", report.violations)


if __name__ == "__main__":
    unittest.main()
