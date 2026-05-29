# Research Tap Runtime

Tap runtime wakes terminal-hosted agents explicitly.

## Contract

1. Append one signal to the target agent bus.
2. Wake the target terminal session.
3. Agent reads from its cursor.
4. Agent writes the round artifact.
5. Agent writes completion proof.
6. Agent advances cursor and acks the signal.

For a full Research round, tap must preserve this chain:

- proposer: `proposer.md` plus `proposer.complete`
- critic: `critic.md` plus `critic.complete`
- synthesizer: `consensus.md` plus `synthesizer.complete`

The synthesizer may close the thread only after the required artifacts and
completion markers exist.

## When To Use

Use tap when your model SDK or harness does not provide a durable monitor
primitive, or when you want the same loop to run across mixed agent runtimes.

## Terminal Host Tip

If you host agents inside tmux, enable mouse scroll on the tmux server before
attaching:

```bash
tmux set -g mouse on
# or, for a named socket:
tmux -L <socket> set-option -g mouse on
```

Without this, trackpad scroll can be forwarded into the agent input box instead
of scrolling terminal history.

## Rule

The bus signal is the source of truth. The terminal wake is only transport.
