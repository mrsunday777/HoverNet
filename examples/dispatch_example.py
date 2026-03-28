#!/usr/bin/env python3
"""Dispatch a signal to an agent's bus.

Usage:
    python3 dispatch_example.py --agent builder --task "Fix error handling in api.py"
    python3 dispatch_example.py --agent proposer --type RESEARCH_UNLOCK --task "Analyze main.py for edge cases"
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

AGENTS_ROOT = Path(os.environ.get('AGENTS_ROOT', Path.home() / "Desktop/Vessel/agents"))


def dispatch(agent: str, task: str, signal_type: str = "BUILDER_UNLOCK", notes: str = "") -> dict:
    """Write a signal to an agent's bus."""
    bus_dir = AGENTS_ROOT / agent / "shared_intel" / "signal_bus"
    signals_file = bus_dir / "signals.jsonl"

    if not bus_dir.exists():
        raise FileNotFoundError(f"Agent bus not found: {bus_dir}\nRun setup.sh first.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    signal_id = f"{agent.upper()}-{signal_type}-{timestamp}"

    signal = {
        "signal_id": signal_id,
        "type": signal_type,
        "target_agent": agent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "notes": notes or task,
    }

    with open(signals_file, "a") as f:
        f.write(json.dumps(signal) + "\n")

    return signal


def main():
    parser = argparse.ArgumentParser(description="Dispatch a signal to an agent")
    parser.add_argument("--agent", required=True, help="Target agent name (e.g., builder, proposer)")
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument("--type", default="BUILDER_UNLOCK", help="Signal type (default: BUILDER_UNLOCK)")
    parser.add_argument("--notes", default="", help="Additional notes")
    args = parser.parse_args()

    signal = dispatch(args.agent, args.task, args.type, args.notes)

    print(f"Dispatched to {args.agent}:")
    print(f"  Signal ID: {signal['signal_id']}")
    print(f"  Type:      {signal['type']}")
    print(f"  Task:      {signal['task']}")

    # Show pending count
    bus_dir = AGENTS_ROOT / args.agent / "shared_intel" / "signal_bus"
    signals_file = bus_dir / "signals.jsonl"
    cursor_file = bus_dir / "cursors" / f"{args.agent}_ran_hover.cursor"

    total = sum(1 for _ in open(signals_file))
    cursor = int(cursor_file.read_text().strip()) if cursor_file.exists() else 0
    pending = total - cursor

    print(f"  Pending:   {pending} signal(s) in queue")


if __name__ == "__main__":
    main()
