#!/usr/bin/env python3
"""Cursor backup and compaction synchronization for signal bus."""

import json
import os
import sys
import time
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

# Number of rotating backups to keep
CURSOR_BACKUP_COUNT = 3


def write_cursor_with_backup(cursor_path: str, value: int) -> dict:
    """
    Write cursor value with rotating backup.
    
    Args:
        cursor_path: Path to cursor file
        value: New cursor value
    
    Returns:
        {"backed_up": True, "position": value, "backups": [list of backup paths]}
    """
    backups = []
    
    # Rotate existing backups: .bak.3 deleted, .bak.2→.bak.3, .bak.1→.bak.2
    # Delete oldest backup if it exists
    oldest_backup = f"{cursor_path}.bak.{CURSOR_BACKUP_COUNT}"
    if os.path.exists(oldest_backup):
        try:
            os.remove(oldest_backup)
        except OSError:
            pass
    
    # Shift backups: .bak.2→.bak.3, .bak.1→.bak.2
    for i in range(CURSOR_BACKUP_COUNT - 1, 0, -1):
        old_path = f"{cursor_path}.bak.{i}"
        new_path = f"{cursor_path}.bak.{i + 1}"
        if os.path.exists(old_path):
            try:
                os.rename(old_path, new_path)
                backups.append(new_path)
            except OSError:
                pass
    
    # Copy current cursor to .bak.1 if it exists
    if os.path.exists(cursor_path):
        backup_path = f"{cursor_path}.bak.1"
        try:
            with open(cursor_path, 'r') as src:
                content = src.read()
            with open(backup_path, 'w') as dst:
                dst.write(content)
            backups.insert(0, backup_path)
        except (IOError, OSError):
            pass
    
    # Write new cursor value atomically (write to .tmp, rename)
    tmp_path = cursor_path + ".tmp"
    try:
        with open(tmp_path, 'w') as f:
            f.write(str(value))
        os.rename(tmp_path, cursor_path)
    except (IOError, OSError) as e:
        # Clean up tmp file if rename failed
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    
    return {
        "backed_up": True,
        "position": value,
        "backups": backups
    }


def restore_cursor_from_backup(cursor_path: str) -> dict:
    """
    Restore cursor from newest valid backup.
    
    Args:
        cursor_path: Path to cursor file
    
    Returns:
        {"restored": True, "from_backup": str, "position": int} or
        {"restored": False, "reason": "no_backups"}
    """
    # Find newest valid backup (.bak.1, then .bak.2, etc.)
    for i in range(1, CURSOR_BACKUP_COUNT + 1):
        backup_path = f"{cursor_path}.bak.{i}"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r') as f:
                    content = f.read().strip()
                position = int(content)
                
                # Write it as current cursor atomically
                tmp_path = cursor_path + ".tmp"
                with open(tmp_path, 'w') as f:
                    f.write(str(position))
                os.rename(tmp_path, cursor_path)
                
                return {
                    "restored": True,
                    "from_backup": backup_path,
                    "position": position
                }
            except (IOError, ValueError, OSError):
                continue
    
    return {"restored": False, "reason": "no_backups"}


def list_backups(cursor_path: str) -> list:
    """
    List all backup files for a cursor.
    
    Args:
        cursor_path: Path to cursor file
    
    Returns:
        List of {"path": str, "position": int, "age_sec": float} sorted newest first
    """
    backups = []
    now = time.time()
    
    for i in range(1, CURSOR_BACKUP_COUNT + 1):
        backup_path = f"{cursor_path}.bak.{i}"
        if os.path.exists(backup_path):
            try:
                mtime = os.path.getmtime(backup_path)
                age_sec = now - mtime
                
                with open(backup_path, 'r') as f:
                    position = int(f.read().strip())
                
                backups.append({
                    "path": backup_path,
                    "position": position,
                    "age_sec": int(age_sec)
                })
            except (IOError, ValueError, OSError):
                continue
    
    # Sort by age (newest first)
    backups.sort(key=lambda x: x["age_sec"])
    
    return backups


class CompactionLock:
    """
    Lock that prevents hover from reading cursor during compaction.
    """
    
    def __init__(self, bus_path: str):
        self.lock_file = str(bus_path) + ".compaction.lock"
        self._fd = None
    
    def __enter__(self):
        self._fd = open(self.lock_file, 'w')
        fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX)
        return self
    
    def __exit__(self, *args):
        if self._fd:
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
            self._fd.close()
            try:
                os.unlink(self.lock_file)
            except OSError:
                pass


