# Release Checklist

Use this before publishing a new public HoverNet loop-kit release.

## Package Shape

- Public package is generated from the sanitized loop kit, not from a live
  workspace.
- Runtime state is absent: no bus rows, cursor files, ack files, completed
  session artifacts, local paths, or credentials.
- Research and Council templates are both present.
- Tap and Monitor runtime guides are both present for each loop.

## Proof Contracts

- Research tap docs include proposer, critic, and synthesizer completion proof.
- Council tap docs preserve canonical `R1` and `R2` labels.
- Signal schema docs allow string round labels where the loop contract requires
  them.

## Verification

```bash
python3 scripts/oss_loop_release_sanity.py <artifact-or-fresh-clone>
git diff --check
```

Expected result:

```text
status: PASS
findings: high=0 medium=0 low=0
```

## Release Assets

- Tarball is built deterministically.
- Published hash matches a freshly downloaded asset.
- Release notes describe what is included and what is intentionally not
  included.
