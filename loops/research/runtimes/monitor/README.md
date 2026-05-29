# Research Monitor Runtime

Monitor runtime lets each agent keep a scanner armed for new work.

## Contract

1. Scanner watches the bus, inbox, and active thread artifacts.
2. On work, scanner emits the next actionable event.
3. Agent processes exactly one task.
4. Agent writes proof before cursor advance.
5. Agent re-arms the monitor after completion.

## When To Use

Use monitor when the harness supports persistent background watch tasks and the
loop benefits from quiet self-sustain.

## Rule

Monitor detects work. It does not replace the role's reasoning or proof.
