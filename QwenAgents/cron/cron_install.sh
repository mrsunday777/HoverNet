#!/usr/bin/env bash
# cron_install.sh — Install hover tick cron entries for fleet agents
#
# Usage:
#   cron_install.sh                          # Install all defaults (claude agents)
#   cron_install.sh cp0 cp1 cp9 --model qwen # Specific agents on qwen
#   cron_install.sh --list                   # Show what would be installed
#   cron_install.sh --remove cp0             # Remove specific agent's cron
#
# Each agent gets: * * * * * hover_tick.sh <agent> --model <model>
# The cron tag format: #hover-tick-<agent>-<model>

set -euo pipefail

TICK_SCRIPT="$(cd "$(dirname "$0")" && pwd)/hover_tick.sh"
DEFAULT_MODEL="claude"
DEFAULT_AGENTS=("builder" "proposer" "critic" "synth")
CADENCE="* * * * *"

ACTION="install"
AGENTS=()
MODEL="$DEFAULT_MODEL"

# ── Parse args ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL="$2"; shift 2 ;;
        --cadence) CADENCE="$2"; shift 2 ;;
        --list) ACTION="list"; shift ;;
        --remove) ACTION="remove"; shift ;;
        --remove-all) ACTION="remove-all"; shift ;;
        --help|-h)
            echo "Usage: cron_install.sh [agents...] [--model claude|qwen|codex] [--cadence '* * * * *']"
            echo "       cron_install.sh --list"
            echo "       cron_install.sh --remove <agent>"
            echo "       cron_install.sh --remove-all"
            exit 0
            ;;
        *) AGENTS+=("$1"); shift ;;
    esac
done

# Use defaults if no agents specified
if [ ${#AGENTS[@]} -eq 0 ]; then
    AGENTS=("${DEFAULT_AGENTS[@]}")
fi

TAG_PREFIX="#hover-tick"

case "$ACTION" in
    list)
        echo "Would install these cron entries:"
        for agent in "${AGENTS[@]}"; do
            agent_lower=$(echo "$agent" | tr '[:upper:]' '[:lower:]')
            tag="${TAG_PREFIX}-${agent_lower}-${MODEL}"
            echo "  ${CADENCE} ${TICK_SCRIPT} ${agent} --model ${MODEL} --cadence \"${CADENCE}\" ${tag}"
        done
        ;;

    install)
        EXISTING=$(crontab -l 2>/dev/null || true)

        for agent in "${AGENTS[@]}"; do
            agent_lower=$(echo "$agent" | tr '[:upper:]' '[:lower:]')
            tag="${TAG_PREFIX}-${agent_lower}-${MODEL}"
            entry="${CADENCE} ${TICK_SCRIPT} ${agent} --model ${MODEL} --cadence \"${CADENCE}\" ${tag}"

            if echo "$EXISTING" | grep -q "$tag"; then
                # Replace existing
                EXISTING=$(echo "$EXISTING" | grep -v "$tag")
                echo "  ↻ ${agent} (${MODEL}) — updated"
            else
                echo "  + ${agent} (${MODEL}) — installed"
            fi
            EXISTING="${EXISTING}
${entry}"
        done

        echo "$EXISTING" | crontab -
        echo ""
        echo "Done. Verify with: crontab -l | grep hover-tick"
        ;;

    remove)
        EXISTING=$(crontab -l 2>/dev/null || true)
        for agent in "${AGENTS[@]}"; do
            agent_lower=$(echo "$agent" | tr '[:upper:]' '[:lower:]')
            tag="${TAG_PREFIX}-${agent_lower}"
            if echo "$EXISTING" | grep -q "$tag"; then
                EXISTING=$(echo "$EXISTING" | grep -v "$tag")
                echo "  - ${agent} — removed"
            else
                echo "  · ${agent} — not found"
            fi
        done
        echo "$EXISTING" | crontab -
        ;;

    remove-all)
        EXISTING=$(crontab -l 2>/dev/null || true)
        CLEANED=$(echo "$EXISTING" | grep -v "$TAG_PREFIX" || true)
        echo "$CLEANED" | crontab -
        echo "All hover-tick cron entries removed."
        ;;
esac
