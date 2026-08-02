# Model Selection — Rollback

This migration is low-risk to revert: it is behavior-preserving (byte-identical equivalence, PATCH API),
touches no frozen component, and adds a package + a compatibility surface rather than rewriting logic.

## Full rollback (revert the branch)

The cleanest rollback is to not merge, or to `git revert` the migration commits. Because the product-core
modules were moved with `git mv` (tracked as renames), reverting restores them to `execution_gate/` with
their original imports and removes the canonical package and the compatibility `__init__.py`.

Commits (in order):
1. `model-selection: establish canonical package and legacy compatibility surface`
2. `model-selection: migrate consumers to canonical core; classify research`
3. `model-selection: add packaging and equivalence verification`
4. `model-selection: publish migration evidence and validation`

`git revert <c4> <c3> <c2> <c1>` (newest first) returns the tree to the pre-migration state.

## Partial rollback (keep the package, restore legacy imports)

If only the consumer repointing needs reverting (e.g. an external consumer pins the legacy path), revert
just commit 2's edits to `control_plane/adapters.py` and
`governed_inference_pilot/adapters/execution_gate.py`; they will import via the `execution_gate`
compatibility surface again, which resolves to the same canonical objects. No behavior change either way.

## Verification after rollback

- `python -m pytest execution_gate execution_gate_shadow control_plane control_plane_shadow governed_inference_pilot`
- `python execution_gate/frozen/replay_v1/verify_frozen.py` (aggregate `8b05b2da798a6222`)
- `python -m platform_freeze.verify` (digest `d4ad77e16516e0db6bf2faf3275c8ac8351644e7561d33f157bb55b5a174a1a6`)

## Safety properties that make rollback cheap

- No frozen artifact, API snapshot, or Governance Contract was modified.
- The equivalence capture (`equivalence_before.json` == `equivalence_after.json`) documents that
  behavior is identical in both directions, so a rollback cannot silently change results.
- The compatibility surface means un-migrated consumers keep working whether or not the rollback happens.
