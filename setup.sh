#!/usr/bin/env bash
# HoverNet Setup — Creates agent fleet structure and signal buses
# Usage: bash setup.sh [--agents-root ~/Desktop/Vessel/agents]

set -euo pipefail

# Defaults
AGENTS_ROOT="${AGENTS_ROOT:-$HOME/Desktop/Vessel/agents}"
HOVERNET_DIR="$(cd "$(dirname "$0")" && pwd)"

# Agent roles (name=template pairs)
AGENTS="builder proposer critic synth"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --agents-root) AGENTS_ROOT="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: bash setup.sh [--agents-root PATH]"
            echo ""
            echo "Creates the agent fleet directory structure with signal buses."
            echo ""
            echo "Options:"
            echo "  --agents-root PATH   Where to create agent dirs (default: ~/Desktop/Vessel/agents)"
            echo ""
            echo "Environment:"
            echo "  AGENTS_ROOT          Same as --agents-root"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "╔═══════════════════════════════════════╗"
echo "║        HoverNet Fleet Setup           ║"
echo "╚═══════════════════════════════════════╝"
echo ""
echo "Agents root: $AGENTS_ROOT"
echo "HoverNet:    $HOVERNET_DIR"
echo ""

# Create agent directories
for agent in $AGENTS; do
    role="$agent"
    bus_dir="$AGENTS_ROOT/$agent/shared_intel/signal_bus"

    if [[ -d "$bus_dir" ]]; then
        echo "[exists] $agent — signal bus already set up"
        continue
    fi

    echo "[create] $agent"

    # Agent workspace
    mkdir -p "$AGENTS_ROOT/$agent"

    # Signal bus structure
    mkdir -p "$bus_dir/cursors"
    mkdir -p "$bus_dir/completions"

    # Runtime dir (hover.json goes here)
    mkdir -p "$AGENTS_ROOT/$agent/runtime"

    # Empty signal log
    touch "$bus_dir/signals.jsonl"

    # Cursor at 0 (no signals consumed yet)
    echo "0" > "$bus_dir/cursors/${agent}_ran_hover.cursor"

    # Copy agent template (CLAUDE.md with role instructions)
    if [[ ! -f "$AGENTS_ROOT/$agent/CLAUDE.md" ]]; then
        template="$HOVERNET_DIR/agents/$role/CLAUDE.md"
        if [[ -f "$template" ]]; then
            cp "$template" "$AGENTS_ROOT/$agent/CLAUDE.md"
            echo "         copied CLAUDE.md from agents/$role/"
        else
            echo "         [warn] template not found: agents/$role/CLAUDE.md"
        fi
    fi

    # Copy slash commands (/hover, /hoveroff, /autohover)
    if [[ -d "$HOVERNET_DIR/.claude/commands" ]]; then
        mkdir -p "$AGENTS_ROOT/$agent/.claude/commands"
        cp "$HOVERNET_DIR/.claude/commands/"*.md "$AGENTS_ROOT/$agent/.claude/commands/" 2>/dev/null
        echo "         installed /hover, /hoveroff, /autohover commands"
    fi
done

echo ""

# Install statusline (optional)
if [[ -f "$HOVERNET_DIR/.claude/statusline.sh" ]]; then
    STATUSLINE_DEST="$HOME/.claude/statusline.sh"
    if [[ ! -f "$STATUSLINE_DEST" ]]; then
        mkdir -p "$HOME/.claude"
        cp "$HOVERNET_DIR/.claude/statusline.sh" "$STATUSLINE_DEST"
        chmod +x "$STATUSLINE_DEST"
        echo "[install] statusline → ~/.claude/statusline.sh"
    else
        echo "[exists]  statusline already installed"
    fi
fi

# Install cron hover ticks (optional — for Qwen agents that need external LOOK)
read -p "Install cron hover ticks for Qwen agents? [y/N] " install_cron
if [[ "${install_cron:-n}" =~ ^[Yy]$ ]]; then
    if [[ -f "$HOVERNET_DIR/QwenAgents/cron/cron_install.sh" ]]; then
        echo ""
        echo "Installing Qwen hover cron..."
        bash "$HOVERNET_DIR/QwenAgents/cron/cron_install.sh"
    else
        echo "Qwen cron installer not found — install manually from QwenAgents/cron/"
    fi
fi

echo ""
echo "══════════════════════════════════════════"
echo "Setup complete."
echo ""
echo "Agent directories created at: $AGENTS_ROOT"
echo ""
echo "Next steps:"
echo ""
echo "  Terminal 1 — Your orchestrator:"
echo "       cd $AGENTS_ROOT/builder && claude"
echo "       Type: /autohover"
echo ""
echo "  Terminal 2+ — Your workers (open as many as you need):"
echo "       cd $AGENTS_ROOT/builder && claude     # or use a different agent name"
echo "       Type: /hover"
echo ""
echo "  Tell your orchestrator what to build. It dispatches to hovering agents."
echo ""
echo "  For full setup (aliases, statusline), see SETUP.md"
echo "══════════════════════════════════════════"
