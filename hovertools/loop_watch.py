"""Public loop watcher for HoverNet v1.5 workspaces.

The watcher is read-only. It reports the next actionable event from the local
manifest, bus cursors, inbox files, and active thread artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RESEARCH_ROLES = {
    "proposer": "propose",
    "critic": "critique",
    "synthesizer": "synthesize",
}
RESEARCH_ALIASES = {
    "RepoProposer": "proposer",
    "RepoCritic": "critic",
    "RepoSynthesizer": "synthesizer",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _workspace(root: str) -> Path:
    return Path(root).expanduser().resolve() / ".hovernet"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest(root: str) -> tuple[Path, dict[str, Any]]:
    workspace = _workspace(root)
    manifest_path = workspace / "hovernet.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no manifest at {manifest_path}; run hover_init first")
    return workspace, _read_json(manifest_path)


def _loop_entry(manifest: dict[str, Any], loop_name: str | None) -> tuple[str, dict[str, Any]]:
    loops = manifest.get("loops") or {}
    if loop_name:
        entry = loops.get(loop_name)
        if not entry:
            raise KeyError(f"loop {loop_name!r} not found in manifest")
        return loop_name, entry
    if len(loops) == 1:
        name, entry = next(iter(loops.items()))
        return str(name), entry
    raise KeyError("loop_name is required when the manifest has zero or multiple loops")


def _read_int(path: Path, default: int = 0) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip() or default)
    except (OSError, ValueError):
        return default


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _normalize_agent(agent: str, agents: dict[str, Any]) -> str:
    if agent in agents:
        return agent
    alias = RESEARCH_ALIASES.get(agent)
    if alias and alias in agents:
        return alias
    return agent


def _loop_type(loop_name: str, loop_entry: dict[str, Any], requested: str) -> str:
    if requested and requested != "auto":
        return requested
    name = loop_name.lower()
    agents = {str(agent).lower() for agent in loop_entry.get("agents") or []}
    if "research" in name or {"proposer", "critic", "synthesizer"}.issubset(agents):
        return "research"
    if "council" in name or "chairman" in agents:
        return "council"
    return "research"


def _session_dir(loop_entry: dict[str, Any]) -> Path:
    return Path(str(loop_entry["session_dir"])).expanduser()


def _active_root(loop_entry: dict[str, Any]) -> Path:
    return Path(str(loop_entry.get("active_dir") or _session_dir(loop_entry) / "active")).expanduser()


def _inbox_dir(loop_entry: dict[str, Any]) -> Path:
    return Path(str(loop_entry.get("inbox_dir") or _session_dir(loop_entry) / "inbox")).expanduser()


def _visible_inbox_files(inbox_dir: Path) -> list[Path]:
    if not inbox_dir.exists():
        return []
    ignored = {".reason"}
    return sorted(
        path
        for path in inbox_dir.iterdir()
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() not in ignored
    )


def _parse_frontier(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    status = "OPEN"
    round_no = 0
    thread = path.parent.name

    status_match = re.search(r"Status:\**\s*([A-Z][A-Z _-]*)", text, re.I)
    if status_match:
        status = status_match.group(1).strip().upper()
    round_match = re.search(r"Round:\**\s*([0-9]+)", text, re.I)
    if round_match:
        round_no = int(round_match.group(1))
    thread_match = re.search(r"Thread:\**\s*([A-Za-z0-9_.-]+)", text, re.I)
    if thread_match:
        thread = thread_match.group(1).strip()

    return {
        "thread": thread,
        "status": status,
        "round": round_no,
        "path": str(path),
        "dir": str(path.parent),
    }


def _active_threads(active_root: Path) -> list[dict[str, Any]]:
    if not active_root.exists():
        return []
    threads: list[dict[str, Any]] = []
    for thread_dir in sorted(path for path in active_root.iterdir() if path.is_dir()):
        frontier = thread_dir / "frontier.md"
        meta = _parse_frontier(frontier) if frontier.exists() else {
            "thread": thread_dir.name,
            "status": "OPEN",
            "round": 0,
            "path": "",
            "dir": str(thread_dir),
        }
        if str(meta["status"]).startswith("OPEN"):
            threads.append(meta)
    return threads


def _round_dirs(thread_dir: Path) -> list[tuple[int, Path]]:
    rounds: list[tuple[int, Path]] = []
    for path in thread_dir.glob("round_*"):
        match = re.fullmatch(r"round_([0-9]+)", path.name)
        if path.is_dir() and match:
            rounds.append((int(match.group(1)), path))
    return sorted(rounds)


def _bus_event(
    manifest: dict[str, Any],
    agent: str,
    active_names: set[str],
    lookback: int,
) -> dict[str, Any] | None:
    agents = manifest.get("agents") or {}
    entry = agents.get(agent)
    if not entry:
        return None

    bus_path = Path(str(entry["bus_path"])).expanduser()
    cursor_path = Path(str(entry["cursor_path"])).expanduser()
    acks_dir = bus_path.parent / "acks"
    saved = _read_int(cursor_path)
    if not bus_path.exists():
        return None

    lines = bus_path.read_text(encoding="utf-8", errors="replace").splitlines()
    # Public v1.5 uses cursor advancement as the ack. Do not re-emit lines at
    # or before the saved cursor; private loop variants may keep separate ack
    # files, but the public contract should stay cursor-first.
    start = max(0, min(saved, len(lines)))
    target_names = {agent}
    for alias, canonical in RESEARCH_ALIASES.items():
        if canonical == agent:
            target_names.add(alias)

    for index, line in enumerate(lines[start:], start=start + 1):
        try:
            signal = json.loads(line)
        except json.JSONDecodeError:
            continue
        target = signal.get("target_agent") or signal.get("to")
        if target not in target_names:
            continue
        signal_id = str(signal.get("signal_id") or "")
        if not signal_id:
            continue
        if (acks_dir / f"{signal_id}.ack").exists():
            continue
        thread = str(signal.get("thread") or "")
        if index <= saved and thread not in active_names:
            continue
        return {
            "event": "NEW_BUS",
            "agent": agent,
            "line": index,
            "cursor": saved,
            "bus_lines": len(lines),
            "signal": signal,
            "message": f"NEW_BUS line={index} signal_id={signal_id}",
        }
    return None


def _research_ready_event(agent: str, threads: list[dict[str, Any]]) -> dict[str, Any] | None:
    role = RESEARCH_ROLES.get(agent)
    if not role:
        return None

    for meta in threads:
        thread_dir = Path(str(meta["dir"]))
        rounds = _round_dirs(thread_dir)

        if role == "propose":
            round0 = thread_dir / "round_000"
            if not (round0 / "proposer.md").exists():
                return _ready_event(agent, meta, 0, "proposer.md", "new thread needs proposer")
            for round_no, round_dir in rounds:
                consensus = round_dir / "consensus.md"
                next_round = round_no + 1
                next_dir = thread_dir / f"round_{next_round:03d}"
                if consensus.exists() and not (next_dir / "proposer.md").exists():
                    return _ready_event(agent, meta, next_round, "proposer.md", "previous consensus exists")

        if role == "critique":
            for round_no, round_dir in rounds:
                if (round_dir / "proposer.md").exists() and not (round_dir / "critic.md").exists():
                    return _ready_event(agent, meta, round_no, "critic.md", "proposer.md exists")

        if role == "synthesize":
            for round_no, round_dir in rounds:
                if (round_dir / "critic.md").exists() and not (round_dir / "consensus.md").exists():
                    return _ready_event(agent, meta, round_no, "consensus.md", "critic.md exists")
    return None


def _ready_event(agent: str, meta: dict[str, Any], round_no: int, output: str, reason: str) -> dict[str, Any]:
    thread_dir = Path(str(meta["dir"]))
    return {
        "event": "READY_WORK",
        "agent": agent,
        "thread": meta["thread"],
        "thread_dir": str(thread_dir),
        "frontier": meta.get("path") or "",
        "round": round_no,
        "round_dir": str(thread_dir / f"round_{round_no:03d}"),
        "expected_output": output,
        "reason": reason,
        "message": f"READY_WORK thread={meta['thread']} round={round_no:03d} output={output}",
    }


def _council_ready_event(agent: str, sessions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if agent == "chairman":
        return None
    for session in sessions:
        session_dir = Path(str(session["dir"]))
        for round_name in ("R1", "R2"):
            round_dir = session_dir / round_name
            dispatched = (round_dir / f".dispatch_{agent}").exists()
            done = (round_dir / f"{agent}.md").exists() or (round_dir / f".complete_{agent}").exists()
            if dispatched and not done:
                return {
                    "event": "READY_WORK",
                    "agent": agent,
                    "thread": session["thread"],
                    "thread_dir": str(session_dir),
                    "round": round_name,
                    "round_dir": str(round_dir),
                    "expected_output": f"{agent}.md",
                    "reason": f"{round_name} dispatch marker exists",
                    "message": f"READY_WORK session={session['thread']} round={round_name} output={agent}.md",
                }
    return None


def _council_round_complete(agent: str, agents: list[str], sessions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if agent != "chairman":
        return None
    advisors = [name for name in agents if name != "chairman"]
    if not advisors:
        return None
    for session in sessions:
        session_dir = Path(str(session["dir"]))
        for round_name in ("R1", "R2"):
            round_dir = session_dir / round_name
            if not round_dir.exists() or (round_dir / ".round_complete_ack").exists():
                continue
            if all((round_dir / f".complete_{advisor}").exists() for advisor in advisors):
                return {
                    "event": "ROUND_COMPLETE",
                    "agent": agent,
                    "thread": session["thread"],
                    "thread_dir": str(session_dir),
                    "round": round_name,
                    "round_dir": str(round_dir),
                    "message": f"ROUND_COMPLETE session={session['thread']} round={round_name}",
                }
    return None


def scan_once(
    *,
    root: str,
    loop_name: str | None = None,
    agent: str,
    loop_type: str = "auto",
    bus_lookback: int = 200,
) -> dict[str, Any]:
    """Return the next actionable watcher event for one public loop agent."""
    try:
        _, manifest = _load_manifest(root)
        loop_id, loop = _loop_entry(manifest, loop_name)
        agents = manifest.get("agents") or {}
        agent_name = _normalize_agent(agent, agents)
        if agent_name not in agents:
            return {"ok": False, "error": f"agent {agent!r} not found in manifest"}
        kind = _loop_type(loop_id, loop, loop_type)
        active = _active_threads(_active_root(loop))
        active_names = {str(item["thread"]) for item in active}
        inbox_files = _visible_inbox_files(_inbox_dir(loop))

        bus = _bus_event(manifest, agent_name, active_names, bus_lookback)
        if bus:
            return {"ok": True, "loop": loop_id, "loop_type": kind, **bus}

        if kind == "research":
            if inbox_files and not active:
                return {
                    "ok": True,
                    "loop": loop_id,
                    "loop_type": kind,
                    "event": "NEW_BRIEF",
                    "agent": agent_name,
                    "files": [str(path) for path in inbox_files],
                    "intake_policy": "single-thread",
                    "message": f"NEW_BRIEF {inbox_files[0]}",
                }
            ready = _research_ready_event(agent_name, active)
            if ready:
                return {"ok": True, "loop": loop_id, "loop_type": kind, **ready}

        if kind == "council":
            if agent_name == "chairman" and inbox_files and not active:
                return {
                    "ok": True,
                    "loop": loop_id,
                    "loop_type": kind,
                    "event": "NEW_BRIEF",
                    "agent": agent_name,
                    "files": [str(path) for path in inbox_files],
                    "intake_policy": "single-thread",
                    "message": f"NEW_BRIEF {inbox_files[0]}",
                }
            complete = _council_round_complete(agent_name, list(loop.get("agents") or []), active)
            if complete:
                return {"ok": True, "loop": loop_id, "loop_type": kind, **complete}
            ready = _council_ready_event(agent_name, active)
            if ready:
                return {"ok": True, "loop": loop_id, "loop_type": kind, **ready}

        return {
            "ok": True,
            "loop": loop_id,
            "loop_type": kind,
            "event": "IDLE",
            "agent": agent_name,
            "active_threads": [item["thread"] for item in active],
            "inbox_backlog": [str(path) for path in inbox_files],
            "intake_policy": "single-thread",
            "checked_at": utc_now(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _emit(event: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(event, separators=(",", ":")), flush=True)
    else:
        print(event.get("message") or event.get("event") or event, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Workspace root passed to hover_init.")
    parser.add_argument("--loop-name", default=None, help="Loop name from hovernet.json.")
    parser.add_argument("--loop-type", default="auto", choices=("auto", "research", "council"))
    parser.add_argument("--agent", required=True)
    parser.add_argument("--bus-lookback", type=int, default=200)
    parser.add_argument("--poll-sec", type=float, default=30.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--quiet-idle", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    while True:
        event = scan_once(
            root=args.root,
            loop_name=args.loop_name,
            agent=args.agent,
            loop_type=args.loop_type,
            bus_lookback=args.bus_lookback,
        )
        if event.get("event") != "IDLE" or not args.quiet_idle:
            _emit(event, args.json)
        if args.once or not args.watch:
            return 0 if event.get("ok") else 1
        time.sleep(args.poll_sec)


if __name__ == "__main__":
    raise SystemExit(main())
