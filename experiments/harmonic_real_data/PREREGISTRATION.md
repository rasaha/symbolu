# Harmonic summaries on real demand — Preregistration

**Question:** do continuous fixed-harmonic summary tokens improve a quadratic
reader's prediction of real Azure Functions demand over ordinary statistical
summaries and daily seasonal-naive forecasting, using the two-memory design —
continuous summary tokens plus retrievable minute-level raw evidence, with no
inferred event bottleneck?

**Status:** preregistered after data acquisition and provenance recording
(`PROVENANCE.md`), before any implementation and before inspecting any
held-out-period content. Frozen at the commit introducing this file. Hardware:
4 CPU cores, no GPU; verdicts capped at PROVISIONALLY SUPPORTED.

**Contracts:** nothing under `symbolu/lightweight_phase/` is imported or
modified; the collector is never called Phase; no inferred event bottleneck;
all non-claim contracts of `experiments/phase_temporal_collector` and the
closed `harmonic_event_collector`/`_v2` carry forward. The trace spans 14
days: harmonic claims are restricted to **intraday and daily** structure; no
weekly-period claim is made or implied. The dataset never enters Git.

## Data construction (deterministic)

Function identity = (HashOwner, HashApp, HashFunction). Minute counts
concatenated d01…d14 → 20,160 minutes; a function absent from a day's file has
zero invocations that day. Demand series: 15-minute bins by summation → 1,344
bins (96/day). Modeling and metrics operate on log1p(bin sum). Minute-level
counts are preserved as retrievable raw evidence.

**Contiguous split (frozen):** train = days 1–8 (bins 0–767); development /
model freeze = days 9–10 (bins 768–959); held-out = days 11–14 (bins
960–1343), evaluated exactly once.

**Eligibility and cohort (train days only, frozen before any held-out
inspection):** a function is eligible iff, on d01–d08: active (≥1 invocation)
on ≥7 of 8 days; nonzero in ≥40% of the 768 train bins; mean ≥2
invocations/bin; log1p-bin variance ≥0.05; and coefficient of variation of bin
counts ≥0.1. Cohort: stratify eligible functions into quintiles by total train
invocations; within each quintile take the 40 functions with lexicographically
smallest HashFunction → **N = 200 frozen functions**, committed as
`frozen_functions.json` before the development period is used for anything.

## Task, queries, metrics

At query bin t (history = bins < t, plus minute-level evidence < t), predict
log1p of summed invocations over the next H bins for **H ∈ {1, 4, 12}**
(15/60/180 minutes; one model, three heads). Held-out queries: t ∈ {960, 964,
…, 1332} (every 4th bin; 94 queries/function). Dev and training queries come
only from their own periods (train t ∈ [96, 756]).

**Subject-level aggregation (frozen):** per function f, horizon h, arm a:
MSE in log1p domain over f's queries; nMSE_f = MSE_f / Var_f, with Var_f the
variance of f's own held-out log1p targets at h. Functions with Var_f < 0.01
at a horizon are excluded from that horizon for ALL arms identically and their
count reported (coverage accounting). Models answer every query — no
abstention; coverage is 100% of included function-queries by construction.
Headline statistics: **median across functions of nMSE_f** and **win
fraction** (share of included functions where arm a beats arm b). Pooled
averages are reported but gate nothing.

## Arms

Deterministic baselines: **P `persistence`** (predicted sum = sum of the H
bins immediately before t) and **N `seasonal_naive`** (sum of the same H bins
96 bins = 24 h earlier).

Reader arms (shared 2-layer pre-norm quadratic transformer, d=64, 4 heads;
query token = bin-of-day cos/sin + horizon encoding; total parameters matched
across reader arms to <1% via FFN width; seeds {0, 1, 2}; identical training
data, steps, and optimizer):

- **S `stats_reader`:** statistical summary tokens — decayed mean/variance/
  trend of log1p bin counts at timescales γ ∈ {0.9, 0.98, 0.995} (3 tokens).
- **HS `harmonic_reader`:** S + fixed-harmonic tokens — decayed complex
  accumulators of log1p counts at periods **{4, 8, 16, 32, 48, 96} bins**
  (1, 2, 4, 8, 12, 24 h; intraday + daily only), decay horizon 4 periods,
  features [normalized magnitude, cos θ, sin θ, clock-angle cos/sin, period
  code] (6 tokens).
- **SR `stats_retrieval`:** S + the retrieval tokens below.
- **HR `harmonic_retrieval`:** HS + the identical retrieval tokens.

**Retrieval budget (frozen): 6 tokens per query**, deterministic, identical
machinery in SR and HR, all computed from minute-level raw evidence before t:
2 recency tokens (for each of the last 2 bins: log1p of mean/max/std/last of
its 15 minute counts + relative-time code) and 4 anomaly tokens (the 4 bins in
the trailing 96 with the largest |log1p(bin sum) − seasonal median|, where the
per-bin-of-day seasonal median is computed on train days only and frozen;
features: log1p bin sum, anomaly score, bin-of-day cos/sin, relative time,
log1p minute-level max).

**Spike queries (for the retrieval question, frozen):** held-out queries whose
target window contains ≥1 bin with actual count ≥ 3× that function's frozen
train seasonal median for its bin-of-day AND ≥ 10 invocations.

## Development envelope (frozen)

Implementation internals — tokenizer details, reader sizing, training
hyperparameters (steps, batch, learning rate, selection cadence), retrieval
scoring internals — may be iterated using train + dev data ONLY, until a
freeze commit that closes development. Frozen now and not iterable: the
gates, split boundaries, eligibility rule and cohort procedure, arm list,
metric and aggregation definitions, retrieval budget (6 tokens), harmonic
period set, parameter matching, seeds, spike definition, and the one-shot
held-out rule. The held-out period is evaluated exactly once, after the
freeze commit.

## Gates (frozen; RI = relative improvement of median nMSE, lower is better)

- **V-GATE (validity of the reader setup):** at H=180 min, S beats P with win
  fraction ≥ 0.55 and RI ≥ 0.03, in 3/3 seeds. Failure → INVALID AT TESTED
  SCALE (readers did not train usefully); no harmonic verdict issued.
- **H-GATE (harmonic credit):** HS beats EACH of {S, P, N} at BOTH H=60 and
  H=180 min, each comparison with win fraction ≥ 0.55 AND RI ≥ 0.03, in 3/3
  seeds. H=15 min is reported informationally (persistence is expected to be
  strong at the shortest horizon and is not gated there).
- **S-GATE (raw evidence on irregular spikes; independent of H-GATE):** on
  spike queries at H=15 and H=60 min, HR beats HS with win fraction ≥ 0.55
  and RI ≥ 0.03 in 3/3 seeds (SR vs S reported informationally).

**Outcomes:** V fails → INVALID AT TESTED SCALE. V passes, H fails → harmonic
summaries NOT SUPPORTED on real demand at tested scale (the synthetic Sweep 3
G1 result stands but is shown not to transfer under these gates). H passes →
PROVISIONALLY SUPPORTED on real data. S-GATE is read solely as the
raw-evidence-retrieval claim, pass or fail. All outcomes: no weekly claims,
no Phase claims, no reversal of any closed experiment.
