"""agent_register — add an agent to an existing hovernet.json manifest (idempotent)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _workspace(root: str) -> tuple[Path, Path]:
    r = Path(root).expanduser().resolve()
    return r, r / ".hovernet"


def run(*, root: str, agent_name: str, role: str | None = None) -> dict:
    """Add agent_name to the manifest and create its bus/cursor dirs.

    Idempotent: re-running for an existing agent updates role if provided,
    and creates any missing filesystem artifacts, but never truncates the bus.
    """
    name = str(agent_name).strip()
    if not name:
        return {"ok": False, "error": "agent_name must not be empty"}
    if not AGENT_NAME_RE.match(name):
        return {
            "ok": False,
            "error": f"invalid agent_name {name!r}; use letters, numbers, underscore, dash, or dot",
        }

    _, workspace = _workspace(root)
    manifest_path = workspace / "hovernet.json"

    if not manifest_path.exists():
        return {
            "ok": False,
            "error": f"no manifest found at {manifest_path}; run hover_init first",
        }

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"manifest is not valid JSON: {exc}"}

    bus_dir = workspace / "agents" / name / "shared_intel" / "signal_bus"
    cursor_dir = bus_dir / "cursors"
    bus_path = bus_dir / "signals.jsonl"
    cursor_path = cursor_dir / f"{name}.cursor"

    created: list[str] = []
    bus_dir.mkdir(parents=True, exist_ok=True)
    cursor_dir.mkdir(parents=True, exist_ok=True)

    if not bus_path.exists():
        bus_path.write_text("", encoding="utf-8")
        created.append(str(bus_path))
    if not cursor_path.exists():
        cursor_path.write_text("0\n", encoding="utf-8")
        created.append(str(cursor_path))

    agent_entry = manifest.setdefault("agents", {}).get(name, {})
    agent_entry["bus_path"] = str(bus_path)
    agent_entry["cursor_path"] = str(cursor_path)
    if role is not None:
        agent_entry["role"] = role
    else:
        agent_entry.setdefault("role", "agent")
    manifest["agents"][name] = agent_entry
    manifest["updated_at"] = _utc_now()

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "agent": name,
        "role": agent_entry["role"],
        "bus_path": str(bus_path),
        "cursor_path": str(cursor_path),
        "created_paths": created,
    }
