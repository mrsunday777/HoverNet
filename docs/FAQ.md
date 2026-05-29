# HoverNet v1.5 FAQ

## What is HoverNet v1.5?

HoverNet v1.5 is the free local loop kit. It gives you the filesystem contract
for agent coordination: manifests, signal buses, cursors, session files,
completion proofs, and Research/Council loop templates.

It is not the managed product surface or hosted runtime control plane.

## Which repo should I use?

Use the canonical repo:

```text
https://github.com/mrsunday777/HoverNet
```

The `v1.5.0` release is the public loop-kit release.

## Do I need hosted infrastructure?

No. v1.5 runs locally. Runtime state is created inside your chosen workspace
under `.hovernet/`.

## Why are there Research and Council loops?

Research is for proposal, critique, and synthesis. Council is for independent
analysis, blind peer review, and final verdict. These are the two free canonical
loops in v1.5.

## What is Tap vs Monitor?

Tap is explicit terminal wake transport. Use it when agents run in terminals or
mixed SDK harnesses.

Monitor is scanner/watch transport. Use it when your harness can keep moving
from durable background observation.

The loop contract is the same idea in both cases: signals enter the bus, agents
read through cursors, work lands as artifacts, and completion proof closes the
step.

## Why does terminal scroll sometimes type into the agent instead of scrolling?

If you host agents in tmux, enable mouse mode on the tmux server:

```bash
tmux set -g mouse on
```

For a named socket:

```bash
tmux -L <socket> set-option -g mouse on
```

Without this, trackpad scroll may be forwarded into the agent input box.

## Where do completions go?

`completion_write` writes proof files under:

```text
<workspace>/.hovernet/sessions/<loop_name>/completions/
```

Completion artifacts are part of the contract. Do not advance a loop step
without an artifact or completion proof for the work consumed.

## Can signals contain large payloads?

No. `signal_send` has a 64 KB limit. Put large context in a file and pass a path
or contract reference in the signal payload.

## Are credentials or private runtime files included?

No. The release is sanitized. It does not ship managed product code, live buses,
cursor state, hosted runtime hooks, cloud storage wiring, or model credentials.

## How do I check the install?

After installing:

```bash
python -m unittest discover -s tests
python examples/basic-loop/run_basic_loop.py
```

Both commands should complete without writing outside temporary workspaces.
