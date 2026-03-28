#!/usr/bin/env python3
"""
Hover — Model-Agnostic Agent Continuous Polling Runtime

Implements the 3 hover invariants:
1. Continuous polling — cron-backed, return to idle after every tick
2. Fresh explicit unlocks — every signal gets fresh ID, targeted to one consumer
3. Execute, prove, return — consume signal, do work, write proof, advance cursor, return

Usage:
    python3 Hover.py --agent <name> --poll-sec <int> [--once]

Example:
    python3 Hover.py --agent builder --poll-sec 10
    python3 Hover.py --agent builder --once           # single tick (cron mode)
    python3 Hover.py --agent builder --health          # health check (JSON)
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from _path_utils import resolve_signal_bus, resolve_cursor_file, check_agent_health, resolve_agent_dir


def resolve_bus(agent: str) -> tuple[Path, Path, Path, Path, Path]:
    """Resolve signal bus paths for an agent.

    Returns:
        Tuple of (signals_file, cursors_dir, completions_dir, bus_root, agent_dir)
    """
    agent_dir = resolve_agent_dir(agent)
    if agent_dir is None:
        agents_root = Path(os.environ.get('AGENTS_ROOT', Path.home() / "Desktop" / "Vessel" / "agents"))
        agent_dir = agents_root / agent
    bus_root = agent_dir / "shared_intel" / "signal_bus"
    return (
        bus_root / "signals.jsonl",
        bus_root / "cursors",
        bus_root / "completions",
        bus_root,
        agent_dir,
    )


# ── ANSI Colors ──
_TTY = sys.stdout.isatty()
C_GREEN = '\033[0;32m' if _TTY else ''
C_BGREEN = '\033[1;32m' if _TTY else ''
C_CYAN = '\033[0;36m' if _TTY else ''
C_BCYAN = '\033[1;36m' if _TTY else ''
C_DIM = '\033[0;90m' if _TTY else ''
C_YELLOW = '\033[0;33m' if _TTY else ''
C_RED = '\033[0;31m' if _TTY else ''
C_BOLD = '\033[1m' if _TTY else ''
C_RESET = '\033[0m' if _TTY else ''

HOVER_BANNER = f"""
{C_BGREEN}    ██   ██  ██████  ██    ██ ███████ ██████  {C_RESET}
{C_BGREEN}    ██   ██ ██    ██ ██    ██ ██      ██   ██ {C_RESET}
{C_BGREEN}    ███████ ██    ██ ██    ██ █████   ██████  {C_RESET}
{C_GREEN}    ██   ██ ██    ██  ██  ██  ██      ██   ██ {C_RESET}
{C_GREEN}    ██   ██  ██████    ████   ███████ ██   ██ {C_RESET}
{C_DIM}    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░{C_RESET}"""

# ── Graceful Shutdown ──
_shutdown_requested = False


def _request_shutdown(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    log(f'shutdown requested (signal {signum}), finishing current tick...')


def ts() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def log(msg: str) -> None:
    print(f'{C_DIM}[{ts()}]{C_RESET} {msg}')


def log_signal(msg: str) -> None:
    print(f'{C_DIM}[{ts()}]{C_RESET} {C_BGREEN}◆{C_RESET} {C_BCYAN}{msg}{C_RESET}')


def log_idle(cursor: int, total: int, poll: int, cycles: int) -> None:
    print(f'{C_DIM}[{ts()}] ◜ idle ░░░░░░░░░░░░ cursor={cursor}/{total} poll={poll}s cycles={cycles}{C_RESET}')


def log_warn(msg: str) -> None:
    print(f'{C_DIM}[{ts()}]{C_RESET} {C_YELLOW}⚠ {msg}{C_RESET}')


def log_blocked(msg: str) -> None:
    print(f'{C_DIM}[{ts()}]{C_RESET} {C_RED}✖ {msg}{C_RESET}')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Hover — Model-Agnostic Agent Continuous Polling Runtime')
    parser.add_argument('--agent', type=str, required=True, help='Agent name (e.g., builder, proposer)')
    parser.add_argument('--poll-sec', type=int, default=10, help='Poll interval in seconds (default: 10)')
    parser.add_argument('--once', action='store_true', help='Run one tick and exit')
    parser.add_argument('--show-dispatch', type=int, default=1, help='Show dispatch file previews (0 or 1)')
    parser.add_argument('--health', action='store_true', help='Check agent health and exit (JSON output)')
    return parser.parse_args()


def ensure_dirs(signals_file: Path, cursors_dir: Path, completions_dir: Path) -> None:
    cursors_dir.mkdir(parents=True, exist_ok=True)
    completions_dir.mkdir(parents=True, exist_ok=True)
    signals_file.parent.mkdir(parents=True, exist_ok=True)
    if not signals_file.exists():
        signals_file.touch()


def get_cursor_path(agent: str, cursors_dir: Path) -> Path:
    return cursors_dir / f"{agent}_hover.cursor"


def read_cursor(cursor_path: Path) -> int:
    if not cursor_path.exists():
        return 0
    try:
        val = int(cursor_path.read_text().strip())
        return val if val >= 0 else 0
    except (ValueError, IOError):
        return 0


def write_cursor(cursor_path: Path, value: int) -> None:
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(f"{value}\n", encoding='utf-8')


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except IOError:
        return 0


def read_signal_line(path: Path, line_num: int) -> str | None:
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if i == line_num:
                    return line.strip()
        return None
    except IOError:
        return None


def parse_signal(json_line: str) -> dict:
    try:
        obj = json.loads(json_line)
        return {
            'target_agent': obj.get('target_agent', '-'),
            'signal_id': obj.get('signal_id', '-'),
            'type': obj.get('type', 'UNLOCK'),
            'task_or_phase_id': obj.get('task_or_phase_id') or obj.get('task', '-'),
            'dispatch_file': obj.get('dispatch_file') or obj.get('dispatch_payload', '-'),
        }
    except json.JSONDecodeError:
        return {
            'target_agent': '-',
            'signal_id': '-',
            'type': 'INVALID',
            'task_or_phase_id': '-',
            'dispatch_file': '-',
        }


def validate_dispatch_path(dispatch_file: str) -> bool:
    """Validate dispatch file path — block directory traversal."""
    if not dispatch_file or dispatch_file == '-':
        return True
    if '..' in dispatch_file:
        return False
    return True


def write_ack(completion_dir: Path, signal_id: str, agent: str, task_id: str) -> Path:
    ack_content = f"""# SIGNAL ACK

