# Operator Runbook

## Dispatch a Task

1. Write a task contract to `queues/builders/tasks/YOUR-TASK-ID.md`
2. Add a row to `queues/builders/QUEUE.md` with state `UNLOCKED`
3. Write a signal to the builder's bus:

```bash
python3 examples/dispatch_example.py --agent builder --task "Your task description"
```

Or write the signal directly:

```python
import json
from datetime import datetime, timezone

signal = {
    "signal_id": "BUILDER-YOUR-TASK-ID-UNLOCK-20260328",
    "type": "BUILDER_UNLOCK",
    "target_agent": "builder",
    "task_or_phase_id": "YOUR-TASK-ID",
    "dispatch_file": "queues/builders/tasks/YOUR-TASK-ID.md",
    "issued_at_utc": datetime.now(timezone.utc).isoformat()
}

bus_path = "path/to/agents/builder/shared_intel/signal_bus/signals.jsonl"
with open(bus_path, "a") as f:
    f.write(json.dumps(signal) + "\n")
```

## Check Queue Status

```bash
cat queues/builders/QUEUE.md
cat queues/builders/ACTIVE_TASKS.json
```

## Check Completions

```bash
ls shared_intel/signal_bus/completions/
```

## Reset a Failed Task

1. Find the task in `QUEUE.md` with state `FAILED`
2. Fix the root cause (check completion files for error details)
3. Change state from `FAILED` to `UNLOCKED`
4. Clear attempt count in `task_attempts.json` if it exists

**Never reset without understanding why it failed.**

## Worker Management

```bash
# View active workers
cat queues/builders/WORKERS.json

# Add a worker
# Edit WORKERS.json, add agent name to "workers" array
```
