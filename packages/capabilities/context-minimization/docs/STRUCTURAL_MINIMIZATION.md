# Structural minimization (Mode A)

`structural_minimize(...)` / `deduplicate_context(...)`.

Removes exact-duplicate text and collapses **declared** redundancy sets, keeping one
representative. **Needs no oracle.**

## What "structurally lossless" means

Losslessness holds **by the declared structural contract**: every removed unit is a
duplicate of a retained unit carrying the same information — either

- an exact (whitespace/case-normalized) text duplicate of a retained span, or
- a member of a `redundancy_set` for which a representative is retained.

This is **narrower** than full Context Minimization. It is *not* authorization- or
semantics-preserving in any general sense — do **not** describe structural
deduplication alone as authorization-preserving Context Minimization. It makes no
claim about what a downstream model or oracle would decide; it only asserts that no
*distinct* information was dropped.

## Protected-span behaviour

A protected unit is never removed. Deduplication applies only to unprotected units.
A protected unit may act as the retained representative that makes an *unprotected*
duplicate removable; two protected duplicates are both retained. See
`PROTECTION_CONTRACT.md`.

## Determinism

Representative selection is first-in-source-order. Given the same context and
protected set, output ids and the result fingerprint are identical.
