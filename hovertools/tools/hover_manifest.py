"""hover_manifest_read + hover_manifest_validate — manifest inspection tools."""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST_VERSION = "0.1"

_REQUIRED_TOP = {"manifest_version", "root", "workspace_dir", "agents", "loops"}
_REQUIRED_AGENT = {"bus_path", "cursor_path"}
_REQUIRED_LOOP = {"name", "agents", "session_dir", "completions_dir"}


def _workspace(root: str) -> tuple[Path, Path]:
    r = Path(root).expanduser().resolve()
    return r, r / ".hovernet"


def _load(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        raise FileNotFoundError(f"no manifest at {manifest_path}")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest is not valid JSON: {exc}") from exc


def read(*, root: str) -> dict:
    """Return the parsed hovernet.json from root/.hovernet/hovernet.json."""
    try:
        _, workspace = _workspace(root)
        manifest = _load(workspace / "hovernet.json")
        return {"ok": True, "manifest": manifest, "manifest_path": str(workspace / "hovernet.json")}
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"unexpected: {exc}"}


def validate(*, root: str) -> dict:
    """Validate manifest structure. Returns {ok, errors} where errors is a list of strings."""
    try:
        _, workspace = _workspace(root)
        manifest = _load(workspace / "hovernet.json")
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "errors": [str(exc)]}
    except Exception as exc:
        return {"ok": False, "errors": [f"unexpected: {exc}"]}

    errors: list[str] = []

    # Top-level required fields
    for field in _REQUIRED_TOP:
        if field not in manifest:
            errors.append(f"missing top-level field: {field!r}")

    # manifest_version check
    ver = manifest.get("manifest_version", "")
    if ver and ver.split(".")[0] != MANIFEST_VERSION.split(".")[0]:
        errors.append(
            f"manifest_version major mismatch: got {ver!r}, expected {MANIFEST_VERSION!r}"
        )

    # agents
    agents = manifest.get("agents", {})
    if not isinstance(agents, dict):
        errors.append("'agents' must be a dict")
    else:
        for name, entry in agents.items():
            for field in _REQUIRED_AGENT:
                if field not in entry:
                    errors.append(f"agent {name!r} missing field: {field!r}")

    # loops
    loops = manifest.get("loops", {})
    if not isinstance(loops, dict):
        errors.append("'loops' must be a dict")
    else:
        for name, entry in loops.items():
            for field in _REQUIRED_LOOP:
                if field not in entry:
                    errors.append(f"loop {name!r} missing field: {field!r}")
            # agents list references valid agent names
            for agent in entry.get("agents", []):
                if agent not in agents:
                    errors.append(
                        f"loop {name!r} references unknown agent {agent!r}"
                    )

    return {"ok": len(errors) == 0, "errors": errors, "manifest_version": ver}
