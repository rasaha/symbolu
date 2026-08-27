# ADR — Cloud Scaling: Third-Baseline Replay Evaluation (preregistration)

**Status:** **PREREGISTRATION — NO BASELINE IS RATIFIED.** This document defines an
evaluation. It ratifies no forecaster, authorizes no implementation, and records no result.
**Date:** 2026-08-27
**Package (evaluated, not modified here):** `packages/capabilities/cloud-scaling-controller`
(`ugence-cloud-scaling-controller`, currently `0.4.0`)
**Governing ADR:** [`ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md`](ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md)
**Run manifest:** [`CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md`](CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md)
— preregistration template carrying the ratified thresholds; **manifest incomplete, run prohibited**,
with two run-blocking repository gaps recorded in its §10.

The governing ADR states that "a **third baseline is deliberately deferred** until replay evaluation on
representative data justifies it" and prohibits "neural networks, model services,
hyperparameter search, or automatic promotion".

> **Owner decisions authorize the evaluation design only. No third baseline is ratified.
> Ratification requires an authorized replay run to clear all applicable preregistered gates.**

> This is a design artifact. It creates no runtime code, adds no enum member, changes no
> schema or digest, accesses no telemetry, and runs nothing. Where it names a type, field or
> enum value as **proposed**, that is a design proposal, not a committed contract. Every
> contract it relies on as existing is cited by file in §13.

---

## 1. What this evaluates — and what it does not

This evaluates **classical clock-anchored harmonic regression**, derived from the frozen
Phase equations by fixing the phase angle to wall-clock time rather than learning it from
content.

It therefore **does not reverse, weaken, reopen or bear upon** any existing verdict
concerning learned content phases, neural Phase retrieval, BindingSlots or Phase-Quad.
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `E1_TEMPORAL_TRANSFER_PARTIAL` and
`KDA_VALIDATION_BLOCKED` are untouched by this document and by any outcome of the evaluation
it specifies. A pass here is evidence about a deterministic regression over timestamps and
nothing else; a failure here is likewise not additional evidence against neural Phase.

**No novelty is claimed.** Harmonic regression and seasonal-naive forecasting are textbook
methods. Nothing in this document proposes a new forecasting algorithm, and no result from
it may be presented as one. Any Ugence differentiation lies elsewhere: deterministic
evidence, typed abstention, leakage-safe replay, disclosed uncertainty and
execution-governance integration.

**Outcome neutrality.** Five outcomes are permitted and equally reportable: ratify H, ratify
N, ratify T, keep P alone with no third baseline, or ratify nothing pending better data
(§10). The design must not be re-run with adjusted periods, gates or windows to recover a
failed outcome.

## 2. Arms

Four arms. **Identical skeleton**: the same observations, the same cutoffs, the same
`FeatureConfig`, `AdmissionPolicy`, `UncertaintyConfig`, `NormalizationPolicy`,
`SeriesConstructionPolicy` and `match_tolerance_seconds`. Only the `BaselineForecaster`
differs. Any difference in configuration between arms invalidates the run.

| Arm | Identity | Predictor | Status |
|---|---|---|---|
| **P** | `persistence` (exists) | last observed value | reference denominator; the ADR's hard-to-beat baseline |
| **T** | `linear_trend` (exists) | closed-form OLS `value ~ a + b·t`, extrapolated | **evaluation-only control** |
| **N** | `seasonal_naive` (proposed) | value at `t* − P`, nearest in-window sample within the matching tolerance; abstains if none | **outcome-eligible control** |
| **H** | `harmonic_phase` (proposed) | joint OLS over `[1, t, cos φ, sin φ]` | candidate |

P and T exist today (`forecasting/forecasters.py:105`, `:121`). N and H do **not** exist and
are **not created by this document**.

### 2.1 H — normative definition

For a window of samples `(t_i, y_i)` at cutoff `c`, with the ratified daily period
`P = 86400` seconds and UTC-fixed clock semantics:

```
u_i  = (epoch(t_i) − epoch(c)) / P            # centred and scaled time coordinate
φ_i  = 2π · (epoch(t_i) mod P) / P            # UTC-fixed clock phase
X_i  = [ 1 , u_i , cos φ_i , sin φ_i ]
β    = argmin_β Σ_i ( y_i − X_i·β )²          # ONE joint ordinary least squares
ŷ(t*) = [ 1 , u* , cos φ* , sin φ* ] · β
```

The fit is **joint**: the constant, trend and harmonic coefficients are solved together in a
single 4×4 normal-equation system. The trend is part of H, not a preprocessing step.

