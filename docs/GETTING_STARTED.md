# Getting Started

This guide runs one local loop entirely on disk. It does not require hosted
infrastructure.

## 1. Install Locally

```bash
git clone https://github.com/mrsunday777/HoverNet.git
cd HoverNet
python3.11 -m venv .venv  # any Python >= 3.10 is fine
. .venv/bin/activate
python -m pip install -e .
```

## 2. Create A Workspace

```python
from hovertools import public_server as hover

root = "/tmp/hovernet-demo"

manifest = hover.hover_init(
    root=root,
    loop_name="demo",
    agents=["alice", "bob"],
)

print(manifest["manifest_path"])
```

This creates runtime state under:

```text
/tmp/hovernet-demo/.hovernet/
```

## 3. Send Work

```python
from hovertools import public_server as hover

root = "/tmp/hovernet-demo"

sent = hover.signal_send(
    root=root,
    target_agent="bob",
    signal_type="TASK_DISPATCH",
    payload={
        "from": "alice",
        "notes": "Review the local loop contract and write a short response.",
    },
)

print(sent["signal_id"])
```

## 4. Read And Ack

```python
from hovertools import public_server as hover

root = "/tmp/hovernet-demo"
manifest = hover.hover_manifest_read(root=root)["manifest"]
bob = manifest["agents"]["bob"]

pending = hover.bus_read(
    bus_path=bob["bus_path"],
    cursor_path=bob["cursor_path"],
    limit=10,
)

print(pending["pending"])

if pending["pending"]:
    hover.bus_ack(cursor_path=bob["cursor_path"], advance_by=1)
```

`bus_read` does not consume rows unless `advance=True` is passed. The explicit
ack step makes the proof path visible.

## 5. Write Completion Proof

```python
from hovertools import public_server as hover

root = "/tmp/hovernet-demo"

done = hover.completion_write(
    root=root,
    loop_name="demo",
    agent="bob",
    signal_id="TASK_DISPATCH-example",
    content="Reviewed the contract. Local bus, cursor, and completion proof are working.",
)

print(done["path"])
```

Completions are written under:

```text
/tmp/hovernet-demo/.hovernet/sessions/demo/completions/
```

## 6. Watch For Work

For a one-shot read-only watcher event:

```bash
hover-loop-watch \
  --root /tmp/hovernet-demo \
  --loop-name demo \
  --agent bob \
  --once \
  --json
```

The same scanner is available through MCP as `loop_watch_once`.

## Next

- Run the smoke test: `python -m unittest discover -s tests`.
- Run the basic example: `python examples/basic-loop/run_basic_loop.py`.
- Read `docs/PUBLIC_SURFACE.md` for the tool contract.
- Read `docs/RUNTIME_MATRIX.md` for Research/Council and Tap/Monitor.
- Use `loops/research` or `loops/council` as the template for your own local
  loop.
