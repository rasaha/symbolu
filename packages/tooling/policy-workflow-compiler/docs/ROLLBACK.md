# Rollback

This package is **additive**. It adds a new tooling package and its CI workflow;
it touches no frozen tree and modifies no existing product. Removing it is
therefore clean and complete.

## What was added

- The package directory
  `/home/user/symbolu/packages/tooling/policy-workflow-compiler/`.
- The associated CI workflow for the package.

Nothing outside these was changed. In particular, the Procurement product is not
modified (the equivalence harness only reads it), and no shared or frozen files
are edited.

## How to roll back

1. Delete the package directory
   `/home/user/symbolu/packages/tooling/policy-workflow-compiler/`.
2. Remove the package's CI workflow.

That is the entire rollback. Because the package installs outside the repository
and its distribution artifacts are self-contained, there are no side effects to
unwind elsewhere in the tree.

## Guarantees preserved by rollback

- **No frozen tree touched.** The addition never modified a frozen tree, so
  removal cannot corrupt one.
- **Freeze digest unchanged.** Because nothing in the frozen tree changed on the
  way in, the freeze digest is unchanged by the addition and remains unchanged
  after removal.
- **No cross-product impact.** No other product depends on this package at
  runtime; the optional `procurement-reference` extra is one-directional
  (compiler reads Procurement, never the reverse), so removing the compiler
  leaves Procurement and every other product exactly as they were.

Rollback is a pure subtraction: the tree returns to its prior state with no
migration, no data cleanup, and no digest change. See `PROCUREMENT_REFERENCE_VALIDATION.md`
for the read-only nature of the Procurement dependency and `INSTALL.md` for the
out-of-repo install property.
