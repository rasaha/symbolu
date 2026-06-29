# A_PRIME_READINESS — execution-readiness check (NOT an A′ run)

> GUARDED readiness check only. A′ remains canonically halted (no admissible, licensed, construct-aligned E×Y dataset). No data fabricated, no A′/B decision executed, no semantics, no PASS/FAIL/⊥ for Symbol-U. Stage A frozen.

> **DECISION: NOT_RUN**

## Missing inputs (checklist)

- E ratings table: path not configured
- semantic observable Y: path not configured
- phonology baseline features: path not configured
- license / data-use terms not acknowledged (A1.2 criterion 5)

## Building blocks ready to wire on data arrival

- experiments/a_prime/projection.py — A1.4 deterministic E→E′ projection (P)
- experiments/common/stats.py — ridge OOF R², shuffle/permutation/percentile nulls, bootstrap CI, BH-FDR
- experiments/b0_synthetic_harness/harness_operator.py — operator-aware probe + generic detector
- experiments/b0_synthetic_harness/harness.py — bag/bigram baselines + shuffle-null decision

## On READY_BUT_GATED

If inputs are present and licensed, A′/B execution still requires lifting the pre-registered gate per MILESTONE_A_PRIME_PREREGISTRATION(_AMENDMENT_1).md and the roadmap. This entrypoint hands off; it does not run the gated decision.

## Reproducibility metadata

| field | value |
|---|---|
| git_hash | bae437cb4dd7e2bdd0f5c2b79c75f50da06919cf |
| python | 3.11.15 |
| platform | Linux-6.18.5-x86_64-with-glibc2.39 |
| numpy | 2.4.6 |
| seed | None |
| runtime_s | 0.0 |

Config:
```json
{
  "version": 1,
  "e_path": "",
  "y_path": "",
  "phonology_path": "",
  "license_acknowledged": false,
  "endpoint": "size",
  "min_delta_r2": 0.01,
  "shuffle_pctl": 95.0,
  "n_eff_floor": 800
}
```

> structure, not validated meaning.
