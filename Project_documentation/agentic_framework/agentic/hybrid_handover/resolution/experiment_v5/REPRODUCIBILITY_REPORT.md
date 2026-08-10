# REPRODUCIBILITY_REPORT — Competing Operative Resolution Experiment v0.1

## Table 1 — calibration gates

| gate | pass |
|---|---|
| C0_control_identity | True |
| C1_discovery_identity | True |
| C2_classification_identity | True |
| C3_validation_identity | True |
| C4_governing_set_identity | True |
| C5_g3_operative_identity | True |
| C6_modeP_identity | True |
| C7_visible_non_degradation | True |
| C8_cooccurrence_safety | True |
| C9_genuine_conflict_activation | True |

## Table 2 — protected-stage identity (C0–C4)

| stage | identical |
|---|---|
| discovery P/R/F1 | yes |
| classification | yes |
| proposal-validation records | yes |
| governing set (Mode G) | yes |
| G3 operative selection | yes |
| packet Mode P | yes |

## Table 19 — reproducibility

| property | value |
|---|---|
| deterministic | True |
| repetitions | 2 |
| byte-identical reps | True |
| all calibration gates pass | True |
| all 5 G3 fixes retained | True |

- No LLM, no training, no inference-time RNG. Lock: v0.5 sources + specs + v0.4/v0.3/
  v0.2/v0.1 + frozen platform content-hashed before the first hidden evaluation
  (COMPETING_OPERATIVE_HIDDEN_LOCK.md); `lock_v5.verify()` reports zero drift, and all
  four prior locks verify clean.
- C0 reproduces G3 bit-for-bit; the synthetic fixtures (C8/C9) prove the genuine-conflict
  machinery abstains only on genuine conflict and never on co-occurrence alone.
