# TAP-E3 — Corpus

A **new, independently authored** synthetic enterprise corpus. TAP-E2 query annotations
are **not** reused as relationship gold; TAP-E2 evidence structures are used only as the
upstream interface (each case builds a `RetrievalRecord` from its own evidence units).

- **14 documents / 32 evidence units / 29 cases** — dev 17, eval 12.
- Sources span policies, SOPs, contracts, technical specs, design docs, regulatory text,
  manuals.
- Gold allows ontology-equivalent predicates (`acceptable_predicates`) and multiple
  normalized forms; scoring separates exact-triple, ontology-equivalent, and
  partial-structure evaluation.

## Case families (required types covered)

direct explicit · passive voice · negation · modality (may/must/should) · conditional ·
exception · temporal supersession · value conflict · ontology conflict · co-occurrence
distractor · attribution (alleges → ALLEGED, not fact) · nested/coordinated · historical
(previously…but now) · scope · duplicate consolidation · distributes-not-owns · upstream
retrieval-gap preservation · future applicability · structural (part_of) · governance
signal (requires).

## Ground truth

Each gold relationship carries subject, predicate (+acceptable set), object, direction,
polarity, modality, temporality, scope, conditions, exceptions, explicitness, supporting
evidence units, and prohibited predicates (e.g. `distributes` must **not** be read as
`owns`). Cases also carry `expected_conflicts` and `expected_gaps`.

## Splits & locking

`dev` (development) and `eval` (locked development evaluation). The eval inputs are
content-hash locked (`eval_inputs_hash`); a future independent holdout is left as a
placeholder (see LEAKAGE_AUDIT / EXPERIMENT_REPORT §9).
