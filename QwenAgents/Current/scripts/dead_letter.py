#!/usr/bin/env python3
"""Dead-letter queue and signal audit log for QwenBuilderLoop."""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


def move_to_dead_letter(agent_dir: str, signal_json: dict, reason: str) -> dict:
    """
    Move a failed signal to the dead letter queue.
    
    Args:
        agent_dir: Base agent directory
        signal_json: The signal dict to move
        reason: Reason for moving to dead letter
    
    Returns:
        {"moved": True, "signal_id": str, "reason": str}
    """
    dead_letter_file = os.path.join(agent_dir, "shared_intel/signal_bus/dead_letter.jsonl")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(dead_letter_file), exist_ok=True)
    
    # Add dead letter fields
    signal_with_reason = signal_json.copy()
    signal_with_reason["dead_letter_reason"] = reason
    signal_with_reason["dead_letter_utc"] = datetime.now(timezone.utc).isoformat()
    
    # Append to dead letter file
    with open(dead_letter_file, 'a') as f:
        f.write(json.dumps(signal_with_reason) + '\n')
    
    signal_id = signal_json.get('signal_id', 'unknown')
    
    return {
        "moved": True,
        "signal_id": signal_id,
        "reason": reason
    }


def retry_from_dead_letter(agent_dir: str, signal_id: str) -> dict:
    """
    Retry a signal from the dead letter queue.
    
    Args:
        agent_dir: Base agent directory
        signal_id: ID of signal to retry
    
    Returns:
        {"retried": True, "signal_id": str, "retry_count": int}
    """
    dead_letter_file = os.path.join(agent_dir, "shared_intel/signal_bus/dead_letter.jsonl")
    signals_file = os.path.join(agent_dir, "shared_intel/signal_bus/signals.jsonl")
    
    # Read dead letter file and find the signal
    dead_letters = []
    found_signal = None
    
    with open(dead_letter_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get('signal_id') == signal_id and found_signal is None:
                    found_signal = data
                else:
                    dead_letters.append(line)
            except json.JSONDecodeError:
                dead_letters.append(line)
    
    if found_signal is None:
        return {"retried": False, "signal_id": signal_id, "error": "Signal not found in dead letter queue"}
    
    # Remove dead letter fields
    found_signal.pop('dead_letter_reason', None)
    found_signal.pop('dead_letter_utc', None)
    
    # Increment retry count
    retry_count = found_signal.get('retry_count', 0) + 1
    found_signal['retry_count'] = retry_count
    
    # Append back to signals file
    with open(signals_file, 'a') as f:
        f.write(json.dumps(found_signal) + '\n')
    
    # Rewrite dead letter file without the retried signal
    with open(dead_letter_file, 'w') as f:
        f.writelines(line + '\n' if not line.endswith('\n') else line for line in dead_letters)
    
    return {
        "retried": True,
        "signal_id": signal_id,
        "retry_count": retry_count
    }


def list_dead_letters(agent_dir: str) -> list[dict]:
    """
    List all signals in the dead letter queue.
    
    Returns:
        List of {"signal_id": str, "reason": str, "dead_letter_utc": str, "type": str}
    """
    dead_letter_file = os.path.join(agent_dir, "shared_intel/signal_bus/dead_letter.jsonl")
    
    if not os.path.exists(dead_letter_file):
        return []
    
    results = []
    with open(dead_letter_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                results.append({
                    "signal_id": data.get('signal_id', 'unknown'),
                    "reason": data.get('dead_letter_reason', ''),
                    "dead_letter_utc": data.get('dead_letter_utc', ''),
                    "type": data.get('type', '')
                })
            except json.JSONDecodeError:
                continue
    
    return results


def detect_poison_pill(agent_dir: str, signal_id: str, max_retries: int = 3) -> dict:
    """
    Detect if a signal is a poison pill (retried too many times).
    
    Args:
        agent_dir: Base agent directory
        signal_id: ID of signal to check
        max_retries: Maximum allowed retries before marking as poison
    
    Returns:
        {"is_poison": bool, "retry_count": int, "signal_id": str}
    """
    dead_letter_file = os.path.join(agent_dir, "shared_intel/signal_bus/dead_letter.jsonl")
    
    if not os.path.exists(dead_letter_file):
        return {"is_poison": False, "retry_count": 0, "signal_id": signal_id}
    
    retry_count = 0
    with open(dead_letter_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get('signal_id') == signal_id:
                    retry_count += 1
            except json.JSONDecodeError:
                continue
    
    is_poison = retry_count > max_retries
    
    return {
        "is_poison": is_poison,
        "retry_count": retry_count,
        "signal_id": signal_id
    }


def audit_log(agent_dir: str, event_type: str, signal_id: str, details: str = "") -> None:
    """
    Append an audit log entry.
    
    Args:
        agent_dir: Base agent directory
        event_type: One of "consumed", "completed", "failed", "dead_lettered", "retried", "expired"
        signal_id: ID of the signal
        details: Additional details
    """
    audit_file = os.path.join(agent_dir, "shared_intel/signal_bus/audit.jsonl")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(audit_file), exist_ok=True)
    
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "signal_id": signal_id,
        "details": details
    }
    
    with open(audit_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def expire_old_signals(agent_dir: str, ttl_minutes: int = 60) -> dict:
    """
    Move old uncompleted signals to dead letter queue.
    
    Args:
        agent_dir: Base agent directory
        ttl_minutes: Time-to-live in minutes
    
    Returns:
        {"expired": int, "signal_ids": list}
    """
    signals_file = os.path.join(agent_dir, "shared_intel/signal_bus/signals.jsonl")
    agent_name = os.path.basename(agent_dir)
    cursor_file = os.path.join(agent_dir, f"shared_intel/signal_bus/cursors/{agent_name}_ran_hover.cursor")
    completions_dir = os.path.join(agent_dir, "shared_intel/signal_bus/completions")
    
    # Read cursor position
    cursor = 0
    if os.path.exists(cursor_file):
        with open(cursor_file, 'r') as f:
            cursor = int(f.read().strip())
    
    # Get completed signal IDs
    completed_ids = set()
    if os.path.isdir(completions_dir):
        for filename in os.listdir(completions_dir):
            if filename.endswith('_completion.md'):
                signal_id = filename[:-14]  # Remove '_completion.md'
                completed_ids.add(signal_id)
    
    # Read signals from cursor onward
    expired_ids = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
    
    # Read all lines first
    with open(signals_file, 'r') as f:
        lines = f.readlines()
    
    # Process from cursor position
    new_lines = lines[:cursor]
    
    for i, line in enumerate(lines[cursor:], start=cursor):
        line = line.strip()
        if not line:
            new_lines.append(line + '\n')
            continue
        
        try:
            data = json.loads(line)
            signal_id = data.get('signal_id', '')
            
            # Check if signal is completed
            if signal_id in completed_ids:
                new_lines.append(line + '\n')
                continue
            
            # Check timestamp - try different timestamp fields
            timestamp_str = data.get('timestamp_utc') or data.get('issued_at_utc', '')
            if timestamp_str:
                try:
                    # Handle various ISO formats
                    timestamp_str = timestamp_str.replace('Z', '+00:00')
                    signal_time = datetime.fromisoformat(timestamp_str)
                    if signal_time.tzinfo is None:
                        signal_time = signal_time.replace(tzinfo=timezone.utc)
                    
                    if signal_time < cutoff_time:
                        # Move to dead letter
                        move_to_dead_letter(agent_dir, data, "expired")
                        audit_log(agent_dir, "expired", signal_id, f"expired after {ttl_minutes} minutes")
                        expired_ids.append(signal_id)
                        continue
                except (ValueError, TypeError):
                    pass
            
            # Keep the signal
            new_lines.append(line + '\n')
            
        except json.JSONDecodeError:
            new_lines.append(line + '\n')
    
    # Write back modified lines
    with open(signals_file, 'w') as f:
        f.writelines(new_lines)
    
    return {
        "expired": len(expired_ids),
        "signal_ids": expired_ids
    }


def cleanup_completions(agent_dir: str, max_age_days: int = 7) -> dict:
    """
    Delete completion files older than max_age_days.
    
    Args:
        agent_dir: Base agent directory
        max_age_days: Maximum age in days
    
    Returns:
        {"deleted": int}
    """
    completions_dir = os.path.join(agent_dir, "shared_intel/signal_bus/completions")
    
    if not os.path.isdir(completions_dir):
        return {"deleted": 0}
    
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    deleted = 0
    
    for filename in os.listdir(completions_dir):
        if not filename.endswith('_completion.md'):
            continue
        
        filepath = os.path.join(completions_dir, filename)
        
        # Check file modification time
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath), tz=timezone.utc)
            if mtime < cutoff_time:
                os.remove(filepath)
                deleted += 1
        except (OSError, ValueError):
            continue
    
    return {"deleted": deleted}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Dead letter queue manager")
    parser.add_argument("--agent-dir", required=True, help="Agent directory")
    parser.add_argument("--list", action="store_true", help="List dead letters")
    parser.add_argument("--retry", metavar="SIGNAL_ID", help="Retry a dead letter")
    parser.add_argument("--expire", type=int, metavar="MINUTES", help="Expire old signals")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="Clean old completions")
    args = parser.parse_args()
    
    results = {}
    
    if args.list:
        dead_letters = list_dead_letters(args.agent_dir)
        results["dead_letters"] = dead_letters
    
    if args.retry:
        retry_result = retry_from_dead_letter(args.agent_dir, args.retry)
        results["retry"] = retry_result
    
    if args.expire:
        expire_result = expire_old_signals(args.agent_dir, args.expire)
        results["expire"] = expire_result
    
    if args.cleanup:
        cleanup_result = cleanup_completions(args.agent_dir, args.cleanup)
        results["cleanup"] = cleanup_result
    
    print(json.dumps(results, indent=2))