#!/usr/bin/env python3
"""
Dispatch builder contracts to builder signal buses.

This script reads a contracts file (markdown with ## Contract sections),
parses each contract into a bounded task, and writes signals to builder
buses round-robin.

Usage:
    python3 dispatch_to_builders.py \
        --contracts /path/to/r001_contracts.md \
        --agents-root /path/to/fleet \
        [--round R001] \
        [--next-round-to-proposer]

The contracts file should contain sections like:

    ## Contract: FIX-001
    **Task:** Fix hardcoded path in hover_tick.sh
    **File:** ClaudeAgents/cron/hover_tick.sh
    **Change:** Replace /Users/sunday with $HOME
    **Verification:** grep for hardcoded /Users paths
    **Complexity:** simple
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_contracts(contracts_path: str) -> list[dict]:
    """Parse a markdown contracts file into structured contract dicts."""
    with open(contracts_path, 'r') as f:
        content = f.read()

    contracts = []
    # Split on ## Contract: headers
    sections = re.split(r'(?=^## Contract:\s*)', content, flags=re.MULTILINE)

    for section in sections:
        if not section.strip().startswith('## Contract:'):
            continue

        contract: dict[str, str] = {}

        # Extract contract ID from header
        header_match = re.match(r'## Contract:\s*(\S+)', section)
        if header_match:
            contract['id'] = header_match.group(1)

        # Extract fields
        for field in ('Task', 'File', 'Change', 'Verification', 'Complexity'):
            pattern = rf'\*\*{field}:\*\*\s*(.+?)(?:\n|$)'
            match = re.search(pattern, section)
            if match:
                contract[field.lower()] = match.group(1).strip()

        if contract.get('id') and contract.get('task'):
            contracts.append(contract)

    return contracts


def find_builders(agents_root: str) -> list[str]:
    """Find all builder agent directories under agents_root."""
    builders = sorted([
        os.path.basename(d)
        for d in glob.glob(os.path.join(agents_root, 'builder*'))
        if os.path.isdir(d)
    ])
    return builders


def dispatch_signal(agents_root: str, builder: str, contract: dict, round_id: str) -> dict:
    """Write a signal to a builder's signal bus. Returns the signal dict."""
    now = datetime.now(timezone.utc)
    signal_id = f"{builder.upper()}-BUILD-{contract['id']}-{now.strftime('%Y%m%dT%H%M%S')}"

    notes_parts = [f"Execute contract {contract['id']}: {contract.get('task', '')}"]
    if contract.get('file'):
        notes_parts.append(f"File: {contract['file']}")
    if contract.get('change'):
        notes_parts.append(f"Change: {contract['change']}")
    if contract.get('verification'):
        notes_parts.append(f"Verify: {contract['verification']}")

    signal = {
        'signal_id': signal_id,
        'type': 'BUILDER_UNLOCK',
        'target_agent': builder,
        'task_or_phase_id': contract['id'],
        'notes': '. '.join(notes_parts),
        'round': round_id,
        'complexity': contract.get('complexity', 'medium'),
        'issued_at_utc': now.isoformat(),
    }

    bus_path = os.path.join(agents_root, builder, 'shared_intel', 'signal_bus', 'signals.jsonl')
    os.makedirs(os.path.dirname(bus_path), exist_ok=True)

    with open(bus_path, 'a') as f:
        f.write(json.dumps(signal) + '\n')

    return signal


def dispatch_proposer_round(agents_root: str, round_num: int, research_output_dir: str) -> dict:
    """Write a next-round signal to the proposer's bus."""
    now = datetime.now(timezone.utc)
    round_id = f"R{round_num:03d}"
    signal_id = f"PROPOSER-RESEARCH-{round_id}-{now.strftime('%Y%m%dT%H%M%S')}"

    signal = {
        'signal_id': signal_id,
        'type': 'BUILDER_UNLOCK',
        'target_agent': 'proposer',
        'task_or_phase_id': f'research-{round_id.lower()}',
        'notes': f"Round {round_num}: Continue analyzing the codebase. Review what was found in previous rounds and look for new issues in areas not yet examined. Write findings to {research_output_dir}/{round_id.lower()}_findings.md",
        'output_dir': research_output_dir,
        'issued_at_utc': now.isoformat(),
    }

    bus_path = os.path.join(agents_root, 'proposer', 'shared_intel', 'signal_bus', 'signals.jsonl')
    with open(bus_path, 'a') as f:
        f.write(json.dumps(signal) + '\n')

    return signal


def main():
    parser = argparse.ArgumentParser(description='Dispatch builder contracts to builder signal buses')
    parser.add_argument('--contracts', required=True, help='Path to contracts markdown file')
    parser.add_argument('--agents-root', required=True, help='Path to fleet agents root')
    parser.add_argument('--round', default='R001', help='Round identifier (e.g., R001)')
    parser.add_argument('--next-round-to-proposer', action='store_true',
                        help='Also dispatch next round signal to proposer')
    parser.add_argument('--research-output', default='', help='Research output directory for proposer')
    parser.add_argument('--dry-run', action='store_true', help='Parse and show what would be dispatched')
    args = parser.parse_args()

    # Parse contracts
    contracts = parse_contracts(args.contracts)
    if not contracts:
        print("ERROR: No contracts found in file", file=sys.stderr)
        return 1

    # Find builders
    builders = find_builders(args.agents_root)
    if not builders:
        print("ERROR: No builder directories found", file=sys.stderr)
        return 1

    print(f"Parsed {len(contracts)} contracts, {len(builders)} builders available")
    print(f"Builders: {', '.join(builders)}")

    if args.dry_run:
        for i, contract in enumerate(contracts):
            builder = builders[i % len(builders)]
            print(f"  [{builder}] Contract {contract['id']}: {contract.get('task', '?')}")
        if args.next_round_to_proposer:
            round_num = int(args.round.replace('R', '').replace('r', '')) + 1
            print(f"  [proposer] Next round R{round_num:03d}")
        return 0

    # Dispatch round-robin
    dispatched = []
    for i, contract in enumerate(contracts):
        builder = builders[i % len(builders)]
        signal = dispatch_signal(args.agents_root, builder, contract, args.round)
        dispatched.append(signal)
        print(f"  -> {builder}: {signal['signal_id']}")

    # Dispatch next round to proposer if requested
    if args.next_round_to_proposer:
        round_num = int(args.round.replace('R', '').replace('r', '')) + 1
        research_output = args.research_output or os.path.join(args.agents_root, 'research-output')
        proposer_signal = dispatch_proposer_round(args.agents_root, round_num, research_output)
        print(f"  -> proposer: {proposer_signal['signal_id']} (Round {round_num})")

    print(f"\nDispatched {len(dispatched)} contracts to {len(builders)} builders")

    # Summary per builder
    builder_counts: dict[str, int] = {}
    for i, contract in enumerate(contracts):
        builder = builders[i % len(builders)]
        builder_counts[builder] = builder_counts.get(builder, 0) + 1
    for builder, count in sorted(builder_counts.items()):
        print(f"  {builder}: {count} tasks")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
