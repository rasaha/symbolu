# REPRODUCIBILITY_REPORT — Proposal Validation Experiment v0.1

- **Deterministic:** True — no LLM, no training, no inference-time RNG.
- **Repetitions:** 2; **byte-identical:** True.
- **Bootstrap:** fixed seed 20240601, 10000 iters (reused from v0.1 `stats.py`, unchanged).
- **Lock:** all v0.2 sources + the v0.1 experiment + frozen platform were
  content-hashed before the first hidden evaluation (HIDDEN_EVALUATION_LOCK_V2.md);
  `lock_v2.verify()` reports zero drift.
- **V0 faithfulness:** with validation disabled, the resolver reproduces Hybrid
  v0.1 exactly on both visible and hidden corpora (identical discovery,
  classification, governance, packet, selective, coverage, unsafe).
- **Calibration provenance:** the two floors (lexical 0.6, structural 0.5) and every
  rule were fixed on the visible corpus, where V4 rejects zero correct edges.

Re-running
`python -m agentic.hybrid_handover.resolution.experiment_v2.run_validation_experiment`
reproduces VALIDATION_RESULTS.json exactly; `make_reports_v2` is a pure function of
that output.
