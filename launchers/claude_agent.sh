#!/usr/bin/env bash
# Launch a Claude Code agent in its own terminal
# Usage: bash claude_agent.sh <agent_name>
#
# Opens the agent's workspace and starts Claude Code.
# You type /hover in the session to begin the hover loop.
#
# Prerequisites: Claude Code CLI installed (claude)

set -euo pipefail

AGENT_NAME="${1:?Usage: bash claude_agent.sh <agent_name>}"
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

# Verify Claude CLI
if ! command -v claude &>/dev/null; then
    echo "Claude Code CLI not found."
    echo "Install: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

# Read model default (written by setup.sh, user can override)
MODEL_FLAG=""
MODEL_FILE="$AGENT_DIR/runtime/model"
if [[ -f "$MODEL_FILE" ]]; then
    MODEL="$(cat "$MODEL_FILE" | tr -d '[:space:]')"
    MODEL_FLAG="--model $MODEL"
fi

echo "═══════════════════════════════════════"
echo "  HoverNet — $AGENT_NAME"
echo "═══════════════════════════════════════"
echo "  Agent dir:  $AGENT_DIR"
echo "  Signal bus: $BUS_DIR"
echo "  Model:      ${MODEL:-default}"
echo ""
echo "  Type /hover once Claude starts."
echo "  To change model: edit runtime/model"
echo "═══════════════════════════════════════"
echo ""

# Launch Claude Code in the agent's workspace — you're in it
cd "$AGENT_DIR"
HOVERNET_ROOT="$HOVERNET_ROOT" AGENTS_ROOT="$AGENTS_ROOT" exec claude $MODEL_FLAG --dangerously-skip-permissions
