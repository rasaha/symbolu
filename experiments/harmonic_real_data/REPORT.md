# Harmonic summaries on real demand — Report

Protocol: `PREREGISTRATION.md` (frozen at 0ffc22f9, before implementation);
provenance: `PROVENANCE.md`; cohort frozen from train days only at 010468f5;
development closed by the freeze commit 7ec237ff before any held-out
inspection. Hardware: 4 CPU cores, no GPU; micro scale.

**Disclosure:** the first invocation of the held-out evaluator crashed on
harness bugs (a baseline off-by-one that NaN'd t=1332 and an arm-dispatch
key error) before printing any metric value; the fixes touched only the
evaluation harness — frozen models, metric definitions, and gates unchanged —
and were committed before the successful run. The held-out period's metrics
were computed and revealed exactly once.

## Gate outcomes

| Gate | Requirement (each in 3/3 seeds) | Result |
|---|---|---|
| **V — validity** | stats reader beats persistence at 180 min (win ≥ 0.55, RI ≥ 0.03) | **PASS** — win 0.74–0.78, RI 0.37–0.41 |
| **H — harmonic credit** | harmonic reader beats stats reader, persistence, AND seasonal-naive at 60 and 180 min (win ≥ 0.55, RI ≥ 0.03 each) | **PASS** — all 18 comparisons clear: win 0.61–0.83, RI 0.18–0.54 |
| **S — raw-evidence retrieval on spikes** | harmonic+retrieval beats harmonic on spike queries at 15 and 60 min | **FAIL** — win 0.41–0.56, RI −0.11 to +0.03 |

**Verdict: continuous fixed-harmonic summary tokens are PROVISIONALLY
SUPPORTED on real demand data** — the synthetic Sweep 3 G1 result transfers
to the Azure Functions 2019 trace under subject-level gates (per-function
win fractions and median nMSE, never pooled averages). The 6-token
raw-evidence retrieval, as specified, is NOT SUPPORTED as a spike remedy at
this scale.

## Held-out numbers (d11–d14, one-shot; median across functions of
per-function nMSE in log1p domain; readers seed-averaged; lower is better)

| Arm | 15 min | 60 min | 180 min |
|---|---|---|---|
| persistence | 0.694 | 0.587 | 1.028 |
| seasonal-naive (daily) | 1.103 | 0.864 | 0.772 |
| stats reader | 0.529 | 0.499 | 0.632 |
| **harmonic reader** | **0.499** | **0.398** | **0.491** |
| stats + retrieval | 0.532 | 0.475 | 0.625 |
| harmonic + retrieval | 0.504 | 0.405 | 0.487 |

Coverage (preregistered accounting): 176 / 169 / 165 of the 200 frozen
functions included at the three horizons (variance-floor exclusions applied
identically to every arm); models answered every query — no abstention.
Spike-query functions: 39 / 80 / 102 per horizon. Memory/items: reader arms
attend over 4–16 tokens per query versus 96+ bins of raw history; the
harmonic addition is 6 tokens (12 complex accumulators of state per function).

## Reading the result

- **The harmonic win is broad, not pooled.** At 60 and 180 minutes the
  harmonic reader beats plain statistical summaries for ~73–83% of functions,
  and both deterministic baselines for ~61–82%, consistently across seeds. At
  the ungated 15-minute horizon it is also the best arm (0.499), though the
  margin over stats is smaller — as expected where recency dominates.
- **Both baselines are beaten on their home turf**: persistence at short-mid
  horizons and daily seasonal-naive at the daily-structure horizon. The
  harmonic tokens' value is precisely intraday+daily rhythm (periods 1–24 h);
  no weekly claim is made or possible from a 14-day trace.
- **Retrieval as specified adds nothing on spikes.** With harmonic summaries
  present, the 4-anomaly+2-recency token budget neither helps nor
  catastrophically hurts (RIs −0.11 to +0.03, win ≈ 0.5). The two-memory
  *principle* is not refuted — this tests one small, fixed retrieval design at
  one budget — but this design earns no credit, and the S-GATE is reported as
  the failure it is.

## Non-claims

Harmonic claims are restricted to intraday and daily structure. The collector
is a classical fixed-frequency mechanism, not Phase; nothing here validates
the frozen Phase equations, reverses `experiments/phase_lc`, or upgrades any
closed experiment. Verdicts are capped at PROVISIONALLY SUPPORTED: one trace,
one 200-function cohort, 4 held-out days, micro-scale readers (~69K params).

## Standing conclusions for the program (after all five experiments)

1. Continuous fixed-harmonic summaries improve a quadratic reader over
   ordinary statistics — supported on synthetic streams (Sweep 3 G1) **and
   now on real cloud demand (this experiment, H-GATE)**.
