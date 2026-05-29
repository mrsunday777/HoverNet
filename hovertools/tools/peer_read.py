"""peer_read — Read a set of sibling artifacts for local fan-in gates."""

from __future__ import annotations

from pathlib import Path


def run(*, artifact_paths: list[str], require_all: bool = True) -> dict:
    present: dict[str, str] = {}
    missing: list[str] = []

    for raw in artifact_paths:
        p = Path(raw).expanduser()
        if p.exists() and p.is_file():
            present[str(p)] = p.read_text(encoding="utf-8")
        else:
            missing.append(str(p))

    ready = len(missing) == 0
    if require_all and not ready:
        return {
            "ok": True,
            "ready": False,
            "missing": missing,
            "present_count": len(present),
            "total": len(artifact_paths),
        }

    return {
        "ok": True,
        "ready": ready,
        "missing": missing,
        "present_count": len(present),
        "total": len(artifact_paths),
        "artifacts": present,
    }
