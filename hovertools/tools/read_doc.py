"""read_doc — Big-file reader. Ports smart_read behaviour without external deps.

Modes:
    - default  → small file: full content. Large file: metadata + chunk 0
    - chunk=N  → return chunk N (0-indexed)
    - grep=PAT → return matching lines with ±3 line context
    - lines=M-N → return line range (inclusive, 1-indexed)
"""

from __future__ import annotations

import re
from pathlib import Path

CHUNK_LINES = 400
SMALL_FILE_LIMIT = 800  # if file <= this many lines, return whole thing by default


def _meta(p: Path, lines: list[str]) -> dict:
    return {
        "path": str(p),
        "size_bytes": p.stat().st_size,
        "line_count": len(lines),
        "chunk_size": CHUNK_LINES,
        "total_chunks": (len(lines) + CHUNK_LINES - 1) // CHUNK_LINES,
    }


def _parse_range(spec: str, total: int) -> tuple[int, int]:
    if "-" in spec:
        a, b = spec.split("-", 1)
        start = max(1, int(a or 1))
        end = min(total, int(b or total))
    else:
        start = end = int(spec)
    return start, end


def run(*, filepath: str, chunk: int | None = None, grep: str | None = None, lines: str | None = None) -> dict:
    p = Path(filepath).expanduser()
    if not p.exists():
        return {"ok": False, "error": "not_found", "path": str(p)}
    if not p.is_file():
        return {"ok": False, "error": "not_a_file", "path": str(p)}

    try:
        raw = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "error": "binary_file", "path": str(p), "size_bytes": p.stat().st_size}

    all_lines = raw.splitlines()
    meta = _meta(p, all_lines)

    if grep is not None:
        pattern = re.compile(grep)
        hits = []
        for i, line in enumerate(all_lines):
            if pattern.search(line):
                lo = max(0, i - 3)
                hi = min(len(all_lines), i + 4)
                hits.append({
                    "line": i + 1,
                    "match": line,
                    "context": all_lines[lo:hi],
                    "context_start": lo + 1,
                })
        return {"ok": True, "mode": "grep", "pattern": grep, "hits": hits, **meta}

    if lines is not None:
        start, end = _parse_range(lines, len(all_lines))
        slice_ = all_lines[start - 1 : end]
        return {
            "ok": True,
            "mode": "lines",
            "range": [start, end],
            "content": "\n".join(slice_),
            **meta,
        }

    if chunk is not None:
        start = chunk * CHUNK_LINES
        end = start + CHUNK_LINES
        slice_ = all_lines[start:end]
        return {
            "ok": True,
            "mode": "chunk",
            "chunk": chunk,
            "range": [start + 1, min(end, len(all_lines))],
            "content": "\n".join(slice_),
            **meta,
        }

    # default
    if len(all_lines) <= SMALL_FILE_LIMIT:
        return {"ok": True, "mode": "full", "content": raw, **meta}
    return {
        "ok": True,
        "mode": "chunk",
        "chunk": 0,
        "range": [1, min(CHUNK_LINES, len(all_lines))],
        "content": "\n".join(all_lines[:CHUNK_LINES]),
        "hint": "file exceeds small-file threshold — pass chunk=N, lines=M-N, or grep=PAT",
        **meta,
    }
