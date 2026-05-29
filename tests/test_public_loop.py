from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hovertools import public_server as hover


class PublicLoopSmokeTests(unittest.TestCase):
    def test_local_loop_signal_ack_and_completion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hovernet-test-") as tmp:
            root = Path(tmp)

            init = hover.hover_init(
                root=str(root),
                loop_name="research-demo",
                agents=["proposer", "critic", "synthesizer"],
            )
            self.assertTrue(init["ok"])

            manifest_result = hover.hover_manifest_read(root=str(root))
            self.assertTrue(manifest_result["ok"])
            manifest = manifest_result["manifest"]
            self.assertIn("critic", manifest["agents"])

            validation = hover.hover_manifest_validate(root=str(root))
            self.assertTrue(validation["ok"], validation.get("errors"))

            signal = hover.signal_send(
                root=str(root),
                target_agent="critic",
                signal_type="TASK_DISPATCH",
                payload={
                    "from": "proposer",
                    "notes": "Review the proposal and return a concise finding.",
                },
                thread="demo-thread",
                round="R1",
            )
            self.assertTrue(signal["ok"])

            critic = manifest["agents"]["critic"]
            pending = hover.bus_read(
                bus_path=critic["bus_path"],
                cursor_path=critic["cursor_path"],
            )
            self.assertEqual(pending["pending_count"], 1)
            self.assertEqual(pending["pending"][0]["round"], "R1")

            watch = hover.loop_watch_once(
                root=str(root),
                loop_name="research-demo",
                loop_type="research",
                agent="critic",
            )
            self.assertTrue(watch["ok"])
            self.assertEqual(watch["event"], "NEW_BUS")
            self.assertEqual(watch["signal"]["signal_id"], signal["signal_id"])

            ack = hover.bus_ack(cursor_path=critic["cursor_path"], advance_by=1)
            self.assertTrue(ack["ok"])

            after_ack = hover.loop_watch_once(
                root=str(root),
                loop_name="research-demo",
                loop_type="research",
                agent="critic",
            )
            self.assertTrue(after_ack["ok"])
            self.assertEqual(after_ack["event"], "IDLE")

            status = hover.bus_status(root=str(root), agent="critic")
            self.assertTrue(status["ok"])
            self.assertEqual(status["pending_count"], 0)

            completion = hover.completion_write(
                root=str(root),
                loop_name="research-demo",
                agent="critic",
                signal_id=signal["signal_id"],
                content="Critic completed the review.",
            )
            self.assertTrue(completion["ok"])
            self.assertTrue(Path(completion["artifact_path"]).exists())

    def test_session_fs_rejects_escape_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hovernet-session-") as tmp:
            session = Path(tmp) / "session"
            session.mkdir()

            written = hover.session_fs_write(
                session_dir=str(session),
                relative_path="notes/result.md",
                content="ok",
            )
            self.assertTrue(written["ok"])

            listed = hover.session_fs_list(session_dir=str(session), relative_path="notes")
            self.assertTrue(listed["ok"])
            self.assertEqual(listed["entries"][0]["name"], "result.md")

            with self.assertRaises(PermissionError):
                hover.session_fs_read(session_dir=str(session), relative_path="../outside.md")

    def test_research_loop_watch_detects_ready_work(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hovernet-watch-") as tmp:
            root = Path(tmp)
            init = hover.hover_init(
                root=str(root),
                loop_name="research",
                agents=["proposer", "critic", "synthesizer"],
            )
            loop = init["manifest"]["loops"]["research"]
            thread_dir = Path(loop["active_dir"]) / "thread-a"
            round_dir = thread_dir / "round_000"
            round_dir.mkdir(parents=True)
            (thread_dir / "frontier.md").write_text(
                "Thread: thread-a\nStatus: OPEN\nRound: 000\n",
                encoding="utf-8",
            )
            (round_dir / "proposer.md").write_text("proposal", encoding="utf-8")

            event = hover.loop_watch_once(
                root=str(root),
                loop_name="research",
                loop_type="research",
                agent="RepoCritic",
            )
            self.assertTrue(event["ok"])
            self.assertEqual(event["event"], "READY_WORK")
            self.assertEqual(event["agent"], "critic")
            self.assertEqual(event["expected_output"], "critic.md")

    def test_council_loop_watch_detects_round_complete(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hovernet-council-") as tmp:
            root = Path(tmp)
            init = hover.hover_init(
                root=str(root),
                loop_name="council",
                agents=["chairman", "alpha", "beta"],
            )
            loop = init["manifest"]["loops"]["council"]
            round_dir = Path(loop["active_dir"]) / "session-a" / "R1"
            round_dir.mkdir(parents=True)
            (round_dir / ".complete_alpha").write_text("done", encoding="utf-8")
            (round_dir / ".complete_beta").write_text("done", encoding="utf-8")

            event = hover.loop_watch_once(
                root=str(root),
                loop_name="council",
                loop_type="council",
                agent="chairman",
            )
            self.assertTrue(event["ok"])
            self.assertEqual(event["event"], "ROUND_COMPLETE")
            self.assertEqual(event["round"], "R1")


if __name__ == "__main__":
    unittest.main()
