from __future__ import annotations

import unittest
from pathlib import Path

from seraph_demo.web_export import build_demo_data, render_javascript


class WebDemoExportTests(unittest.TestCase):
    def test_demo_uses_expected_real_verdicts(self) -> None:
        data = build_demo_data()
        scenarios = {
            item["scenario_id"]: item
            for item in data["scenarios"]
        }

        self.assertEqual(scenarios["closed"]["verdict"], "proven")
        self.assertTrue(scenarios["closed"]["permit_eligible"])
        self.assertEqual(scenarios["closed"]["derived_affected"], ["bob"])

        self.assertEqual(scenarios["omitted"]["verdict"], "refuted")
        self.assertIn(
            "affected_inhabitant_omitted",
            scenarios["omitted"]["reasons"],
        )
        self.assertIn(
            "affected_inhabitant_effect_omitted",
            scenarios["omitted"]["reasons"],
        )

        self.assertEqual(scenarios["laundered"]["verdict"], "refuted")
        self.assertTrue(scenarios["laundered"]["label_ignored_digest_match"])

        self.assertEqual(scenarios["unresolved"]["verdict"], "unresolved")
        self.assertEqual(
            scenarios["unresolved"]["unresolved_entities"],
            ["external-neighbor"],
        )

        self.assertEqual(
            scenarios["delayed"]["consequence"],
            {
                "first_checkpoint": "active",
                "second_checkpoint": "diverged",
                "contained": True,
            },
        )

    def test_checked_in_browser_fixture_matches_generator(self) -> None:
        fixture = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "demo"
            / "seraph-demo-data.js"
        )

        self.assertEqual(
            fixture.read_text(encoding="utf-8"),
            render_javascript(build_demo_data()),
        )


if __name__ == "__main__":
    unittest.main()