2. Learned Phase and learned-oscillator collectors: NOT SUPPORTED at tested
   scale (Sweep 3 G2'/G3).
3. Event-bottleneck eventization at 100× compression: NOT SUPPORTED
   (harmonic_event_collector V1+V2, closed permanently).
4. Raw-evidence retrieval at a 6-token budget for spike robustness: NOT
   SUPPORTED at tested scale (this experiment, S-GATE).

The natural strengthening steps — a larger cohort, additional traces, and a
redesigned spike-retrieval mechanism under a new preregistration — are owner
decisions and are not begun here.

## Cohort 2 — strict disjoint replication (PREREGISTRATION_COHORT2.md)

Owner-ratified replication on a second 200-function cohort (identical
eligibility rule, Cohort 1 excluded, 4,178 remaining eligible), with every
frozen definition, budget, and gate unchanged; development closed at commit
3d63060a before Cohort 2's single held-out evaluation.

**Cohort 2 results, reported separately (frozen order):**

- **V-GATE: PASS** (win 0.71–0.77, RI 0.22–0.30, 3/3 seeds).
- **H-GATE: PASS — the replication succeeds.** All 18 preregistered
  comparisons clear again: harmonic reader vs stats reader (win 0.70–0.82,
  RI 0.10–0.30), vs persistence (win 0.77–0.81, RI 0.14–0.45), vs daily
  seasonal-naive (win 0.61–0.81, RI 0.35–0.56), at both 60 and 180 min, 3/3
  seeds.
- **S-GATE: FAIL again** (win 0.46–0.61, RI −0.11 to +0.07) — the 6-token
  retrieval's null result on spikes also replicates.

Cohort 2 median nMSE (15/60/180 min): persistence 0.603/0.510/0.988 ·
seasonal-naive 1.141/0.926/0.839 · stats reader 0.516/0.504/0.734 ·
**harmonic reader 0.513/0.428/0.542** · stats+retrieval 0.497/0.496/0.716 ·
harmonic+retrieval 0.475/0.429/0.541. Coverage: 168/162/159 of 200 functions
per horizon.

**Aggregation (after separate reporting; `results/aggregate_cohorts.json`):**
pooled per-function win fractions over the ~320–340-function union are
0.75–0.82 for the harmonic reader vs stats reader and vs persistence at both
gated horizons, and 0.61–0.64 vs seasonal-naive at 180 min — consistent with
each cohort individually.

**Updated standing conclusion 1:** continuous fixed-harmonic summaries
improve a quadratic reader over ordinary statistics, persistence, and daily
seasonal-naive on real cloud demand — **replicated across two disjoint
cohorts** under one-shot held-out discipline. Still PROVISIONALLY SUPPORTED
(one trace, 14 days, micro-scale readers); no Phase, semantic-understanding,
production-readiness, or cross-dataset claims.

## Spike Retrieval 2 (PREREGISTRATION_SPIKE_RETRIEVAL2.md) — S2-GATE: **FAILED
in both cohorts; the spike-retrieval question closes**

Motivating diagnostic (train days only, committed first): 81–86% of
train-period spikes show recurrence structure within 72 h
(`results/spike_predictability.json`) — the information exists.

The three ratified changes (spike-upweighted training for all arms, signed
anomaly tokens with time-since-previous and last inter-anomaly gap, 72 h
lookback; 6-token budget unchanged) were implemented, frozen at 7cb5e4bf, and
evaluated once per cohort. Result: harmonic+retrieval vs harmonic on spike
queries — Cohort 1 win 0.31–0.59 with RI −0.28 to +0.11; Cohort 2 win
0.36–0.54 with RI −0.34 to −0.02. **Every gated cell misses the unchanged
thresholds (win ≥ 0.55 AND RI ≥ 0.03 per seed); most are negative.**

Informational observations, gating nothing: stats+retrieval vs stats was
mixed-positive in Cohort 1 (win up to 0.79) but negative in Cohort 2 —
seed- and cohort-unstable. Spike-upweighted training also degraded overall
(uniform-query) accuracy for all arms relative to the original runs (e.g.,
harmonic reader 60-min median nMSE 0.398 → 0.477 in Cohort 1); per the
preregistration H-GATE is settled on the original runs and none of this
re-litigates it.

**Reading.** The diagnostic says the recurrence signal exists; two design
generations say a 6-token retrieval feeding a ~69K-parameter reader cannot
convert it into spike-query forecast gains — and the upweighting change
bought spike emphasis at a real cost to overall accuracy without delivering
the spike win. Per the frozen outcome clause: raw-evidence retrieval for
spikes is **NOT SUPPORTED at tested scale under this design family**, any
further attempt requires new ratification, and the held-out days are spent
for the spike question. The honest suspects for a future, differently-shaped
attempt (larger readers, richer retrieval interfaces, or explicit
point-process modeling of spike timing) are recorded here without being
started.

**Final gate ledger for this experiment:** V ✓ (both cohorts) · H ✓ (both
cohorts, settled) · S ✗ (v1, both cohorts) · S2 ✗ (both cohorts, closed).
