# Research Loop Workflow

The Research Loop turns a question into successive rounds of evidence.

## Roles

- `proposer` finds new evidence and frames a thesis.
- `critic` verifies, challenges, and identifies what the proposer missed.
- `synthesizer` resolves the round into consensus, next-round frontier, or close.

## Round Shape

```text
brief
  -> proposer.md
  -> critic.md
  -> consensus.md
  -> next round or close
```

Each round writes proof before advancing the cursor. Every handoff is a signal
plus an artifact path. Runtime adapters decide how agents wake; the workflow
does not depend on one model provider or harness.

## Completion Contract

Research rounds require one proof artifact per role:

- proposer: `proposer.md`
- critic: `critic.md`
- synthesizer: `consensus.md`

Each role writes its completion marker before advancing or handing off. The
synthesizer closes the thread only after proposer and critic proof exists for
the round it is resolving.

## Close Conditions

The synthesizer closes the thread when one of these is true:

- the question is answered with enough evidence
- the next action should move to an implementation loop
- the loop needs human review before continuing

## Runtime Adapter Choice

Use `runtimes/tap` when agents are hosted in terminals and need explicit wake.
Use `runtimes/monitor` when the harness supports a persistent scanner/watch
primitive.
