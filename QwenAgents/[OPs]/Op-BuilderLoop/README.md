# Op-BuilderLoop

Queue-based builder dispatch harness. Sits on top of the hover primitive — agents pull work from a queue, execute bounded tasks, write completion proof, and return to idle.

## Structure

```
Op-BuilderLoop/
  docs/               — harness doctrine, queue spec, operator runbook
  queues/builders/    — queue state, worker pool, task contracts
    tasks/            — individual task specs (one file per task)
    QUEUE.md          — queue state table (UNLOCKED/LOCKED/IN_PROGRESS/DONE/FAILED)
    WORKERS.json      — active worker pool
    ACTIVE_TASKS.json — current worker assignments
  dispatches/builders/ — dispatch artifacts (generated per signal)
  shared_intel/        — signal bus for this op slice
```

## How It Works

1. **Submit a task** — drop a contract into `queues/builders/tasks/`
2. **Queue it** — add a row to `QUEUE.md` as `UNLOCKED`
3. **Dispatch** — write a signal to the builder's bus with the dispatch file path
4. **Builder picks up** — hover tick reads signal, reads dispatch, executes bounded work
5. **Completion proof** — builder writes `{signal_id}_completion.md`
6. **Autoprogress** — mark task `DONE` in `QUEUE.md`

## Task Contract Format

Every task in `queues/builders/tasks/` must contain:

```markdown
# TASK-ID — Title

## Objective
What exactly needs to be done. Bounded scope.

## Source Paths
- path/to/file.py

## Deliverables
- What must exist when done

## Forbidden
- What the builder must NOT touch
```

## Worker Pool

Workers are task-agnostic by default. Specialization is opt-in at the task level via `preferred_agent` or `allowed_agents` — not hardcoded into the queue.

`WORKERS.json` tracks which agents are available:
```json
{
  "workers": ["builder", "worker-2", "worker-3"],
  "offline": []
}
```

## Completion Detection

A task is `DONE` when **any** of these are true:
1. `{signal_id}_completion.md` exists in `completions/`
2. `{signal_id}_ack.md` exists with explicit `ALREADY_FIXED` status
3. An `EXECUTED` entry in `signals.jsonl` matches the signal ID

ACK alone is not enough. Completion proof is required.

## Dispatch Shape

Every dispatch must answer:
1. What is the bounded objective?
2. What source files or paths matter?
3. What outputs must exist on completion?
4. What is explicitly forbidden?

If that's not clear in the dispatch file, the signal is bad.

## Queue States

| State | Meaning |
|-------|---------|
| `UNLOCKED` | Ready for a builder to pick up |
| `LOCKED` | Has unresolved `depends_on` — will unlock when deps are `DONE` |
| `IN_PROGRESS` | Dispatched to a builder, awaiting completion |
| `DONE` | Completion proof verified |
| `FAILED` | Exceeded retry limit (3 attempts) — requires manual reset |
