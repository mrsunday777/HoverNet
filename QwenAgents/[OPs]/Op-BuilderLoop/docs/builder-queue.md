# Builder Queue

The builder queue is the dispatch path for builder work.

## Path

1. Write a task contract into `queues/builders/tasks/`
2. Add it to `QUEUE.md` as `UNLOCKED`
3. Write a signal to the builder's bus with the dispatch file
4. The builder's hover picks it up
5. The builder writes completion proof
6. Mark the task `DONE` in `QUEUE.md`

## Canonical Truth

- Queue state: `queues/builders/QUEUE.md`
- Active assignments: `queues/builders/ACTIVE_TASKS.json`
- Worker pool: `queues/builders/WORKERS.json`
- Dispatch artifacts: `dispatches/builders/`

## Contract Rule

Every task contract must contain:
- `task_id`
- `title`
- `objective`

Optional fields:
- `depends_on`
- `instructions`
- `source_paths`
- `deliverables`
- `forbidden`
- `preferred_agent`
- `allowed_agents`

`depends_on` controls readiness:
- Unresolved deps → `LOCKED`
- All deps `DONE` → `UNLOCKED`

## Completion Rule

A task is `DONE` only when one of these is true:
- A completion artifact exists for the signal ID
- An ACK artifact exists with explicit `ALREADY_FIXED` status
- The signal bus contains a terminal EXECUTED record for the signal ID

`_ack.md` by itself is not enough.
