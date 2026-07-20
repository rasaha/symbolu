# Hidden Corpus Curation + Pilot Expansion (audit-only)

A validated, reproducible process for expanding the hidden relationship corpus
(roles A/B/C, blinding, lifecycle, agreement, anti-template, difficulty rubric,
gold sufficiency, answer-position bias, leakage) plus a blind pilot expansion.
Runs no resolver; reports no resolver performance. Touches nothing frozen. All
data synthetic.

## Run
```bash
python -m agentic.hybrid_handover.resolution.hidden_corpus.curation.run_curation
python -m pytest tests/test_hidden_corpus_curation.py -q
```

## Result
- **CURATION PIPELINE VALIDATED** (all gates pass; deterministic).
- Pilot: 43 authored → 38 accepted / 4 rejected / 1 quarantined.
- Combined hidden corpus: 22 seed + 38 pilot = **60** (seed immutable).
- Every capability ≥3 total; L5 = 5; every negative-control category ≥3.
- Corpus is **Hidden Relationship Corpus Pilot v0.2** — NOT sufficient to certify
  broad generalisation (conservative floor ~300–600 cases).

## Docs
`CORPUS_CURATION_PROTOCOL.md` · `ROLE_SEPARATION_AND_BLINDING.md` ·
`CANDIDATE_LIFECYCLE.md` · `ANNOTATION_SCHEMA.md` · `ADJUDICATION_PROTOCOL.md` ·
`ANNOTATOR_AGREEMENT.md` · `DIFFICULTY_RUBRIC.md` ·
`DUPLICATE_AND_TEMPLATE_AUDIT.md` · `ANSWER_POSITION_BIAS_AUDIT.md` ·
`PILOT_EXPANSION_REPORT.md` · `UPDATED_CAPABILITY_COVERAGE.md` ·
`CORPUS_ACCEPTANCE_REPORT.md` · `LEAKAGE_VERIFICATION_PILOT.md`
