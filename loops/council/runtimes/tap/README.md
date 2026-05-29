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

## Rule

Round barriers are real. Do not synthesize until required advisor artifacts,
completion markers, and canonical completion signals are present.
