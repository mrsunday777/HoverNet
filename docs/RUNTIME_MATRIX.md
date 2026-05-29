# HoverNet v1.5 Runtime Matrix

Research and Council are the free canonical HoverNet loops.

They are packaged as loop templates with runtime adapters, not as four copied
loop folders. The loop is the enduring primitive. The runtime is the transport
that keeps that loop alive.

## Canonical Free Loops

| Loop | Purpose | Why It Ships Free |
| --- | --- | --- |
| Research | Multi-agent proposal, critique, and synthesis over a target question or codebase. | This is the original knowledge-production loop that made HoverNet useful. |
| Council | Multi-agent independent analysis, blind peer review, and final verdict. | This is the original decision-quality loop and should stay available by virtue. |

## Runtime Adapters

| Runtime | Purpose | Best Fit |
| --- | --- | --- |
| Tap | Terminal/tmux wake transport for SDK agents that do not expose a durable monitor primitive. | Cross-runtime support, high-model access, mixed harness fleets. |
| Monitor | Persistent scanner/watch transport for harnesses with a native background monitor. | File-event recovery, quiet autonomous loops, scanner-driven self-sustain. |

Tap is not lesser. Monitor is not lesser. They solve different constraints.

The monitor path was originally tied to the strongest harness. That made it
valuable, but it also made the loop too dependent on one harness. Tap evolved
because excluding better model access was not acceptable. The public kit should
give users both shapes.

## Package Shape

```text
loops/
  research/
    loop.yaml
    workflow.md
    roles/
      proposer.md
      critic.md
      synthesizer.md
    contracts/
      brief.example.yaml
      signal.example.json
      completion.example.md
    runtimes/
      tap/README.md
      monitor/README.md

  council/
    loop.yaml
    workflow.md
    roles/
      chairman.md
      advisor.md
    contracts/
      brief.example.yaml
      signal.example.json
      completion.example.md
    runtimes/
      tap/README.md
      monitor/README.md
```

This matrix provides four runnable modes without duplicating the loop:

```text
Research + Tap
Research + Monitor
Council + Tap
Council + Monitor
```

## Research Tap Proof Contract

Research tap mode is part of v1.5 because the proof path is explicit:

- proposer receives the brief signal and writes `proposer.md`
- proposer completes before handing off to critic
- critic verifies the proposer artifact and writes `critic.md`
- critic completes before handing off to synthesizer
- synthesizer writes `consensus.md`
- synthesizer either closes the thread or writes the next-round frontier

Do not accept a Research run that advances a cursor without an artifact and a
completion marker for the step it consumed.

## Council Tap Proof Contract

Council tap mode is part of v1.5 because the two-round proof path is now
explicit:

- chairman dispatches round work to every advisor
- advisors write their round artifact before signaling completion
- advisors mark the artifact complete
- advisors emit `COUNCIL_DONE.round` as canonical `R1` or `R2`
- chairman audits every completion record before verdict

Do not accept numeric round drift in a public Council run. Numeric values can be
kept as helper metadata, but the semantic `round` field is the canonical label.

## Public Packaging Rule

Do not copy raw live loop workspaces into the open-source package.

The shipped loop templates must be sanitized:

- no private runtime state
- no live bus files
- no cursor files
- no ack files
- no completed session artifacts
- no local operator paths
- no model credentials
- no launch history
- no agent memory logs

Runtime state is created by the user when they initialize a workspace.

## Product Boundary

The free kit gives users local loop civilization:

- roles
- workflow contracts
- signal envelopes
- bus/cursor/completion primitives
- tap runtime adapter docs
- monitor runtime adapter docs

The private product keeps managed runtime hosting, app experience, account
pairing, production transport, and commercial onboarding.
