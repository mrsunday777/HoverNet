#!/usr/bin/env python3
"""
Cursor Resilience Tools for HoverNet QwenBuilderLoop

Implements file locking and cursor metadata for drift detection.
Prevents multi-agent race conditions on cursor files.
"""

import fcntl
import os
import json
import time
from datetime import datetime, timezone
from typing import Optional


class CursorLock:
    """File-based lock preventing concurrent cursor modifications."""
    
    def __init__(self, cursor_file: str):
        self.cursor_file = cursor_file
        self.lock_file = cursor_file + ".lock"
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


class CursorWithMetadata:
    """Enhanced cursor with metadata for drift detection."""
    
    def __init__(self, cursor_file: str):
        self.cursor_file = cursor_file
    
    def read(self) -> dict:
        """
        Read cursor, handle both old (plain int) and new (JSON) formats.
        
        Returns:
            Dict with position, last_signal_id, last_signal_timestamp, updated_utc, format
        """
        try:
            content = open(self.cursor_file).read().strip()
            
            # Try JSON first (new format)
            try:
                data = json.loads(content)
                return data
            except json.JSONDecodeError:
                # Old format: plain integer
                return {
                    "position": int(content),
                    "last_signal_id": None,
                    "last_signal_timestamp": None,
                    "updated_utc": None,
                    "format": "legacy"
                }
        except (FileNotFoundError, ValueError):
            return {"position": 0, "format": "missing"}
    
    def write(self, position: int, last_signal_id: Optional[str] = None, 
              last_signal_timestamp: Optional[str] = None) -> dict:
        """
        Write cursor with full metadata, using file lock.
        
        Args:
            position: Cursor position (line number)
            last_signal_id: ID of last processed signal
            last_signal_timestamp: Timestamp of last processed signal
            
        Returns:
            The written data dict
        """
        data = {
            "position": position,
            "last_signal_id": last_signal_id,
            "last_signal_timestamp": last_signal_timestamp,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "format": "v2"
        }
        
        with CursorLock(self.cursor_file):
            # Atomic write: write to tmp, rename
            tmp = self.cursor_file + ".tmp"
            with open(tmp, 'w') as f:
                json.dump(data, f)
            os.replace(tmp, self.cursor_file)
        
        return data
    
    def advance(self, signal_id: Optional[str] = None, 
                signal_timestamp: Optional[str] = None) -> dict:
        """
        Advance cursor by 1 with metadata.
        
        Args:
            signal_id: ID of signal being completed
            signal_timestamp: Timestamp of signal being completed
            
        Returns:
            The new cursor data dict
        """
        current = self.read()
        new_pos = current.get("position", 0) + 1
        return self.write(new_pos, signal_id, signal_timestamp)


def detect_drift(cursor_file: str, signals_file: str) -> dict:
    """
    Detect cursor drift by comparing metadata with actual bus state.
    
    Args:
        cursor_file: Path to cursor file
        signals_file: Path to signals.jsonl file
        
    Returns:
        Dict with drifted, type, and details keys
    """
    # Read cursor metadata
    cursor = CursorWithMetadata(cursor_file)
    cursor_data = cursor.read()
    
    position = cursor_data.get("position", 0)
    last_signal_id = cursor_data.get("last_signal_id")
    
    # Check if signals file exists
    if not os.path.exists(signals_file):
        return {
            "drifted": False,
            "type": "none",
            "details": "Signals file does not exist"
        }
    
    # Read signals file
    with open(signals_file, 'r') as f:
        lines = f.readlines()
    
    total_signals = sum(1 for line in lines if line.strip())
    
    # Check position drift
    if position > total_signals:
        return {
            "drifted": True,
            "type": "position",
            "details": f"Cursor position ({position}) exceeds total signals ({total_signals})"
        }
    
    # Check ID mismatch
    if last_signal_id and position > 0 and position <= len(lines):
        try:
            signal_at_pos = json.loads(lines[position - 1].strip())
            actual_signal_id = signal_at_pos.get("signal_id")
            
            if actual_signal_id != last_signal_id:
                return {
                    "drifted": True,
                    "type": "id_mismatch",
                    "details": f"Last signal ID ({last_signal_id}) doesn't match signal at position {position} ({actual_signal_id})"
                }
        except (json.JSONDecodeError, IndexError):
            pass
    
    return {
        "drifted": False,
        "type": "none",
        "details": f"Cursor at position {position}/{total_signals}, no drift detected"
    }


