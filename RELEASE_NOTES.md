# HoverNet v1.5 Release Notes

HoverNet v1.5 is the final free self-sustained local release before HoverNet v2
moves into the managed product line.

## What This Release Is

This release packages the public local loop primitive:

- manifest-backed agent registration
- append-only JSONL signal buses
- cursor-based reads and acks
- completion artifacts as proof of work
- scoped session file helpers
- peer artifact reads
- decision logs
- sanitized Research and Council loop templates
- proven Research tap contract with proposer, critic, and synthesizer proof
- proven Council tap contract with canonical R1/R2 round labels
- tap and monitor runtime adapter docs

It is designed for developers who want to run local agent loops on their own
machine and manage their own terminal/runtime process.

## What This Release Is Not

This release does not include:

- app source
- hosted agent runtime
- cloud persistence or sync
- production telemetry bridges
- managed control-plane APIs
- account pairing, billing, or beta onboarding
- production provisioning flows

Those pieces belong to the private HoverNet product path.

## Included Loops

- Research: proposer, critic, synthesizer, with proposer/critic/synthesizer proof
- Council: chairman and advisors, with canonical R1/R2 completion proof

Both loops include two runtime adapter guides:

- tap: explicit terminal wake transport
- monitor: scanner/watch transport

## Install

Requires Python 3.10 or newer.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## First Run

```python
from hovertools import public_server

public_server.hover_init(
    root="/path/to/workspace",
    loop_name="demo",
    agents=["alice", "bob"],
)
```

Then use `signal_send`, `bus_read`, `bus_ack`, and `completion_write` to run a
local filesystem loop.
