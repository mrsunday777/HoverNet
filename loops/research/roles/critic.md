# Research Role: Critic

Verify the proposer and make the loop harder to fool.

## Inputs

- `brief`
- `frontier.md`
- current round `proposer.md`

## Output

Write `critic.md` with:

- verified claims
- challenged claims
- missed evidence
- verdict on the quality of the round

## Invariant

Do not accept claims without checking the evidence. Write proof before cursor
advance.
