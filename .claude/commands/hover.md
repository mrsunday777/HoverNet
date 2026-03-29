---
description: Enter the continuous hover loop — poll your signal bus, consume one task, write proof, return to idle, repeat forever.
---

# Hover

You are entering hover mode. This is a continuous polling loop, not a one-shot task.

## STEP 0 — Announce yourself IMMEDIATELY

Before doing anything else, write your hover state file so the orchestrator knows you're alive:

```bash
HOVER_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat > runtime/hover.json << HOVER
{
  "state": "hovering",
  "started_at_utc": "$HOVER_TS",
  "cursor_value": 0,
  "bus_count": 0,
  "last_result": "just_started",
  "last_tick_utc": "$HOVER_TS",
  "tasks_completed": 0
}
HOVER
```

This file is how the orchestrator detects you. Write it FIRST, before checking the bus.

## The Loop

1. **Resolve** your signal bus: `shared_intel/signal_bus/signals.jsonl`
2. **Read** your cursor: `shared_intel/signal_bus/cursors/<your_name>_ran_hover.cursor`
3. **Check** if signals.jsonl has lines past your cursor position
4. **If no new signals:** report idle, wait for next tick
5. **If signal found:**
   a. Read the signal at cursor + 1
   b. Verify `target_agent` matches you (skip if it doesn't, advance cursor)
   c. Read the task from `dispatch_file` or `task` field
   d. Write an ACK to `completions/<signal_id>_ack.md`
   e. Execute the bounded work described
   f. Write completion proof to `completions/<signal_id>_completion.md`
   g. Advance cursor to cursor + 1
6. **Return to idle**
7. **Repeat** — use CronCreate to schedule this loop at `* * * * *` (every minute)

## Completion Proof Format

```markdown
---
signal_id: <SIGNAL_ID>
status: DONE
completed_at_utc: <ISO_TIMESTAMP>
files_changed:
  - <list of files>
---

## What was done
<description>

## Verification
<how you verified>
```

If you cannot complete the task, write `status: BLOCKED` with an explanation.

## Critical Rules

- **One signal per tick** — never batch
- **Proof before cursor** — write completion BEFORE advancing cursor. If you crash between, the work is recoverable.
- **Bounded work only** — if a task is unbounded, write BLOCKED
- **Append-only bus** — never edit signals.jsonl
- **Your cursor only** — only read/write your own cursor file

## State File

Write your hover state to `runtime/hover.json` after each tick:

```json
{
  "cursor_value": 5,
  "bus_count": 7,
  "last_result": "executed",
  "last_tick_utc": "2026-03-28T10:00:00Z",
  "last_signal_id": "TASK-005-UNLOCK-20260328",
  "signals_file": "shared_intel/signal_bus/signals.jsonl",
  "tasks_completed": 3
}
```

This powers the statusline display. Without it, your status shows "(no hover state)".

## Starting the Loop

Use CronCreate to schedule the tick:
```
CronCreate: schedule="* * * * *" command="check signal bus and process next signal"
```

Report that you are now hovering. Then wait for the first tick.
