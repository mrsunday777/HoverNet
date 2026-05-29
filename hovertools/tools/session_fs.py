"""session_fs — Scoped read/write rooted at a session dir. Cannot escape."""

from __future__ import annotations

from pathlib import Path


def _resolve(session_dir: str, relative_path: str) -> Path:
    root = Path(session_dir).expanduser().resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise PermissionError(f"path {target} escapes session_dir {root}")
    return target


def read(*, session_dir: str, relative_path: str) -> dict:
    target = _resolve(session_dir, relative_path)
    if not target.exists():
        return {"ok": False, "error": "not_found", "path": str(target)}
    content = target.read_text(encoding="utf-8")
    return {
        "ok": True,
        "path": str(target),
        "size": len(content),
        "content": content,
    }


def write(*, session_dir: str, relative_path: str, content: str) -> dict:
    target = _resolve(session_dir, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "path": str(target),
        "bytes_written": len(content.encode("utf-8")),
    }


def list_dir(*, session_dir: str, relative_path: str = ".") -> dict:
    target = _resolve(session_dir, relative_path)
    if not target.exists():
        return {"ok": False, "error": "not_found", "path": str(target)}
    if not target.is_dir():
        return {"ok": False, "error": "not_a_directory", "path": str(target)}
    entries = []
    for p in sorted(target.iterdir()):
        entries.append({
            "name": p.name,
            "path": str(p),
            "is_dir": p.is_dir(),
            "size": p.stat().st_size if p.is_file() else None,
        })
    return {"ok": True, "path": str(target), "entries": entries}
