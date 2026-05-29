"""bus_read — Canonical cursor-aware bus read.

Agents sometimes cache bus state in their head and claim "no pending signals" when
there are. This tool returns ground truth from disk, every call.
"""

from __future__ import annotations

import json
from pathlib import Path


def _load_cursor(cursor_path: Path) -> int:
    if not cursor_path.exists():
        return 0
    try:
        return int(cursor_path.read_text().strip() or "0")
    except ValueError:
        return 0


def _load_bus(bus_path: Path) -> list[str]:
    if not bus_path.exists():
        return []
    return bus_path.read_text().splitlines()


def run(
    *,
    bus_path: str,
    cursor_path: str,
    advance: bool = False,
    peek: bool | None = None,
    limit: int | None = None,
) -> dict:
    """Read pending bus rows.

    `advance=True` consumes the rows returned by this call. The legacy `peek`
    argument is kept as a compatibility alias for older callers where
    `peek=True` meant "read and advance".
    """
    bus = Path(bus_path).expanduser()
    cursor_file = Path(cursor_path).expanduser()
    should_advance = advance or bool(peek)

    lines = _load_bus(bus)
    cursor = _load_cursor(cursor_file)

    pending_lines = lines[cursor:]
    if limit is not None:
        pending_lines = pending_lines[:limit]

    pending: list[dict] = []
    for i, raw in enumerate(pending_lines):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"_parse_error": True, "raw": raw}
        payload["_bus_index"] = cursor + i
        pending.append(payload)

    new_cursor = cursor
    if should_advance and pending_lines:
        new_cursor = cursor + len(pending_lines)
        cursor_file.parent.mkdir(parents=True, exist_ok=True)
        cursor_file.write_text(f"{new_cursor}\n")

    return {
        "bus_path": str(bus),
        "cursor_path": str(cursor_file),
        "cursor": new_cursor,
        "cursor_before": cursor,
        "advanced": should_advance and bool(pending_lines),
        "total_lines": len(lines),
        "pending_count": len(pending),
        "pending": pending,
    }


def ack(*, cursor_path: str, advance_by: int = 1) -> dict:
    cursor_file = Path(cursor_path).expanduser()
    cursor = _load_cursor(cursor_file)
    new_cursor = cursor + advance_by
    cursor_file.parent.mkdir(parents=True, exist_ok=True)
    cursor_file.write_text(f"{new_cursor}\n")
    return {
        "cursor_path": str(cursor_file),
        "cursor_before": cursor,
        "cursor": new_cursor,
        "advanced_by": advance_by,
    }


def rewind(
    *,
    cursor_path: str,
    rewind_by: int | None = None,
    new_cursor: int | None = None,
) -> dict:
    """Move a cursor backwards. Recovery tool for skip / over-ack scenarios.

    Pass exactly one of:
      - `rewind_by`: subtract N from current cursor (clamped at 0)
      - `new_cursor`: set cursor to absolute value (must be >= 0)

    Returns {ok, cursor_before, cursor, mode, ...}. Refuses to advance forward —
    use `bus_ack` for that. Cursor file is written to disk.
    """
    if (rewind_by is None) == (new_cursor is None):
        return {
            "ok": False,
            "error": "must pass exactly one of rewind_by or new_cursor",
        }

    cursor_file = Path(cursor_path).expanduser()
    cursor = _load_cursor(cursor_file)

    if rewind_by is not None:
        if rewind_by <= 0:
            return {
                "ok": False,
                "error": f"rewind_by must be > 0, got {rewind_by}",
            }
        target = max(0, cursor - rewind_by)
        mode = "relative"
    else:
        if new_cursor < 0:
            return {
                "ok": False,
                "error": f"new_cursor must be >= 0, got {new_cursor}",
            }
        if new_cursor > cursor:
            return {
                "ok": False,
                "error": (
                    f"refusing to advance: new_cursor={new_cursor} > "
                    f"current cursor={cursor}. Use bus_ack to advance."
                ),
            }
        target = new_cursor
        mode = "absolute"

    cursor_file.parent.mkdir(parents=True, exist_ok=True)
    cursor_file.write_text(f"{target}\n")
    return {
        "ok": True,
        "cursor_path": str(cursor_file),
        "cursor_before": cursor,
        "cursor": target,
        "rewound_by": cursor - target,
        "mode": mode,
    }
