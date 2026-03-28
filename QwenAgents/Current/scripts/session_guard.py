#!/usr/bin/env python3
"""
Session Guard and Cursor Validation for HoverNet QwenBuilderLoop

Detects when multiple agents try to process the same bus, and validates
cursor against completions to prevent duplicates after truncation.
"""

import fcntl
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional


class SessionGuard:
    """Prevents duplicate hover sessions on the same agent bus."""
    
    def __init__(self, agent_dir: str, agent_name: str):
        self.agent_dir = agent_dir
        self.agent_name = agent_name
        self.lock_path = os.path.join(agent_dir, "shared_intel/signal_bus/hover.lock")
        self._fd = None
    
    def acquire(self) -> bool:
        """
        Try to acquire exclusive hover lock.
        
        Returns:
            True if acquired, False if another session holds it
        """
        try:
            os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
            self._fd = open(self.lock_path, 'w')
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write PID + timestamp for debugging
            self._fd.write(json.dumps({
                "pid": os.getpid(),
                "agent": self.agent_name,
                "acquired_utc": datetime.now(timezone.utc).isoformat()
            }))
            self._fd.flush()
            return True
        except (IOError, OSError):
            return False
    
    def release(self) -> None:
        """Release the hover lock."""
        if self._fd:
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
            self._fd.close()
            try:
                os.unlink(self.lock_path)
            except OSError:
                pass
            self._fd = None
    
    def check_existing(self) -> dict:
        """
        Check if another session holds the lock.

        Returns:
            Dict with lock status and holder info
        """
        try:
            with open(self.lock_path) as f:
                data = json.load(f)
            pid = data.get("pid")
            
            # Check if PID is still alive
            try:
                os.kill(pid, 0)
                return {
                    "locked": True,
                    "by_pid": pid,
                    "agent": data.get("agent"),
                    "since": data.get("acquired_utc")
                }
            except ProcessLookupError:
                return {
                    "locked": False,
                    "stale_lock": True,
                    "dead_pid": pid
                }
        except (FileNotFoundError, json.JSONDecodeError):
            return {"locked": False}
    
    def __enter__(self):
        if not self.acquire():
            existing = self.check_existing()
            raise RuntimeError(f"Another session already holds hover lock: {existing}")
        return self
    
    def __exit__(self, *args):
        self.release()


def validate_cursor_against_completions(agent_dir: str, cursor_position: int) -> dict:
    """
    Validate cursor position against completion files.
    
    Args:
        agent_dir: Agent directory path
        cursor_position: Current cursor position
        
    Returns:
        Dict with valid, duplicates, and gaps keys
    """
    signals_file = os.path.join(agent_dir, "shared_intel/signal_bus/signals.jsonl")
    completions_dir = os.path.join(agent_dir, "shared_intel/signal_bus/completions")
    
    completed_signal_ids = set()
    
    # Read all completion files
    if os.path.exists(completions_dir):
        for fname in os.listdir(completions_dir):
            if fname.endswith("_completion.md") or fname.endswith("_ack.md"):
                # Extract signal_id from filename
                signal_id = fname.replace("_completion.md", "").replace("_ack.md", "")
                completed_signal_ids.add(signal_id)
    
    # Read signals up to cursor position
    signals_before_cursor = set()
    all_signals = []
    
    if os.path.exists(signals_file):
        with open(signals_file, 'r') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    signal = json.loads(line)
                    signal_id = signal.get("signal_id")
                    all_signals.append(signal_id)
                    if i < cursor_position:
                        signals_before_cursor.add(signal_id)
                except json.JSONDecodeError:
                    continue
    
    # Check for duplicates: completed signals that cursor hasn't passed yet
    duplicates = list(completed_signal_ids - signals_before_cursor)
    
    # Check for gaps: signals cursor passed but no completion
    gaps = list(signals_before_cursor - completed_signal_ids)
    
    valid = len(duplicates) == 0
    
    return {
        "valid": valid,
        "duplicates": duplicates,
        "gaps": gaps
    }


def safe_cursor_reset(agent_dir: str, cursor_path: str, signals_path: str) -> dict:
    """
    Safe cursor reset after bus truncation.
    
    Args:
        agent_dir: Agent directory path
        cursor_path: Path to cursor file
        signals_path: Path to signals.jsonl file
        
    Returns:
        Dict with new_position, skipped_completed, and reason
    """
    completions_dir = os.path.join(agent_dir, "shared_intel/signal_bus/completions")
    
    # Read all completion signal_ids
    completed_signal_ids = set()
    if os.path.exists(completions_dir):
        for fname in os.listdir(completions_dir):
            if fname.endswith("_completion.md") or fname.endswith("_ack.md"):
                signal_id = fname.replace("_completion.md", "").replace("_ack.md", "")
                completed_signal_ids.add(signal_id)
    
    # Scan new bus for completed signal_ids
    last_completed_position = -1
    found_count = 0
    
    if os.path.exists(signals_path):
        with open(signals_path, 'r') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    signal = json.loads(line)
                    signal_id = signal.get("signal_id")
                    if signal_id in completed_signal_ids:
                        last_completed_position = i
                        found_count += 1
                except json.JSONDecodeError:
                    continue
    
    # Set cursor to position AFTER last completed signal
    new_position = last_completed_position + 1 if last_completed_position >= 0 else 0
    
    # Write new cursor position using atomic write
    from cursor_resilience import CursorWithMetadata
    cursor = CursorWithMetadata(cursor_path)
    cursor.write(new_position)
    
    return {
        "new_position": new_position,
        "skipped_completed": found_count,
        "reason": f"Set cursor after {found_count} completed signals"
    }


