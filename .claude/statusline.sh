#!/bin/bash
# HoverNet Status Line — Clean agent identity + signal bus status
# Ships with the repo. Shows: agent_name ◆ cursor/signals status age

set -o pipefail

SESSION_JSON=$(cat)
AGENTS_ROOT="${AGENTS_ROOT:-$HOME/hovernet-fleet}"

# Colors
GREEN='\033[32m'
CYAN='\033[36m'
YELLOW='\033[33m'
RED='\033[31m'
GRAY='\033[38;5;8m'
DIM='\033[2m'
RESET='\033[0m'

# Resolve agent name from cwd
CWD=$(echo "$SESSION_JSON" | jq -r '.workspace.current_dir // ""' 2>/dev/null)
AGENT_NAME=$(basename "$CWD" 2>/dev/null || echo "agent")
AGENT_DIR="$CWD"

# If we're in an agents subdirectory, use the agent folder name
if [[ "$CWD" == *"/agents/"* ]]; then
    AGENT_NAME=$(echo "$CWD" | sed 's|.*/agents/||' | cut -d'/' -f1)
    AGENT_DIR="$AGENTS_ROOT/$AGENT_NAME"
fi

# Model name (short)
MODEL_NAME=""
MODEL=$(echo "$SESSION_JSON" | jq -r '.model // ""' 2>/dev/null)
if [[ "$MODEL" == *"opus"* ]]; then MODEL_NAME="opus"
elif [[ "$MODEL" == *"sonnet"* ]]; then MODEL_NAME="sonnet"
elif [[ "$MODEL" == *"haiku"* ]]; then MODEL_NAME="haiku"
elif [ -n "$MODEL" ]; then MODEL_NAME="$MODEL"
fi

# Read hover state
HOVER_FILE="$AGENT_DIR/runtime/hover.json"
if [ -f "$HOVER_FILE" ]; then
    HOVER=$(cat "$HOVER_FILE" 2>/dev/null)
    CURSOR=$(echo "$HOVER" | jq -r '.cursor_value // "0"' 2>/dev/null)
    BUS_COUNT=$(echo "$HOVER" | jq -r '.bus_count // "0"' 2>/dev/null)
    LAST_RESULT=$(echo "$HOVER" | jq -r '.last_result // "none"' 2>/dev/null)
    LAST_TICK=$(echo "$HOVER" | jq -r '.last_tick_utc // ""' 2>/dev/null)

    # Pending count
    [[ "$BUS_COUNT" =~ ^[0-9]+$ ]] || BUS_COUNT=0
    [[ "$CURSOR" =~ ^[0-9]+$ ]] || CURSOR=0
    PENDING=$((BUS_COUNT - CURSOR))

    # Age calculation
    AGE_STR="--"
    STATE_COLOR="$GREEN"
    STALENESS=""
    if [ -n "$LAST_TICK" ] && [ "$LAST_TICK" != "null" ]; then
        TICK_EPOCH=$(TZ=UTC date -jf "%Y-%m-%dT%H:%M:%SZ" "$LAST_TICK" +%s 2>/dev/null || \
                     date -d "$LAST_TICK" +%s 2>/dev/null || echo "0")
        NOW_EPOCH=$(date +%s)
        AGE=$((NOW_EPOCH - TICK_EPOCH))

        if [ "$AGE" -lt 60 ]; then AGE_STR="${AGE}s"
        elif [ "$AGE" -lt 3600 ]; then AGE_STR="$((AGE / 60))m"
        else AGE_STR="$((AGE / 3600))h"
        fi

        if [ "$AGE" -gt 600 ]; then
            STATE_COLOR="$RED"; STALENESS=" DEAD"
        elif [ "$AGE" -gt 300 ]; then
            STATE_COLOR="$YELLOW"; STALENESS=" STALE"
        fi
    fi

    # Choose symbol
    if [ "$PENDING" -gt 0 ]; then
        SYMBOL="${YELLOW}▸${RESET}"
    else
        SYMBOL="${STATE_COLOR}◆${RESET}"
    fi

    # Line 1: identity + bus status
    LINE1="${GREEN}${AGENT_NAME}${RESET} ${SYMBOL} ${CYAN}${CURSOR}/${BUS_COUNT}${RESET} ${LAST_RESULT} ${GRAY}${AGE_STR} ago${STALENESS}${RESET}"

    # Line 2: model (dimmed)
    if [ -n "$MODEL_NAME" ]; then
        printf "${LINE1}\n${DIM}${MODEL_NAME}${RESET}"
    else
        printf "$LINE1"
    fi
else
    # No hover state — try reading signal bus directly
    BUS_DIR="$AGENT_DIR/shared_intel/signal_bus"
    if [ -d "$BUS_DIR" ]; then
        SIGNALS_FILE="$BUS_DIR/signals.jsonl"
        TOTAL=0
        CURSOR=0
        if [ -f "$SIGNALS_FILE" ]; then
            TOTAL=$(wc -l < "$SIGNALS_FILE" | tr -d ' ')
        fi
        # Find cursor file
        for cf in "$BUS_DIR/cursors/"*.cursor 2>/dev/null; do
            [ -f "$cf" ] || continue
            val=$(cat "$cf" 2>/dev/null | tr -d '[:space:]')
            [[ "$val" =~ ^[0-9]+$ ]] && [ "$val" -gt "$CURSOR" ] && CURSOR=$val
        done
        PENDING=$((TOTAL - CURSOR))

        if [ "$PENDING" -gt 0 ]; then
            SYMBOL="${YELLOW}▸${RESET}"
        else
            SYMBOL="${GREEN}◆${RESET}"
        fi

        LINE1="${GREEN}${AGENT_NAME}${RESET} ${SYMBOL} ${CYAN}${CURSOR}/${TOTAL}${RESET}"
        if [ -n "$MODEL_NAME" ]; then
            printf "${LINE1}\n${DIM}${MODEL_NAME}${RESET}"
        else
            printf "$LINE1"
        fi
    else
        # Bare session — just show name + model
        if [ -n "$MODEL_NAME" ]; then
            printf "${GREEN}${AGENT_NAME}${RESET}\n${DIM}${MODEL_NAME}${RESET}"
        else
            printf "${GREEN}${AGENT_NAME}${RESET}"
        fi
    fi
fi
