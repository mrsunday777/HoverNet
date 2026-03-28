# Qwen Hover — LOOK-Based Cron Pattern

## Why LOOK-Based

Qwen (and Codex) agents lack the sustained reasoning depth to self-poll. A Claude Code agent can be told "check your bus every tick" and it'll maintain that behavior indefinitely. Qwen finishes a task and sits idle — it won't self-initiate the next bus check.

**This is not a bug. It's a model capability boundary.**

The solution: the cron tick doesn't just check the bus — it actively **LOOKs into the tmux session** and tells the agent to process. The agent executes perfectly when prompted. It just can't prompt itself.

**Without LOOK, Qwen agents are dead on arrival.** They will complete one task and sit there forever.

## The Pattern

```
cron/launchd (every 60s)
    → hover_tick.sh builder --model qwen
        → Read signals.jsonl line count
        → Read cursor value
        → If pending > 0:
            → Find agent's tmux session
            → tmux send-keys: "You have N pending signal(s). Run /hover to process them."
            → tmux send-keys: Enter
        → If pending == 0:
            → Silent exit
```

## Key Difference from Claude Agents

| | Claude Code | Qwen / Codex |
|--|------------|--------------|
| **Self-poll** | Yes — maintains hover loop between ticks | No — finishes task, sits idle |
| **Cron role** | Safety net / heartbeat | Active wake mechanism (LOOK) |
| **LOOK needed** | No (but doesn't hurt) | Yes — required for every signal |
| **Signal bus** | Same | Same |
| **Cursor** | Same | Same |
| **Proofs** | Same | Same |

The bus layer is 100% model-agnostic. Only the wake mechanism differs.

## Qwen LOOK Behavior Note

Qwen Coder CLI does **not** consume injected text mid-response like Claude Code does. It buffers the full LOOK message and only submits it after the agent's current output stops. This means:

- LOOK during idle: works immediately
- LOOK during response: queues, submits after response completes
- No race conditions from overlapping LOOKs

## Files

| File | Purpose |
|------|---------|
| `hover_tick.sh` | Canonical tick — checks bus, finds session, LOOKs |
| `cron_install.sh` | Manage launchd/crontab entries |

## Install

```bash
# Using crontab (Linux / macOS)
crontab -e
# Add:  * * * * * /path/to/HoverNet/QwenAgents/cron/hover_tick.sh builder --model qwen

# Using LaunchAgent (macOS — preferred, avoids FDA restrictions)
bash cron_install.sh
```

## LaunchAgent (macOS)

macOS cron has FDA (Full Disk Access) restrictions on `~/Desktop/` paths. LaunchAgents run as your user with full permissions.

```bash
# Plist location
~/Library/LaunchAgents/com.hovernet.hover-tick-builder.plist

# Manage
launchctl load ~/Library/LaunchAgents/com.hovernet.hover-tick-builder.plist
launchctl unload ~/Library/LaunchAgents/com.hovernet.hover-tick-builder.plist
launchctl list | grep hovernet
```

## Verification

After installing the cron tick:
1. Dispatch a signal: `python3 examples/dispatch_example.py --agent builder --task "Hello world"`
2. Wait up to 60 seconds for the cron tick
3. Check that a completion appeared: `ls ~/Desktop/Vessel/agents/builder/shared_intel/signal_bus/completions/`
4. Full loop: dispatch → cron tick → LOOK → agent processes → proof → idle
