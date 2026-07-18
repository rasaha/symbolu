# Instrumentation Thresholds (frozen)

Timing quality is the **first hard gate**. Thresholds are frozen in `config.py`
(`InstrumentationThresholds`) **before** pilot analysis. A session is graded
mechanically by `quality.analyze`:

- `INSTRUMENTATION_READY` — clears **every** ready bound below.
- `INSTRUMENTATION_DEGRADED` — fails a ready bound but clears every degraded bound.
- `INSTRUMENTATION_NOT_READY` — fails a degraded bound (or has no events).

A `NOT_READY` (and, for identity analysis, optionally `DEGRADED`) session is
**excluded from identity analysis with its failing metrics recorded** in the pilot
report's `excluded_sessions` — it is never silently dropped.

| metric | ready | degraded | meaning |
|---|---|---|---|
| `drop_rate` | ≤ 0.02 | ≤ 0.10 | dropped / (emitted + dropped) |
| `duplicate_rate` | ≤ 0.005 | ≤ 0.02 | duplicate (seq, modality, type, t) |
| `reorder_rate` | ≤ 0.005 | ≤ 0.02 | source-time or seq decreases |
| `jitter_ms` | ≤ 12 | ≤ 35 | MAD of periodic-stream sampling residuals |
| `quantization_ms` | ≤ 16 | ≤ 34 | finest distinct timestamp step (timer grid) |
| `clock_drift_ppm` | ≤ 500 | ≤ 2000 | monotonic-vs-source slope deviation |
| `source_to_receipt_ms` | ≤ 25 | ≤ 75 | median source→collector latency |
| `collector_overhead_ms` | ≤ 5 | ≤ 15 | receipt − monotonic per event |
| `session_seconds` | ≥ 20 | ≥ 10 | session duration |
| `n_events` | ≥ 200 | ≥ 80 | total events |
| `active_fraction` | ≥ 0.35 | ≥ 0.15 | 1 − idle/span |

Also reported (not gated): `modality_alignment` (fraction of span covered by ≥2
modalities), `sparse_gap_count`.

Notes:
- **Jitter** is measured on periodically-sampled streams (pointer move, motion) as the
  MAD of residuals from a linear fit of timestamp vs sample index — event-driven
  keyboard is irregular by nature and excluded.
- **Quantization** is the timer *resolution* (finest distinct step), so a coarse tick
  is caught independent of sample rate.

## Cohort verdict

`verdicts.instrumentation_verdict` aggregates a cohort: `READY` if ≥ 70% of sessions
are `READY`; else `DEGRADED` if ≥ 40% are at least `DEGRADED`; else `NOT_READY`.

## Practical effect thresholds (identity/coupling)

Frozen in `config.py` (`PracticalEffectThresholds`). Significance never suffices — a
favorable CI whose point effect is below threshold yields a **small-effect** outcome.

| threshold | value |
|---|---|
| `min_auc_improvement` (credit a signal) | 0.03 |
| `min_marginal_auc` (marginal clears chance+margin) | 0.60 |
| `min_detection_at_far_gain` @ `fixed_far`=0.05 | 0.05 |
| `max_false_challenge_increase` | 0.02 |
| `min_within_between_separation` | 0.10 |
| `ci_alpha` (two-sided bootstrap) | 0.05 |

## Minimum real-data sample (before any positive verdict)

Frozen in `config.py` (`MinimumSampleRequirements`): ≥ 10 participants, ≥ 3 sessions
each, ≥ 2-day span, ≥ 2 ready sessions/participant, ≥ 40 genuine trials, ≥ 20
same-task live-impostor trials, ≥ 8 usable windows/session. Below these, identity and
coupling verdicts return `*_INSUFFICIENT_DATA`.
