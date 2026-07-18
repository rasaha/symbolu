# Mock Data Regimes

Deterministic **MOCK_TEST_ONLY** fixtures (`mockdata.py`) for **branch + integrity
testing**. Each encodes a known ground truth so a code path can be exercised. These are
NOT a biometric dataset, and algorithms are **not tuned to recover every regime
perfectly** — the goal is to verify the machinery, not to prove any method works.
Every record/fixture is marked `data_origin = MOCK_TEST_ONLY`, so verdicts can only emit
`*_PATH_VERIFIED` / `*_NO_SCIENTIFIC_VERDICT`.

## Cohort regimes (feature-record cohorts)

| regime | what is encoded |
|---|---|
| `NO_SIGNAL` | no user structure in any modality → all arms ≈ chance |
| `KEYBOARD_ONLY_SIGNAL` | user identity in keyboard marginals only; pointer is noise |
| `POINTER_ONLY_SIGNAL` | user identity in pointer marginals only |
| `MULTIMODAL_MARGINAL_SIGNAL` | user identity in BOTH marginals; no coupling |
| `COUPLING_ONLY_SIGNAL` | marginals are noise; per-user coupling in the real coupling stats only |
| `COUPLING_PLUS_MARGINAL_SIGNAL` | user identity in marginals AND coupling |
| `DEVICE_CONFOUND` | apparent identity is DEVICE-bound; collapses across devices |
| `TASK_CONFOUND` | apparent identity is TASK-bound; collapses task-disjoint |
| `SAMPLING_ARTIFACT` | coupling "signal" survives the shuffle control (marginal/sampling artifact) |
| `SPARSE_ACTIVITY` | marginal signal present but low event counts (quality-limited) |

Coupling statistics carry an independent 4-dim per-user vector (one per statistic:
lagged xcorr, zero-lag xcorr, event correlogram, windowed CCA). Controls: `__shuf`
(time-shuffled — destroys cross-modal alignment, keeps marginals) and `__ctxm`
(context-matched shuffle — keeps task-forced coupling). Context-conditioned coupling =
`real − ctxm`.

## Estimator / score fixtures

| regime | encoding |
|---|---|
| `BCVF_HELPFUL` | two same-latent estimators; genuine users CONSISTENT, impostors DISAGREE → disagreement adds info |
| `BCVF_REDUNDANT` | strong joint estimators; disagreement adds nothing |
| `BCVF_HARMFUL` | disagreement is noise (does not help the joint) |
| `FUSION_HELPFUL` | two weak modalities with INDEPENDENT noise → fusion beats best single |
| `FUSION_REDUNDANT` | shared noise → fusion ≈ best single |
| `CONFIDENCE_WELL_CALIBRATED` | scores = true P(genuine), stationary → held-out ECE low |
| `CONFIDENCE_MISCALIBRATED` | held-out half drifts to constant over-confidence over uninformative labels → uncalibratable |
| `ABRUPT_TAKEOVER` | score stream drops sharply at a known onset |
| `SLOW_TAKEOVER` | score stream ramps down slowly from onset |
| `LEGITIMATE_DRIFT` | gradual benign drift, no takeover (no true change point) |

## Notes on branches not cleanly reachable from mock data

Some branches (`BCVF_REGRESSES`, `USER_SPECIFIC_COUPLING_SMALL_EFFECT`,
`DEVICE_BOUND_COUPLING_ONLY`) depend on effect sizes/CIs that a well-behaved model does
not always produce from a stub. These branches are exercised via **pure-classifier unit
tests over fabricated measured numbers** (`tests/`), which is legitimate — it tests the
decision function, not a data verdict — and avoids manufacturing a positive result from
mock data.
