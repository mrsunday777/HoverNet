#!/usr/bin/env python3
"""
HoverNet Queue Daemon — watches for research completions and auto-dispatches to builders.

This is the bridge between the research chain (proposer→critic→synth) and the
build chain (builders). The research chain self-dispatches internally, but the
synth→builder fan-out requires infrastructure because:

1. Synth writes contracts as markdown (artifacts), not signals
2. Contracts need to be parsed and distributed round-robin to builders
3. The next research round needs to be dispatched to proposer

The daemon watches:
- Synth completion proofs → parses contracts → dispatches to builders
- Builder completion proofs → tracks progress
- Thread status → dispatches next round or closes

Usage:
    # One-shot check (for cron or orchestrator)
    python3 queue_daemon.py --agents-root /tmp/hovernet-e2e --once

    # Continuous daemon (runs until killed)
    python3 queue_daemon.py --agents-root /tmp/hovernet-e2e --interval 30

    # Dry run (show what would be dispatched)
    python3 queue_daemon.py --agents-root /tmp/hovernet-e2e --once --dry-run
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Import sibling module
sys.path.insert(0, os.path.dirname(__file__))
from dispatch_to_builders import parse_contracts, find_builders, dispatch_signal, dispatch_proposer_round


def get_synth_completions(agents_root: str) -> list[dict]:
    """Find all synth completion files."""
    comp_dir = os.path.join(agents_root, 'synth', 'shared_intel', 'signal_bus', 'completions')
    completions = []

    if not os.path.isdir(comp_dir):
        return completions

    for fname in sorted(os.listdir(comp_dir)):
        if 'completion' not in fname:
            continue
        path = os.path.join(comp_dir, fname)
        try:
            with open(path, 'r') as f:
                content = f.read()

            # Parse YAML frontmatter
            meta = {}
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    for line in parts[1].strip().split('\n'):
                        if ':' in line:
                            key, val = line.split(':', 1)
                            meta[key.strip()] = val.strip()

            completions.append({
                'file': path,
                'signal_id': meta.get('signal_id', ''),
                'status': meta.get('status', ''),
                'content': content,
            })
        except OSError:
            continue

    return completions


def find_contracts_file(agents_root: str, round_id: str = 'r001') -> str | None:
    """Find the contracts file for a given round in research-output."""
    research_dir = os.path.join(agents_root, 'research-output')
    if not os.path.isdir(research_dir):
        return None

    # Try exact match first
    exact = os.path.join(research_dir, f'{round_id}_contracts.md')
    if os.path.exists(exact):
        return exact

    # Try glob
    matches = glob.glob(os.path.join(research_dir, f'*{round_id}*contract*'))
    if matches:
        return sorted(matches)[-1]

    return None


def get_dispatched_tracker(agents_root: str) -> Path:
    """Get path to the dispatch tracker file."""
    return Path(agents_root) / '.dispatched_rounds.json'


def load_dispatched_rounds(agents_root: str) -> dict:
    """Load the set of already-dispatched round IDs."""
    tracker = get_dispatched_tracker(agents_root)
    if tracker.exists():
        try:
            return json.loads(tracker.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {'dispatched_to_builders': [], 'dispatched_to_proposer': []}


def save_dispatched_rounds(agents_root: str, data: dict):
    """Save the dispatch tracker."""
    tracker = get_dispatched_tracker(agents_root)
    tracker.write_text(json.dumps(data, indent=2))


def extract_round_from_signal_id(signal_id: str) -> str | None:
    """Extract round identifier from a signal ID like SYNTH-CONSENSUS-R001-..."""
    match = re.search(r'(R\d{3})', signal_id, re.IGNORECASE)
    return match.group(1).upper() if match else None


def count_builder_signals(agents_root: str) -> dict[str, int]:
    """Count unread signals per builder."""
    counts = {}
    for builder_dir in sorted(glob.glob(os.path.join(agents_root, 'builder*'))):
        if not os.path.isdir(builder_dir):
            continue
        name = os.path.basename(builder_dir)
        bus = os.path.join(builder_dir, 'shared_intel', 'signal_bus', 'signals.jsonl')
        cursor_dir = os.path.join(builder_dir, 'shared_intel', 'signal_bus', 'cursors')

        bus_lines = 0
        if os.path.exists(bus):
            with open(bus, 'r') as f:
                bus_lines = sum(1 for line in f if line.strip())

        cursor = 0
        if os.path.isdir(cursor_dir):
            for cf in glob.glob(os.path.join(cursor_dir, '*.cursor')):
                try:
                    cursor = int(Path(cf).read_text().strip())
                except (ValueError, OSError):
                    pass

        counts[name] = bus_lines - cursor
    return counts


def daemon_tick(agents_root: str, dry_run: bool = False) -> list[str]:
    """Run one daemon tick. Returns list of actions taken."""
    actions = []
    dispatched = load_dispatched_rounds(agents_root)

    # Check synth completions
    completions = get_synth_completions(agents_root)
    for comp in completions:
        if comp['status'] != 'DONE':
            continue

        round_id = extract_round_from_signal_id(comp['signal_id'])
        if not round_id:
            continue

        # Skip if already dispatched
        if round_id in dispatched.get('dispatched_to_builders', []):
            continue

        # Find contracts file
        contracts_file = find_contracts_file(agents_root, round_id.lower())
        if not contracts_file:
            actions.append(f"WARN: Synth completed {round_id} but no contracts file found")
            continue

        contracts = parse_contracts(contracts_file)
        if not contracts:
            actions.append(f"WARN: Contracts file for {round_id} has no parseable contracts")
            continue

        builders = find_builders(agents_root)
        if not builders:
            actions.append("ERROR: No builder directories found")
            continue

        # Check if builders already have unread work
        builder_signals = count_builder_signals(agents_root)
        busy_builders = [b for b, count in builder_signals.items() if count > 0]
        if busy_builders:
            actions.append(f"SKIP: Builders {busy_builders} still have unread signals")
            continue

        if dry_run:
            actions.append(f"DRY-RUN: Would dispatch {len(contracts)} contracts from {round_id} to {len(builders)} builders")
            for i, c in enumerate(contracts):
                b = builders[i % len(builders)]
                actions.append(f"  [{b}] {c['id']}: {c.get('task', '?')}")
        else:
            # Dispatch contracts to builders
            for i, contract in enumerate(contracts):
                builder = builders[i % len(builders)]
                signal = dispatch_signal(agents_root, builder, contract, round_id)
                actions.append(f"DISPATCHED: {signal['signal_id']} -> {builder}")

            # Track this round
            dispatched.setdefault('dispatched_to_builders', []).append(round_id)

            # Dispatch next round to proposer
            if round_id not in dispatched.get('dispatched_to_proposer', []):
                round_num = int(round_id.replace('R', '')) + 1
                research_output = os.path.join(agents_root, 'research-output')
                proposer_signal = dispatch_proposer_round(agents_root, round_num, research_output)
                actions.append(f"DISPATCHED: {proposer_signal['signal_id']} -> proposer (Round {round_num})")
                dispatched.setdefault('dispatched_to_proposer', []).append(round_id)

            save_dispatched_rounds(agents_root, dispatched)

    if not actions:
        actions.append("IDLE: No new synth completions to process")

    return actions


def main():
    parser = argparse.ArgumentParser(description='HoverNet queue daemon')
    parser.add_argument('--agents-root', required=True, help='Path to fleet agents root')
    parser.add_argument('--once', action='store_true', help='Run one tick and exit')
    parser.add_argument('--interval', type=int, default=30, help='Seconds between ticks (default: 30)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be dispatched')
    args = parser.parse_args()

    if args.once:
        actions = daemon_tick(args.agents_root, args.dry_run)
        for action in actions:
            print(action)
        return 0

    # Continuous mode
    print(f"Queue daemon started — watching {args.agents_root} every {args.interval}s")
    print(f"Press Ctrl+C to stop\n")

    try:
        tick = 0
        while True:
            tick += 1
            now = datetime.now(timezone.utc).strftime('%H:%M:%S')
            actions = daemon_tick(args.agents_root, args.dry_run)

            non_idle = [a for a in actions if not a.startswith('IDLE')]
            if non_idle:
                print(f"[{now}] Tick {tick}:")
                for action in non_idle:
                    print(f"  {action}")
            else:
                print(f"[{now}] Tick {tick}: idle")

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
