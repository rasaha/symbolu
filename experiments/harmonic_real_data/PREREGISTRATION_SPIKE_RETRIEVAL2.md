# Spike Retrieval 2 — Preregistration

**Question:** does a minimally redesigned raw-evidence retrieval pass the
unchanged S-GATE (retrieval improves spike-query forecasts) that the original
design failed in both cohorts? Motivated by the committed train-only
diagnostic (`results/spike_predictability.json`): 81–86% of train-period
spikes show recurrence structure within 72 h.

**Status:** preregistered before implementation; frozen at the commit
introducing this file. Owner-ratified scope: changes limited to the three
items below; same 6-token retrieval budget; S-GATE thresholds unchanged;
**H-GATE is settled and is not re-litigated** — overall (non-spike) medians
from the new runs are reported informationally only and gate nothing.

**Inherited unchanged** from `PREREGISTRATION.md` / `PREREGISTRATION_COHORT2.md`:
both frozen cohorts, splits (8/2/4 days), arms, seeds {0,1,2}, harmonic
periods, token definitions other than the anomaly tokens, metric and
subject-level aggregation, variance floor, spike definition, training budget
and optimizer, parameter matching, development envelope, one-shot held-out
rule (one evaluation per cohort of the newly frozen models).

## The three changes (the only changes)

1. **Spike-upweighted training queries** — applied to ALL FOUR reader arms
   identically, so the S-GATE comparison still isolates retrieval: 50% of
   each training batch's (function, t) pairs are drawn uniformly from queries
   whose 180-min target window contains a train-defined spike (spike set
   computed from train bins and the frozen train seasonal medians only); the
   other 50% uniform as before.
2. **Anomaly-token redesign (retrieval arms only):** anomalies are the top-4
   bins by |signed score| in the lookback, where signed score = log1p(bin) −
   train seasonal median (sign preserved: surge vs drought). Tokens are
   time-ordered a1..a4 with features [log1p value, signed score,
   relative time (a−t)/96, time since previous selected anomaly
   (a_j − a_{j−1})/96 (first token: lookback-edge sentinel 3.0), last
   inter-anomaly gap (a4 − a3)/96 (same on every token), log1p minute-level
   max]. Feature count per token unchanged (6); bin-of-day features are
   dropped from these tokens (the summary and query tokens already carry
   bin-of-day).
3. **Lookback 288 bins (72 h)** instead of 96 (24 h), matching where the
   diagnostic measured recurrence. Recency tokens and the 2+4 = 6-token
   budget unchanged.

## Gate (unchanged thresholds)

**S2-GATE:** on spike queries at H=15 and H=60 min, harmonic_retrieval beats
harmonic_reader with win fraction ≥ 0.55 AND median-nMSE RI ≥ 0.03, in 3/3
seeds — **in BOTH cohorts**. stats_retrieval vs stats_reader reported
informationally. Failure in either cohort = S2-GATE FAIL: raw-evidence
retrieval for spikes remains NOT SUPPORTED at tested scale under this design
family, and any further attempt requires new ratification.

**Declared limitation:** the held-out days (d11–d14) are the same physical
days evaluated by the original experiment; cross-experiment selection
pressure is bounded by preregistration-before-results but cannot be zero.
This is the second and, absent new ratification, last use of these held-out
days for the spike question.

**Non-claims:** no Phase, semantic-understanding, production-readiness, or
cross-dataset claims; intraday+daily structure only; dataset outside Git;
verdicts capped at PROVISIONALLY SUPPORTED.
