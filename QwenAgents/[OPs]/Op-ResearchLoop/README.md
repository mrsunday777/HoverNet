# Op-ResearchLoop

Karpathy-style 3-agent research loop. Proposer finds bugs, Critic verifies against actual code, Synth produces consensus and builder contracts.

## Structure

```
Op-ResearchLoop/
  config/          — thread registry, dispatch rules
  threads/         — research thread directories (one per target)
  rounds/          — research round output (proposer.md, critic.md, consensus.md)
  README.md        — this file
```

## How It Works

```
Proposer  →  Reads target codebase, proposes concrete findings
     ↓ signal dispatch
Critic    →  Verifies findings against actual code, catches false positives
     ↓ signal dispatch
Synth     →  Produces consensus, accepted findings → frontier.md
     ↓ signal dispatch (if CONTINUE)
Proposer  →  Next round (reads updated frontier, finds NEW findings only)
     ↓ ...loop until SATURATED...
Synth     →  Recommendation: CLOSE → loop ends naturally
```

## Threads

Each research target gets its own thread directory:

```
threads/<thread-name>/
  frontier.md      — accumulating accepted findings (Synth owns this file)
  rounds/
    001/
      proposer.md  — round 1 findings
      critic.md    — round 1 critique
      consensus.md — round 1 accepted/rejected verdicts
    002/
      ...
```

## Dispatch

Agents self-dispatch to the next role via the signal bus:

```bash
# Proposer dispatches to Critic
python3 examples/dispatch_example.py \
  --agent critic \
  --task "Critique round 001 proposer findings for thread <name>"

# Critic dispatches to Synth
python3 examples/dispatch_example.py \
  --agent synth \
  --task "Synthesize round 001 for thread <name>"

# Synth dispatches to Proposer (if CONTINUE)
python3 examples/dispatch_example.py \
  --agent proposer \
  --task "Propose round 002 for thread <name>, target <codebase>"
```

## Saturation

The loop ends naturally when:
- Synth finds zero new accepted findings in a round
- Saturation assessment is `SATURATED`
- Recommendation is `CLOSE`

No manual intervention needed — the chain just stops dispatching.

## Starting a Thread

1. Create thread directory: `mkdir -p threads/<name>/rounds/001`
2. Create empty frontier: `touch threads/<name>/frontier.md`
3. Add to registry: edit `config/registry.yaml`
4. Dispatch to Proposer with the target codebase path

## Registry

`config/registry.yaml` tracks all threads:

```yaml
threads:
  - name: my-thread
    target_project: /path/to/codebase
    status: ACTIVE
    created: 2026-03-28
```