def detect_duplicate_processing(agent_dir: str) -> dict:
    """
    Detect signals that are both in-flight and completed.
    
    Args:
        agent_dir: Agent directory path
        
    Returns:
        Dict with duplicates list and count
    """
    in_flight_path = os.path.join(agent_dir, "shared_intel/signal_bus/in_flight.json")
    completions_dir = os.path.join(agent_dir, "shared_intel/signal_bus/completions")
    
    # Read in_flight signal
    in_flight_signal_id = None
    if os.path.exists(in_flight_path):
        try:
            with open(in_flight_path) as f:
                data = json.load(f)
            in_flight_signal_id = data.get("signal_id")
        except (json.JSONDecodeError, IOError):
            pass
    
    # Read completed signal_ids
    completed_signal_ids = set()
    if os.path.exists(completions_dir):
        for fname in os.listdir(completions_dir):
            if fname.endswith("_completion.md") or fname.endswith("_ack.md"):
                signal_id = fname.replace("_completion.md", "").replace("_ack.md", "")
                completed_signal_ids.add(signal_id)
    
    # Check for duplicates
    duplicates = []
    if in_flight_signal_id and in_flight_signal_id in completed_signal_ids:
        duplicates.append(in_flight_signal_id)
    
    return {
        "duplicates": duplicates,
        "count": len(duplicates)
    }


def clean_stale_locks(agent_dir: str) -> dict:
    """
    Clean stale lock files (dead PID).
    
    Args:
        agent_dir: Agent directory path
        
    Returns:
        Dict with list of cleaned lock files
    """
    signal_bus = os.path.join(agent_dir, "shared_intel/signal_bus")
    lock_files = ["hover.lock", "compaction.lock"]
    cleaned = []
    
    for lock_name in lock_files:
        lock_path = os.path.join(signal_bus, lock_name)
        
        if not os.path.exists(lock_path):
            continue

        try:
            with open(lock_path) as f:
                data = json.load(f)
            pid = data.get("pid")
            
            if pid:
                # Check if PID is still alive
                try:
                    os.kill(pid, 0)
                    # PID is alive, lock is not stale
                    continue
                except ProcessLookupError:
                    # PID is dead, remove stale lock
                    os.unlink(lock_path)
                    cleaned.append(lock_name)
        except (json.JSONDecodeError, IOError):
            # Invalid lock file, remove it
            try:
                os.unlink(lock_path)
                cleaned.append(lock_name)
            except OSError:
                pass
    
    return {"cleaned": cleaned}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Session guard and cursor validation")
    sub = parser.add_subparsers(dest="command")
    
    # check command
    guard = sub.add_parser("check", help="Check for existing sessions")
    guard.add_argument("--agent-dir", required=True)
    guard.add_argument("--agent-name", required=True)
    
    # validate command
    validate = sub.add_parser("validate", help="Validate cursor against completions")
    validate.add_argument("--agent-dir", required=True)
    validate.add_argument("--cursor-pos", type=int, required=True)
    
    # safe-reset command
    reset = sub.add_parser("safe-reset", help="Safe cursor reset after truncation")
    reset.add_argument("--agent-dir", required=True)
    reset.add_argument("--cursor", required=True)
    reset.add_argument("--signals", required=True)
    
    # clean-locks command
    clean = sub.add_parser("clean-locks", help="Clean stale lock files")
    clean.add_argument("--agent-dir", required=True)
    
    args = parser.parse_args()
    
    if args.command == "check":
        guard_instance = SessionGuard(args.agent_dir, args.agent_name)
        result = guard_instance.check_existing()
        print(json.dumps(result, indent=2))
    
    elif args.command == "validate":
        result = validate_cursor_against_completions(args.agent_dir, args.cursor_pos)
        print(json.dumps(result, indent=2))
    
    elif args.command == "safe-reset":
        result = safe_cursor_reset(args.agent_dir, args.cursor, args.signals)
        print(json.dumps(result, indent=2))
    
    elif args.command == "clean-locks":
        result = clean_stale_locks(args.agent_dir)
        print(json.dumps(result, indent=2))
    
    else:
        parser.print_help()
