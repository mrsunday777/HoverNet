# HoverTools Public Surface

Version: 1.1
Entrypoint: `hovertools.public_server:main`

HoverTools public mode is for a developer using the generated HoverNet v1.5
with no private infrastructure running. All public tools work with a local
filesystem, a repo checkout, and an MCP host. The exported package does not ship
the internal live-operator modules.

---

## 1. The Outsider Journey (5 Steps)

A first-time cloner goes through this sequence exactly once per workspace:

### Step 1 — Init

```
hover_init(root="/path/to/your/project", loop_name="my-loop", agents=["alice", "bob"])
```

Creates `.hovernet/` under `root`. Writes `hovernet.json`. Creates per-agent
signal buses, cursors, and a session folder. Returns the parsed manifest,
manifest path, and all created paths so you know exactly what landed.

This is idempotent. Re-running adds missing agents and loops without clobbering
existing ones.

### Step 2 — Register

Agents are registered during `hover_init`. Each agent in the `agents` list gets:
- A signal bus at `.hovernet/agents/<agent>/shared_intel/signal_bus/signals.jsonl`
- A cursor at `.hovernet/agents/<agent>/shared_intel/signal_bus/cursors/<agent>.cursor`
- An entry in `hovernet.json` with resolved `bus_path` and `cursor_path`

To add a new agent to an existing workspace, call `hover_init` again with the
same `root` and `loop_name` but the expanded `agents` list. Existing agents are
preserved.

### Step 3 — Send

Write a signal to an agent's bus:

```
signal_send(
    root="/path/to/your/project",
    target_agent="bob",
    signal_type="TASK_DISPATCH",
    payload={"from": "alice", "notes": "review the patch"}
)
```

`signal_send` resolves `bob` through `hovernet.json`, fills `signal_id`,
`timestamp`, `type`, and `to`, enforces the 64 KB signal cap, and appends one
JSON line. `from` remains a label, not authentication.

### Step 4 — Read

Read pending signals from an agent's bus:

```
bus_read(
    bus_path=manifest["agents"]["alice"]["bus_path"],
    cursor_path=manifest["agents"]["alice"]["cursor_path"],
    limit=20
)
```

Returns `{cursor, total_lines, pending: [...signals...]}`. Cursor is NOT advanced
automatically — call `bus_ack` separately once you have processed each signal.
If you want read-and-consume behavior in one call, pass `advance=True`.

### Step 5 — Complete

Advance the cursor and write a completion artifact:

```
# Advance cursor by 1 after processing one signal
bus_ack(cursor_path=manifest["agents"]["alice"]["cursor_path"], advance_by=1)

completion_write(
    root="/path/to/your/project",
    loop_name="my-loop",
    agent="alice",
    signal_id="<signal_id>",
    content="completed summary",
    status="DONE"
)
```

---

## 2. Public Tools

The open-source artifact starts `hovertools.public_server:main`. It imports and
registers only this tool list:

| Tool | Purpose |
|------|---------|
| `hover_init` | Create/update workspace manifest and per-agent bus dirs |
| `hover_manifest_read` | Read the parsed `.hovernet/hovernet.json` manifest |
| `hover_manifest_validate` | Validate manifest structure |
| `agent_register` | Add one agent to an existing manifest |
| `signal_send` | Append a manifest-resolved signal to an agent bus |
| `bus_read` | Read pending signals from an agent's bus |
| `bus_ack` | Advance cursor after processing signals |
| `bus_status` | Inspect one agent's bus/cursor health |
| `loop_watch_once` | Report the next read-only Research/Council watcher event |
| `completion_write` | Write proof-of-work into a loop completion artifact |
| `session_fs_read` | Read a file inside the session directory |
| `session_fs_write` | Write a file inside the session directory |
| `session_fs_list` | List files inside the session directory |
| `peer_read` | Read a set of sibling artifact files (poll pattern) |
| `read_doc` | Chunked reader for large files |
| `decision_log_append` | Append a decision record to a JSONL audit log |
| `decision_log_query` | Read decisions from a JSONL audit log |

## Terminal Viewer

