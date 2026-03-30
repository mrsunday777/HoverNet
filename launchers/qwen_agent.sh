#!/usr/bin/env bash
# Launch a Qwen Code agent in its own terminal
# Usage: bash qwen_agent.sh <agent_name>
#
# Opens the agent's workspace and starts Qwen Code.
# The cron tick (LOOK) handles waking the agent when signals arrive.
#
# Prerequisites: Qwen Code CLI installed (qwen-code or collaborator)

set -euo pipefail

AGENT_NAME="${1:?Usage: bash qwen_agent.sh <agent_name>}"
AGENTS_ROOT="${AGENTS_ROOT:-$HOME/hovernet-fleet}"
AGENT_DIR="$AGENTS_ROOT/$AGENT_NAME"
HOVERNET_ROOT="${HOVERNET_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

if [[ ! -d "$AGENT_DIR" ]]; then
    echo "Agent directory not found: $AGENT_DIR"
    echo "Run setup.sh first."
    exit 1
fi

# Verify signal bus exists
BUS_DIR="$AGENT_DIR/shared_intel/signal_bus"
if [[ ! -d "$BUS_DIR" ]]; then
    echo "Signal bus not found: $BUS_DIR"
    echo "Run setup.sh first."
    exit 1
fi

# Detect Qwen CLI
QWEN_CMD=""
if command -v qwen-code &>/dev/null; then
    QWEN_CMD="qwen-code"
elif command -v collaborator &>/dev/null; then
    QWEN_CMD="collaborator"
else
    echo "No Qwen Code CLI found (tried: qwen-code, collaborator)"
    echo "Install Qwen Code or set QWEN_CMD_OVERRIDE environment variable."
    exit 1
fi
QWEN_CMD="${QWEN_CMD_OVERRIDE:-$QWEN_CMD}"

echo "═══════════════════════════════════════"
echo "  HoverNet — $AGENT_NAME (Qwen)"
echo "═══════════════════════════════════════"
echo "  Agent dir:  $AGENT_DIR"
echo "  Signal bus: $BUS_DIR"
echo "  CLI:        $QWEN_CMD"
echo ""
echo "  Signals arrive via cron LOOK."
echo "═══════════════════════════════════════"
echo ""

# ── Collab Session Wrapping ──
# Agents must run inside a collab tmux session so:
#   1. LOOK (find_agent_session) can locate this agent by pane title
#   2. pane-border-status renders the green title line
#
# If we're not already inside tmux, create a named collab session and
# re-exec this script inside it. $TMUX is set inside tmux — prevents loop.
AGENT_LOWER="${AGENT_NAME,,}"
if [[ -z "${TMUX:-}" ]]; then
    SESSION="collab-${AGENT_LOWER}"
    tmux -L collab kill-session -t "$SESSION" 2>/dev/null || true
    tmux -L collab new-session -d -s "$SESSION" -c "$AGENT_DIR" \
        bash "$0" "$AGENT_NAME"
    tmux -L collab set-option -wt "${SESSION}:0" pane-border-status top    2>/dev/null || true
    tmux -L collab set-option -wt "${SESSION}:0" pane-border-format "#{pane_title}" 2>/dev/null || true
    tmux -L collab set-option -wt "${SESSION}:0" pane-border-style "fg=green" 2>/dev/null || true
    exec tmux -L collab attach-session -t "$SESSION"
fi

# Set pane title — enables LOOK session matching (tmux pane-border-format + find_agent_session)
# Without this, the orchestrator cannot identify which tmux session belongs to this agent
# and LOOK (the core agent-wakeup mechanism) breaks silently.
printf '\033]0;🐍 Qwen - %s | qwen\007' "$AGENT_NAME"

# Launch Qwen Code in the agent's workspace — you're in it
cd "$AGENT_DIR"
HOVERNET_ROOT="$HOVERNET_ROOT" AGENTS_ROOT="$AGENTS_ROOT" exec "$QWEN_CMD"
