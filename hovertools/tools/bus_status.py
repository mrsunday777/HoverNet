"""bus_status — read-only bus health check for one agent. Never mutates cursor."""

from __future__ import annotations

import json
from pathlib import Path


def _workspace(root: str) -> tuple[Path, Path]:
    r = Path(root).expanduser().resolve()
    return r, r / ".hovernet"


def _load_manifest(workspace: Path) -> dict:
    p = workspace / "hovernet.json"
    if not p.exists():
        raise FileNotFoundError(f"no manifest at {p}; run hover_init first")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest is not valid JSON: {exc}") from exc


def run(*, root: str, agent: str) -> dict:
    """Return bus line count, cursor position, pending count, and recent pending signal IDs.

    Read-only — never advances or modifies any cursor file.
    """
    _, workspace = _workspace(root)

    try:
        manifest = _load_manifest(workspace)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

    agent_entry = manifest.get("agents", {}).get(agent)
    if agent_entry is None:
        return {
            "ok": False,
            "error": f"agent {agent!r} not found in manifest",
        }

    bus_path = Path(agent_entry["bus_path"])
    cursor_path = Path(agent_entry["cursor_path"])

    # Read bus
    total_lines = 0
    pending_signals: list[dict] = []
    if bus_path.exists():
        lines = bus_path.read_text(encoding="utf-8").splitlines()
        total_lines = len(lines)

        # Read cursor (read-only)
        cursor = 0
        if cursor_path.exists():
            try:
                cursor = int(cursor_path.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                cursor = 0

        # Collect pending signals (after cursor)
        for i, line in enumerate(lines[cursor:], start=cursor + 1):
            line = line.strip()
            if not line:
                continue
            try:
                sig = json.loads(line)
                pending_signals.append({
                    "line": i,
                    "signal_id": sig.get("signal_id", f"<line-{i}>"),
                    "type": sig.get("type", ""),
                    "from": sig.get("from", ""),
                    "timestamp": sig.get("timestamp", ""),
                })
            except json.JSONDecodeError:
                pending_signals.append({"line": i, "signal_id": f"<malformed-line-{i}>", "type": "ERROR"})
    else:
        cursor = 0

    return {
        "ok": True,
        "agent": agent,
        "bus_path": str(bus_path),
        "cursor_path": str(cursor_path),
        "total_lines": total_lines,
        "cursor": cursor,
        "pending_count": len(pending_signals),
        "pending_signals": pending_signals,
    }
