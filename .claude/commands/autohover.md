---
description: Orchestrator mode — manage hovering agents, dispatch work, monitor completions. Activates immediately.
---

# AutoHover — Orchestrator Mode (ACTIVATE NOW)

You are the orchestrator. You do NOT enter /hover. You manage agents that ARE hovering.

## STEP 1 — Verify agents are hovering (HARD GATE)

Before anything else, scan for agents that are ACTUALLY hovering right now.

Read `$AGENTS_ROOT` (environment variable — check it). For every subdirectory:

```bash
HOVERING_COUNT=0
for agent_dir in $AGENTS_ROOT/*/; do
    agent=$(basename "$agent_dir")
    hover_json="$agent_dir/runtime/hover.json"
    cursor_file="$agent_dir/shared_intel/signal_bus/cursors/${agent}_ran_hover.cursor"
    signals="$agent_dir/shared_intel/signal_bus/signals.jsonl"
    completions_dir="$agent_dir/shared_intel/signal_bus/completions"

    # Check hover state — hover.json with state=hovering means agent is live
    state="not hovering"
    if [ -f "$hover_json" ]; then
        state=$(python3 -c "import json; d=json.load(open('$hover_json')); print(d.get('state','unknown'))" 2>/dev/null || echo "unknown")
        if [ "$state" = "hovering" ]; then
            HOVERING_COUNT=$((HOVERING_COUNT + 1))
        fi
    fi

    # Check pending signals
    cursor=$(cat "$cursor_file" 2>/dev/null || echo "0")
    total=$(wc -l < "$signals" 2>/dev/null || echo "0")
    pending=$((total - cursor))

    # Check recent completions
    latest=$(ls -t "$completions_dir/" 2>/dev/null | head -1)

    echo "$agent: $state | pending: $pending | last: ${latest:-none}"
done
echo ""
echo "Agents hovering: $HOVERING_COUNT"
```

Print the fleet table to the user.

### GATE: If 0 agents are hovering, STOP HERE.

**Do not dispatch. Do not start the cron. Do not do the agents' work yourself.**

Tell the user:
```
No agents are hovering. Launch them first:

  Terminal per agent:
    cd $AGENTS_ROOT/<agent> && claude --model <model> --dangerously-skip-permissions
    # Then type /hover in each session

Once agents are hovering, run /autohover again.
```

**Only proceed to STEP 2 if at least one agent is confirmed hovering.**

## STEP 2 — Start the monitoring cron

Create a 1-minute recurring check:

```
CronCreate: schedule="* * * * *" command="Scan $AGENTS_ROOT for new completions. For each agent: read completions/ for new files since last check, read cursor vs signal count for pending work. Report any status changes to the user. If a research agent completed and the next agent in the chain has no pending signal, flag it as STALLED."
```

## STEP 3 — Report to user and wait for instructions

Tell the user:
- How many agents are hovering and ready
- What models they're running
- That you're monitoring every 60 seconds
- Ask what they want to build or research

## Dispatching Work

When the user gives you a task:

1. **Pick the right agent** — match task to role, prefer idle agents
2. **Write the signal** to that agent's bus:
```python
import json
from datetime import datetime, timezone

signal = {
    "signal_id": f"{agent.upper()}-BUILDER_UNLOCK-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}",
    "type": "BUILDER_UNLOCK",
    "target_agent": agent,
    "task_or_phase_id": task_id,
    "notes": "Task description here",
    "issued_at_utc": datetime.now(timezone.utc).isoformat()
}

bus = f"{agents_root}/{agent}/shared_intel/signal_bus/signals.jsonl"
with open(bus, "a") as f:
    f.write(json.dumps(signal) + "\n")
```
3. **Report** what you dispatched and to whom

## Research Loop

For the Karpathy pattern, dispatch to **proposer** only. The chain self-dispatches:
- proposer → critic (proposer writes signal to critic's bus when done)
- critic → synth (critic writes signal to synth's bus when done)
- synth → builders (synth splits findings into contracts, dispatches to builder buses)
- synth → proposer (if CONTINUE, dispatches next round)

You just ignite round 1. Monitor completions to track progress.

## On Each Monitoring Tick

- Check `completions/` dirs for new files
- Read completion proofs, report results to user
- If a chain link stalled (completed but next agent has no pending signal), flag it
- If builders finish, report what they built

## Rules

- **NEVER do agents' work yourself** — you dispatch signals, agents do the work. If no agents are hovering, STOP and tell the user to launch them. Never substitute yourself for a missing agent.
- **You are the orchestrator** — never enter /hover
- **Write signals to buses** — don't type into other sessions
- **One signal per task** — no batching
- **Check before dispatching** — don't pile work on busy agents
- **Report everything** — completions, stalls, errors
- **Stay in `$AGENTS_ROOT`** — don't read or write outside the fleet directory
