# Rollback

The procurement extraction is designed to be **safely reversible**. Because the
legacy trees were reduced to logic-free facades and behavior is proven identical,
rolling back is a mechanical git operation with no behavioral risk.

## Why rollback is low-risk

- The canonical implementation and the legacy facades produce identical behavior:
  `before == canonical == legacy`
  (hash `541a5ab70af18e774e00cfc99986f87f96db7ccb2424478c20362527988a4336`).
- The `domains/procurement/` and `applications/procurement/` facades contain **no
  logic** — they only alias the canonical modules. Reverting them restores the
  original in-tree implementation exactly.
- The audit found **no** production or application consumers of the legacy paths
  outside the procurement test suite and two docs, so the consumer graph is clean.

## What rolling back involves

1. **Restore the original trees from git.** Check out the pre-extraction
   `domains/procurement/` and `applications/procurement/` trees at the recorded
   default tip (`b760c9e5440bc4572c9f3a197a682b0c95b53ad8`). This replaces the
   logic-free facades with the original implementation.
2. **Remove the extracted package.** Delete
   `packages/products/procurement/` (the `ugence-procurement` distribution).
3. **Remove the canonical dependency edge** if anything referenced
   `ugence-procurement`. Nothing outside the package does today.

Because the original source (`b760c9e5`) is the behavior baseline the capture was
taken against, the restored tree is byte-for-byte the pre-extraction implementation.

## What is safe

- **Safe:** removing the package and restoring the original trees — behavior is
  identical either way, so no consumer breaks.
- **Safe:** partial rollback of only the facades (keeping the package) — the
  legacy paths would then resolve to the restored in-tree code rather than the
  facade aliases; still behavior-identical, but avoid running both as owners of the
  same import names simultaneously.

## What to verify after rollback

- Run the procurement test suite (baseline: **33 passed**).
- Confirm no stale `ugence_procurement` imports remain in consumers.

Rollback does not touch the Decision Authority kernel, which was never modified by
the extraction.
