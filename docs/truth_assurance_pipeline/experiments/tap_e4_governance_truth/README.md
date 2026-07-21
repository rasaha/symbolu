# TAP-E4 — Governance Truth (docs index)

The fourth TAP research layer. Given `IntentRecord` (E1), `RetrievalRecord` (E2), and
`RelationshipRecord` (E3) — all via frozen public interfaces — plus an explicit governance
`Situation`, it resolves **which documented authority governs the situation, and why**.

- Verdict: **`PASS_WITH_LIMITED_CLAIM`** (selected baseline **F**, all 14 gates pass on the
  locked eval).
- Scope: *which documented authority controls here* — **not** claim truth, factual
  correctness, a user answer, retrieval, relationship discovery, or enforcement.

## Documents

| Doc | Contents |
|---|---|
| [EXPERIMENT_REPORT](EXPERIMENT_REPORT.md) | objective, method, results, verdict, next layer |
| [ARCHITECTURE](ARCHITECTURE.md) | pipeline position, boundary, 13 stages, determinism |
| [SCHEMA](SCHEMA.md) | `GovernanceRecord` and all sub-structures |
| [CORPUS](CORPUS.md) | 30 cases / 15 families, construction, ground truth, locking |
| [METRICS](METRICS.md) | metric definitions, gates, ablation ladder |
| [FAILURE_ANALYSIS](FAILURE_ANALYSIS.md) | critical-failure classes, why each baseline is unsafe, limits |
| [LEAKAGE_AUDIT](LEAKAGE_AUDIT.md) | leakage controls, determinism, upstream integrity, future validation |
| [CHANGELOG](CHANGELOG.md) | what was added in v4 |

## Reproduce

```bash
python -m truth_assurance_pipeline.tap_e4_governance_truth.experiments.run_experiment
python -m pytest truth_assurance_pipeline/tap_e4_governance_truth/tests/ -q
```

## Integrity

TAP-E1/E1.1/E2/E3 unchanged (byte-identical; consumed through frozen public interfaces).
Full regression: 124 tests pass. Deterministic across `PYTHONHASHSEED ∈ {0,1,7,42,123}`.
`frozen_components_hash = 9e44afd7…`, `eval_inputs_hash = c28e23f3…`.

**Next layer: TAP-E5 — Evidence Packet.**
