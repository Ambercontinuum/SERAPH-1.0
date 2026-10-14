import unittest

from validation.runtime_governance import CASES, run_validation


class RuntimeGovernanceValidationTests(unittest.TestCase):
    def test_case_ids_are_unique(self):
        case_ids = tuple(case.case_id for case in CASES)
        self.assertEqual(len(case_ids), len(set(case_ids)))

    def test_bounded_corpus_passes(self):
        report = run_validation()

        self.assertTrue(report["summary"]["all_passed"])
        self.assertEqual(report["summary"]["total"], 17)
        self.assertEqual(report["summary"]["failed"], 0)

    def test_report_preserves_claim_boundary(self):
        report = run_validation()

        self.assertIn("not complete mitigation", report["claim_boundary"])
        self.assertTrue(
            all("duration_ns" in result for result in report["cases"])
        )


if __name__ == "__main__":
    unittest.main()
