#!/usr/bin/env python3
"""Check fleet status — cursor position vs signal count for all agents.

Usage:
    python3 check_status.py              # All agents
    python3 check_status.py --agent cp0  # Single agent
"""
import argparse
import json
import os
from pathlib import Path

AGENTS_ROOT = Path(os.environ.get('AGENTS_ROOT', Path.home() / "Desktop/Vessel/agents"))


def get_agent_status(agent: str) -> dict:
    """Read an agent's bus status."""
    bus_dir = AGENTS_ROOT / agent / "shared_intel" / "signal_bus"
    signals_file = bus_dir / "signals.jsonl"
    cursor_file = bus_dir / "cursors" / f"{agent}_ran_hover.cursor"
    completions_dir = bus_dir / "completions"

    if not bus_dir.exists():
        return {"agent": agent, "status": "NO_BUS"}

    total = sum(1 for _ in open(signals_file)) if signals_file.exists() else 0
    cursor = int(cursor_file.read_text().strip()) if cursor_file.exists() else 0
    completions = len(list(completions_dir.glob("*_completion.md"))) if completions_dir.exists() else 0
    pending = total - cursor

    # Read last signal
    last_signal = None
    if total > 0 and signals_file.exists():
        with open(signals_file) as f:
            for line in f:
                last_signal = line.strip()
        if last_signal:
            try:
                last_signal = json.loads(last_signal)
            except json.JSONDecodeError:
                last_signal = {"raw": last_signal}

    return {
        "agent": agent,
        "status": "IDLE" if pending == 0 else "PENDING",
        "total_signals": total,
        "cursor": cursor,
        "pending": pending,
        "completions": completions,
        "last_signal": last_signal,
    }


def main():
    parser = argparse.ArgumentParser(description="Check fleet signal bus status")
    parser.add_argument("--agent", help="Check a single agent (default: all)")
    args = parser.parse_args()

    if args.agent:
        agents = [args.agent]
    else:
        # Discover agents with signal buses
        agents = sorted([
            d.name for d in AGENTS_ROOT.iterdir()
            if d.is_dir() and (d / "shared_intel" / "signal_bus").exists()
        ])

    if not agents:
        print(f"No agents found at {AGENTS_ROOT}")
        print("Run setup.sh first.")
        return

    print(f"{'Agent':<12} {'Status':<10} {'Signals':<10} {'Cursor':<10} {'Pending':<10} {'Completions':<12}")
    print("-" * 64)

    for agent in agents:
        s = get_agent_status(agent)
        if s["status"] == "NO_BUS":
            print(f"{s['agent']:<12} {'NO BUS':<10}")
            continue

        indicator = "." if s["pending"] == 0 else f">>> {s['pending']}"
        print(f"{s['agent']:<12} {s['status']:<10} {s['total_signals']:<10} {s['cursor']:<10} {indicator:<10} {s['completions']:<12}")

    # Summary
    total_pending = sum(
        get_agent_status(a).get("pending", 0) for a in agents
    )
    print("-" * 64)
    print(f"Fleet: {len(agents)} agents, {total_pending} pending signals")


if __name__ == "__main__":
    main()