def safe_compact(bus_path: str, cursor_path: str, keep_lines: Optional[int] = None) -> dict:
    """
    Safely compact bus with locking and atomic writes.
    
    Args:
        bus_path: Path to signals.jsonl
        cursor_path: Path to cursor file
        keep_lines: Number of lines to keep (None = keep active signals only)
    
    Returns:
        {"compacted": True, "old_lines": int, "new_lines": int, "cursor_reset_to": int}
    """
    with CompactionLock(bus_path):
        # Read bus
        with open(bus_path, 'r') as f:
            lines = f.readlines()
        
        old_lines = len(lines)
        
        # Filter lines
        if keep_lines is not None:
            new_lines_data = lines[-keep_lines:]
        else:
            # Keep only valid JSON lines (active signals)
            new_lines_data = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    new_lines_data.append(line)
                    continue
                try:
                    json.loads(stripped)
                    new_lines_data.append(line)
                except json.JSONDecodeError:
                    pass
        
        new_lines = len(new_lines_data)
        
        # Write bus atomically
        tmp_path = bus_path + ".tmp"
        with open(tmp_path, 'w') as f:
            f.writelines(new_lines_data)
        os.rename(tmp_path, bus_path)
        
        # Reset cursor to match new bus length
        cursor_value = new_lines
        tmp_cursor = cursor_path + ".tmp"
        with open(tmp_cursor, 'w') as f:
            f.write(str(cursor_value))
        os.rename(tmp_cursor, cursor_path)
        
        return {
            "compacted": True,
            "old_lines": old_lines,
            "new_lines": new_lines,
            "cursor_reset_to": cursor_value
        }


def check_compaction_safe(bus_path: str, cursor_path: str) -> dict:
    """
    Check if it's safe to compact.
    
    Args:
        bus_path: Path to signals.jsonl
        cursor_path: Path to cursor file
    
    Returns:
        {"safe": bool, "reason": str}
    """
    # Check if compaction lock exists (someone compacting?)
    lock_file = str(bus_path) + ".compaction.lock"
    if os.path.exists(lock_file):
        try:
            # Try to acquire lock non-blocking
            fd = open(lock_file, 'w')
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
                fd.close()
            except (IOError, BlockingIOError):
                fd.close()
                return {"safe": False, "reason": "compaction_lock_exists"}
        except (IOError, OSError):
            return {"safe": False, "reason": "compaction_lock_exists"}
    
    # Check if cursor > bus lines (already drifted?)
    cursor_value = 0
    if os.path.exists(cursor_path):
        try:
            with open(cursor_path, 'r') as f:
                cursor_value = int(f.read().strip())
        except (IOError, ValueError):
            pass
    
    bus_lines = 0
    if os.path.exists(bus_path):
        with open(bus_path, 'r') as f:
            bus_lines = sum(1 for line in f if line.strip())
    
    if cursor_value > bus_lines:
        return {"safe": False, "reason": "cursor_drifted", "cursor": cursor_value, "bus_lines": bus_lines}
    
    return {"safe": True, "reason": "ok"}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cursor backup and compaction sync")
    sub = parser.add_subparsers(dest="command")
    
    backup = sub.add_parser("backup", help="Write cursor with backup")
    backup.add_argument("--cursor", required=True)
    backup.add_argument("--value", type=int, required=True)
    
    restore = sub.add_parser("restore", help="Restore from backup")
    restore.add_argument("--cursor", required=True)
    
    ls = sub.add_parser("list", help="List backups")
    ls.add_argument("--cursor", required=True)
    
    compact = sub.add_parser("compact", help="Safe compaction")
    compact.add_argument("--bus", required=True)
    compact.add_argument("--cursor", required=True)
    compact.add_argument("--keep-lines", type=int, help="Lines to keep")
    
    check = sub.add_parser("check", help="Check compaction safety")
    check.add_argument("--bus", required=True)
    check.add_argument("--cursor", required=True)
    
    args = parser.parse_args()
    
    results = {}
    
    if args.command == "backup":
        result = write_cursor_with_backup(args.cursor, args.value)
        results["backup"] = result
    
    elif args.command == "restore":
        result = restore_cursor_from_backup(args.cursor)
        results["restore"] = result
    
    elif args.command == "list":
        backups = list_backups(args.cursor)
        results["backups"] = backups
    
    elif args.command == "compact":
        result = safe_compact(args.bus, args.cursor, args.keep_lines)
        results["compact"] = result
    
    elif args.command == "check":
        result = check_compaction_safe(args.bus, args.cursor)
        results["check"] = result
    
    else:
        parser.print_help()
        sys.exit(0)
    
    print(json.dumps(results, indent=2))