`hover-agentmap-viewer` renders a public AgentMap YAML file into a stable tmux
viewer. It does not start model runtimes; it only attaches panes to existing tmux
sessions.

Public files:

```text
schemas/AgentMap.schema.yaml
examples/agentmaps/research.yaml
examples/agentmaps/council.yaml
```

Preview without touching tmux:

```bash
hover-agentmap-viewer examples/agentmaps/research.yaml --plan --json
hover-agentmap-viewer examples/agentmaps/council.yaml --plan --json
```

### Internal Tools Not In The OSS Artifact

| Tool | Why internal |
|------|-------------|
| `agent_signal` | `tap=True` triggers tmux/qwenLOOK — requires live council sockets |
| `agent_reply` | Fires tmux `wait-for` release channel — requires live tmux sessions |
| `council_round` | Fan-out dispatch to live AgnosticCouncil tmux sessions |
| `bus_rewind` | Moves cursors backwards — global mutation risk in shared workspaces |
| `web_search` | External network access — off by default, needs provider config |

The export does not copy these modules. They are absent from the published
package, not merely hidden behind a runtime flag.

---

## 3. Workspace Layout Contract

`hover_init` creates this layout under the declared root:

```
root/
  .hovernet/
    hovernet.json                         ← manifest (single source of truth)
    agents/
      <agent_name>/
        shared_intel/
          signal_bus/
            signals.jsonl                 ← append-only signal bus
            cursors/
              <agent_name>.cursor         ← line-number cursor (starts at 0)
    sessions/
      <loop_name>/
        README.md                         ← runnable example thread
        active/                           ← active thread/session folders
        closed/                           ← completed thread/session folders
        completions/                      ← proof-of-work artifacts land here
        inbox/                            ← optional brief drop folder
```

**hovernet.json** is the public contract. Tools should resolve agent buses, cursors,
and session roots through the manifest rather than constructing paths manually.
The manifest schema:

```json
{
  "manifest_version": "0.1",
  "created_at": "<ISO8601>",
  "updated_at": "<ISO8601>",
  "root": "/absolute/path/to/root",
  "workspace_dir": "/absolute/path/to/root/.hovernet",
  "profiles": ["public"],
  "agents": {
    "<agent_name>": {
      "role": "agent",
      "bus_path": "/absolute/.hovernet/agents/<agent>/shared_intel/signal_bus/signals.jsonl",
      "cursor_path": "/absolute/.hovernet/agents/<agent>/shared_intel/signal_bus/cursors/<agent>.cursor"
    }
  },
  "loops": {
    "<loop_name>": {
      "name": "<loop_name>",
      "agents": ["<agent_name>", ...],
      "session_dir": "/absolute/.hovernet/sessions/<loop_name>",
      "active_dir": "/absolute/.hovernet/sessions/<loop_name>/active",
      "closed_dir": "/absolute/.hovernet/sessions/<loop_name>/closed",
      "completions_dir": "/absolute/.hovernet/sessions/<loop_name>/completions",
      "inbox_dir": "/absolute/.hovernet/sessions/<loop_name>/inbox"
    }
  }
}
```

**Path resolution rule:** All public tools resolve paths under the declared workspace
root. Paths that escape (e.g. via `../` traversal) are rejected with an error.

---

## 4. Signal Envelope Schema

Every signal written to a bus must be a single JSON object on one line. Required fields:

| Field | Type | Description |
|-------|------|-------------|
| `signal_id` | string | Unique identifier. Format: `<TYPE>-<THREAD>-<TIMESTAMP>` |
| `type` | string | Signal type, e.g. `TASK_DISPATCH`, `BUILDER_UNLOCK`, `COUNCIL_DONE` |
| `from` | string | Sender agent name. This is a label, not authentication — see trust note below |
| `to` | string | Target agent name |
| `timestamp` | string | ISO8601 UTC, e.g. `2026-05-09T12:00:00Z` |

Optional fields (include when relevant):

