"""Public AgentMap tmux viewer.

This module renders a small AgentMap YAML file into a stable tmux viewer. It
does not launch model runtimes; it only creates a multi-pane viewer that
attaches to already-running tmux sessions.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - exercised by packaging
    raise SystemExit("PyYAML is required. Install with: python -m pip install -e .") from exc


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def tmux(socket: str | None, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    base = ["tmux"]
    if socket:
        base += ["-L", socket]
    return run(base + list(args), check=check)


def positive_int(value: Any, key: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a positive integer, got {value!r}") from exc
    if result <= 0:
        raise ValueError(f"{key} must be a positive integer, got {value!r}")
    return result


def _name_list(raw: Any, key: str) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{key} must be a non-empty list")
    names = [str(item).strip() for item in raw]
    if any(not item for item in names):
        raise ValueError(f"{key} cannot contain empty names")
    return names


def _validate_unique(names: list[str], key: str) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for name in names:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        raise ValueError(f"{key} contains duplicate pane names: {', '.join(duplicates)}")


def _columns_from_rows(rows: list[list[str]]) -> list[list[str]]:
    max_cols = max(len(row) for row in rows)
    columns: list[list[str]] = []
    for col_index in range(max_cols):
        column = [row[col_index] for row in rows if col_index < len(row)]
        if column:
            columns.append(column)
    return columns


def _columns_from_order(pane_order: list[str], column_count: int, fill: str) -> list[list[str]]:
    column_count = min(column_count, len(pane_order))
    if fill == "column":
        row_count = (len(pane_order) + column_count - 1) // column_count
        return [
            pane_order[index:index + row_count]
            for index in range(0, len(pane_order), row_count)
        ]
    if fill != "row":
        raise ValueError(f"viewer.pane_layout.fill must be row or column, got {fill!r}")
    return [pane_order[index::column_count] for index in range(column_count)]


def resolve_viewer_pane_layout(viewer: dict[str, Any], default_order: list[str]) -> tuple[list[str], list[list[str]]]:
    pane_layout = viewer.get("pane_layout") or {}
    if not isinstance(pane_layout, dict):
        raise ValueError("viewer.pane_layout must be a mapping when provided")
    kind = str(pane_layout.get("kind", "grid")).strip().lower()
    if kind not in ("grid", "agent-grid"):
        raise ValueError(f"viewer.pane_layout.kind must be grid, got {kind!r}")

    raw_rows = pane_layout.get("rows")
    if raw_rows is not None:
        if not isinstance(raw_rows, list) or not raw_rows:
            raise ValueError("viewer.pane_layout.rows must be a non-empty list of rows")
        rows = [_name_list(row, f"viewer.pane_layout.rows[{index}]") for index, row in enumerate(raw_rows)]
        pane_order = [name for row in rows for name in row]
        _validate_unique(pane_order, "viewer.pane_layout.rows")
        return pane_order, _columns_from_rows(rows)

    pane_order = _name_list(viewer.get("pane_order") or default_order, "viewer.pane_order")
    _validate_unique(pane_order, "viewer.pane_order")
    column_count = positive_int(pane_layout.get("columns", 2), "viewer.pane_layout.columns")
    fill = str(pane_layout.get("fill", "row")).strip().lower()
    return pane_order, _columns_from_order(pane_order, column_count, fill)


def load_agentmap(path: str) -> dict[str, Any]:
    loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("AgentMap must be a YAML mapping")
    return loaded


def attach_cmd(socket: str | None, session: str) -> str:
    if socket:
        return f"env -u TMUX tmux -L {socket} attach -t {session}"
    return f"env -u TMUX tmux attach -t {session}"


def _viewer_plan(cfg: dict[str, Any]) -> dict[str, Any]:
    viewer = cfg.get("viewer") or {}
    agents = cfg.get("agents") or []
    if not isinstance(viewer, dict):
        raise ValueError("viewer must be a mapping")
    if not isinstance(agents, list) or not agents:
        raise ValueError("agents must be a non-empty list")

    agents_by_name = {str(agent["name"]): agent for agent in agents if isinstance(agent, dict) and agent.get("name")}
    pane_order, pane_columns = resolve_viewer_pane_layout(viewer, list(agents_by_name))
    missing = [name for name in pane_order if name not in agents_by_name]
    if missing:
        raise KeyError(f"viewer references unknown agents: {', '.join(missing)}")

    return {
        "name": cfg.get("name") or viewer.get("session") or "agentmap",
        "viewer": viewer,
        "agents_by_name": agents_by_name,
        "pane_order": pane_order,
        "pane_columns": pane_columns,
    }


def plan(cfg: dict[str, Any]) -> dict[str, Any]:
    viewer_plan = _viewer_plan(cfg)
    return {
        "name": viewer_plan["name"],
        "viewer_session": viewer_plan["viewer"].get("session"),
        "viewer_socket": viewer_plan["viewer"].get("socket") or "",
        "pane_order": viewer_plan["pane_order"],
        "pane_columns": viewer_plan["pane_columns"],
    }


def build_viewer(cfg: dict[str, Any], force: bool = False) -> dict[str, Any]:
    viewer_plan = _viewer_plan(cfg)
    viewer = viewer_plan["viewer"]
    agents_by_name = viewer_plan["agents_by_name"]
    pane_order = viewer_plan["pane_order"]
    pane_columns = viewer_plan["pane_columns"]
    vsession = str(viewer["session"])
    vsocket = viewer.get("socket") or None
    mouse = bool(viewer.get("mouse", True))
    status_left = str(viewer.get("status_left") or f"[{viewer_plan['name']}] ")
    status_right = str(viewer.get("status_right") or "%H:%M %d-%b-%y")

    if tmux(vsocket, "has-session", "-t", vsession).returncode == 0:
        if not force:
            return {"ok": True, "status": "exists", "session": vsession, "socket": vsocket or ""}
        tmux(vsocket, "kill-session", "-t", vsession, check=True)

    first = agents_by_name[pane_order[0]]
    first_cmd = attach_cmd(first.get("socket") or None, str(first["session"]))
    tmux(vsocket, "new-session", "-d", "-s", vsession, "-n", "agents", "bash", "-c", first_cmd, check=True)

    pane_ids: dict[str, str] = {}
    first_list = tmux(vsocket, "list-panes", "-t", f"{vsession}:agents", "-F", "#{pane_id}", check=True)
    pane_ids[pane_order[0]] = first_list.stdout.split()[0]

    def split_pane(target_pane_id: str, orient: str, cmd: str, pct: int | None = None) -> str:
        args = ["split-window", orient, "-t", target_pane_id]
        if pct is not None:
            args += ["-l", f"{pct}%"]
        args += ["-P", "-F", "#{pane_id}", "bash", "-c", cmd]
        return tmux(vsocket, *args, check=True).stdout.strip()

    def agent_cmd_for(name: str) -> str:
        agent = agents_by_name[name]
        return attach_cmd(agent.get("socket") or None, str(agent["session"]))

    top_row = [column[0] for column in pane_columns if column]
    prev = pane_ids[pane_order[0]]
    for index, name in enumerate(top_row[1:], start=1):
        pct = round(100 * (len(top_row) - index) / (len(top_row) - index + 1))
        pane_ids[name] = split_pane(prev, "-h", agent_cmd_for(name), pct=pct)
        prev = pane_ids[name]

    for column in pane_columns:
        if len(column) < 2:
            continue
        rows = len(column)
        prev = pane_ids[column[0]]
        for index in range(1, rows):
            pct = round(100 * (rows - index) / (rows - index + 1))
            pane_ids[column[index]] = split_pane(prev, "-v", agent_cmd_for(column[index]), pct=pct)
            prev = pane_ids[column[index]]

    if mouse:
        tmux(vsocket, "set-option", "-g", "mouse", "on")
        tmux(vsocket, "set-option", "-t", vsession, "mouse", "on")

    tmux(vsocket, "set-option", "-wt", f"{vsession}:agents", "pane-border-status", "top")
    tmux(
        vsocket,
        "set-option",
        "-wt",
        f"{vsession}:agents",
        "pane-border-format",
        "#{?pane_active,#[bold],#[nobold]} #{pane_title} ",
    )
    tmux(vsocket, "set-option", "-wt", f"{vsession}:agents", "pane-border-style", "fg=colour240")

    for name in pane_order:
        agent = agents_by_name[name]
        title = f"{agent.get('icon', name)} {name}"
        if agent.get("model"):
            title = f"{title} · {agent['model']}"
        color = str(agent.get("border_color") or "colour244")
        pid = pane_ids[name]
        tmux(vsocket, "select-pane", "-t", pid, "-T", title)
        tmux(vsocket, "set-option", "-p", "-t", pid, "pane-active-border-style", f"fg={color}")
        tmux(vsocket, "set-option", "-p", "-t", pid, "pane-border-style", f"fg={color}")

    tmux(vsocket, "set-option", "-t", vsession, "status-left", f"#[fg=colour226,bold]{status_left}")
    tmux(vsocket, "set-option", "-t", vsession, "status-right", f"#[fg=colour244]{status_right}")
    tmux(vsocket, "set-option", "-t", vsession, "status-style", "bg=colour235,fg=white")
    tmux(vsocket, "select-pane", "-t", pane_ids[pane_order[0]])
    return {"ok": True, "status": "created", "session": vsession, "socket": vsocket or ""}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a public HoverNet AgentMap into a tmux viewer.")
    parser.add_argument("agentmap", help="Path to AgentMap YAML")
    parser.add_argument("--force", action="store_true", help="Rebuild viewer if it already exists")
    parser.add_argument("--plan", action="store_true", help="Print resolved layout and exit")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args(argv)

    cfg = load_agentmap(args.agentmap)
    result = plan(cfg) if args.plan else build_viewer(cfg, force=args.force)
    if args.json or args.plan:
        print(json.dumps(result, indent=2))
    else:
        socket = f" -L {result['socket']}" if result.get("socket") else ""
        print(f"{result['status']}: tmux{socket} attach -t {result['session']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
