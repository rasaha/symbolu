# TAP-E3 — Changelog

## v3 (Relationship Truth — initial research & falsification phase)

**Added** a self-contained TAP-E3 track under
`truth_assurance_pipeline/tap_e3_relationship_truth/`. It imports TAP-E1 (`IntentRecord`)
and TAP-E2 (`RetrievalRecord`, evidence-unit structures) through their frozen public
interfaces and modifies neither.

- `ontology.py` — versioned 49-type relationship ontology, families, inverses, predicate
  lexicon.
- `schema.py` — versioned `RelationshipRecord` / `RelationshipAssertion` /
  `RelationshipConflict` / `RelationshipGap` with all dimensions separated.
- `normalization.py`, `polarity.py`, `modality.py`, `temporality.py` — deterministic
  dimension detectors.
- `extractor.py` — 15-stage pipeline + A–F baselines + gap detection + processing trace.
- `conflict.py`, `confidence.py`, `validator.py`.
- `metrics.py` — per-dimension metrics + independent critical failures.
- `harness.py` — E1→E2→E3 driver, dev-only selection, preregistered gates, verdict.
- `loader.py` — gold-free public loader.
- `corpus/` — NEW independent corpus (14 docs / 32 units / 29 cases).
- `experiments/` — `run_experiment.py`, `preregistration.json`, `results_v3.json`,
  `experiment_lock.json`.
- `tests/test_tap_e3.py` — 27 behavioral tests.

**Result:** selected baseline **F** (the simplest satisfying all preregistered gates — the
conflict/gap/severe gates require it); all eleven gates pass on the locked eval; verdict
**`PASS_WITH_LIMITED_CLAIM`**.

**Findings:** co-occurrence (A) is unsafe (invents relationships, inverts authorization);
predicate-keyword (B) reverses passives and drops negation/modality; normalization (C)
fixes direction; polarity/modality (D) preserve negation and `must`≠`may`; temporality/
scope/conditions (E) complete per-assertion structure and preserve upstream gaps; only the
full pipeline (F) detects cross-evidence conflicts and reaches zero severe failures.

**Honesty:** synthetic corpus; deterministic pattern-based extraction over parseable
sentences (not general NLU); locked **development** evaluation inspected during iteration.
Mechanism/construction validation only. TAP-E1 and TAP-E2 are unchanged. Next layer:
**TAP-E4 — Governance Truth**.
