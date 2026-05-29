---
name: RepoLoopWatch
description: Public HoverNet v1.5 research-loop watcher. Scans a local .hovernet workspace for bus signals, inbox briefs, and ready research artifacts.
---

# /RepoLoopWatch

Use this after every Research loop handoff, or whenever a research agent has no
immediate work.

This public skill is read-only. It does not write artifacts or advance cursors.
It reports the next event the agent should handle:

- `NEW_BUS`
- `NEW_BRIEF`
- `READY_WORK`
- `IDLE`

## One-Shot Check

```bash
hover-loop-watch \
  --root "<workspace-root>" \
  --loop-name "research" \
  --loop-type research \
  --agent "proposer" \
  --once \
  --json
```

Agent aliases are accepted:

- `RepoProposer` -> `proposer`
- `RepoCritic` -> `critic`
- `RepoSynthesizer` -> `synthesizer`

## Continuous Watch

Use this only when your harness supports a persistent watch task:

```bash
hover-loop-watch \
  --root "<workspace-root>" \
  --loop-name "research" \
  --loop-type research \
  --agent "proposer" \
  --watch \
  --poll-sec 30 \
  --json \
  --quiet-idle
```

Replace `proposer` with `critic` or `synthesizer`.

## Event Handling

`NEW_BUS`: read the emitted `.signal`, process exactly that signal, write the
required artifact, then ack the cursor after proof exists.

`NEW_BRIEF`: create or ingest one new active thread from the emitted inbox file.
Keep inbox intake single-threaded.

`READY_WORK`: write the emitted `expected_output` inside the emitted
`round_dir`, then write completion proof before handoff.

`IDLE`: no actionable work was found.

## Rule

The watcher detects work. It does not replace the role's reasoning and it does
not manufacture proof.
