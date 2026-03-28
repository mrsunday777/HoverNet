# Builder Harness

Builder hover is not a new hover primitive.

It is a harness layer above the frozen hover loop for a generic worker pool.

## Layering

Builder hover keeps the same four-way split:

1. **hover core**
   - fixed 1-minute tick
   - read canonical bus
   - consume one signal
   - return to idle

2. **bus resolver**
   - resolve each worker's canonical agent dir
   - use one bus, one cursor, one completions directory

3. **task interpreter**
   - worker-specific dispatch file
   - bounded objective
   - required outputs
   - completion summary

4. **governance**
   - no self-dispatch
   - no free-roaming scope expansion
   - no silent infra mutation unless the dispatch explicitly authorizes it

## Worker Pool

Workers are task-agnostic by default.

Specialization should be opt-in at the task level, not hardcoded into the base queue.

That means:
- do not hard-bind one worker to one job family
- do not encode role assumptions into the queue
- let explicit task constraints narrow assignment only when needed

The queue's active worker set lives in `queues/builders/WORKERS.json`.

## Canonical Dispatch Shape

Every worker dispatch should answer:

1. What is the bounded objective?
2. What source files or paths matter?
3. What outputs must exist on completion?
4. What is explicitly forbidden?

If that is not clear in the dispatch file, the signal is bad.

## Completion Detection

Two valid completion detection paths:

### Path 1: File-Based Completion

Write a completion artifact: `{signal_id}_completion.md` to the completions directory.

### Path 2: Bus-Based Completion (EXECUTED)

Append an EXECUTED entry to `signals.jsonl` with:
- `"type": "EXECUTED"` or `"status": "completed"`
- `"signal_id"` or `"original_signal_id"` matching the original dispatch signal

Either style satisfies the completion check. Builders should use whichever is natural for their harness. Do not require both.
