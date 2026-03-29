# HoverNet Rules — Non-Negotiables

**These are not suggestions. Violating any of these will break your fleet.**

Every rule here exists because we broke it in production and paid the price.

***

## 1. Proof Before Cursor

Write the completion proof **before** advancing the cursor. Never the other way around.

```text
CORRECT:  execute → write proof → advance cursor
BROKEN:   execute → advance cursor → write proof
```

**Why:** If your agent crashes between cursor advance and proof write, the signal is marked consumed but no proof exists. The work is lost. No one knows if it happened. The orchestrator thinks it's done. It isn't.

***

## 2. One Signal Per Tick

Each hover tick consumes exactly **one** signal. Not two. Not "all pending."

```text
CORRECT:  read cursor → consume signal N+1 → prove → advance → idle
BROKEN:   read cursor → consume signals N+1 through N+5 → prove all → advance
```

**Why:** Batching breaks atomicity. If signal 3 of 5 fails, what's your cursor? You can't partially advance. You either lose work or double-execute. One signal, one tick, one proof.

***

## 3. Append-Only Signal Log

`signals.jsonl` is **append-only**. Never edit, truncate, reorder, or delete lines.

```text
CORRECT:  echo '{"signal_id": "..."}' >> signals.jsonl
BROKEN:   Editing line 47 to fix a typo
BROKEN:   Deleting old signals to "clean up"
BROKEN:   Rewriting the file to remove duplicates
```

**Why:** Cursors are line numbers. If you delete line 10, every cursor pointing to line 11+ is now off by one. Every agent will skip a signal or re-execute one. The entire bus becomes untrustworthy.

**If a signal is bad:** dispatch a new corrective signal. Don't edit the old one.

***

## 4. Unique Signal IDs

Every signal must have a globally unique `signal_id`. Never reuse one.

```text
CORRECT:  signal_id: "PROPOSER-RESEARCH-20260328T094517"
BROKEN:   signal_id: "task-1" (used for 50 different tasks)
BROKEN:   Resending a failed signal with the same ID
```

**Why:** Completion proofs are keyed by signal ID (`<signal_id>_completion.md`). Reusing an ID overwrites the previous proof. You lose evidence of completed work and can't distinguish between the original and the retry.

**If you need to retry:** create a new signal with a new ID. Reference the original in the `notes` field.

***

## 5. Fresh IDs on Resend

When retrying or resending work, always generate a **fresh signal ID**.

```text
CORRECT:  "RETRY-TASK42-20260328T100000" (references original in notes)
BROKEN:   Copy-pasting the original signal back into the bus
```

**Why:** Same as Rule 4. Old completions get overwritten, cursor math breaks if the original was already consumed, and you can't tell retries from originals in the completion log.

***

## 6. Cursor Starts at 0

A new agent's cursor file must contain `0`, not `1`, not empty, not missing.

```text
CORRECT:  echo "0" > cursors/agent_ran_hover.cursor
BROKEN:   Empty file (read as "" → crash or NaN)
BROKEN:   Missing file (crash on first tick)
BROKEN:   Starting at 1 (skips the first signal)
```

**Why:** The cursor represents "last consumed line." 0 means "nothing consumed yet." The first tick reads line 1 (cursor + 1). Starting at 1 skips the first signal silently.

***

## 7. Bounded Work Only

Every task dispatched via signal must be **bounded** — finite, completable, provable.

```text
CORRECT:  "Fix the hardcoded path in signal_retry.py line 42"
BROKEN:   "Refactor the entire codebase"
BROKEN:   "Monitor this service indefinitely"
BROKEN:   "Keep improving until it's perfect"
```

**Why:** The hover loop is: consume → execute → prove → return. If the work never finishes, the agent never returns to hover, the cursor never advances, and the bus stalls. Every signal behind it is blocked forever.

**Rule of thumb:** If you can't write a completion proof for it, it's not bounded.

***

## 8. One Writer Per Bus

Each `signals.jsonl` should have **one orchestrator** writing to it. Multiple writers require coordination.

```text
CORRECT:  The orchestrator dispatches all signals to all agents
BROKEN:   Three different scripts appending to the same signals.jsonl without locks
```

**Why:** Concurrent appends to the same file can interleave JSON lines, producing corrupt entries. If two writes land on the same line, both signals are destroyed. Use file locks or a single dispatch point.

**If you need multiple dispatchers:** use `flock` or funnel all dispatches through one script.

***

## 9. Never Edit Cursor Files Externally (Unless Recovery)

Cursor files are managed by the hover loop. Don't manually edit them during normal operation.

```text
CORRECT:  Let the hover tick advance the cursor after writing proof
BROKEN:   "Let me just set the cursor to 50 to skip those old signals"
```

**Why:** Skipping signals means skipping work. If you fast-forward, those signals are silently dropped — no proof, no record, no completion. If you rewind, signals get double-executed.

**Recovery exception:** If an agent is genuinely stuck, you can reset the cursor — but document it and accept that skipped signals are lost.

***

## 10. Completions Are Sacred

Never delete completion files. They are the proof-of-work record.

```text
CORRECT:  Archive old completions if disk is tight
BROKEN:   rm completions/*.md to "clean up"
```

**Why:** Completions are how you audit what happened. They're how you detect if a signal was actually executed. They're how you debug when something goes wrong three days later. Delete them and you're flying blind.

***

## Quick Reference

| Rule | One-liner                         |
| ---- | --------------------------------- |
| 1    | Proof before cursor advance       |
| 2    | One signal per tick               |
| 3    | Never edit signals.jsonl          |
| 4    | Signal IDs must be unique         |
| 5    | Fresh ID on every retry           |
| 6    | Cursor starts at 0                |
| 7    | Bounded work only                 |
| 8    | One writer per bus                |
| 9    | Don't touch cursor files manually |
| 10   | Never delete completions          |

***

**If you follow these 10 rules, HoverNet will run indefinitely without intervention. Break any one of them and you'll spend your afternoon debugging ghost signals.**

⠀