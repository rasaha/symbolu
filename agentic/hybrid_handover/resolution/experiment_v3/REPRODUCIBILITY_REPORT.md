# REPRODUCIBILITY_REPORT — Edge Prioritization Experiment v0.1

- **Deterministic:** True — no LLM, no training, no inference-time RNG.
- **Repetitions:** 2; **byte-identical:** True.
- **Lock:** all v0.3 sources + the v0.2 experiment (proposal + validation) + the v0.1
  experiment + frozen platform were content-hashed before the first hidden
  evaluation (HIDDEN_EVALUATION_LOCK_V3.md); `lock_v3.verify()` reports zero drift.
- **P0 faithfulness:** with prioritization disabled, the resolver reproduces v0.2
  exactly on visible and hidden.
- **Structural invariants confirmed empirically:** discovery precision/recall,
  classification, governance Mode G, packet Mode P, and unsafe answers are identical
  across P0–P4 (the layer never touches the discovery graph, Mode G, or Mode P).
- **Calibration:** the visible corpus contains no multi-governance-source
  competition, so P1–P4 leave every visible metric unchanged; no correct visible
  decision is altered.

Re-running
`python -m agentic.hybrid_handover.resolution.experiment_v3.run_prioritization_experiment`
reproduces PRIORITIZATION_RESULTS.json exactly; `make_reports_v3` is a pure function
of that output.
