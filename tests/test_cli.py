import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from seraph.__main__ import DEFAULT_INPUT_PATH, main


class CLITests(unittest.TestCase):
    def test_cli_commits_release_gate_example(self):
        path = DEFAULT_INPUT_PATH
        output = StringIO()

        with redirect_stdout(output):
            self.assertEqual(main([str(path)]), 0)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["decision"], "commit")
        self.assertEqual(payload["operating_layer"], "commit")
        self.assertEqual(payload["deployment_posture"]["active_path"], "embedded")
        self.assertEqual(payload["reasons"], ["commit_granted"])
        self.assertTrue(payload["environment"]["safe"])

    def test_cli_output_matches_evidence_loss_example(self):
        path = DEFAULT_INPUT_PATH.parent / "evidence_loss_denied.json"
        output = StringIO()

        with redirect_stdout(output):
            self.assertEqual(main([str(path)]), 0)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["decision"], "deny")
        self.assertEqual(payload["operating_layer"], "containment")
        self.assertIn("evidence_fidelity_loss", payload["reasons"])

    def test_cli_output_matches_environment_loss_example(self):
        path = DEFAULT_INPUT_PATH.parent / "environment_unsafe_denied.json"
        output = StringIO()

        with redirect_stdout(output):
            self.assertEqual(main([str(path)]), 0)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["decision"], "deny")
        self.assertEqual(payload["operating_layer"], "containment")
        self.assertIn("environment_safety_loss", payload["reasons"])
        self.assertFalse(payload["environment"]["safe"])

    def test_cli_output_matches_non_traversal_relocation_example(self):
        path = DEFAULT_INPUT_PATH.parent / "non_traversal_relocation_maneuver.json"
        output = StringIO()

        with redirect_stdout(output):
            self.assertEqual(main([str(path)]), 0)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["decision"], "allow")
        self.assertEqual(payload["operating_layer"], "maneuver")
        self.assertTrue(payload["relocation"]["admissible"])

    def test_cli_output_matches_distillation_extraction_example(self):
        path = DEFAULT_INPUT_PATH.parent / "distillation_extraction_denied.json"
        output = StringIO()

        with redirect_stdout(output):
            self.assertEqual(main([str(path)]), 0)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["decision"], "deny")
        self.assertEqual(payload["deployment_posture"]["active_path"], "sidecar")
        self.assertEqual(payload["distillation"]["authenticity"], "extraction")
        self.assertIn("distillation_extraction_coupling", payload["reasons"])

    def test_cli_default_uses_bundled_example(self):
        output = StringIO()

        with redirect_stdout(output):
            self.assertEqual(main([]), 0)

        self.assertEqual(json.loads(output.getvalue())["decision"], "commit")


if __name__ == "__main__":
    unittest.main()
