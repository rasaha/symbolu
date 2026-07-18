# Real-Data Eligibility

A **positive scientific verdict** is reachable only when ALL of the following hold. Any
failure keeps the outcome at a `*_PATH_VERIFIED` / `*_NO_SCIENTIFIC_VERDICT` /
`*_INSUFFICIENT_DATA` / `*_SMALL_EFFECT` state.

## 1. Data origin

`data_origin == REAL_PARTICIPANT` for every record. `SYNTHETIC_TEST_ONLY`,
`MOCK_TEST_ONLY`, and `DEMO_ONLY` are all non-real and can never produce a positive
verdict (`origin.py`; `verdicts.session_is_real`).

## 2. Sufficient real data (`effects.MinimumSamples`, frozen)

- ≥ 10 participants, ≥ 3 sessions each, ≥ 2-day span;
- ≥ 2 `INSTRUMENTATION_READY` sessions per participant;
- ≥ 40 genuine trials, ≥ 20 same-task live-impostor trials;
- ≥ 60 calibration samples; ≥ 200 events per session.

## 3. Favorable confidence interval

The primary contrast's participant-clustered bootstrap CI lower bound must exclude the
null.

## 4. Effect above the practical minimum (`effects.EffectThresholds`, frozen)

`min_auc_improvement = 0.03`, `min_tar_gain_at_far = 0.05` at `fixed_far = 0.05`,
`min_marginal_auc = 0.60`, `min_ece_improvement = 0.02`, `max_confidence_ece = 0.10`,
`min_ttd_reduction = 0.10`. A favorable CI whose point effect is below the minimum
yields a `*_SMALL_EFFECT` outcome, not a positive.

## 5. No critical regression

No increase in false challenges beyond `max_false_challenge_regression = 0.02` and no
calibration regression.

## 6. Artifact / confound gates passed

Signal must survive same-task same-device live impostors, must not vanish across devices
(device gate) or tasks (task gate), and must survive timestamp-perturbation checks.

## Preregistration

All of the above are frozen in `preregistration.py` (the machine-readable template)
before real data is analyzed. **No value may be silently selected after test results are
visible.** `preregistration.validate` refuses an under-specified config.

## Current status

No real participant data has been collected or analyzed. Every machinery branch is
implemented and tested on `MOCK_TEST_ONLY` fixtures; every real biometric claim remains
locked pending eligible human data.
