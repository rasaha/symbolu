# Interoperability Report — Implementations A and B on TAP-E7-BASE v1.1.1

## Common ground (verified)
- Same normative package `tap-e7-base-companion-1.1.1` (commit a876ce4).
- Same runtime config fingerprint, each **recomputed independently**: `d01e466e…`.
- Same mandatory corpus (86 authoritative fixtures).

## Observable agreement
Implementation A (Python, class-based) EXACT_PASS 86/86 vs v1.1.1. Implementation B (JavaScript,
functional pipeline) EXACT_PASS 86/86 vs v1.1.1. Because both match the same expected oracle on
outcome, findings, polarity, correspondence stage, evaluation-summary counts, projection Π, and Π
hash, they agree with **each other** on all 86 fixtures: **agreement 86/86, disagreements 0**
(reports/implementation-a-vs-b-observable-comparison.json).

Both pass deterministic replay independently; neither mutated the package.

## Verdict: **2 — interoperability substantially demonstrated, with one explicitly listed bounded limitation**
The technical interoperability is complete: two independently authored codebases in different
languages, run blind, recompute the same fingerprint and produce identical mandatory outputs with
zero divergences. The single bounded limitation is **authorship**: A and B share one author, so this
establishes *language + architecture* interoperability, not *organizational* independence. Genuine
third-party authorship is the remaining step to reach unqualified interoperability.

(Per §35, the corpus builder, packaging validator, and auditors are NOT counted as implementations.)
