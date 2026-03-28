#!/usr/bin/env python3
"""
Fleet status checker for HoverNet.

Scans all agent directories under a fleet root and reports:
- Signal bus line counts
- Completion/ACK counts
- Hover state (from runtime/hover.json)
- Handoff status (stalls detected)

Usage:
    python3 fleet_status.py --agents-root /tmp/hovernet-e2e
    python3 fleet_status.py --agents-root /tmp/hovernet-e2e --json
    python3 fleet_status.py --agents-root /tmp/hovernet-e2e --watch
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def get_agent_status(agent_dir: str) -> dict:
    """Get the status of a single agent."""
    agent_name = os.path.basename(agent_dir)
    bus_dir = os.path.join(agent_dir, 'shared_intel', 'signal_bus')
    signals_file = os.path.join(bus_dir, 'signals.jsonl')
    completions_dir = os.path.join(bus_dir, 'completions')
    hover_file = os.path.join(agent_dir, 'runtime', 'hover.json')

    # Count signals
    bus_lines = 0
    if os.path.exists(signals_file):
        with open(signals_file, 'r') as f:
            bus_lines = sum(1 for line in f if line.strip())

    # Count completions and acks
    comp_count = 0
    ack_count = 0
    if os.path.isdir(completions_dir):
        for fname in os.listdir(completions_dir):
            if 'completion' in fname:
                comp_count += 1
            elif 'ack' in fname:
                ack_count += 1

    # Read cursor
    cursor = 0
    cursors_dir = os.path.join(bus_dir, 'cursors')
    if os.path.isdir(cursors_dir):
        for cursor_file in glob.glob(os.path.join(cursors_dir, '*.cursor')):
            try:
                with open(cursor_file, 'r') as f:
                    cursor = int(f.read().strip())
            except (ValueError, OSError):
                pass

    # Read hover state
    hover_state = None
    if os.path.exists(hover_file):
        try:
            with open(hover_file, 'r') as f:
                hover_state = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    unread = bus_lines - cursor

    return {
        'agent': agent_name,
        'bus_lines': bus_lines,
        'cursor': cursor,
        'unread': unread,
        'completions': comp_count,
        'acks': ack_count,
        'hover': hover_state,
    }


def detect_stalls(statuses: list[dict]) -> list[str]:
    """Detect handoff stalls in the research chain."""
    stalls = []
    agent_map = {s['agent']: s for s in statuses}

    # Check research chain: proposer -> critic -> synth
    chain = [
        ('proposer', 'critic'),
        ('critic', 'synth'),
    ]

    for source, target in chain:
        src = agent_map.get(source)
        tgt = agent_map.get(target)
        if not src or not tgt:
            continue

        # If source has completions but target has no unread signals
        if src['completions'] > 0 and tgt['unread'] == 0:
            src_hover = src.get('hover') or {}
            tasks_done = src_hover.get('tasks_completed', 0)
            if tasks_done > 0:
                stalls.append(f"{source} completed {tasks_done} task(s) but {target} has no unread signals")

    # Check synth -> builder fan-out
    synth = agent_map.get('synth')
    if synth and synth['completions'] > 0:
        synth_hover = synth.get('hover') or {}
        if synth_hover.get('tasks_completed', 0) > 0:
            builders = [s for s in statuses if s['agent'].startswith('builder')]
            total_builder_unread = sum(b['unread'] for b in builders)
            if total_builder_unread == 0:
                stalls.append("synth completed but no builder has unread signals (dispatch gap)")

    return stalls


def print_status(agents_root: str, as_json: bool = False):
    """Print fleet status."""
    agent_dirs = sorted(glob.glob(os.path.join(agents_root, '*')))
    agent_dirs = [d for d in agent_dirs if os.path.isdir(d)
                  and os.path.basename(d) not in ('research-output', 'dispatches', '.git')]

    statuses = [get_agent_status(d) for d in agent_dirs]
    stalls = detect_stalls(statuses)

    if as_json:
        print(json.dumps({
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'agents': statuses,
            'stalls': stalls,
        }, indent=2))
        return

    print(f"Fleet Status — {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
    print(f"{'Agent':<15} {'Bus':>4} {'Cursor':>7} {'Unread':>7} {'Comps':>6} {'ACKs':>5} {'Hover State'}")
    print("-" * 75)

    for s in statuses:
        hover = s.get('hover') or {}
        state = hover.get('state', '-')
        last = hover.get('last_result', '')
        tasks = hover.get('tasks_completed', 0)
        hover_str = f"{state}"
        if last:
            hover_str += f" ({last})"
        if tasks > 0:
            hover_str += f" [{tasks} done]"

        unread_marker = f"  {s['unread']}" if s['unread'] > 0 else f"  {s['unread']}"
        print(f"{s['agent']:<15} {s['bus_lines']:>4} {s['cursor']:>7} {unread_marker:>7} {s['completions']:>6} {s['acks']:>5}  {hover_str}")

    if stalls:
        print(f"\n⚠ Stalls detected:")
        for stall in stalls:
            print(f"  - {stall}")
    else:
        print(f"\nNo stalls detected.")


def main():
    parser = argparse.ArgumentParser(description='HoverNet fleet status')
    parser.add_argument('--agents-root', required=True, help='Path to fleet agents root')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--watch', action='store_true', help='Continuous monitoring (refresh every 5s)')
    parser.add_argument('--stalls-only', action='store_true', help='Only report stalls (exit 1 if any)')
    args = parser.parse_args()

    if args.watch:
        try:
            while True:
                os.system('clear')
                print_status(args.agents_root, args.json)
                time.sleep(5)
        except KeyboardInterrupt:
            pass
        return 0

    if args.stalls_only:
        agent_dirs = sorted(glob.glob(os.path.join(args.agents_root, '*')))
        agent_dirs = [d for d in agent_dirs if os.path.isdir(d)
                      and os.path.basename(d) not in ('research-output', 'dispatches', '.git')]
        statuses = [get_agent_status(d) for d in agent_dirs]
        stalls = detect_stalls(statuses)
        if stalls:
            for s in stalls:
                print(s, file=sys.stderr)
            return 1
        return 0

    print_status(args.agents_root, args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
