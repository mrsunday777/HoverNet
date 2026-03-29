#!/usr/bin/env python3
"""
Hover MCP Server — Exposes Hover as native tools for Qwen Code / Claude Code

Usage:
    python3 hover_mcp.py stdio

Add to your agent's MCP config:
{
  "mcpServers": {
    "hover": {
      "command": "python3",
      "args": ["/path/to/hover_mcp.py", "stdio"]
    }
  }
}
"""
import asyncio
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Any

from _path_utils import resolve_signal_bus, check_agent_health

# MCP Protocol constants
MCP_VERSION = "2024-11-05"
SERVER_NAME = "hover"
SERVER_VERSION = "1.0.0"

HOVER_SCRIPT = Path(__file__).parent / "Hover.py"
AGENTS_ROOT = Path(os.environ.get('AGENTS_ROOT', Path.home() / "hovernet-fleet"))


def log(message: str) -> None:
    sys.stderr.write(f"[hover-mcp] {message}\n")
    sys.stderr.flush()


def send_message(message: dict) -> None:
    json_str = json.dumps(message)
    sys.stdout.write(f"{json_str}\n")
    sys.stdout.flush()


def create_response(id: int, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def create_error(id: int, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


HOVER_TOOLS = [
    {
        "name": "hover_run",
        "description": "Run one hover tick — poll the signal bus, consume one task, write proof, return. Implements the 3 hover invariants.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Agent name (e.g., builder, proposer)", "default": "builder"},
                "once": {"type": "boolean", "description": "Run one tick and exit (default: true)", "default": True},
                "poll_sec": {"type": "integer", "description": "Poll interval in seconds", "default": 60}
            },
            "required": []
        }
    },
    {
        "name": "hover_status",
        "description": "Check hover status — cursor position, signals count, pending, recent completions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Agent name to check"}
            },
            "required": ["agent"]
        }
    },
    {
        "name": "hover_dispatch",
        "description": "Write a new signal to an agent's signal bus.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Target agent name"},
                "signal_id": {"type": "string", "description": "Unique signal ID"},
                "task_id": {"type": "string", "description": "Task or phase ID"},
                "dispatch_file": {"type": "string", "description": "Path to dispatch file (optional)"},
                "signal_type": {"type": "string", "description": "Signal type (UNLOCK, DISPATCH, etc.)", "default": "UNLOCK"}
            },
            "required": ["agent", "signal_id", "task_id"]
        }
    },
    {
        "name": "hover_reset_cursor",
        "description": "Reset hover cursor to 0 or specific position. Use for recovery.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Agent name"},
                "position": {"type": "integer", "description": "Cursor position (default: 0)", "default": 0}
            },
            "required": ["agent"]
        }
    }
]


async def handle_initialize(id: int, params: dict) -> dict:
    log(f"Initialize: {params}")
    return create_response(id, {
        "protocolVersion": MCP_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}
    })


async def handle_tools_list(id: int) -> dict:
    return create_response(id, {"tools": HOVER_TOOLS})


async def handle_tools_call(id: int, params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments", {})
    log(f"Tool call: {name} with args {args}")

    if name == "hover_run":
        return await run_hover_tool(id, args)
    elif name == "hover_status":
        return await run_hover_status(id, args)
    elif name == "hover_dispatch":
        return await run_hover_dispatch(id, args)
    elif name == "hover_reset_cursor":
        return await run_hover_reset_cursor(id, args)
    else:
        return create_error(id, -32601, f"Unknown tool: {name}")


async def run_hover_tool(id: int, args: dict) -> dict:
    agent = args.get("agent", "builder")
    poll_sec = args.get("poll_sec", 60)
    once = args.get("once", True)

    cmd = ["python3", str(HOVER_SCRIPT), "--agent", agent, "--poll-sec", str(poll_sec)]
    if once:
        cmd.append("--once")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return create_response(id, {
            "content": [{"type": "text", "text": f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}\n\nreturncode: {result.returncode}"}]
        })
    except subprocess.TimeoutExpired:
        return create_error(id, -32000, "Hover execution timed out")
    except Exception as e:
        return create_error(id, -32000, f"Hover execution failed: {e}")


async def run_hover_status(id: int, args: dict) -> dict:
    agent = args.get("agent")
    if not agent:
        return create_error(id, -32602, "Missing required argument: agent")

    try:
        health = check_agent_health(agent)
        return create_response(id, {
            "content": [{"type": "text", "text": json.dumps(health, indent=2)}]
        })
    except FileNotFoundError as e:
        return create_error(id, -32602, str(e))
    except Exception as e:
        return create_error(id, -32000, f"Health check failed: {type(e).__name__}: {e}")


async def run_hover_dispatch(id: int, args: dict) -> dict:
    agent = args.get("agent")
    signal_id = args.get("signal_id")
    task_id = args.get("task_id")
    dispatch_file = args.get("dispatch_file", "-")
    signal_type = args.get("signal_type", "UNLOCK")

    if not all([agent, signal_id, task_id]):
        return create_error(id, -32602, "Missing required arguments: agent, signal_id, task_id")

    signals_file = AGENTS_ROOT / agent / "shared_intel" / "signal_bus" / "signals.jsonl"
    signals_file.parent.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timezone
    sig = {
        "signal_id": signal_id,
        "type": signal_type,
        "target_agent": agent,
        "task_or_phase_id": task_id,
        "dispatch_file": dispatch_file,
        "issued_at_utc": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    }

    with open(signals_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(sig, separators=(',', ':')) + '\n')

    return create_response(id, {
        "content": [{"type": "text", "text": f"Signal dispatched:\n- signal_id: {signal_id}\n- target_agent: {agent}\n- task_id: {task_id}\n- type: {signal_type}"}]
    })


async def run_hover_reset_cursor(id: int, args: dict) -> dict:
    agent = args.get("agent")
    position = args.get("position", 0)
    if not agent:
        return create_error(id, -32602, "Missing required argument: agent")

    cursor_file = AGENTS_ROOT / agent / "shared_intel" / "signal_bus" / "cursors" / f"{agent}_ran_hover.cursor"
    cursor_file.parent.mkdir(parents=True, exist_ok=True)
    cursor_file.write_text(f"{position}\n", encoding='utf-8')

    return create_response(id, {
        "content": [{"type": "text", "text": f"Cursor reset for {agent} to position {position}"}]
    })


async def process_message(line: str) -> None:
    try:
        msg = json.loads(line)
    except json.JSONDecodeError as e:
        log(f"JSON decode error: {e}")
        return

    msg_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {})

    if method == "initialize":
        response = await handle_initialize(msg_id, params)
    elif method == "tools/list":
        response = await handle_tools_list(msg_id)
    elif method == "tools/call":
        response = await handle_tools_call(msg_id, params)
    elif method == "notifications/initialized":
        log("Client initialized")
        return
    else:
        response = create_error(msg_id, -32601, f"Method not found: {method}")

    send_message(response)


async def main():
    log("Hover MCP Server starting...")

    if len(sys.argv) < 2 or sys.argv[1] != "stdio":
        log("Usage: python3 hover_mcp.py stdio")
        sys.exit(1)

    log(f"HOVER_SCRIPT: {HOVER_SCRIPT} (exists: {HOVER_SCRIPT.exists()})")

    for line in sys.stdin:
        try:
            line_str = line.strip()
            if line_str:
                await process_message(line_str)
        except Exception as e:
            log(f"Error processing message: {e}")
            continue

    log("Hover MCP Server shutting down")


if __name__ == "__main__":
    asyncio.run(main())
