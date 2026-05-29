---
name: CouncilLoopWatch
description: Public HoverNet v1.5 council-loop watcher. Scans a local .hovernet workspace for council bus signals, inbox briefs, advisor work, and round completion.
---

# /CouncilLoopWatch

Use this after council dispatch, advisor completion, or whenever a council agent
has no immediate work.

This public skill is read-only. It reports:

- `NEW_BUS`
- `NEW_BRIEF`
- `READY_WORK`
- `ROUND_COMPLETE`
- `IDLE`

## One-Shot Check

```bash
hover-loop-watch \
  --root "<workspace-root>" \
  --loop-name "council" \
  --loop-type council \
  --agent "chairman" \
  --once \
  --json
```

For advisors, replace `chairman` with the advisor name registered in
`hovernet.json`.

## Continuous Watch

Use this only when your harness supports a persistent watch task:

```bash
hover-loop-watch \
  --root "<workspace-root>" \
  --loop-name "council" \
  --loop-type council \
  --agent "chairman" \
  --watch \
  --poll-sec 30 \
  --json \
  --quiet-idle
```

## Event Handling

`NEW_BUS`: process the emitted signal and only advance the cursor after proof
exists.

`NEW_BRIEF`: chairman should create one active council session from the emitted
brief file.

`READY_WORK`: advisor should write the emitted `expected_output` for the emitted
round.

`ROUND_COMPLETE`: chairman should verify advisor artifacts and then advance the
council round or write the final verdict.

`IDLE`: no actionable work was found.

## Rule

The watcher reports readiness. It does not substitute for missing advisor work.