- **signal_id**: {signal_id}
- **agent**: {agent}
- **task_id**: {task_id}
- **status**: SIGNAL_ID_EXECUTED
- **timestamp**: {ts()}

This signal was consumed and executed by the agent.
"""
    ack_path = completion_dir / f"{signal_id}_ack.md"
    ack_path.write_text(ack_content, encoding='utf-8')
    return ack_path


def write_completion(completion_dir: Path, signal_id: str, agent: str, task_id: str, result: str) -> Path:
    completion_content = f"""# TASK COMPLETION

- **signal_id**: {signal_id}
- **agent**: {agent}
- **task_id**: {task_id}
- **result**: {result}
- **timestamp**: {ts()}

## Completion Proof

Task executed successfully. All deliverables completed.
"""
    completion_path = completion_dir / f"{signal_id}_completion.md"
    completion_path.write_text(completion_content, encoding='utf-8')
    return completion_path


def execute_dispatch(dispatch_file: str, signal_id: str, agent: str, task_id: str) -> str:
    """Execute the dispatch task.

    This is the integration point — replace this with your model's inference.
    """
    log(f"Executing dispatch: {dispatch_file}")
    # TODO: Integrate your model's inference here
    time.sleep(0.1)
    return "SUCCESS"


def process_signal(signal_data: dict, agent: str, line_num: int, cursor_path: Path, completions_dir: Path) -> tuple[bool, bool]:
    """Process a single signal. Returns (processed, should_advance_cursor)."""
    signal_id = signal_data['signal_id']
    target_agent = signal_data['target_agent']
    task_id = signal_data['task_or_phase_id']
    dispatch_file = signal_data['dispatch_file']

    # Filter by target agent (case-insensitive)
    if target_agent.lower() != agent.lower():
        log(f"Line {line_num}: signal for '{target_agent}', skipping (we are '{agent}')")
        return False, True

    if not signal_id or signal_id == '-':
        log(f"Line {line_num}: no signal_id, skipping")
        return False, True

    log_signal(f"signal={signal_id} type={signal_data['type']} task={task_id}")

    # Validate dispatch path
    if dispatch_file and dispatch_file != '-':
        if not validate_dispatch_path(dispatch_file):
            log_blocked(f"BLOCKED: dispatch_file path validation failed: {dispatch_file}")
            return False, True

        if not Path(dispatch_file).exists():
            log_warn(f"Dispatch file not found: {dispatch_file}")

    # Show dispatch preview
    if dispatch_file and dispatch_file != '-' and Path(dispatch_file).exists():
        try:
            preview = Path(dispatch_file).read_text(encoding='utf-8').split('\n')[:8]
            for line in preview:
                print(f"{C_CYAN}    ▸ {C_RESET}{line}")
        except IOError:
            pass

    # Execute the dispatch
    try:
        result = execute_dispatch(dispatch_file, signal_id, agent, task_id)

        if result == "SUCCESS":
            ack_path = write_ack(completions_dir, signal_id, agent, task_id)
            log(f"ACK written: {ack_path.name}")

            completion_path = write_completion(completions_dir, signal_id, agent, task_id, result)
            log(f"Completion written: {completion_path.name}")

            return True, True
        else:
            log_blocked(f"Execution failed: {result}")
            return False, False

    except Exception as e:
        log_blocked(f"Execution error: {type(e).__name__}: {e}")
        return False, False


def hover_tick(agent: str, cursor_path: Path, signals_file: Path, completions_dir: Path) -> tuple[bool, int]:
    """Single hover tick — poll, process, return."""
    total_lines = count_lines(signals_file)
    last_line = read_cursor(cursor_path)

    # Handle signal file truncation
    if total_lines < last_line:
        log(f"Signals truncated (total={total_lines}, last={last_line}), resetting cursor to 0")
        last_line = 0
        write_cursor(cursor_path, 0)

    if total_lines <= last_line:
        return False, last_line

    processed_any = False
    new_cursor = last_line
    for line_num in range(last_line + 1, total_lines + 1):
        json_line = read_signal_line(signals_file, line_num)
        if not json_line:
            new_cursor = line_num
            continue

        signal_data = parse_signal(json_line)
        processed, should_advance = process_signal(signal_data, agent, line_num, cursor_path, completions_dir)

        if processed:
            processed_any = True

        if should_advance:
            new_cursor = line_num
            write_cursor(cursor_path, new_cursor)

    return processed_any, new_cursor


def main() -> int:
    args = parse_args()

    if args.health:
        try:
            health = check_agent_health(args.agent)
            print(json.dumps(health, indent=2))
            return 0 if health['pending_signals'] == 0 else 1
        except FileNotFoundError as e:
            print(f"{C_RED}ERROR: {e}{C_RESET}")
            return 1
        except Exception as e:
            print(f"{C_RED}ERROR: Health check failed: {type(e).__name__}: {e}{C_RESET}")
            return 1

    signals_file, cursors_dir, completions_dir, bus_root, agent_dir = resolve_bus(args.agent)

    if not agent_dir.exists():
        agents_root = Path(os.environ.get('AGENTS_ROOT', Path.home() / "Desktop" / "Vessel" / "agents"))
        print(f"{C_RED}ERROR: Agent '{args.agent}' not found at {agent_dir}{C_RESET}")
        print(f"{C_DIM}Set AGENTS_ROOT to your agents directory, or create: {agents_root / args.agent}{C_RESET}")
        return 1

    ensure_dirs(signals_file, cursors_dir, completions_dir)
    cursor_path = get_cursor_path(args.agent, cursors_dir)

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    if not args.once:
        print(HOVER_BANNER)
        print(f"{C_CYAN}    ◈ agent: {C_BGREEN}{args.agent:<8}{C_CYAN} ◈ poll: {C_BGREEN}{args.poll_sec}s{C_CYAN} ◈ pid: {C_DIM}0x{os.getpid():04x}{C_RESET}")
        print(f"{C_DIM}    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░{C_RESET}")
        print()
        log(f"bus={bus_root}")
        log(f"signals={signals_file}")
        log(f"cursor={cursor_path}")
        print()

    idle_cycles = 0

    while not _shutdown_requested:
        processed, cursor = hover_tick(args.agent, cursor_path, signals_file, completions_dir)

        if processed:
            idle_cycles = 0
        else:
            idle_cycles += 1
            total = count_lines(signals_file)

            if idle_cycles == 1 or idle_cycles % 6 == 0:
                log_idle(cursor, total, args.poll_sec, idle_cycles)

            if args.once:
                return 0

        if args.once:
            return 0

        time.sleep(args.poll_sec)

    log('hover shutting down gracefully...')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
