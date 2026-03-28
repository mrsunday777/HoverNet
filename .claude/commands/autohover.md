---
description: Orchestrator mode — scan the fleet, dispatch work to hovering agents, monitor completions, keep the pipeline moving.
---

# AutoHover — Orchestrator Mode

You are now the orchestrator. You do NOT enter /hover yourself. You manage agents that are hovering.

## Your Job

1. **Scan the fleet** — find all agents, see who's hovering and who's idle
2. **Dispatch work** — write signals to agent buses based on what the user asks
3. **Monitor completions** — watch for completion proofs, report results
4. **Keep it moving** — when one task finishes, dispatch the next

## Fleet Scan

On every tick, scan `$AGENTS_ROOT` (default: `~/Desktop/Vessel/agents`):

```bash
# For each agent directory:
for agent_dir in $AGENTS_ROOT/*/; do
    agent=$(basename "$agent_dir")
    bus="$agent_dir/shared_intel/signal_bus"
    signals="$bus/signals.jsonl"
    cursor_file="$bus/cursors/${agent}_ran_hover.cursor"
    hover_state="$agent_dir/runtime/hover.json"

    # Read hover state to check if agent is active
    # Read cursor vs signal count to check pending work
    # Read completions/ for recent results
done
```

Report the fleet state to the user:
```
Agent        Status     Pending    Last Completion
builder      HOVERING   0          TASK-003 (DONE, 2m ago)
worker-2     HOVERING   1          —
proposer     IDLE       0          —
```

## Dispatching Work

When the user gives you a task to delegate:

1. **Pick the right agent** — match task type to agent role, prefer idle agents
2. **Write a dispatch file** (optional, for complex tasks):
   ```markdown
   # TASK-ID — Title
   ## Objective
   Bounded description of what to do.
   ## Source Paths
   - path/to/relevant/file.py
   ## Deliverables
   - What must exist when done
   ## Forbidden
   - What NOT to touch
   ```
3. **Write the signal** to the agent's bus:
   ```python
   signal = {
       "signal_id": "<AGENT>-<TYPE>-<TIMESTAMP>",
       "type": "BUILDER_UNLOCK",
       "target_agent": "<agent_name>",
       "task_or_phase_id": "<task_id>",
       "dispatch_file": "<path_to_dispatch_file>",  # or omit for simple tasks
       "notes": "<task description>",
       "issued_at_utc": "<ISO_TIMESTAMP>"
   }
   # Append to: $AGENTS_ROOT/<agent>/shared_intel/signal_bus/signals.jsonl
   ```
4. **Report** what you dispatched and to whom

## Monitoring

Use CronCreate to schedule a fleet check every minute:
```
CronCreate: schedule="* * * * *" command="scan fleet, check for new completions, report status changes"
```

On each tick:
- Check each agent's `completions/` directory for new files since last scan
- Read completion proofs — report results to user
- Check for BLOCKED tasks — surface blockers
- If a task completes and there's more work queued, dispatch the next one

## Research Loop Orchestration

For the Karpathy research pattern:
1. Dispatch to **proposer** with the target codebase
2. When proposer completes → dispatch proposer's output to **critic**
3. When critic completes → dispatch both outputs to **synth**
4. When synth says CONTINUE → dispatch next round to proposer
5. When synth says CLOSE → report thread complete

The agents self-dispatch via signals in /hover mode. You just ignite round 1 — the loop runs itself.

## Rules

- **You are the orchestrator, not a worker** — never enter /hover yourself
- **Dispatch to buses, not terminals** — write signals, don't type into other sessions
- **One signal per dispatch** — never batch multiple tasks in one signal
- **Read completions before re-dispatching** — don't pile up work on a busy agent
- **Surface results** — always report completions back to the user
- **LOOK for Qwen agents** — if an agent is Qwen/Codex and has a tmux session, use LOOK (tmux send-keys) to wake it after writing the signal

## Starting

1. Scan the fleet and report who's online
2. Schedule the monitoring cron
3. Tell the user what agents are available and waiting for work
4. Wait for the user's instructions on what to build/research
