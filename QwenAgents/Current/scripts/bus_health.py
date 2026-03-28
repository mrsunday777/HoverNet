#!/usr/bin/env python3
"""Bus self-healing infrastructure for QwenBuilderLoop."""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def validate_json_lines(signals_file: str) -> list[tuple[int, str]]:
    """
    Read each line of signals.jsonl and validate JSON.
    
    Returns list of (line_number, error_message) for bad lines.
    Returns empty list if all valid.
    """
    errors = []
    with open(signals_file, 'r') as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                errors.append((line_number, str(e)))
    return errors


def validate_cursor_drift(cursor_file: str, signals_file: str) -> dict:
    """
    Check if cursor has drifted beyond total signals.
    
    Returns:
        {"drifted": bool, "cursor": int, "total": int, "gap": int}
    """
    # Read cursor value
    with open(cursor_file, 'r') as f:
        cursor = int(f.read().strip())
    
    # Count total lines in signals file
    with open(signals_file, 'r') as f:
        total = sum(1 for line in f if line.strip())
    
    gap = max(0, cursor - total)
    drifted = cursor > total
    
    return {
        "drifted": drifted,
        "cursor": cursor,
        "total": total,
        "gap": gap
    }


def repair_bus(signals_file: str, backup_dir: Optional[str] = None) -> dict:
    """
    Backup and repair signals file by removing invalid JSON lines.
    
    Args:
        signals_file: Path to signals.jsonl
        backup_dir: If provided, use as backup directory. Otherwise use signals_file + ".bak"
    
    Returns:
        {"removed": int, "kept": int, "backup": str}
    """
    if backup_dir is None:
        backup_path = signals_file + ".bak"
    else:
        backup_path = os.path.join(backup_dir, os.path.basename(signals_file) + ".bak")
    
    # Create backup
    shutil.copy2(signals_file, backup_path)
    
    # Read all lines and filter valid JSON
    with open(signals_file, 'r') as f:
        lines = f.readlines()
    
    valid_lines = []
    removed = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            valid_lines.append(line)
            continue
        try:
            json.loads(stripped)
            valid_lines.append(line)
        except json.JSONDecodeError:
            removed += 1
    
    # Write back valid lines
    with open(signals_file, 'w') as f:
        f.writelines(valid_lines)
    
    kept = len(valid_lines) - sum(1 for l in valid_lines if not l.strip())
    
    return {
        "removed": removed,
        "kept": kept,
        "backup": backup_path
    }


def scan_orphan_signals(signals_file: str, completions_dir: str) -> list[str]:
    """
    Find signal IDs that have no matching completion file.
    
    Returns list of signal IDs without completions.
    """
    # Read all signal IDs from signals file
    signal_ids = set()
    with open(signals_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if 'signal_id' in data:
                    signal_ids.add(data['signal_id'])
            except json.JSONDecodeError:
                continue
    
    # List all completion files and extract signal IDs
    completion_signal_ids = set()
    if os.path.isdir(completions_dir):
        for filename in os.listdir(completions_dir):
            if filename.endswith('_completion.md'):
                # Extract signal_id from filename: <SIGNAL_ID>_completion.md
                signal_id = filename[:-14]  # Remove '_completion.md'
                completion_signal_ids.add(signal_id)
    
    # Find orphans (signals without completions)
    orphans = list(signal_ids - completion_signal_ids)
    return orphans


def compact_bus_verified(signals_file: str, archive_dir: str, max_lines: int = 500) -> dict:
    """
    Compact signals file by archiving old lines.
    
    If signals file has more than max_lines:
        - Copy first (total - 100) lines to archive file with timestamp name
        - Keep last 100 lines in signals file
        - Verify archive line count matches expected
    
    Returns:
        {"archived": int, "remaining": int, "archive_file": str | None}
    """
    with open(signals_file, 'r') as f:
        lines = f.readlines()
    
    total = len(lines)
    
    if total <= max_lines:
        return {
            "archived": 0,
            "remaining": total,
            "archive_file": None
        }
    
    # Calculate lines to archive and keep
    lines_to_archive = total - 100
    lines_to_keep = 100
    
    archive_lines = lines[:lines_to_archive]
    remaining_lines = lines[lines_to_archive:]
    
    # Create archive file with timestamp
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    archive_filename = f"signals_archive_{timestamp}.jsonl"
    archive_path = os.path.join(archive_dir, archive_filename)
    
    # Ensure archive directory exists
    os.makedirs(archive_dir, exist_ok=True)
    
    # Write archive
    with open(archive_path, 'w') as f:
        f.writelines(archive_lines)
    
    # Verify archive line count
    with open(archive_path, 'r') as f:
        archived_count = sum(1 for _ in f)
    
    if archived_count != lines_to_archive:
        raise RuntimeError(f"Archive verification failed: expected {lines_to_archive}, got {archived_count}")
    
    # Write remaining lines back to signals file
    with open(signals_file, 'w') as f:
        f.writelines(remaining_lines)
    
    return {
        "archived": lines_to_archive,
        "remaining": lines_to_keep,
        "archive_file": archive_path
    }


def log_self_healing_event(agent_dir: str, event_type: str, details: dict) -> None:
    """
    Append JSON line to self_healing.jsonl.
    
    Args:
        agent_dir: Base agent directory
        event_type: One of "cursor_drift_detected", "bus_repaired", "orphan_found", "compaction_done"
        details: Additional details dict
    """
    log_file = os.path.join(agent_dir, "shared_intel/signal_bus/self_healing.jsonl")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    event = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details
    }
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(event) + '\n')


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Bus health checker")
    parser.add_argument("--signals", required=True, help="Path to signals.jsonl")
    parser.add_argument("--cursor", help="Path to cursor file")
    parser.add_argument("--completions", help="Path to completions dir")
    parser.add_argument("--repair", action="store_true", help="Repair bus by removing invalid lines")
    parser.add_argument("--compact", action="store_true", help="Compact bus by archiving old signals")
    parser.add_argument("--max-lines", type=int, default=500, help="Max lines before compaction")
    parser.add_argument("--agent-dir", help="Agent directory for logging")
    args = parser.parse_args()
    
    results = {}
    
    # Validate JSON lines
    json_errors = validate_json_lines(args.signals)
    results["json_validation"] = {
        "valid": len(json_errors) == 0,
        "errors": json_errors
    }
    
    # Check cursor drift if cursor file provided
    if args.cursor:
        drift_result = validate_cursor_drift(args.cursor, args.signals)
        results["cursor_drift"] = drift_result
        
        if drift_result["drifted"] and args.agent_dir:
            log_self_healing_event(args.agent_dir, "cursor_drift_detected", drift_result)
    
    # Repair if requested
    if args.repair:
        repair_result = repair_bus(args.signals)
        results["repair"] = repair_result
        
        if args.agent_dir and repair_result["removed"] > 0:
            log_self_healing_event(args.agent_dir, "bus_repaired", repair_result)
    
    # Scan orphans if completions dir provided
    if args.completions:
        orphans = scan_orphan_signals(args.signals, args.completions)
        results["orphan_signals"] = {
            "count": len(orphans),
            "signal_ids": orphans
        }
    
    # Compact if requested
    if args.compact:
        archive_dir = os.path.join(os.path.dirname(args.signals), "archive")
        compact_result = compact_bus_verified(args.signals, archive_dir, args.max_lines)
        results["compaction"] = compact_result
        
        if args.agent_dir and compact_result["archived"] > 0:
            log_self_healing_event(args.agent_dir, "compaction_done", compact_result)
    
    print(json.dumps(results, indent=2))
