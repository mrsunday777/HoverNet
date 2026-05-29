"""decision_log — Append-only audit trail, JSONL format."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append(
    *,
    log_path: str,
    decision_id: str,
    title: str,
    actor: str,
    choice: str,
    rationale: str,
    context: str | None = None,
    alternatives: list[str] | None = None,
    impacts: list[str] | None = None,
) -> dict:
    p = Path(log_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "decision_id": decision_id,
        "timestamp": _utc_now(),
        "title": title,
        "actor": actor,
        "choice": choice,
        "rationale": rationale,
    }
    if context is not None:
        record["context"] = context
    if alternatives is not None:
        record["alternatives"] = alternatives
    if impacts is not None:
        record["impacts"] = impacts

    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")))
        f.write("\n")

    return {"ok": True, "log_path": str(p), "decision_id": decision_id, "timestamp": record["timestamp"]}


def query(*, log_path: str, since: str | None = None, limit: int = 50) -> dict:
    p = Path(log_path).expanduser()
    if not p.exists():
        return {"ok": True, "log_path": str(p), "decisions": [], "count": 0}

    decisions: list[dict] = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and rec.get("timestamp", "") < since:
            continue
        decisions.append(rec)

    decisions = decisions[-limit:]
    return {"ok": True, "log_path": str(p), "count": len(decisions), "decisions": decisions}
