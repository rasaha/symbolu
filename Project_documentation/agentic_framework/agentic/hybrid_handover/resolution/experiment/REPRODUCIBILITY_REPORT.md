# Reproducibility Report

- **Deterministic:** yes (no LLM, no training, no RNG except the fixed-seed bootstrap).
- **Repetitions:** 2 full runs.
- **Byte-identical across repetitions:** yes.
- **Bootstrap:** fixed seed 20240601, 10000 iterations, recorded in the manifest.
- **Lock:** all resolver/metric/stat/prereg sources and frozen dependencies were
  content-hashed before the first hidden evaluation (HIDDEN_EVALUATION_LOCK.md).
  `lock.verify()` reports zero drift.
- **Run order:** fixed comparator order recorded in the manifest.

Re-running `python -m agentic.hybrid_handover.resolution.experiment.run_experiment`
reproduces EXPERIMENT_RESULTS.json exactly; `analyze` and `make_reports` are pure
functions of that output.
