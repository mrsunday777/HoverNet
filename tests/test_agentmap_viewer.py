from __future__ import annotations

from pathlib import Path
import unittest

from hovertools import agentmap_viewer


ROOT = Path(__file__).resolve().parents[1]


class AgentMapViewerTests(unittest.TestCase):
    def test_research_example_resolves_public_layout(self):
        cfg = agentmap_viewer.load_agentmap(str(ROOT / "examples" / "agentmaps" / "research.yaml"))

        resolved = agentmap_viewer.plan(cfg)

        self.assertEqual(resolved["pane_order"], ["proposer", "critic", "synthesizer"])
        self.assertEqual(resolved["pane_columns"], [["proposer", "synthesizer"], ["critic"]])

    def test_council_example_resolves_public_layout(self):
        cfg = agentmap_viewer.load_agentmap(str(ROOT / "examples" / "agentmaps" / "council.yaml"))

        resolved = agentmap_viewer.plan(cfg)

        self.assertEqual(
            resolved["pane_order"],
            ["chairman", "contrarian", "executor", "expansionist", "firstprinciples", "outsider"],
        )
        self.assertEqual(
            resolved["pane_columns"],
            [
                ["chairman", "executor", "firstprinciples"],
                ["contrarian", "expansionist", "outsider"],
            ],
        )

    def test_rejects_duplicate_pane_names(self):
        with self.assertRaises(ValueError):
            agentmap_viewer.resolve_viewer_pane_layout(
                {"pane_layout": {"rows": [["a", "a"]]}},
                [],
            )


if __name__ == "__main__":
    unittest.main()
