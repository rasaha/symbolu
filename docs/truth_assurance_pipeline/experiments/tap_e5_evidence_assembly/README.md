# TAP-E5 — Evidence Assembly (docs index)

The fifth TAP research layer. Given `IntentRecord` (E1), `RetrievalRecord` (E2),
`RelationshipRecord` (E3), and `GovernanceRecord` (E4) — all via frozen public interfaces —
it assembles one deterministic `EvidencePacket`: the **smallest complete, dependency-
preserving, provenance-preserving** object required by downstream claim validation.

- Verdict: **`PASS_WITH_LIMITED_CLAIM`** (selected baseline **F**, all 14 gates pass on the
  locked eval).
- Scope: *package the minimal complete evidence* — **not** truth determination, claim
  validation, response generation, retrieval, governance reasoning, conflict resolution, or
  gap filling.

## Documents

| Doc | Contents |
|---|---|
| [EXPERIMENT_REPORT](EXPERIMENT_REPORT.md) | objective, method, results, verdict, freeze, next layer |
| [ARCHITECTURE](ARCHITECTURE.md) | pipeline position, boundary, 14 stages, minimization contract, determinism |
| [SCHEMA](SCHEMA.md) | `EvidencePacket` and all sub-structures |
| [CORPUS](CORPUS.md) | 32 cases / 13 families, construction, independent gold, locking |
| [METRICS](METRICS.md) | metric definitions, gates, ablation ladder |
| [FAILURE_ANALYSIS](FAILURE_ANALYSIS.md) | critical-failure classes, why each baseline is unsafe, limits |
| [LEAKAGE_AUDIT](LEAKAGE_AUDIT.md) | leakage controls, determinism, upstream integrity, future validation |
| [CHANGELOG](CHANGELOG.md) | what was added in v5 |

## Reproduce

```bash
python -m truth_assurance_pipeline.tap_e5_evidence_assembly.experiments.run_experiment
python -m pytest truth_assurance_pipeline/tap_e5_evidence_assembly/tests/ -q
```

## Integrity

TAP-E1/E1.1/E2/E3/E4 unchanged (byte-identical; consumed through frozen public interfaces).
Full regression: 153 tests pass. Deterministic across `PYTHONHASHSEED ∈ {0,1,7,42,123}`.
`frozen_components_hash = 7a91bcf9…`, `eval_inputs_hash = 04b87570…`.

**EvidencePacket interface frozen. Next layer: TAP-E6 — Claim Validation.**
