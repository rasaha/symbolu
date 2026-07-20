# CORPUS_CURATION_PROTOCOL — Relationship Corpus Curation Specification v1.0

**Phase:** hidden-corpus curation + blind pilot expansion. SEEB v1.0.0, Hybrid
Handover, retrieval benchmarks, baseline extractors, Relationship Measurement
Spec v1.0, resolver interfaces, deterministic resolvers, the visible development
corpus, the existing 22 hidden seed cases, and the seed annotations are all
unmodified (verified). No resolver run; no resolver performance reported. All
data synthetic.

## Purpose
Establish a trustworthy, reproducible process for expanding the hidden corpus
without author bias, annotation inconsistency, duplicate reasoning templates, or
hidden leakage — then use it for a limited blind pilot expansion.

## The pipeline
```
DRAFT → AUTHOR_COMPLETE → READY_FOR_BLIND_ANNOTATION → ANNOTATED
      → READY_FOR_ADJUDICATION → {ACCEPTED | REJECTED | QUARANTINED}
```
Only ACCEPTED cases enter the hidden pilot executable corpus. No stage is skipped
(`schema.validate_path`). Three logically separate role artifacts (Author /
Independent Annotator / Adjudicator) are projected from each candidate.

## Steps
1. **Author (Role A)** writes question, documents, intended capability, proposed
   difficulty, and a private rationale (+ private intended graph).
2. **Blind annotation (Role B)** produces a graph, governance, expectation,
   abstention, ambiguity, confidence, and per-edge evidence provenance — WITHOUT
   the author rationale or intended graph (enforced by `blinding.py`).
3. **Adjudication (Role C)** compares A and B, computes the final difficulty from
   the deterministic rubric (authors never assign it), and ACCEPTS / REJECTS /
   QUARANTINES with a recorded rationale.
4. **Gates** (see CORPUS_ACCEPTANCE_REPORT.md): lifecycle, blinding, agreement,
   duplicate/template, difficulty, gold sufficiency, answer-position bias,
   leakage. A case is accepted only if all pass (with documented adjudicator
   overrides where a near-structural match is a deliberate contrastive pair).

## Reproducibility
Every artifact and audit is deterministic (content-hash ids; no randomness);
repeated builds are byte-identical. `run_curation.py` regenerates
`CURATION_AUDIT.json`.

## Versioning
- This specification: **Relationship Corpus Curation Specification v1.0**.
- The expanded corpus: **Hidden Relationship Corpus Pilot v0.2** (prerelease).
- The original 22-case seed is preserved as an immutable subset (unchanged).
- The corpus is explicitly NOT called RRB v1.0.
