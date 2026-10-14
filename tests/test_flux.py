import unittest

from seraph import Decision, FluxBounds, evaluate_flux


class FluxTests(unittest.TestCase):
    def test_flux_allows_stable_trajectory(self):
        result = evaluate_flux(["normal", "normal", "repair", "repair", "normal", "normal"])

        self.assertTrue(result.coherent)
        self.assertEqual(result.decision, Decision.ALLOW)

    def test_flux_witnesses_fragmented_trajectory(self):
        result = evaluate_flux(["normal"])

        self.assertFalse(result.coherent)
        self.assertEqual(result.decision, Decision.WITNESS)
        self.assertIn("fragmentation", result.violations)

    def test_flux_stabilizes_divergent_trajectory(self):
        result = evaluate_flux(
            ["a", "b", "c", "d", "e", "f", "g"],
            bounds=FluxBounds(max_switches=99, max_drift_run=5, min_stability=1),
        )

        self.assertFalse(result.coherent)
        self.assertEqual(result.decision, Decision.STABILIZE)
        self.assertEqual(result.drift_run, 6)
        self.assertIn("divergence", result.violations)

    def test_flux_witnesses_oscillation_without_divergence(self):
        result = evaluate_flux(
            ["a", "b", "a", "b", "a"],
            bounds=FluxBounds(max_switches=3, max_drift_run=99, min_stability=1),
        )

        self.assertFalse(result.coherent)
        self.assertEqual(result.decision, Decision.WITNESS)
        self.assertEqual(result.switches, 4)
        self.assertIn("oscillation", result.violations)


if __name__ == "__main__":
    unittest.main()
