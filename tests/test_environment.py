import unittest

from seraph import EnvironmentVector, evaluate_environment


class EnvironmentTests(unittest.TestCase):
    def test_environment_is_safe_when_all_constraints_hold(self):
        report = evaluate_environment(EnvironmentVector())

        self.assertTrue(report.safe)
        self.assertEqual(report.safety_score, 1.0)
        self.assertEqual(report.violations, ())

    def test_environment_safety_is_weakest_constraint(self):
        report = evaluate_environment(
            EnvironmentVector(
                containment=1.0,
                reversibility=1.0,
                blast_radius_control=0.4,
                externality_control=1.0,
            )
        )

        self.assertFalse(report.safe)
        self.assertEqual(report.safety_score, 0.4)
        self.assertEqual(report.violations, ("environment_safety_loss",))


if __name__ == "__main__":
    unittest.main()
