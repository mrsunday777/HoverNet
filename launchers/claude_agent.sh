#!/usr/bin/env bash
# Launch a Claude Code agent in hover mode
# Usage: bash claude_agent.sh <agent_name> [--session-name NAME]
#
# Prerequisites: Claude Code CLI installed (claude)
# Claude agents self-poll via the built-in /hover skill — no external cron needed.

set -euo pipefail

AGENT_NAME="${1:?Usage: bash claude_agent.sh <agent_name>}"
AGENTS_ROOT="${AGENTS_ROOT:-$HOME/Desktop/Vessel/agents}"
AGENT_DIR="$AGENTS_ROOT/$AGENT_NAME"
SESSION_NAME="${2:-claude-$AGENT_NAME}"

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

# Check for existing tmux session
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Session '$SESSION_NAME' already running. Attaching..."
    tmux attach -t "$SESSION_NAME"
    exit 0
fi

echo "Launching $AGENT_NAME in tmux session: $SESSION_NAME"
echo "Agent dir: $AGENT_DIR"
echo "Signal bus: $BUS_DIR"

# Verify Claude CLI
if ! command -v claude &>/dev/null; then
    echo "Claude Code CLI not found."
    echo "Install: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

# Launch in tmux
tmux new-session -d -s "$SESSION_NAME" -c "$AGENT_DIR" \
    "HOVERNET_ROOT='$(dirname "$(dirname "$0")")' AGENTS_ROOT='$AGENTS_ROOT' claude"

echo "Started. Attach with: tmux attach -t $SESSION_NAME"
echo "Claude agents self-poll — use /hover in the session to start the hover loop."
