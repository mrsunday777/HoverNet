# Council Tap Runtime

Tap runtime gives the chairman explicit control over round dispatch.

## Contract

1. Chairman appends one round signal per advisor.
2. Chairman wakes each terminal-hosted advisor.
3. Advisor reads its bus, writes its artifact, and acks.
4. Advisor signals completion.
5. Chairman waits for all required completions before moving on.

Completion signals use canonical round labels:

- `round: "R1"` after the independent-analysis round
- `round: "R2"` after the peer-review round

If a runtime also needs numeric helper metadata, keep it separate from the
semantic `round` field.

## When To Use

Use tap when advisors run in mixed SDK terminals or when the loop needs explicit
round barriers.

## Terminal Host Tip

If you host advisors inside tmux, enable mouse scroll on the tmux server before
attaching:

```bash
tmux set -g mouse on
# or, for a named socket:
tmux -L <socket> set-option -g mouse on
```

Without this, trackpad scroll can be forwarded into the agent input box instead
of scrolling terminal history.

## Rule

Round barriers are real. Do not synthesize until required advisor artifacts,
completion markers, and canonical completion signals are present.
