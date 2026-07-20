# HIDDEN_CORPUS_SPECIFICATION — SEEB Hidden Relationship Corpus

**Phase:** benchmark-corpus hardening. SEEB v1.0.0, Hybrid Handover, retrieval
benchmark, baseline extractors, Relationship Measurement Specification v1.0,
resolver interfaces, the existing deterministic resolvers, and the visible
development corpus are all unmodified (verified). No benchmark score changed. No
resolver was run or optimised. All data synthetic.

## Purpose
Determine whether the relationship benchmark can certify **generalisation** rather
than cue memorisation. The 16 visible development cases are for debugging; this
hidden corpus is for evaluation, under substantial linguistic and structural
variation.

## Hard separation (executable vs private)
The corpus is split into two views that never mix:

| View | Module | Contents | Who may read it |
|---|---|---|---|
| Executable | `corpus.py` | opaque id, question, documents | resolvers (evidence only) |
| Private | `annotations.py` | gold graph, governance, expectation, justification, confidence, ambiguity, difficulty, capability | evaluation/audit only |

A resolver is handed only `evidence_for(id)` (spans) or `executable_cases()`
(id + question + documents). It can never reach an annotation. Ids are SHA-1
content hashes (`HX…`) encoding nothing about the answer, capability, or
difficulty. See LEAKAGE_VERIFICATION.md.

## Case format (authored, private)
Every case records: question, documents, `capability[]`, `difficulty` (1–5),
`variation[]`, gold `nodes`/`edges`, `governing`/`abstain`, `expectation`,
`governance_explanation`, `author_justification`, `confidence`, `ambiguity`,
`negative_control`.

## Coverage (this seed corpus)
- **22 cases**, difficulty 1–5 (3/4/7/6/2).
- **All 24 capabilities** present (0 uncovered); 13 currently single-example.
- **All 9 governance edge types** present.
- **11 of 13 variation dimensions** present (missing: `sentence_structure`,
  `clause_numbering`).
- **5 negative controls** (no-relationship, unresolvable-conflict, insufficient-
  evidence, circular-reference, multiple-valid-interpretations); **16 ambiguous**.

## Guarantees
- Integrity-clean (validate.py): every gold node is a real document citation;
  every edge references a gold node or an intentional dangling reference; abstain
  is consistent with expectation.
- Leakage-free (leakage.py): opaque ids, no metadata in the executable view, no
  banned/difficulty token in document surface, order uncorrelated with difficulty,
  no metadata accessor on the executable module.
- Deterministic and audit-only: never used to tune a resolver; reports no resolver
  performance.

## Status
This is a **seed** hidden corpus: broad capability coverage, but shallow depth
(many single-example capabilities). It is sufficient to *detect* cue-memorisation
and to seed a generalisation harness; it is **not yet** sufficient to *certify*
broad relationship generalisation (see the final assessment in
GENERALIZATION_PROTOCOL.md and CORPUS_STATISTICS.md).
