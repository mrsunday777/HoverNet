#!/usr/bin/env python3
"""Watch for new completion proofs across the fleet.

Usage:
    python3 watch_completions.py              # Watch all agents
    python3 watch_completions.py --agent cp0  # Watch single agent
    python3 watch_completions.py --once       # Print current, don't watch
"""
import argparse
import os
import time
from pathlib import Path

AGENTS_ROOT = Path(os.environ.get('AGENTS_ROOT', Path.home() / "Desktop/Vessel/agents"))


def get_completions(agent_dir: Path) -> list:
    """Get all completion files sorted by mtime."""
    completions_dir = agent_dir / "shared_intel" / "signal_bus" / "completions"
    if not completions_dir.exists():
        return []
    files = sorted(completions_dir.glob("*_completion.md"), key=lambda f: f.stat().st_mtime)
    return files


def print_completion(path: Path, agent: str):
    """Print a completion file summary."""
    content = path.read_text().strip()
    # Extract signal_id from frontmatter
    signal_id = "unknown"
    status = "unknown"
    for line in content.split("\n"):
        if line.startswith("signal_id:"):
            signal_id = line.split(":", 1)[1].strip()
        if line.startswith("status:"):
            status = line.split(":", 1)[1].strip()

    mtime = time.strftime("%H:%M:%S", time.localtime(path.stat().st_mtime))
    print(f"[{mtime}] {agent:<12} {status:<8} {signal_id}")


def main():
    parser = argparse.ArgumentParser(description="Watch for completion proofs")
    parser.add_argument("--agent", help="Watch a single agent")
    parser.add_argument("--once", action="store_true", help="Print current completions and exit")
    args = parser.parse_args()

    if args.agent:
        agent_dirs = [(args.agent, AGENTS_ROOT / args.agent)]
    else:
        agent_dirs = sorted([
            (d.name, d) for d in AGENTS_ROOT.iterdir()
            if d.is_dir() and (d / "shared_intel" / "signal_bus" / "completions").exists()
        ])

    if not agent_dirs:
        print(f"No agents with completions found at {AGENTS_ROOT}")
        return

    # Track seen files
    seen = set()
    for agent, agent_dir in agent_dirs:
        for f in get_completions(agent_dir):
            seen.add(f)
            if args.once:
                print_completion(f, agent)

    if args.once:
        if not seen:
            print("No completions yet.")
        return

    print(f"Watching {len(agent_dirs)} agent(s) for new completions... (Ctrl+C to stop)")
    print(f"{'Time':<10} {'Agent':<12} {'Status':<8} {'Signal ID'}")
    print("-" * 60)

    # Print existing
    for agent, agent_dir in agent_dirs:
        for f in get_completions(agent_dir):
            print_completion(f, agent)

    # Poll for new
    try:
        while True:
            time.sleep(2)
            for agent, agent_dir in agent_dirs:
                for f in get_completions(agent_dir):
                    if f not in seen:
                        seen.add(f)
                        print_completion(f, agent)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
