from pathlib import Path
import unittest

from seraph_demo.runner import DEFAULT_SCENARIO_PATH, run_path


class ScenarioCorpusTests(unittest.TestCase):
    def test_all_scenarios_pass_expected_outcomes(self):
        results = run_path(DEFAULT_SCENARIO_PATH)
        failures = {
            result.name: result.failures
            for result in results
            if not result.passed
        }

        self.assertEqual(failures, {})
        self.assertGreaterEqual(len(results), 8)

    def test_trace_contains_operator_readout(self):
        result = run_path(DEFAULT_SCENARIO_PATH / "clean_commit.json")[0]

        self.assertIn("SCENARIO: clean_commit", result.trace)
        self.assertIn("CONSTRAINTS: proven", result.trace)
        self.assertIn("FLUX: ok", result.trace)
        self.assertIn("SERAPH: ok", result.trace)
        self.assertIn("Decision: commit", result.trace)
        self.assertIn("PASS", result.trace)


if __name__ == "__main__":
    unittest.main()