**Explicitly not claimed.** Detrending separately and then accumulating a complex sum
`Σ y_i·e^{−iφ_i}` is **not** asserted to be equivalent to the above. It coincides only under
assumptions this data does not satisfy (uniform sampling, whole-cycle coverage, orthogonality
of the trend and harmonic bases over the window). A streaming accumulator is therefore a
**later optimization**, admissible only under a separately specified and separately verified
equivalence bound against this normative definition. This evaluation uses the joint OLS form.

### 2.2 Why T is in the ladder

H contains a trend term. Without T, a win by H over P and N could be caused entirely by that
trend term, and the harmonic component — the only reason this evaluation exists — would be
unjustified and unmeasured. T isolates it. H must beat T (§7) or the harmonic component has
not earned its place.

## 3. Target × horizon matrix

Targets are the canonical `ForecastTarget` members (`forecasting/targets.py:44-49`).
Horizons are the configured standards `HORIZON_5M` / `HORIZON_15M` / `HORIZON_60M`
(`forecasting/window.py:107-109`).

| Target | 5m | 15m | 60m |
|---|---|---|---|
| `cpu_utilization` | gating | gating | gating |
| `memory_utilization` | gating | gating | gating |
| `queue_depth` | gating | gating | gating |
| `running_replicas` | gating | gating | gating |
| `p99_latency` | reported | reported | reported |
| `error_rate` | reported | reported | reported |

**Twelve gating cells.** `p99_latency` and `error_rate` are spike-driven rather than
periodic; they are measured and reported so that a regression is visible, but H is neither
credited nor retired on them.

## 4. Data, window and admission

**Data (owner ruling 1).** Read-only historical production telemetry under shadow-only
scope. No live request, production write, scaling action, credential use or
customer-identifying data. Subjects are fixed in advance by an anonymized, preregistered run
manifest naming **every eligible subject in the approved export**; subject selection after
seeing results is prohibited and voids the run. Synthetic or staging data may validate the
harness but **cannot ratify a baseline**.

**Clock and period (owner ruling 2).** UTC-fixed clock semantics. **The daily period
`86400` seconds is the only ratified period for this experiment.** A weekly period is
excluded: it is not resolvable within the ratified lookback and would require a separately
ratified multiweek lookback. Local-calendar and DST-aware period definitions remain deferred
research and must not be introduced by implementation.

**Window (owner ruling 3).** `FeatureConfig` with `lookback_seconds = 604800` (seven days)
at `expected_cadence_seconds = 60` — 10,080 samples before missing-data handling. This is a
deliberate departure from the 3600-second default (`forecasting/window.py:125`), and it
applies **identically to all four arms**. Shortening H's window, or giving any arm a
different window, invalidates the run: the comparison would then measure lookback, not
method.

**Compute.** If the run is too large, reduce **replay-origin density** by a deterministic,
preregistered stride over `default_cutoffs(...)` — never by shortening a window and never
per-arm. The estimated run size (subjects × cells × origins × arms, and the rolling-origin
calibration cost per origin) is reported **before** execution.

**Admission.** One `AdmissionPolicy` for all arms, with `min_history` set to the maximum
across arms so no arm is admitted on history another was denied. All thresholds are
disclosed through the policy digest already bound into evidence.

## 5. Protocol

Per (arm, target, horizon): `run_replay_evaluation(observations, target, horizon, forecaster,
normalization_policy=…, cutoffs=…, feature_config=…, uncertainty_config=…,
admission_policy=…, series_policy=…, match_tolerance_seconds=…)`
(`forecasting/replay.py:136`).

**Leakage.** Two guards already exist and are relied upon, not reimplemented: the window's
`__post_init__` invariant rejecting any sample after the cutoff
(`forecasting/window.py:218-226`), and the harness's own assertion that the constructed
series does not extend beyond the cutoff, with the matched actual required to be strictly
later than the cutoff (`forecasting/replay.py:171-186`). This design adds one **third**
guard of its own:

> **Configuration-identity guard.** Before scoring, assert that the `feature_config`,
> `admission_policy`, `uncertainty_config`, normalization-policy and series-policy digests
> recorded in every arm's evidence are byte-identical across arms for the same cell, and
> that all arms ran the same cutoff list. A mismatch fails the run closed.

**Cutoffs.** One shared, deterministic cutoff list per cell, derived from `default_cutoffs`
and the preregistered stride, used by all four arms.

