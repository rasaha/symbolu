# 2021 cross-dataset replication — Report

Protocol: `PREREGISTRATION.md` (frozen at 7fc725db, before implementation);
provenance: `PROVENANCE.md`.

## Outcome: **INVALID AT TESTED SCALE — cohort floor failed. No gate verdicts.**

Under the identical 2019 eligibility rule, computed from train days d1–d8
only, **6 of 424** (app, func) pairs are eligible — far below the
preregistered floor of 40 (`frozen_functions_2021.json`). Per the frozen
clause, no training was run and no V/H verdicts exist for this trace.

Eligibility waterfall (train days only, recorded for audit):

| Criterion (cumulative) | Pairs remaining |
|---|---|
| total (app, func) pairs | 424 |
| active ≥ 7 of 8 train days | 76 |
| + nonzero in ≥ 40% of train bins | 19 |
| + mean ≥ 2 invocations/bin | 15 |
| + log1p bin variance ≥ 0.05 | 6 |
| + CV ≥ 0.1 (full rule) | **6** |

The population is categorically different from 2019's: the median pair has
**3** total train-period invocations (99th percentile ≈ 58k) — this trace is
dominated by extremely sparse, bursty functions, and its ~424-pair population
cannot supply the subject count that the frozen subject-level gates (win
fractions across functions) require. Train-only sensitivity checks show even
aggressive relaxation (mean ≥ 0.25/bin, nonzero ≥ 10%) reaches only 42
pairs — at the floor, and measuring mostly-zero series rather than the
demand-forecasting population the 2019 experiment studied. **No relaxation
was applied**; changing the eligibility rule post-preregistration to
manufacture a cohort would alter what is being measured and is exactly what
the floor exists to prevent.

## What this does and does not mean

- The 2019 result (harmonic summaries beat statistics/persistence/seasonal-
  naive, replicated across two disjoint cohorts) is **settled and untouched**.
- **No cross-dataset claim is made** — the preregistered condition (both
  H-GATEs pass) cannot be evaluated on this trace, and the cross-dataset
  question remains open, not answered negatively: this is a subject-pool
  incompatibility, not a failed replication.
- The 2021 invocation trace remains a fine dataset for other questions
  (per-invocation timing, durations); it is simply not a suitable subject
  pool for this experiment's design.

Any further cross-dataset attempt requires a denser trace (many functions
with sustained per-bin activity) and new owner ratification. Non-claims
carried forward: no Phase, no semantic-understanding, no production-readiness
claims; dataset outside Git.
