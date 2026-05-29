"""completion_write — write a completion artifact into the loop's completions/ folder."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_VALID_STATUSES = {"DONE", "BLOCKED", "PARTIAL"}


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


def _safe_path(under: Path, raw: str) -> Path:
    p = (under / raw).resolve()
    try:
        p.relative_to(under.resolve())
    except ValueError:
        raise PermissionError(f"path {raw!r} escapes allowed directory {under}")
    return p


def run(
    *,
    root: str,
    loop_name: str,
    agent: str,
    signal_id: str,
    content: str,
    status: str = "DONE",
) -> dict:
    """Write a completion artifact to sessions/<loop_name>/completions/<signal_id>.md.

    status must be one of: DONE, BLOCKED, PARTIAL.
    signal_id must contain only safe characters (letters, digits, underscore, dash, dot).
    Path is resolved through hovernet.json — no raw path arguments accepted.
    """
    if not _SAFE_ID_RE.match(signal_id):
        return {
            "ok": False,
            "error": f"signal_id {signal_id!r} contains unsafe characters; use letters, digits, underscore, dash, or dot only",
        }

    status = status.upper()
    if status not in _VALID_STATUSES:
        return {
            "ok": False,
            "error": f"status {status!r} not valid; must be one of {sorted(_VALID_STATUSES)}",
        }

    _, workspace = _workspace(root)
    try:
        manifest = _load_manifest(workspace)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

    loop_entry = manifest.get("loops", {}).get(loop_name)
    if loop_entry is None:
        return {
            "ok": False,
            "error": f"loop {loop_name!r} not found in manifest; run hover_init with this loop_name first",
        }

    completions_dir = Path(loop_entry["completions_dir"])
    try:
        artifact_path = _safe_path(completions_dir, f"{signal_id}.md")
    except PermissionError as exc:
        return {"ok": False, "error": str(exc)}

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    header = (
        f"---\n"
        f"signal_id: {signal_id}\n"
        f"agent: {agent}\n"
        f"loop: {loop_name}\n"
        f"status: {status}\n"
        f"completed_at_utc: {now}\n"
        f"---\n\n"
    )
    full_content = header + content

    completions_dir.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(full_content, encoding="utf-8")

    return {
        "ok": True,
        "signal_id": signal_id,
        "status": status,
        "artifact_path": str(artifact_path),
        "loop": loop_name,
        "agent": agent,
        "bytes_written": len(full_content.encode("utf-8")),
    }
