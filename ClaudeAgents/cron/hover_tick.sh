#!/usr/bin/env bash
# hover_tick.sh — Canonical hover tick for any agent on any model runtime
#
# The heartbeat of hover. Cron runs this every minute. It checks if the agent
# has pending signals, and if so, LOOKs into their terminal session to wake them.
#
# Usage:
#   hover_tick.sh <agent_name> [--model claude|qwen|codex] [--agents-root PATH]
#
# Cron example:
#   * * * * * /path/to/hover_tick.sh builder --model claude
#   */2 * * * * /path/to/hover_tick.sh proposer --model claude
#
# Environment:
#   AGENTS_ROOT   Override agent fleet root (default: ~/Desktop/Vessel/agents)
#
# Model-agnostic by default. The --model flag only changes how we find the
# agent's terminal session and what LOOK message we inject.
#
# Note: Claude Code agents self-poll via the built-in /hover skill.
# This cron tick is only needed as a fallback wake-up mechanism.

set -euo pipefail

# ── Args ──
AGENT="${1:?Usage: hover_tick.sh <agent_name> [--model claude|qwen|codex]}"
shift
MODEL="claude"  # default
CADENCE="* * * * *"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL="$2"; shift 2 ;;
        --cadence) CADENCE="$2"; shift 2 ;;
        --agents-root) AGENTS_ROOT="$2"; shift 2 ;;
        *) shift ;;
    esac
done

AGENT_LOWER=$(echo "$AGENT" | tr '[:upper:]' '[:lower:]')
FLEET_ROOT="${AGENTS_ROOT:-$HOME/Desktop/Vessel/agents}"

# ── Resolve agent dir (case-insensitive) ──
AGENT_DIR=""
for d in "$FLEET_ROOT"/*/; do
    dir_name=$(basename "$d")
    if [ "$(echo "$dir_name" | tr '[:upper:]' '[:lower:]')" = "$AGENT_LOWER" ]; then
        AGENT_DIR="$d"
        break
    fi
done

if [ -z "$AGENT_DIR" ]; then
    exit 0  # Agent not in fleet, silent exit for cron
fi

# ── Ensure bus structure exists ──
SIGNALS_FILE="${AGENT_DIR}shared_intel/signal_bus/signals.jsonl"
CURSORS_DIR="${AGENT_DIR}shared_intel/signal_bus/cursors"
COMPLETIONS_DIR="${AGENT_DIR}shared_intel/signal_bus/completions"

mkdir -p "$CURSORS_DIR" "$COMPLETIONS_DIR" "${AGENT_DIR}runtime"
[[ -f "$SIGNALS_FILE" ]] || : > "$SIGNALS_FILE"

# ── Read bus state ──
TOTAL=$(wc -l < "$SIGNALS_FILE" | tr -d ' ')

# Find highest cursor for this agent
CURSOR=0
CURSOR_FILE=""
if [ -d "$CURSORS_DIR" ]; then
    for cf in "$CURSORS_DIR"/*.cursor; do
        [ -f "$cf" ] || continue
        val=$(cat "$cf" 2>/dev/null | tr -d '[:space:]')
        if [ "$val" -gt "$CURSOR" ] 2>/dev/null; then
            CURSOR=$val
            CURSOR_FILE="$cf"
        fi
    done
fi

# Default cursor file if none exists
if [ -z "$CURSOR_FILE" ]; then
    CURSOR_FILE="${CURSORS_DIR}/${AGENT_LOWER}_ran_hover.cursor"
    [[ -f "$CURSOR_FILE" ]] || echo "0" > "$CURSOR_FILE"
fi

PENDING=$((TOTAL - CURSOR))

# ── If no pending work, exit silently ──
if [ "$PENDING" -le 0 ]; then
    exit 0
fi

# ── Find agent's terminal session ──
SESSION=""

# Strategy 1: Convention-based named session (most reliable)
# Sessions named: <model>-<agent> e.g. qwen-builder, claude-builder
CONVENTION_NAME="${MODEL}-${AGENT_LOWER}"
if tmux has-session -t "$CONVENTION_NAME" 2>/dev/null; then
    SESSION="$CONVENTION_NAME"
fi

# Strategy 2: PID-based discovery (fallback)
if [ -z "$SESSION" ]; then
    find_tmux_session_by_pid() {
        local pid="$1"
        [ -z "$pid" ] && return

        local tty
        tty=$(ps -p "$pid" -o tty= 2>/dev/null | tr -d ' ')
        [ -z "$tty" ] || [ "$tty" = "??" ] && return

        for sess in $(tmux list-sessions -F '#{session_name}' 2>/dev/null); do
            local stty
            stty=$(tmux list-panes -t "$sess" -F '#{pane_tty}' 2>/dev/null)
            if [ "$stty" = "/dev/$tty" ]; then
                SESSION="$sess"
                return
            fi
        done
    }

    case "$MODEL" in
        claude)
            PID=$(pgrep -f "claude.*${AGENT_LOWER}" 2>/dev/null | head -1)
            find_tmux_session_by_pid "$PID"
            ;;
        qwen)
            PID=$(pgrep -f "qwen${AGENT_LOWER}" 2>/dev/null | head -1)
            find_tmux_session_by_pid "$PID"
            ;;
        codex)
            PID=$(pgrep -f "codex.*${AGENT_LOWER}" 2>/dev/null | head -1)
            find_tmux_session_by_pid "$PID"
            ;;
        *)
            PID=$(pgrep -f "${AGENT_LOWER}" 2>/dev/null | head -1)
            find_tmux_session_by_pid "$PID"
            ;;
    esac
fi

if [ -z "$SESSION" ]; then
    exit 0  # Agent not in a tmux session, silent exit
fi

# ── LOOK: Inject hover command into the session ──
LOOK_MSG="You have ${PENDING} pending signal(s) on your bus. Run /hover to process them."

tmux send-keys -t "$SESSION" "$LOOK_MSG" Enter

# ── Log the LOOK ──
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] LOOK → ${AGENT} (${MODEL}) ${PENDING} pending → tmux:${SESSION}"
