# TAP-E2 — Changelog

## v2 (Trusted Retrieval — initial research & falsification phase)

**Added** a self-contained TAP-E2 track under
`truth_assurance_pipeline/tap_e2_trusted_retrieval/`. It imports TAP-E1 through its
public interface (an `IntentRecord` in) and modifies nothing in TAP-E1 or TAP-E1.1.

- `evidence_unit.py` — `EvidenceUnit`/`Document`/`EvidenceProvenance`, authority &
  document-type enums (evidence units, not documents).
- `schema.py` — versioned `RetrievalRecord`, `RetrievalQuery`, multidimensional
  `RetrievalConfidence`, `RankingSignals`, `RetrievalGap`/`GapType`, validator.
- `chunking.py` — sentence chunker + idf-ready concept lexicon (deterministic semantic
  stand-in) with light depluralization.
- `index.py` — lexical inverted index + idf-weighted concept-vector cosine.
- `provenance.py` — provenance attachment.
- `ranking.py` — interpretable multi-signal ranking (lexical, semantic, authority,
  freshness, provenance, specificity, redundancy).
- `retrieval.py` — the 9-stage pipeline + A–F baseline configuration + gap detection.
- `metrics.py` — retrieval metrics + independent critical-failure reporting.
- `harness.py` — E1→E2 driver, dev-only selection, preregistered gates, verdict.
- `loader.py` — gold-free public loader.
- `corpus/` — NEW synthetic enterprise corpus (14 docs / 32 units / 30 queries).
- `experiments/` — `run_experiment.py`, `preregistration.json`, `results_v2.json`,
  `experiment_lock.json`.
- `tests/test_tap_e2.py` — 21 behavioral tests.

**Result:** selected baseline **F** (full pipeline; E is effectively tied); all six
preregistered gates pass on the locked eval split; verdict **`PASS_WITH_LIMITED_CLAIM`**.

**Findings:** hybrid retrieval beats keyword/semantic alone on ranking; provenance
filtering removes unsourced evidence (provenance completeness → 1.0); gap detection is
what eliminates hidden conflicts and surfaces missing/no-authoritative evidence; the full
pipeline only marginally edges the simpler gap-detecting hybrid.

**Honesty:** synthetic corpus; "dense semantic retrieval" is a deterministic
concept-vector stand-in (not embeddings); results are mechanism validation only.
TAP-E1 and TAP-E1.1 are unchanged.