**Burn-in.** The first 20% of each subject's span is excluded from scoring. H cannot fit
before cycles exist, and scoring that region measures warm-up rather than method.

**Regime breaks.** Origins may be excluded only for deployments, incidents or configuration
changes **whose record was known at or before the forecast cutoff**. Retrospective incident
labels, post-hoc annotations and any signal that would not have been available at the cutoff
are prohibited as exclusion criteria — they would silently remove the hardest origins and
inflate every arm's apparent skill. The exclusion source, its as-of semantics and its
coverage are named in the run manifest.

## 6. Metrics and reporting

The ADR forbids percentage-error metrics (MAPE/SMAPE), because several targets are
legitimately zero (`forecasting/evaluation.py:26-28`). Errors stay in each target's own
units, and skill is a **ratio of mean absolute errors**.

```
Skill(A) = 1 − MAE(A) / MAE(P)          computed over the FOUR-ARM PAIRED SET
```

**Four-arm paired set.** Only cutoffs where **all four** arms produced an `EVALUATED` record
enter the accuracy comparison. Unpaired comparison lets a heavily-abstaining arm win by
declining the hard origins.

**Unconditional reporting is mandatory alongside it.** Pairing hides operational coverage
loss, so each arm additionally reports, over the *full* cutoff list and independently of the
other arms: eligible-origin count, `forecast_count`, `abstention_count`, `abstention_rate`,
`evaluated_count`, `unmatched_count`, `subject_mismatch_count` and `ambiguous_count` — all
existing `AggregateEvaluation` fields (`forecasting/evaluation.py:431-449`). A candidate that
wins the paired set while abstaining far more often than P is reported as exactly that, and
the abstention gate in §7 applies to its unconditional rate.

Results are reported per subject and per week as well as per cell. Pooled-only reporting is
not acceptable.

## 7. Gates

### 7.1 Per-cell accuracy gates for H

All four must hold in a cell for that cell to pass:

1. `MAE(H) ≤ 0.90 · MAE(P)` — beats persistence.
2. `MAE(H) ≤ 0.95 · MAE(T)` — beats its own trend term.
3. `MAE(H) ≤ 0.97 · MAE(N)` — beats the cheap seasonal control.
4. The quality gates in §7.2 all hold for that cell.

### 7.2 Per-cell quality gates

- **Signed bias.** `|mean_signed_error(H)| ≤ |mean_signed_error(P)|`. Accuracy may not be
  bought with bias.
- **Interval coverage.** `interval_empirical_coverage` within ±0.05 of
  `UncertaintyConfig.requested_coverage`. An interval that does not cover at its stated rate
  is misleading regardless of point accuracy.
- **Week consistency.** H wins the cell in at least 4 of 5 scored weeks. A single-week win is
  a fitted-noise result.
- **Abstention.** `abstention_rate(H) − abstention_rate(P) ≤ 0.20` on the **unconditional**
  counts of §6.

### 7.3 Scope gate (owner ruling 5)

Ratification may be **target × horizon restricted**. At least **8 of the 12** gating cells
must pass. There is no automatic-retirement rule attached to any individual horizon,
including 60m. Support is claimed only for passing cells; a ratified implementation must
deterministically reject or abstain outside its recorded capability envelope, and that
envelope is part of what is ratified.

### 7.4 Gates for N

N is outcome-eligible (owner ruling 4) and is judged by the same §7.2 quality gates and the
same 8-of-12 scope gate, with the accuracy condition `MAE(N) ≤ 0.90 · MAE(P)` and
`MAE(N) ≤ 0.95 · MAE(T)`.

## 8. Abstention accounting

Every decline is typed, counted and attributed. Existing reasons are used unchanged
(`forecasting/abstention.py:20-39`). H needs two reasons that **do not exist today**:

| Proposed reason | Meaning | Status |
|---|---|---|
| `INSUFFICIENT_CYCLE_COVERAGE` | the window does not span enough of the period to fit it | **PROPOSED — not present in `AbstentionReason`** |
| `PERIOD_NOT_RESOLVABLE` | the period is present in span but not recoverable from these samples | **PROPOSED — not present in `AbstentionReason`** |

They are kept **distinct**: the first says *not enough time*, the second says *not enough
usable structure within that time*. Collapsing them would make H's declines
unattributable. Neither is added by this document (§12).

### 8.1 Resolvability — deterministic checks

A single median-spacing rule is insufficient: it passes windows that are dense on average
but blind over the hours that matter. H declines unless **all** of the following hold, each
computed deterministically from the window alone:

