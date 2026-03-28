# Hover — Qwen Agent Continuous Polling Runtime

**Location:** `scripts/Hover.py`

## Purpose

Implements the **3 hover invariants** for Qwen agents:

1. **Continuous polling** — cron-backed, return to idle after every tick, no manual re-priming

2. **Fresh explicit unlocks** — every signal gets fresh ID, targeted to one consumer, type matches contract

3. **Execute, prove, return** — consume unread signal, do bounded work, write proof, advance cursor, return to hover

## Usage

### Basic Hover (Continuous)

```bash
python3 scripts/Hover.py --agent builder --poll-sec 10
```

### One-Shot (Cron Mode)

```bash
python3 scripts/Hover.py --agent builder --once
```

### Health Check

```bash
python3 scripts/Hover.py --agent builder --health
```

## Command Line Options

| Option            | Description                          | Default |
| ----------------- | ------------------------------------ | ------- |
| `--agent`         | Agent name (required)                | —       |
| `--poll-sec`      | Poll interval in seconds             | 10      |
| `--once`          | Run one tick and exit                | False   |
| `--health`        | Check agent health (JSON output)     | False   |
| `--show-dispatch` | Show dispatch file previews (0 or 1) | 1       |

## Signal Bus Structure

```text
shared_intel/signal_bus/
├── signals.jsonl          # All signals (append-only)
├── cursors/
│   └── builder_hover.cursor  # Last processed line number
└── completions/
    ├── {signal_id}_ack.md       # ACK proof
    └── {signal_id}_completion.md # Completion proof
```

## Signal Format

```json
{
  "signal_id": "BUILDER-TASK-001",
  "type": "UNLOCK",
  "target_agent": "builder",
  "task_or_phase_id": "TASK-123",
  "dispatch_file": "/path/to/dispatch.md",
  "issued_at_utc": "2026-03-28T05:45:00Z"
}
```

## Integration with Your Model

The `execute_dispatch()` function in `Hover.py` is the integration point:

```python
def execute_dispatch(dispatch_file, signal_id, agent, task_id):
    # TODO: Integrate your model's inference here
    time.sleep(0.1)
    return "SUCCESS"
```

Replace this with your model's inference pipeline:

1. Read the dispatch file

2. Send to your model (Ollama, API, etc.)

3. Parse the response

4. Apply edits / execute commands

5. Return result status

## Resilience Scripts

These scripts keep the bus healthy in production:

| Script                 | What It Does                                                 |
| ---------------------- | ------------------------------------------------------------ |
| `self_heal_loop.py`    | Autonomous recovery daemon — runs diagnostics + auto-fixes   |
| `dead_letter.py`       | Quarantines poison signals instead of retrying forever       |
| `circuit_breaker.py`   | CLOSED/OPEN/HALF_OPEN state machine prevents cascade failure |
| `cursor_backup.py`     | Backup and restore cursor state                              |
| `cursor_resilience.py` | Detect cursor drift and metadata tracking                    |
| `signal_retry.py`      | Retry failed signals with exponential backoff                |
| `bus_health.py`        | Validate and repair bus JSON                                 |
| `poison_learning.py`   | Learn from bad signal patterns to auto-detect future ones    |
| `auto_recover.py`      | Automated agent recovery (diagnose → plan → execute)         |
| `session_guard.py`     | POSIX file locks prevent duplicate processing                |

### Quick Health Check

```bash
# Single agent
python3 self_heal_loop.py --agent-dir ~/Desktop/Vessel/agents/builder --dry-run

# Entire fleet
python3 self_heal_loop.py --fleet-root ~/Desktop/Vessel/agents --dry-run

# Continuous daemon mode
python3 self_heal_loop.py --agent-dir ~/Desktop/Vessel/agents/builder --continuous --interval 60
```

## MCP Server

`hover_mcp.py` exposes Hover as native tools for Qwen Code or Claude Code:

* `hover_run` — Execute a hover tick

* `hover_status` — Check agent health

* `hover_dispatch` — Write a signal to the bus

* `hover_reset_cursor` — Reset cursor for recovery

## Environment Variables

| Variable        | Description                  | Default                   |
| --------------- | ---------------------------- | ------------------------- |
| `AGENTS_ROOT`   | Where agent directories live | `~/Desktop/Vessel/agents` |
| `HOVERNET_ROOT` | HoverNet project root        | auto-detected             |

## Error Handling

* **Path traversal blocked**: Dispatch files with `..` are rejected

* **Cursor recovery**: If signals file is truncated, cursor auto-resets to 0

* **Failed execution**: Cursor not advanced, will retry next tick

* **Missing dispatch file**: Warning logged, continues processing

* **Graceful shutdown**: SIGTERM/SIGINT finish current tick before exit

⠀