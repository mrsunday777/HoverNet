# HoverNet User Guide

This is the shortest path to a working HoverNet fleet.

## What Runs What

- **Workers** run in hover mode with `/hover`
- **Orchestrator** runs in orchestrator mode with `/autohover`
- **Research bridge** runs via `scripts/queue_daemon.py` when you want the research loop to keep feeding builders

## Before You Start

Set up the fleet first:

```bash
git clone <repo-url> && cd HoverNet
bash setup.sh
```

Or use the agent-driven setup flow in `SETUP.md`.

You need:

- An agents root: `<AGENTS_ROOT>`
- One terminal per agent you want online
- A CLI agent installed (`claude`, `qwen-code`, `collaborator`, or equivalent)

## Start the Workers

Open one terminal per worker.

For a builder:

```bash
cd <AGENTS_ROOT>/builder
claude
```

For more builders:

```bash
cd <AGENTS_ROOT>/builder-2
claude
```

For research agents:

```bash
cd <AGENTS_ROOT>/proposer
claude
```

```bash
cd <AGENTS_ROOT>/critic
claude
```

```bash
cd <AGENTS_ROOT>/synth
claude
```

Once each worker session is open, type:

```text
/hover
```

That puts the worker into hover mode. It will watch its bus, consume one unread signal per tick, write proof, and return to idle.

## Start the Orchestrator

Open another terminal:

```bash
cd <AGENTS_ROOT>/orchestrator
claude
```

Then type:

```text
/autohover
```

The orchestrator does not do worker jobs. It scans the fleet, watches completions, and dispatches work to hovering agents.

## If You Are Using the Research Loop

Start the bridge from the HoverNet repo root:

```bash
cd <HOVERNET_DIR>
python3 scripts/queue_daemon.py --agents-root <AGENTS_ROOT> --interval 30
```

This is what keeps the research harness moving:

```text
proposer -> critic -> synth -> builders -> next proposer round
```

The loop keeps going until the harness reaches a state with no more work to push forward.

## Dispatch Work

For simple builder work:

```bash
cd <HOVERNET_DIR>
python3 examples/dispatch_example.py --agent builder --task "Fix the bug in config parsing"
```

For research, dispatch round 1 to the proposer and let the harness take it from there.

## How the Loop Behaves

- A worker picks up one unread signal
- It executes bounded work
- It writes completion proof
- It advances its cursor
- It returns to hover

That cycle repeats as long as new work exists.

## Quick Status Checks

```bash
cd <HOVERNET_DIR>
python3 examples/check_status.py
```

```bash
cd <HOVERNET_DIR>
python3 examples/watch_completions.py
```

## Stop Conditions

- If no agents are hovering, the orchestrator has nothing to dispatch to
- If the research bridge is not running, the research loop stops at synth
- If the harness has no more valid work to advance, the loop naturally settles

## The Simple Mental Model

```text
workers -> /hover
orchestrator -> /autohover
research harness -> queue_daemon.py
```

That is the whole thing.
