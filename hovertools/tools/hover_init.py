"""hover_init - Create a manifest-backed public HoverNet workspace."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


MANIFEST_VERSION = "0.1"
AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _agent_paths(workspace: Path, agent: str) -> dict:
    bus_dir = workspace / "agents" / agent / "shared_intel" / "signal_bus"
    return {
        "bus_path": str(bus_dir / "signals.jsonl"),
        "cursor_path": str(bus_dir / "cursors" / f"{agent}.cursor"),
    }


def _validate_agent_names(agents: list[str]) -> list[str]:
    cleaned: list[str] = []
    for agent in agents:
        name = str(agent).strip()
        if not name:
            raise ValueError("agent names must not be empty")
        if not AGENT_NAME_RE.match(name):
            raise ValueError(
                f"invalid agent name {name!r}; use letters, numbers, underscore, dash, or dot"
            )
        if name not in cleaned:
            cleaned.append(name)
    if not cleaned:
        raise ValueError("agents must include at least one agent name")
    return cleaned


def _read_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"existing manifest is invalid JSON: {path}: {exc}") from exc


def run(*, root: str, loop_name: str, agents: list[str]) -> dict:
    """Create a local HoverNet workspace under root/.hovernet.

    The operation is idempotent: existing agents and loop entries are preserved,
    and missing bus/cursor/session files are created.
    """
    root_path = Path(root).expanduser().resolve()
    loop = str(loop_name).strip()
    if not loop:
        return {"ok": False, "error": "loop_name must not be empty"}
    if not AGENT_NAME_RE.match(loop):
        return {
            "ok": False,
            "error": "invalid_loop_name",
            "hint": "use letters, numbers, underscore, dash, or dot",
        }

    try:
        agent_names = _validate_agent_names(agents)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    workspace = root_path / ".hovernet"
    manifest_path = workspace / "hovernet.json"
    sessions_dir = workspace / "sessions"
    loop_dir = sessions_dir / loop

    try:
        manifest = _read_manifest(manifest_path)
    except ValueError as exc:
        return {"ok": False, "error": "invalid_manifest", "detail": str(exc)}

    now = _utc_now()
    manifest.setdefault("manifest_version", MANIFEST_VERSION)
    manifest.setdefault("created_at", now)
    manifest["updated_at"] = now
    manifest["root"] = str(root_path)
    manifest["workspace_dir"] = str(workspace)
    manifest.setdefault("profiles", ["public"])
    manifest.setdefault("agents", {})
    manifest.setdefault("loops", {})

    created_paths: list[str] = []
    for agent in agent_names:
        paths = _agent_paths(workspace, agent)
        bus_path = Path(paths["bus_path"])
        cursor_path = Path(paths["cursor_path"])
        bus_path.parent.mkdir(parents=True, exist_ok=True)
        cursor_path.parent.mkdir(parents=True, exist_ok=True)
        if not bus_path.exists():
            bus_path.write_text("", encoding="utf-8")
            created_paths.append(str(bus_path))
        if not cursor_path.exists():
            cursor_path.write_text("0\n", encoding="utf-8")
            created_paths.append(str(cursor_path))
        manifest["agents"].setdefault(agent, {"role": "agent"})
        manifest["agents"][agent].update(paths)

    loop_dir.mkdir(parents=True, exist_ok=True)
    (loop_dir / "completions").mkdir(parents=True, exist_ok=True)
    readme_path = loop_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(
            f"# {loop}\n\nPublic HoverNet loop initialized by `hover_init`.\n",
            encoding="utf-8",
        )
        created_paths.append(str(readme_path))

    manifest["loops"][loop] = {
        "name": loop,
        "agents": agent_names,
        "session_dir": str(loop_dir),
        "completions_dir": str(loop_dir / "completions"),
    }

    workspace.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "root": str(root_path),
        "workspace_dir": str(workspace),
        "manifest_path": str(manifest_path),
        "loop_name": loop,
        "session_dir": str(loop_dir),
        "agents": agent_names,
        "created_paths": created_paths,
        "next_step": "Use signal_send or bus_read/status once those public wrappers are available.",
    }