1. **Total cycle span** — the window's first-to-last event time covers at least a
   preregistered whole number of periods. Failure → `INSUFFICIENT_CYCLE_COVERAGE`.
2. **Gap bound** — the maximum, and a preregistered high percentile, of consecutive-sample
   gaps are each below preregistered fractions of `P`. Failure → `PERIOD_NOT_RESOLVABLE`.
3. **Phase-bin coverage** — with the period divided into a preregistered number of equal
   phase bins, every bin holds at least a preregistered minimum number of samples. A window
   dense at night and empty at midday fails here. Failure → `PERIOD_NOT_RESOLVABLE`.
4. **Numerical identifiability** — the 4×4 normal-equation system is full rank at a
   preregistered conditioning threshold. Failure → `PERIOD_NOT_RESOLVABLE`.

### 8.2 Ratified thresholds and reason precedence

The thresholds are **ratified** and frozen in
[`CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md`](CLOUD_SCALING_THIRD_BASELINE_REPLAY_RUN_MANIFEST.md) §6.
They are recorded here so this document contains no unresolved placeholder:

| Condition | Ratified threshold | Maps to |
|---|---|---|
| Cycle span | in-lookback event-time span ≥ **604,740 s** | `INSUFFICIENT_CYCLE_COVERAGE` |
| Phase-bin coverage | **96** 15-minute UTC bins/day; ≥ **90 of 96** bins occupied on ≥ **6 of 7** days | `INSUFFICIENT_CYCLE_COVERAGE` |
| Maximum gap | no positive consecutive gap > **900 s** | `PERIOD_NOT_RESOLVABLE` |
| p95 gap | 95th percentile of positive consecutive gaps ≤ **120 s** | `PERIOD_NOT_RESOLVABLE` |
| Rank and conditioning | `[1, u, cos φ, sin φ]` full rank; ∞-norm condition number of the 4×4 normal matrix ≤ **1e8** | `PERIOD_NOT_RESOLVABLE` |

When several conditions fail, the reported reason follows a fixed precedence — cycle span,
phase-bin coverage, maximum gap, p95 gap, rank, conditioning — so an implementation cannot
select the flattering reason. Every failure is still counted; precedence governs reporting,
not measurement.

These thresholds are not tuned after execution. A change to any of them is a new
preregistration, not an amendment to this one.

### 8.3 Uncertainty calibration protocol (Amendment 3)

The interval-coverage gate in §7.2 is **retained**, and the seven-day point-model lookback is
**not shortened**. Its residuals come from an evaluation-specific **bounded causal prequential
residual bank**, specified in the run manifest §7.2 and applied identically to P, T, N and H:
one bank per `(subject, target, horizon, arm)`, calibration origins on the ratified 15-minute
UTC schedule, at most 672 residuals with oldest-origin-first eviction, and a strict as-of
admission rule — a residual enters the bank for cutoff `c` only if its origin precedes `c` and
its matched actual was observable at or before `c`.

A dedicated 7-day calibration block funds the bank (history requirement 42 → **49 days**;
burn-in day 0–7, calibration day 7–14, scoring day 14–49). The calibration block enters **no**
gate — not MAE, signed bias, coverage, abstention rate, or week consistency.

**This is an evaluation protocol, not shipped behavior.** `compute_uncertainty` computes its
own residuals over every in-window sample and exposes no residual-supply parameter
(`.../forecasting/uncertainty.py:210`, `:151-192`). Two consequences are load-bearing for what
a pass here would mean:

1. Executing this protocol requires an evaluation-scoped residual-supply seam that does not
   exist (run manifest §10.2). It is an implementation prerequisite, not a design gap.
2. **A successful replay does not ratify production uncertainty implementation.** Point
   accuracy and interval calibration are separate ratification claims, and if H passes,
   production interval calibration needs its own implementation and conformance decision.

Failure of the interval-coverage gate retires H **even if its point MAE passes** (§10).

### 8.4 Regime breaks — none excluded (Amendment 3)

No regime-break exclusion is applied. The package carries no regime-break record with both an
effective event time and an independent knowledge timestamp, and no nearby timestamp is
treated as a substitute (run manifest §7.1, §10.1). Every otherwise-eligible cutoff is
retained, including those spanning deployments, incidents and configuration changes; no
post-hoc removal by later-known labels is permitted; **no regime-specific performance may be
claimed**; and if H fails because periodicity breaks during operational changes, that failure
counts. Adding exclusion later would define a different evaluation requiring a new
preregistration and a new replay.

