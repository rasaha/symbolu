# Conventional Baselines for SEEB v1.0.0

Strong-conventional reference extractors that every future HybridPhaseTransformer
is compared against — all behind the frozen `ExtractorProtocol`, all run through
the **unchanged** SEEB v1.0.0 benchmark. Nothing here modifies the handover
package or the benchmark.

## Extractors
`keyword` (frozen baseline) · `bm25` (Okapi BM25) · `embedding` (dense NN;
char-n-gram **fallback** — no neural model available) · `hybrid_retriever`
(BM25 ⊕ embedding). See [`EXTRACTOR_ARCHITECTURES.md`](EXTRACTOR_ARCHITECTURES.md).

## Run
```bash
python -m agentic.hybrid_handover.baselines.compare      # writes JSON + CSV, prints table
python -m pytest tests/test_hybrid_handover_baselines.py -q
```

## Deliverables
[`BASELINE_COMPARISON.md`](BASELINE_COMPARISON.md) ·
[`EXTRACTOR_ARCHITECTURES.md`](EXTRACTOR_ARCHITECTURES.md) ·
`COMPARISON_RESULTS.json` · `PER_CASE_RESULTS.csv`

## Headline finding (synthetic; embedding in fallback mode)
Query-conditioned retrieval closes the keyword extractor's **Definition Recall
(0%→100%)** and **Defeater Recall (60%→100%)** gaps, but **Precedence Recall is
unchanged (52.9% for all)** and every residual unsafe handover is a
precedence/relationship-reasoning failure — the capability a HybridPhaseTransformer
would need to move. Full analysis in `BASELINE_COMPARISON.md`.
