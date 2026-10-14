import unittest

from seraph import PRPScore, PRPTrail


class PRPTests(unittest.TestCase):
    def test_prp_score_weights_latency_recovery_and_coupling(self):
        score = PRPScore(
            detection_latency=2.5,
            recovery_fidelity=0.5,
            coupling_preservation=0.5,
        )

        self.assertAlmostEqual(score.overall, 0.5)
        self.assertFalse(score.degraded())

    def test_prp_trail_window_and_recovery_trend(self):
        trail = PRPTrail(window=3)
        for score in [
            PRPScore(5.0, 0.1, 0.1),
            PRPScore(4.5, 0.1, 0.1),
            PRPScore(4.0, 0.2, 0.2),
            PRPScore(3.5, 0.3, 0.3),
        ]:
            trail.push(score)

        self.assertEqual(len(trail.scores), 3)
        self.assertTrue(trail.recovering())
        self.assertFalse(trail.collapsing())


if __name__ == "__main__":
    unittest.main()
