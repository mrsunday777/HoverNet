# Council Loop Workflow

The Council Loop improves decisions by separating first-pass judgment from peer
review.

## Roles

- `chairman` frames the question, dispatches rounds, waits for proof, and writes
  the final verdict.
- `advisor` gives independent analysis in round 1 and blind peer review in round
  2.

## Round Shape

```text
question
  -> round 1 independent advisor responses
  -> round 2 blind peer review
  -> chairman_verdict.md
```

The chairman does not substitute for missing advisor work. If an advisor artifact
is missing, the loop surfaces the failure instead of faking consensus.

## Completion Contract

Council rounds use canonical labels:

- first advisor round: `R1`
- peer-review round: `R2`

Advisor completion signals must preserve the label in `round`. Numeric helper
metadata is allowed, but it must not replace the canonical field. Chairman only
writes `chairman_verdict.md` after every expected advisor artifact, completion
marker, and completion signal is present for the thread.

## Runtime Adapter Choice

Use `runtimes/tap` for explicit terminal wake and return channels. Use
`runtimes/monitor` for scanner-driven council lanes where advisors self-detect
new round work.