def migrate_cursor(cursor_file: str) -> dict:
    """
    Upgrade old cursor format (plain int) to new JSON metadata format.
    
    Args:
        cursor_file: Path to cursor file
        
    Returns:
        Dict with migrated, old_format, and new_position keys
    """
    if not os.path.exists(cursor_file):
        return {
            "migrated": False,
            "old_format": "missing",
            "new_position": 0
        }
    
    try:
        content = open(cursor_file).read().strip()
        
        # Try to parse as JSON first (already new format)
        try:
            data = json.loads(content)
            return {
                "migrated": False,
                "old_format": data.get("format", "json"),
                "new_position": data.get("position", 0)
            }
        except json.JSONDecodeError:
            # Old format: plain integer
            old_position = int(content)
            
            # Migrate to new format
            cursor = CursorWithMetadata(cursor_file)
            cursor.write(old_position)
            
            return {
                "migrated": True,
                "old_format": "legacy_int",
                "new_position": old_position
            }
    except (ValueError, IOError):
        return {
            "migrated": False,
            "old_format": "invalid",
            "new_position": 0
        }


def mark_in_flight(agent_dir: str, signal_id: str) -> None:
    """
    Mark a signal as currently being processed.
    
    Args:
        agent_dir: Agent directory path
        signal_id: ID of signal being processed
    """
    path = os.path.join(agent_dir, "shared_intel/signal_bus/in_flight.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    with open(path, 'w') as f:
        json.dump({
            "signal_id": signal_id,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "status": "processing"
        }, f)


def clear_in_flight(agent_dir: str, status: str = "completed") -> None:
    """
    Clear or update in-flight tracker on completion.
    
    Args:
        agent_dir: Agent directory path
        status: Final status (completed/failed)
    """
    path = os.path.join(agent_dir, "shared_intel/signal_bus/in_flight.json")
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        
        data["status"] = status
        data["completed_utc"] = datetime.now(timezone.utc).isoformat()
        
        with open(path, 'w') as f:
            json.dump(data, f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass


def check_in_flight(agent_dir: str) -> Optional[dict]:
    """
    Check current in-flight status.
    
    Args:
        agent_dir: Agent directory path
        
    Returns:
        In-flight dict or None if not found
    """
    path = os.path.join(agent_dir, "shared_intel/signal_bus/in_flight.json")
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cursor resilience tools")
    parser.add_argument("--cursor", help="Cursor file path")
    parser.add_argument("--signals", help="Signals file path")
    parser.add_argument("--read", action="store_true", help="Read cursor value")
    parser.add_argument("--migrate", action="store_true", help="Migrate cursor to new format")
    parser.add_argument("--check-drift", action="store_true", help="Check for cursor drift")
    parser.add_argument("--agent-dir", help="Agent dir for in-flight tracking")
    parser.add_argument("--mark-in-flight", metavar="SIGNAL_ID", help="Mark signal as in-flight")
    parser.add_argument("--clear-in-flight", metavar="STATUS", nargs="?", default="completed", 
                        help="Clear in-flight tracker")
    parser.add_argument("--check-in-flight", action="store_true", help="Check in-flight status")
    
    args = parser.parse_args()
    
    if args.read and args.cursor:
        cursor = CursorWithMetadata(args.cursor)
        data = cursor.read()
        print(json.dumps(data, indent=2))
    
    if args.migrate and args.cursor:
        result = migrate_cursor(args.cursor)
        print(json.dumps(result, indent=2))
    
    if args.check_drift and args.cursor and args.signals:
        result = detect_drift(args.cursor, args.signals)
        print(json.dumps(result, indent=2))
    
    if args.agent_dir:
        if args.mark_in_flight:
            mark_in_flight(args.agent_dir, args.mark_in_flight)
            print(f"Marked {args.mark_in_flight} as in-flight")
        
        if args.clear_in_flight is not None:
            clear_in_flight(args.agent_dir, args.clear_in_flight)
            print(f"Cleared in-flight with status: {args.clear_in_flight}")
        
        if args.check_in_flight:
            result = check_in_flight(args.agent_dir)
            if result:
                print(json.dumps(result, indent=2))
            else:
                print("No in-flight signal")
