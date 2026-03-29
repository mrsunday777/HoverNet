# HoverNet

Fleet orchestration for AI agents across terminal sessions.

HoverNet turns isolated AI agent sessions into a coordinated fleet. Each agent gets a signal bus, a cursor, and a hover loop. An orchestrator dispatches work, agents execute bounded tasks, write proof, and return to idle. The system self-heals when things break.

**Model-agnostic.** The same architecture runs Claude, Qwen, Codex, or any CLI-based agent. The signal bus doesn't care what model is behind the terminal.

---

## Prerequisites

- **Python 3** — for example scripts and Qwen runtime
- **tmux** — for launcher scripts (`brew install tmux` / `apt install tmux`)
- **jq** — for statusline display (`brew install jq` / `apt install jq`)
- **A CLI agent** — at least one of:
  - [Claude Code](https://claude.ai/claude-code) — `npm install -g @anthropic-ai/claude-code`
  - [Qwen Code / Collaborator](https://github.com/nicepkg/gpt-runner) — Qwen Coder CLI
  - Any CLI-based agent that can read/write files

---

## The 3 Invariants

Everything in HoverNet is built on exactly 3 rules. See [foundation.md](foundation.md) for the full document. See [RULES.md](RULES.md) for the 10 non-negotiables that will break your fleet if violated.

**1. Continuous Polling**
- Hover is cron-backed
- The agent returns to idle after every tick
- No manual re-priming between tasks

**2. Fresh Explicit Unlocks**
- Every task dispatch gets a fresh signal ID
- The signal is targeted to one consumer
- The signal type must match the consumer contract

**3. Execute, Prove, Return**
- Consume the unread signal
- Do the bounded work
- Write proof of what happened
- Advance the cursor
- Return to hover

---

## Quickstart

### Option A: Agent-Driven Setup (Recommended)
```bash
git clone <repo-url> && cd HoverNet
```
Then tell your Claude Code agent: **"Read SETUP.md and set up HoverNet."**

Your agent should provision the full starter fleet: `orchestrator`, `builder`, `proposer`, `critic`, and `synth`. It should also copy the slash commands (`/hover`, `/hoveroff`, `/autohover`) into each workspace, wire up statusline/aliases, and leave you ready to launch.

### Option B: Manual Setup
```bash
git clone <repo-url> && cd HoverNet
bash setup.sh
```

### Launch Agents
```bash
# Orchestrator
hovernet-orchestrator

# Builders (scale by opening more terminals)
hovernet-builder              # Default builder
hovernet-builder worker-2     # Named builder
hovernet-builder worker-3     # As many as you need

# Research loop (3 terminals)
hovernet-proposer
hovernet-critic
hovernet-synth
```

In the orchestrator session, type `/autohover`.
In worker sessions (`builder`, `proposer`, `critic`, `synth`), type `/hover`.

If you're running the research loop, also start the queue daemon from the repo root:

```bash
python3 scripts/queue_daemon.py --agents-root <AGENTS_ROOT> --interval 30
```
Use the same `AGENTS_ROOT` you chose during setup.

### Dispatch Work
```bash
python3 examples/dispatch_example.py --agent builder --task "Fix error handling in api.py"
python3 examples/check_status.py           # Fleet status
python3 examples/watch_completions.py      # Live completion feed
```

---

## Architecture

```
                    ┌──────────────────────┐
                    │    Orchestrator       │
                    │  (Wednesday / You)    │
                    └──────────┬───────────┘
                               │ dispatch signals
                    ┌──────────▼───────────┐
                    │     Signal Bus        │
                    │  signals.jsonl        │
                    │  cursors/<agent>.cursor│
                    │  completions/         │
                    └──────────┬───────────┘
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
        ┌───────────┐   ┌───────────┐    ┌───────────┐
        │  Agent A   │   │  Agent B   │    │  Agent C   │
        │  (hover)   │   │  (hover)   │    │  (hover)   │
        └───────────┘   └───────────┘    └───────────┘
              │                │                 │
              ▼                ▼                 ▼
         tick → read → execute → prove → advance → idle → repeat
```

Each agent has its own bus at:
```
<AGENTS_ROOT>/<name>/shared_intel/signal_bus/
├── signals.jsonl          # Append-only signal log
├── cursors/
│   └── <agent>_ran_hover.cursor   # Line number of last consumed signal
└── completions/
    └── <signal_id>_completion.md  # Proof of work
```

---

## Two Runtimes

HoverNet supports multiple model runtimes on the same signal bus. An agent's identity persists across model switches — same bus, same cursor, same history.

### QwenAgents

Free inference via Qwen Coder CLI. Includes:
- **Hover runtime** — `Hover.py`, `hover_mcp.py` (MCP tools for Qwen Code)
- **Resilience layer** — self-heal loop, dead letter queue, circuit breaker, cursor backup, signal retry, poison detection
- **Research prompts** — Karpathy-style 3-agent debate (proposer → critic → synthesizer)
- **Cron tick** — external LOOK wake-up for agents that can't self-poll

> **LOOK is non-negotiable for Qwen/Codex agents.** These models finish a task and sit idle — they will not self-poll for the next signal. The cron tick uses `tmux send-keys` to inject a wake-up message into the agent's session. Without it, your Qwen agents are dead on arrival. See [`QwenAgents/cron/README.md`](QwenAgents/cron/README.md) for setup.

### ClaudeAgents

Claude Code agents with native `/hover` skill. Includes:
- **Cron tick** — fallback wake-up mechanism (usually not needed)

Claude agents self-poll via the built-in `/hover` skill — no external cron needed. The `/hover` command in `.claude/commands/` handles everything: polling, consuming, proving, and returning to idle.

---

## Signal Bus Protocol

### Writing a Signal

```python
import json
from datetime import datetime, timezone

signal = {
    "signal_id": "TASK-001-UNLOCK-20260328",
    "type": "BUILDER_UNLOCK",
    "target_agent": "builder",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "dispatch_file": "/path/to/task_spec.md",
    "notes": "Fix the cursor parameterization in signal_retry.py"
}

with open("signals.jsonl", "a") as f:
    f.write(json.dumps(signal) + "\n")
```

### Consuming a Signal (Hover Tick)

```
1. Read cursor file → line N
2. Read signal at line N+1 from signals.jsonl
3. If no signal → idle, return
4. Read dispatch_file from signal
5. Execute bounded work
6. Write ACK to completions/
7. Write completion proof to completions/
8. Advance cursor to N+1
9. Return to idle
```

### Completion Proof

```markdown
---
signal_id: TASK-001-UNLOCK-20260328
status: DONE
completed_at_utc: 2026-03-28T09:54:17Z
files_changed:
  - signal_retry.py
---

## What was done
Replaced hardcoded cursor filename with parameterized f-string.

## Verification
- py_compile passes
- grep confirms no hardcoded references remain
```

---

## Cron Infrastructure

The `cron/` directory in each runtime contains the hover tick script:

```bash
# Install for an agent
bash cron/hover_tick.sh <agent_name> --model <claude|qwen>

# What it does:
# 1. Check: signals.jsonl line count > cursor value?
# 2. Yes → find agent's terminal session → deliver work
# 3. No → silent exit, cron wakes again in 60s
```

For Qwen agents, the tick uses LOOK (tmux injection) to wake the agent.
For Claude agents, the built-in `/hover` skill handles polling natively.

---

## Research Loop (Karpathy Pattern)

Three-agent debate for deep code analysis:

```
Proposer  →  Reads codebase, proposes concrete findings
     ↓ signal dispatch
Critic    →  Verifies findings against actual code, catches false positives
     ↓ signal dispatch
Synth     →  Produces consensus + builder contracts
     ↓ signal dispatch
Builders  →  Execute bounded contracts, write completion proofs
```

The research agents self-dispatch internally for the first half of the chain:

```
proposer -> critic -> synth
```

The synth-to-builder fan-out and next-round proposer dispatch are handled by `scripts/queue_daemon.py`. That bridge is part of the runtime, not an optional extra. It keeps the loop moving until the synth marks the thread `CLOSED`.

---

## Self-Healing

The resilience layer monitors bus health and recovers automatically:

- **Dead Letter** — poison signals quarantined, not retried forever
- **Cursor Backup** — cursor state backed up, recoverable after corruption
- **Circuit Breaker** — CLOSED/OPEN/HALF_OPEN state machine prevents cascade failure
- **Session Guard** — POSIX file locks prevent duplicate processing
- **Signal Retry** — failed signals retried with exponential backoff
- **Cascade Detection** — fleet-wide failure pattern detection

---

## Directory Structure

```
HoverNet/
├── README.md              # You're here
├── RULES.md               # 10 non-negotiables — read before integrating
├── SETUP.md               # Agent-readable setup instructions
├── foundation.md          # The 3 invariants — the soul of HoverNet
├── setup.sh               # Manual setup script (alternative to SETUP.md)
├── LICENSE                # MIT
│
├── .claude/               # Claude Code configuration
│   ├── commands/
│   │   ├── hover.md        # /hover — the core loop (auto-available)
│   │   └── hoveroff.md     # /hoveroff — clean stop
│   ├── settings.local.json # Statusline config (auto-loaded)
│   └── statusline.sh       # Clean agent identity display
│
├── agents/                # Agent templates (Lego blocks)
│   ├── builder/            # Universal builder — executes bounded tasks
│   ├── proposer/           # Research proposer — finds issues in code
│   ├── critic/             # Research critic — verifies findings
│   └── synth/              # Research synthesizer — produces consensus
│
├── launchers/             # Agent launch scripts
│   ├── qwen_agent.sh      # Launch Qwen agent in tmux
│   └── claude_agent.sh    # Launch Claude agent in tmux
│
├── examples/              # Getting started
│   ├── dispatch_example.py     # Write a signal to an agent
│   ├── check_status.py         # Fleet bus status dashboard
│   └── watch_completions.py    # Live completion monitor
│
├── QwenAgents/            # Qwen runtime (free inference)
│   ├── Current/scripts/   # Hover runtime + resilience layer (16 files)
│   ├── Current/prompts/   # Research role prompts
│   └── cron/              # Hover tick for Qwen sessions
│
└── ClaudeAgents/          # Claude runtime
    └── cron/              # Hover tick (fallback — /hover handles most cases)
```

---

## End-to-End Example

Here's what a full cycle looks like:

```bash
# 1. You dispatch a task
python3 examples/dispatch_example.py --agent builder --task "Add input validation to parse_config() in config.py"

# 2. The builder's bus now has a signal
python3 examples/check_status.py
# builder      PENDING    1          0          >>> 1      0

# 3. The builder (in its terminal, running /hover) picks it up:
#    - Reads the signal
#    - Writes ACK to completions/
#    - Edits config.py
#    - Writes completion proof
#    - Advances cursor

# 4. You see the result
python3 examples/check_status.py
# builder      IDLE       1          1          .          1

python3 examples/watch_completions.py --once
# [10:15:32] builder      DONE     BUILDER-BUILDER_UNLOCK-20260328T101500
```

---

## Troubleshooting

**Agent shows `?/0` instead of its name**
The statusline script isn't loaded. Run the agent from its own directory (`cd <AGENTS_ROOT>/builder && claude`) so the statusline can resolve the agent name from the path.

**`/hover` command not found**
You need to run Claude Code from inside the HoverNet repo directory (or a directory that has `.claude/commands/hover.md`). The SETUP.md flow copies this into each agent's workspace.

**Signal dispatched but agent doesn't pick it up**
Check that `/hover` is actually running — the agent should have a CronCreate job ticking every minute. Type `/hover` in the agent's session to start it.

**Cursor shows negative number**
The cursor file was initialized at a value higher than the signal count. Reset it: `echo "0" > cursors/<agent>_ran_hover.cursor`

**Statusline shows `(no hover state)`**
The agent hasn't written `runtime/hover.json` yet. This happens after the first `/hover` tick completes. Dispatch a signal and wait for a tick.

---

## Built by

[@mrsunday777](https://x.com/mrsunday777) — Vessel Labs