| Field | Type | Description |
|-------|------|-------------|
| `contract_path` | string | Path to the contract file this signal unlocks |
| `thread` | string | Research thread identifier |
| `round` | string or integer | Round label within a thread. Council uses canonical `R1` and `R2`; numeric helpers may be kept separately when needed. |
| `notes` | string | Short human-readable description |
| `loop_id` | string | Loop name this signal belongs to |

**Size limit:** Signal objects must not exceed 64 KB serialized. Larger payloads
belong in a file referenced by `contract_path`, not in the signal itself.

**Malformed signals:** A line that is not valid JSON is skipped by `bus_read` with
a parse error in the result. It does not corrupt the bus — the cursor still advances
past it on ack.

**Trust note:** `from` is a label only. The bus has no authentication. Any agent
with write access to the bus file can set any `from` value. Do not make trust or
authorization decisions based on the `from` field alone.

---

## 5. Cursor and Completion Semantics

### Cursors

A cursor file contains a single integer: the number of lines the agent has already
consumed from its bus. Line counting is 1-based (cursor=0 means nothing read yet).

```
bus_read returns lines [cursor+1 ... total_lines]
bus_ack(advance_by=N) writes cursor + N back to the cursor file
```

`bus_read(..., advance=True)` is equivalent to reading the pending rows and then
advancing the cursor by the number of rows returned.

**Single-writer constraint:** Only one process should write to a given cursor file
at a time. The bus itself is append-only (multi-writer safe), but the cursor file
is not. If your workflow has concurrent readers, use external file locking or
assign one agent per cursor.

**Cursor protection:** One agent cannot advance another agent's cursor unless the
manifest explicitly grants that relationship. In public mode there is no mechanism
for cross-agent cursor mutation.

### Completions

After processing a signal, write a completion artifact to the session's `completions/`
directory:

```
completion_write(
    root="/path/to/your/project",
    loop_name=loop,
    agent="<agent>",
    signal_id="<signal_id>",
    content="summary of work",
    status="DONE"
)
```

Completions are the proof-of-work record. They are never deleted. If a signal was
blocked or failed, write a completion with `status: BLOCKED` and a reason.

---

## 6. Versioning and Compatibility Rules

- **`manifest_version`** is a string following semver minor versioning. Current: `"0.1"`.
- Tools check `manifest_version` and warn if the major version differs from their
  expected version. They do not fail hard on minor version differences.
- **New agents/loops** can be added to an existing manifest by calling `hover_init`
  again — idempotent by design.
- **New tool parameters** are added with defaults. Callers that omit them get the old
  behavior.
- **Breaking changes** bump the major version and require a migration step documented
  in `CHANGELOG.md`.
- **Bus format is append-only JSONL.** Old signals are never modified. New fields may
  be added to future signals; consumers must tolerate unknown fields.

---

## 7. Public Export Rules

### What public profile enforces

1. **No arbitrary path access.** All reads and writes resolve under the declared
   workspace root. The server rejects any path that traverses above root via `../`
   or absolute path substitution.

2. **No tmux/qwenLOOK side effects.** The exported package does not contain the
   live tap helper modules.

3. **`from_agent` is a label, not authentication.** This is documented in the signal
   schema and must be communicated to callers. Do not build authorization logic on it.

4. **Signal size cap.** Signals exceeding 64 KB are rejected before bus write.

5. **Cursor protection.** `bus_ack` only advances the cursor for the agent whose
   cursor file is passed. Cross-agent cursor mutation requires the manifest to
   explicitly model the relationship — it is not available in public profile.

6. **JSONL writes.** `signal_send` appends one line at a time. Treat each bus as
   append-only and keep each cursor single-writer unless you add external locking.

7. **Public-only entrypoint.** The exported console script points to
   `hovertools.public_server:main`.

### Enforcement point

The public release gate is the export allowlist plus
`scripts/oss_loop_release_sanity.py`. Internal modules are not copied into the
artifact, and the generated `pyproject.toml` points the console script at
`hovertools.public_server:main`.

This means:
- A public-mode server cannot expose internal tools via a crafted MCP call.
- The MCP `tools/list` response cannot include modules that are not shipped.
- Moving from OSS loop kit to product runtime requires the private product layer.
