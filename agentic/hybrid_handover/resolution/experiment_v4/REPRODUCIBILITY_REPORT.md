# REPRODUCIBILITY_REPORT — Governance Semantics Experiment v0.1

## Table 1 — protected-stage identity (G0–G4)

| stage | identical across G0–G4 |
|---|---|
| discovery precision/recall/F1 | yes |
| classification | yes |
| proposal-validation records | yes |
| packet Mode P | yes |

## Table 14 — reproducibility

| property | value |
|---|---|
| deterministic | True |
| repetitions | 2 |
| byte-identical reps | True |
| G0 reproduces v0.2 | True |
| discovery identical | True |
| classification identical | True |
| validation records identical | True |

- No LLM, no training, no inference-time RNG (only the fixed-seed bootstrap).
- Lock: all v0.4 sources + specs + the v0.3/v0.2/v0.1 experiments + frozen platform
  were content-hashed before the first hidden evaluation
  (GOVERNANCE_SEMANTICS_HIDDEN_LOCK.md); `lock_v4.verify()` reports zero drift, and
  all four prior locks verify clean.
- Re-running `run_governance_experiment` reproduces the results JSON exactly;
  `make_reports_v4` is a pure function of that output.
