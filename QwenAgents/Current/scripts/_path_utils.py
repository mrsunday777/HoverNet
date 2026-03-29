#!/usr/bin/env python3
"""Shared path resolution utilities for HoverNet Qwen scripts.

Provides consistent path resolution across all Qwen scripts,
ensuring that agent signal bus paths are resolved the same way everywhere.

Configure via environment variables:
    AGENTS_ROOT     Where agent directories live (default: ~/hovernet-fleet)

Usage:
    from _path_utils import resolve_agent_dir, resolve_signal_bus

    agent_dir = resolve_agent_dir('builder')
    bus = resolve_signal_bus('builder')
    signals_file = bus['signals']
"""
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

# Configurable root via environment variable
AGENTS_ROOT = Path(os.environ.get('AGENTS_ROOT', Path.home() / "hovernet-fleet"))


def resolve_agent_dir(agent: str) -> Optional[Path]:
    """Resolve agent directory with case-insensitive fallback.

    Args:
        agent: Agent name (e.g., 'builder', 'proposer', 'worker-3')

    Returns:
        Path to agent directory, or None if not found
    """
    agent = agent.strip().lower()

    # Try direct path first
    direct = AGENTS_ROOT / agent
    if direct.exists():
        return direct

    # Case-insensitive fallback
    if AGENTS_ROOT.exists():
        for d in AGENTS_ROOT.iterdir():
            if d.is_dir() and d.name.lower() == agent:
                return d

    return None


def resolve_signal_bus(agent: str) -> Dict[str, Path]:
    """Resolve all signal bus paths for an agent.

    Args:
        agent: Agent name

    Returns:
        Dict with keys: signals, cursors, completions, root, agent_dir

    Raises:
        FileNotFoundError: If agent directory not found
    """
    agent_dir = resolve_agent_dir(agent)
    if agent_dir is None:
        raise FileNotFoundError(f'Agent directory not found: {agent} (searched {AGENTS_ROOT})')

    bus_root = agent_dir / "shared_intel" / "signal_bus"

    return {
        'signals': bus_root / "signals.jsonl",
        'cursors': bus_root / "cursors",
        'completions': bus_root / "completions",
        'root': bus_root,
        'agent_dir': agent_dir,
    }


def resolve_cursor_file(agent: str, cursor_type: str = 'hover') -> Path:
    """Resolve cursor file path for an agent.

    Args:
        agent: Agent name
        cursor_type: Type of cursor ('hover', 'ran_hover', etc.)

    Returns:
        Path to cursor file
    """
    bus = resolve_signal_bus(agent)
    cursor_name = f"{agent}_{cursor_type}.cursor"

    # Try standard naming first
    cursor_file = bus['cursors'] / cursor_name
    if cursor_file.exists():
        return cursor_file

    # Try alternative naming (agent_ran_hover.cursor)
    if cursor_type == 'hover':
        alt_cursor = bus['cursors'] / f"{agent}_ran_hover.cursor"
        if alt_cursor.exists():
            return alt_cursor

    # Return standard path even if doesn't exist (will be created)
    return cursor_file


def check_agent_health(agent: str) -> Dict:
    """Check hover health for an agent.

    Args:
        agent: Agent name

    Returns:
        Dict with cursor_position, total_signals, pending_signals,
        completions_count, last_completion_age
    """
    bus = resolve_signal_bus(agent)

    # Read cursor
    cursor_file = resolve_cursor_file(agent)
    cursor = 0
    if cursor_file.exists():
        try:
            cursor = int(cursor_file.read_text().strip())
        except ValueError:
            pass

    # Count signals
    total_signals = 0
    if bus['signals'].exists():
        try:
            with open(bus['signals'], 'r', encoding='utf-8') as f:
                total_signals = sum(1 for _ in f)
        except IOError:
            pass

    # Count completions
    completions_count = 0
    last_completion_age = None
    if bus['completions'].exists():
        try:
            completions = list(bus['completions'].glob("*_completion.md"))
            completions_count = len(completions)
            if completions:
                newest = max(completions, key=lambda p: p.stat().st_mtime)
                last_completion_age = time.time() - newest.stat().st_mtime
        except (IOError, OSError):
            pass

    return {
        'cursor_position': cursor,
        'total_signals': total_signals,
        'pending_signals': max(0, total_signals - cursor),
        'completions_count': completions_count,
        'last_completion_age': last_completion_age,
    }
