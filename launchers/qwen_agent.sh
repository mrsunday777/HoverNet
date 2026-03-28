#!/usr/bin/env bash
# Launch a Qwen Code agent in hover mode
# Usage: bash qwen_agent.sh <agent_name> [--session-name NAME]
#
# Prerequisites: Qwen Code CLI installed (qwen-code or collaborator)
# The agent will load its CLAUDE.md and begin polling its signal bus.

set -euo pipefail

AGENT_NAME="${1:?Usage: bash qwen_agent.sh <agent_name>}"
AGENTS_ROOT="${AGENTS_ROOT:-$HOME/Desktop/Vessel/agents}"
AGENT_DIR="$AGENTS_ROOT/$AGENT_NAME"
SESSION_NAME="${2:-collab-$AGENT_NAME}"

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

# Detect Qwen CLI
QWEN_CMD=""
if command -v qwen-code &>/dev/null; then
    QWEN_CMD="qwen-code"
elif command -v collaborator &>/dev/null; then
    QWEN_CMD="collaborator"
else
    echo "No Qwen Code CLI found (tried: qwen-code, collaborator)"
    echo "Install Qwen Code or set QWEN_CMD environment variable."
    exit 1
fi

QWEN_CMD="${QWEN_CMD_OVERRIDE:-$QWEN_CMD}"

# Launch in tmux
tmux new-session -d -s "$SESSION_NAME" -c "$AGENT_DIR" \
    "HOVERNET_ROOT='$(dirname "$(dirname "$0")")' AGENTS_ROOT='$AGENTS_ROOT' $QWEN_CMD"

echo "Started. Attach with: tmux attach -t $SESSION_NAME"
echo "The agent is now ready to receive signals via its bus."
