#!/usr/bin/env python3
"""Unified configuration module for HoverNet.

Centralized path resolution and configuration via environment variables.

Environment variables:
    HOVERNET_ROOT       Path to HoverNet project root
    AGENTS_ROOT         Path to agents directory

Usage:
    from _config import get_hovernet_root, get_agents_root

    PROJECT_ROOT = get_hovernet_root()
    AGENTS_ROOT = get_agents_root()
"""
import os
from pathlib import Path


def get_hovernet_root() -> Path:
    """Resolve HoverNet project root from environment or defaults.

    Checks:
    1. HOVERNET_ROOT environment variable
    2. Default locations in order of preference
    """
    env_root = os.environ.get('HOVERNET_ROOT')
    if env_root:
        return Path(env_root).expanduser()

    # Try default locations
    defaults = [
        Path.home() / 'HoverNet',
        Path(__file__).resolve().parent.parent.parent.parent,  # scripts -> Current -> QwenAgents -> HoverNet
    ]

    for root in defaults:
        if root.exists():
            return root

    return defaults[0]


def get_agents_root() -> Path:
    """Resolve agents root directory from environment or defaults.

    Checks:
    1. AGENTS_ROOT environment variable
    2. Default locations in order of preference
    """
    env_root = os.environ.get('AGENTS_ROOT')
    if env_root:
        return Path(env_root).expanduser()

    default = Path.home() / 'hovernet-fleet'
    return default


# Configuration constants (overridable via environment)
def get_max_task_retries() -> int:
    return int(os.environ.get('MAX_TASK_RETRIES', '3'))

def get_hover_liveness_window() -> int:
    """Hover liveness window in seconds."""
    return int(os.environ.get('HOVER_LIVENESS_WINDOW', '300'))

def get_max_pending_signals() -> int:
    return int(os.environ.get('MAX_PENDING_SIGNALS', '5'))

def get_max_signal_age_minutes() -> int:
    return int(os.environ.get('MAX_SIGNAL_AGE_MINUTES', '60'))

def get_poll_seconds() -> float:
    return float(os.environ.get('DAEMON_POLL_SECONDS', '2.0'))


# Convenience exports
PROJECT_ROOT = get_hovernet_root()
AGENTS_ROOT = get_agents_root()
