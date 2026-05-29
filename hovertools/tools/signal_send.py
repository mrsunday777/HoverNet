"""signal_send — manifest-aware bus append. No tmux. No tap. Public profile only."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

_SIGNAL_SIZE_LIMIT = 64 * 1024  # 64 KB


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _safe_path(workspace: Path, raw: str) -> Path:
    """Resolve raw path and ensure it stays within workspace."""
    p = Path(raw).expanduser().resolve()
    try:
        p.relative_to(workspace)
    except ValueError:
        raise PermissionError(f"path {raw!r} escapes workspace root {workspace}")
    return p


def run(
    *,
    root: str,
    target_agent: str,
    signal_type: str,
    payload: dict,
    thread: str | None = None,
    round: str | int | None = None,
) -> dict:
    """Append one signal to target_agent's bus, resolving the path from hovernet.json.

    Generates signal_id and timestamp if absent from payload.
    Enforces 64 KB size cap.
    No tmux tap — bus-append only.
    from_agent in payload is a label, not authentication.
    """
    signal_kind = str(signal_type).strip()
    if not signal_kind:
        return {"ok": False, "error": "signal_type must not be empty"}

    _, workspace = _workspace(root)

    try:
        manifest = _load_manifest(workspace)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

    agent_entry = manifest.get("agents", {}).get(target_agent)
    if agent_entry is None:
        return {
            "ok": False,
            "error": f"agent {target_agent!r} not found in manifest; run agent_register first",
        }

    try:
        bus_path = _safe_path(workspace, agent_entry["bus_path"])
    except PermissionError as exc:
        return {"ok": False, "error": str(exc)}

    if not isinstance(payload, dict):
        return {"ok": False, "error": "payload must be a JSON object (dict)"}

    # Build envelope — caller's payload is the base; we fill required fields if missing
    envelope: dict = dict(payload)
    sender = str(envelope.get("from", "")).strip()
    if not sender:
        return {
            "ok": False,
            "error": "payload must include a non-empty 'from' label",
            "hint": "'from' is provenance only, not authentication",
        }
    envelope["from"] = sender
    envelope.setdefault(
        "signal_id",
        f"{signal_kind}-{target_agent}-{uuid.uuid4().hex[:8]}",
    )
    envelope.setdefault("type", signal_kind)
    envelope["type"] = signal_kind  # type is always authoritative from the argument
    envelope["to"] = target_agent
    envelope.setdefault("timestamp", _utc_now())
    if thread is not None:
        envelope.setdefault("thread", thread)
    if round is not None:
        envelope.setdefault("round", round)

    try:
        line = json.dumps(envelope, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": f"payload is not JSON-serializable: {exc}"}

    if len(line.encode("utf-8")) > _SIGNAL_SIZE_LIMIT:
        return {
            "ok": False,
            "error": f"signal exceeds 64 KB limit ({len(line.encode('utf-8'))} bytes); put large data in a file and reference it via contract_path",
        }

    bus_path.parent.mkdir(parents=True, exist_ok=True)
    with bus_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")

    return {
        "ok": True,
        "signal_id": envelope["signal_id"],
        "target_agent": target_agent,
        "signal_type": signal_type,
        "bus_path": str(bus_path),
        "bytes_written": len(line.encode("utf-8")),
    }
