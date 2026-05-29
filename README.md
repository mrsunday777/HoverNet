# HoverNet v1.5

HoverNet v1.5 is the open-source local loop surface for HoverNet.

It gives agents a small filesystem contract:

- initialize a `.hovernet` workspace
- register agents in a manifest
- send JSONL signals to an agent bus
- read and ack pending signals with cursors
- write completion artifacts
- keep scoped session files and decision logs
- start from the free Research and Council loop templates with explicit proof
  contracts

This package is local-first. It does not run hosted agents, ship app code, manage
cloud storage, or provide a production control plane.

## Release Position

v1.5 is the final free self-sustained HoverNet release. It gives developers the
local loop primitive: run agents on your own machine, own the files, and manage
your own runtime.

HoverNet v2 moves into the managed product line: app-driven operation,
provisioning, persistent runtime, cross-device identity, and hosted/beta
infrastructure.

## Install

Requires Python 3.10 or newer.

```bash
python3.11 -m venv .venv  # any Python >= 3.10 is fine
. .venv/bin/activate
python -m pip install -e .
```

## MCP Server

```bash
hovertools
```

The `hovertools` command starts the public MCP server:

```text
hovertools.public_server:main
```

Example MCP config:

```text
examples/mcp/claude-code.json
```

## First Loop

1. Call `hover_init(root="/path/to/workspace", loop_name="demo", agents=["alice", "bob"])`.
2. Call `signal_send(...)` to append work to an agent bus.
3. Call `bus_read(...)` and `bus_ack(...)` from the receiving agent.
4. Call `completion_write(...)` when work is done.
5. Call `loop_watch_once(...)` or `hover-loop-watch --once --json` to detect the
   next monitor event.

See `docs/GETTING_STARTED.md` for a complete local walkthrough.
See `docs/PUBLIC_SURFACE.md` for the full contract.
See `docs/FAQ.md` for common install, runtime, and terminal-hosting questions.

## Canonical Free Loops

The package includes two sanitized loop templates:

- `loops/research` - proposal, critique, synthesis, with completion proof
- `loops/council` - independent analysis, blind peer review, verdict

Each loop ships two runtime adapters:

- `runtimes/tap` for terminal wake transport
- `runtimes/monitor` for scanner/watch transport

See `docs/RUNTIME_MATRIX.md` for the split.

## Project Hygiene

- Changelog: `CHANGELOG.md`
- Security policy: `SECURITY.md`
- Contribution guide: `CONTRIBUTING.md`
- Release checklist: `docs/RELEASE_CHECKLIST.md`
