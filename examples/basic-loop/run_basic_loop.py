#!/usr/bin/env python3
"""Run a tiny local HoverNet loop from end to end."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hovertools import public_server as hover


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hovernet-basic-") as tmp:
        root = Path(tmp)

        manifest = hover.hover_init(
            root=str(root),
            loop_name="demo",
            agents=["alice", "bob"],
        )["manifest"]

        signal = hover.signal_send(
            root=str(root),
            target_agent="bob",
            signal_type="TASK_DISPATCH",
            payload={
                "from": "alice",
                "notes": "Write a short completion proof for the demo loop.",
            },
            thread="demo-thread",
            round="R1",
        )

        bob = manifest["agents"]["bob"]
        pending = hover.bus_read(
            bus_path=bob["bus_path"],
            cursor_path=bob["cursor_path"],
            limit=1,
        )

        if pending["pending_count"] != 1:
            raise SystemExit("expected exactly one pending signal")

        hover.bus_ack(cursor_path=bob["cursor_path"], advance_by=1)
        done = hover.completion_write(
            root=str(root),
            loop_name="demo",
            agent="bob",
            signal_id=signal["signal_id"],
            content="Demo loop completed. Bus, cursor, and proof path are working.",
        )

        print("HoverNet local loop smoke passed")
        print(f"workspace: {root / '.hovernet'}")
        print(f"completion: {done['artifact_path']}")


if __name__ == "__main__":
    main()
