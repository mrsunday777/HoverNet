"""Public HoverTools MCP server.

This entrypoint intentionally imports only the local loop tools that belong in
the open-source kit. It does not expose private product runtime controls.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools import agent_register as _agent_register
from .tools import bus_read as _bus_read
from .tools import bus_status as _bus_status
from .tools import completion_write as _completion_write
from .tools import decision_log as _decision_log
from .tools import hover_init as _hover_init
from .tools import hover_manifest as _hover_manifest
from .tools import peer_read as _peer_read
from .tools import read_doc as _read_doc
from .tools import session_fs as _session_fs
from .tools import signal_send as _signal_send


mcp = FastMCP("hovertools")


def hover_init(root: str, loop_name: str, agents: list[str]) -> dict:
    """Create a manifest-backed local HoverNet loop workspace under root/.hovernet."""
    return _hover_init.run(root=root, loop_name=loop_name, agents=agents)


def hover_manifest_read(root: str) -> dict:
    """Return the parsed hovernet.json from root/.hovernet/hovernet.json."""
    return _hover_manifest.read(root=root)


def hover_manifest_validate(root: str) -> dict:
    """Validate hovernet.json structure. Returns {ok, errors}."""
    return _hover_manifest.validate(root=root)


def agent_register(root: str, agent_name: str, role: str | None = None) -> dict:
    """Add an agent to the local manifest and create its bus/cursor files."""
    return _agent_register.run(root=root, agent_name=agent_name, role=role)


def signal_send(
    root: str,
    target_agent: str,
    signal_type: str,
    payload: dict,
    thread: str | None = None,
    round: int | None = None,
) -> dict:
    """Append one manifest-resolved signal to an agent bus. No tmux tap."""
    return _signal_send.run(
        root=root,
        target_agent=target_agent,
        signal_type=signal_type,
        payload=payload,
        thread=thread,
        round=round,
    )


def bus_read(
    bus_path: str,
    cursor_path: str,
    advance: bool = False,
    limit: int | None = None,
) -> dict:
    """Read pending bus signals. Set advance=True to consume what was returned."""
    return _bus_read.run(bus_path=bus_path, cursor_path=cursor_path, advance=advance, limit=limit)


def bus_ack(cursor_path: str, advance_by: int = 1) -> dict:
    """Advance a cursor after processing signals."""
    return _bus_read.ack(cursor_path=cursor_path, advance_by=advance_by)


def bus_status(root: str, agent: str) -> dict:
    """Return read-only bus/cursor health for one local agent."""
    return _bus_status.run(root=root, agent=agent)


def completion_write(
    root: str,
    loop_name: str,
    agent: str,
    signal_id: str,
    content: str,
    status: str = "DONE",
) -> dict:
    """Write a completion artifact to the loop completions folder."""
    return _completion_write.run(
        root=root,
        loop_name=loop_name,
        agent=agent,
        signal_id=signal_id,
        content=content,
        status=status,
    )


def session_fs_read(session_dir: str, relative_path: str) -> dict:
    """Read a file inside session_dir. Rejects paths that escape the session root."""
    return _session_fs.read(session_dir=session_dir, relative_path=relative_path)


def session_fs_write(session_dir: str, relative_path: str, content: str) -> dict:
    """Write a file inside session_dir. Rejects paths that escape the session root."""
    return _session_fs.write(session_dir=session_dir, relative_path=relative_path, content=content)


def session_fs_list(session_dir: str, relative_path: str = ".") -> dict:
    """List files under a session_dir subpath."""
    return _session_fs.list_dir(session_dir=session_dir, relative_path=relative_path)


def peer_read(artifact_paths: list[str], require_all: bool = True) -> dict:
    """Read sibling artifact files used by local poll/fan-in patterns."""
    return _peer_read.run(artifact_paths=artifact_paths, require_all=require_all)


def read_doc(
    filepath: str,
    chunk: int | None = None,
    grep: str | None = None,
    lines: str | None = None,
) -> dict:
    """Read a document with chunk, grep, or line-range support."""
    return _read_doc.run(filepath=filepath, chunk=chunk, grep=grep, lines=lines)


def decision_log_append(
    log_path: str,
    decision_id: str,
    title: str,
    actor: str,
    choice: str,
    rationale: str,
    context: str | None = None,
    alternatives: list[str] | None = None,
    impacts: list[str] | None = None,
) -> dict:
    """Append one record to a JSONL decision log."""
    return _decision_log.append(
        log_path=log_path,
        decision_id=decision_id,
        title=title,
        actor=actor,
        choice=choice,
        rationale=rationale,
        context=context,
        alternatives=alternatives,
        impacts=impacts,
    )


def decision_log_query(log_path: str, since: str | None = None, limit: int = 50) -> dict:
    """Read recent decision records from a JSONL log."""
    return _decision_log.query(log_path=log_path, since=since, limit=limit)


for _tool in (
    hover_init,
    hover_manifest_read,
    hover_manifest_validate,
    agent_register,
    signal_send,
    bus_read,
    bus_ack,
    bus_status,
    completion_write,
    session_fs_read,
    session_fs_write,
    session_fs_list,
    peer_read,
    read_doc,
    decision_log_append,
    decision_log_query,
):
    mcp.tool()(_tool)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