This is the conservative direction: it retains the difficult origins rather than removing them.

## 9. Outcome table

| Outcome | Condition | Consequence |
|---|---|---|
| **Ratify H** | H clears §7.1–§7.3 | `harmonic_phase` becomes the third baseline, restricted to its passing cells |
| **Ratify N** | N clears §7.4 and ties or beats H | `seasonal_naive` becomes **the third baseline** — not a fourth. H is retired |
| **Ratify T only** | H and N both fail; T already exists | no third baseline; the ADR's two-baseline position stands |
| **No third baseline** | nothing clears its gates | P and T stand; the deferral in the Phase 2 ADR is confirmed, not merely unresolved |
| **Inconclusive** | the run is invalidated under §5 or §11 | no verdict; re-run only after the defect is fixed and re-preregistered |

If N wins, H is retired and does not return as an optimization of N. If H wins, N remains
evaluation-only unless separately ratified.

## 10. Falsification — retire H if any holds

- **N ties or beats H** on the four-arm paired set across the gating cells. This is the
  decisive control, and it is decisive in both directions.
- **T ties or beats H**: the gain was the trend term, not the harmonic component.
- Fewer than 8 of 12 gating cells pass §7.1.
- The week-consistency gate fails: wins are week-specific, i.e. fitted noise.
- Interval coverage breaks its ±0.05 band.
- H's advantage disappears when P, T and N are given H's seven-day lookback — the gain was
  window size. (Under §4 they always are, so this is a design invariant, not a later check.)

A retirement is recorded with the same weight and in the same place as a pass. Re-running
with different periods, thresholds or windows to recover a failed gate is prohibited; a
changed design is a new preregistration.

## 11. What would invalidate the run

Configuration mismatch between arms (§5). Subject selection after results (§4). Exclusion of
origins using information not available at the cutoff (§5). Any tuning of §8.1 thresholds
after execution. Ratification from synthetic or staging data (§4). Any of these voids the
run rather than merely weakening it.

## 12. What this document does not do

It adds no `AbstentionReason` member, defines no forecaster class, changes no enum, schema,
digest or default, touches no telemetry and executes no replay. `forecasting/` remains
standard-library and local-only, and `hybrid_llm` remains a forbidden import root there
(`tests/forecasting/test_boundary.py:35-43`) — any future implementation is an independent
re-derivation of the equations, never an import from the Hybrid LLM lab.

## 13. Repository-grounded citations

| Claim | Source |
|---|---|
| Third baseline deferred pending replay evaluation; no neural nets or automatic promotion | `docs/architecture/ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md` §"Two deterministic baselines ship" |
| `PersistenceForecaster`, `LinearTrendForecaster`, pure `_predict` extension point | `.../forecasting/forecasters.py:105`, `:121`, `:81` |
| `ForecastTarget` members | `.../forecasting/targets.py:44-49` |
| `HORIZON_5M/15M/60M`; `FeatureConfig` fields; 3600s default lookback; leakage invariant | `.../forecasting/window.py:107-109`, `:113-129`, `:218-226` |
| `run_replay_evaluation` signature; leakage guards; deterministic matcher | `.../forecasting/replay.py:136`, `:171-186`, `:93-133` |
| `AggregateEvaluation` fields; no percentage metrics | `.../forecasting/evaluation.py:431-449`, `:26-28` |
| `EvaluationStatus` members | `.../forecasting/evaluation.py:63-68` |
| `AbstentionReason` members (neither proposed reason present) | `.../forecasting/abstention.py:20-39` |
| `AdmissionPolicy`, `UncertaintyConfig` fields | `.../forecasting/evidence.py:81-96`, `.../forecasting/uncertainty.py:50-71` |
| stdlib-and-local-only boundary; `hybrid_llm` forbidden | `.../tests/forecasting/test_boundary.py:35-43`, `:55-66` |
| Rolling-origin calibration iterates every in-window sample; `compute_uncertainty` takes no caller-supplied residuals | `.../forecasting/uncertainty.py:151-192`, `:210` |
| Interval construction is inline and its quantile helper is module-private (no public residual→interval entry point) | `.../forecasting/uncertainty.py:222-236`, `:239-249` |
| Replay reaches uncertainty through evidence construction | `.../forecasting/evidence.py:312` |
| Package version `0.4.0` | `.../src/ugence_cloud_scaling_controller/version.py:7` |

Paths under `.../` are relative to `packages/capabilities/cloud-scaling-controller/`.
