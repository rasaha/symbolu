# Cross-dataset replication on the 2021 invocation trace — Preregistration

**Question:** does the harmonic-summary result of
`experiments/harmonic_real_data` (fixed-harmonic tokens beat statistical
summaries, persistence, and daily seasonal-naive for a quadratic reader on
real demand) replicate on an independent trace — different vintage (Jan
2021), different collection format (per-invocation arrivals), different
workload population?

**Status:** preregistered after provenance recording (`PROVENANCE.md`),
before any implementation and before inspecting held-out-period content;
frozen at the commit introducing this file.

**Inherited UNCHANGED from `experiments/harmonic_real_data/PREREGISTRATION.md`
(frozen at 0ffc22f9):** arm definitions (persistence, daily seasonal-naive,
stats reader, stats+harmonic reader, both + the original v1 retrieval),
harmonic periods {1, 2, 4, 8, 12, 24 h}, statistical timescales, token and
query definitions, log1p modeling domain, 15-minute bins, horizons
{15, 60, 180 min}, metric and subject-level aggregation (per-function nMSE,
median and win fraction; pooled averages gate nothing), variance floor,
training budget/optimizer/selection, parameter matching (<1%), seeds
{0, 1, 2}, the development envelope, and the one-shot held-out rule. The
trace is exactly 14 days, so the contiguous 8/2/4-day split carries over
with **no adaptation**.

## Declared adaptations (the only ones)

1. **Series construction from per-invocation records:** function identity =
   (app, func). Each invocation is assigned to the minute of its **arrival**
   (end_timestamp − duration, clipped into [0, 1,209,600)); minute counts are
   summed to 15-minute bins → 1,344 bins, exactly as in 2019. Minute-level
   counts remain the raw evidence for the retrieval arms.
2. **Cohort = ALL eligible functions** (no stratified subsample — the
   population is only ~424 (app, func) pairs, versus 64k in 2019) under the
   IDENTICAL eligibility rule, computed from train days d1–d8 only and frozen
   before any dev/held-out use. No second disjoint cohort is possible on this
   trace and none is claimed. **Cohort floor:** if fewer than 40 functions
   are eligible, the outcome is INVALID AT TESTED SCALE (too few subjects)
   and no gate verdicts are issued.

## Gates

**V-GATE and H-GATE: identical** to the 2019 experiment (V: stats reader
beats persistence at 180 min, win ≥ 0.55 and RI ≥ 0.03, 3/3 seeds; H:
harmonic reader beats each of stats reader / persistence / seasonal-naive at
both 60 and 180 min, win ≥ 0.55 and RI ≥ 0.03, 3/3 seeds).

**No spike-retrieval re-litigation:** the spike question is closed
(S and S2 failed; held-out days of the 2019 trace spent). The retrieval arms
are trained and evaluated here only because the arm list is inherited; all
retrieval and spike comparisons on this trace are **informational only and
gate nothing**.

**Reporting (frozen order):** 2021 results are reported separately first.
Only if BOTH datasets' H-GATEs pass may a cross-dataset statement be made,
and it must be labeled explicitly as a two-dataset claim (2019 + 2021,
Azure Functions only) — not a general one. If 2021's H-GATE fails, the
conclusion is that the 2019 result did not transfer to this trace, stated
without softening; the 2019 result itself is settled and is not re-litigated.

**Non-claims:** no Phase, semantic-understanding, or production-readiness
claims; intraday+daily structure only (14-day trace, no weekly claims);
dataset outside Git; verdicts capped at PROVISIONALLY SUPPORTED.
