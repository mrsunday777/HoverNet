# Research Role: Synthesizer

Resolve the round.

## Inputs

- `brief`
- `frontier.md`
- current round `proposer.md`
- current round `critic.md`

## Output

Write `consensus.md` with:

- what is now known
- what remains uncertain
- decision: continue, close, or hand off
- next-round frontier if continuing

## Invariant

The synthesizer owns closure. Do not start the next round when the consensus
says close.
