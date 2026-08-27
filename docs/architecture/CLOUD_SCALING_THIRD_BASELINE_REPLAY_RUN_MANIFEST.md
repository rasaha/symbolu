# Cloud Scaling — Third-Baseline Replay Run Manifest (preregistration template)

**Status:** **MANIFEST INCOMPLETE — RUN PROHIBITED.** This is a preregistration template
carrying ratified rules and frozen thresholds. It is not a run authorization, and the fields
in §11 are deliberately unpopulated.
**Date:** 2026-08-27
**Governing design:** [`ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md`](ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md)
**Governing ADR:** [`ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md`](ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md)

**Amended 2026-08-27 (Amendment 3)** — both §10 blockers are ruled on and closed **for design
purposes**. Two execution prerequisites replace them (§10).

> **The replay remains unexecutable until the anonymized subject manifest and approved export
> identity are populated and an evaluation implementation of the bounded causal residual-bank
> protocol exists. No production uncertainty behavior is changed or ratified.**
>
> **No telemetry access is authorized by this document. No third baseline is ratified.** The
> evaluation remains outcome-neutral. Point accuracy and interval calibration are **separate
> ratification claims**: failure of the interval-coverage gate retires H even if its point MAE
> passes.

## 1. Scope and non-authorization

This manifest fixes, in advance, every choice that could otherwise be made after seeing
results: which subjects are eligible, how much history they need, where burn-in ends, which
cutoffs are scored, when the harmonic arm may fit at all, and which reason is reported when
several resolvability conditions fail together.

It creates no code, adds no enum member, changes no schema, digest, default or dependency,
names no real subject, and touches no telemetry. `seasonal_naive` and `harmonic_phase` remain
proposed identities with no implementation. `INSUFFICIENT_CYCLE_COVERAGE` and
`PERIOD_NOT_RESOLVABLE` remain **proposed vocabulary**; they are not present in
`AbstentionReason` (`.../forecasting/abstention.py:20-39`) and are not added here.

## 2. Subject identity and anonymization

No real customer, cluster, namespace, workload or subject identifier may appear in this
repository. The anonymized identifier is:

```
subject_hash = HMAC-SHA256(run_secret, canonical_subject_id)
```

`run_secret` and every `canonical_subject_id` remain **outside the repository**, held with the
approved export. Reports may use a shortened, collision-checked form
`subject-<12 hex characters>`; the shortening must be checked for collisions across the whole
manifest, and a collision is resolved by lengthening the prefix for **all** subjects, never by
renaming one.

`canonical_subject_id` is the canonical serialization of the subject identity carried by
`CapacitySubject` (`.../canonical/identity.py`), which the forecasting layer already treats as
the unit of series identity — cross-subject input fails closed in series construction.

### 2.1 Subject-list schema (populated outside the repository, referenced by digest here)

| Field | Meaning |
|---|---|
| `subject_hash` | HMAC-SHA256 as above, full hex |
| `short_id` | `subject-<12 hex>`, collision-checked |
| `eligible_targets` | subset of the four gating `ForecastTarget` values this subject qualifies for |
| `first_observation_event_time` | earliest event time in the export for this subject, UTC |
| `last_observation_event_time` | latest event time in the export for this subject, UTC |
| `available_days` | whole days of continuous history between those bounds |
| `exclusion_reasons` | typed reasons per target where not eligible (§3.2) |
| `is_synthetic` | true for harness-validation subjects, which may not contribute to ratification |

## 3. Eligibility

### 3.1 Outcome-blind selection

Eligibility is determined **before any forecast is produced**, from history availability and
sampling structure only. The run includes **every** subject in the approved export that
satisfies the rules below. Inspecting forecast results before fixing eligibility, removing
weakly seasonal subjects, or adding subjects after seeing results voids the run.

Eligibility is defined **per subject × target**. A subject need not expose every target. But
within an evaluated target × horizon cell, **all four arms use the identical eligible subject
set** — an arm may not be scored on a subject the others were not.

Synthetic and staging subjects may validate the harness. They may not contribute to
ratification and are reported separately.

### 3.2 Typed, countable exclusion reasons

Every exclusion is recorded with a reason and counted, so coverage loss is visible rather than
implicit. These are manifest-level bookkeeping reasons; they are **not** `AbstentionReason`
members and are not proposed as such.

| Reason | Condition |
|---|---|
| `INSUFFICIENT_SPAN` | fewer than 49 consecutive days of history (§4) |
| `TARGET_NOT_PRESENT` | the subject never carries this `ForecastTarget` |
| `TARGET_UNIT_INCONSISTENT` | the target appears under more than one unit across the span |
| `SYNTHETIC_SUBJECT` | harness-validation subject; excluded from ratification |
| `EXPORT_INTEGRITY_FAILURE` | the export fails its own integrity check for this subject |

## 4. Historical span, burn-in and scoring blocks

A subject × target requires **at least 49 consecutive days** of available history
(raised from 42 by Amendment 3, to fund a dedicated interval-calibration block):

```
day  0  ..  7   model-history burn-in — no forecast scored, no residual admitted
day  7  .. 14   interval-calibration block — residuals only, never scored
day 14  .. 49   five consecutive 7-day scoring blocks — the only weeks that count
```

The first possible scored cutoff is:

```
first_scored_cutoff = first_observation_event_time + 1209600 seconds
```

rounded **forward** to the next aligned cutoff instant under §5.

Both boundaries are **fixed day counts**, not percentages, and neither may be moved after
results are inspected; doing so voids the run. The **point-model lookback remains exactly
seven days for every arm at every forecast origin** — the calibration block funds the residual
bank (§7.2), it does not widen any model's window.

## 5. Deterministic cutoff schedule

Fixed **900-second (15-minute)** stride, aligned to UTC quarter-hours:

```
minute ∈ {00, 15, 30, 45}, second = 00, microsecond = 0
```

- 96 cutoffs per day; 3,360 cutoffs over the 35 scored days.
- The **same ordered cutoff sequence** is used by P, T, N and H for a given subject × target.
- Cutoff density is a property of the schedule, **not** of the forecast horizon. The 5, 15 and
  60-minute horizons all run on this one sequence.
- An ineligible cutoff is **preserved in accounting with its reason**, never silently dropped.
  A deleted cutoff would make two arms' denominators differ.

Alignment compatibility: with a 60-second cadence and quarter-hour cutoffs, each
`forecast_for = cutoff + horizon` also lands on a whole minute for all three horizons, so a
matching actual is expected within the default 5-second match tolerance
(`.../forecasting/replay.py:136`, `match_tolerance_seconds`). The tolerance is frozen
identically across arms in §11.

## 6. Frozen resolvability thresholds (evaluation design §8.1)

For the ratified 86,400-second UTC-fixed daily period and the seven-day lookback, H is
resolvable at a cutoff only when **all five** hold, computed from the window alone:

| # | Condition | Frozen threshold |
|---|---|---|
| 1 | **Cycle span** | observed event-time span inside the lookback ≥ **604,740 s** (604,800 less one expected 60 s endpoint interval) |
| 2 | **High-percentile gap** | 95th percentile of positive consecutive event-time gaps ≤ **120 s** |
| 3 | **Maximum gap** | no positive consecutive event-time gap exceeds **900 s** |
| 4 | **Phase-bin coverage** | each UTC day partitioned into **96** fixed 15-minute phase bins; at least **90 of 96** bins hold ≥ 1 observation on at least **6 of the 7** lookback days |
| 5 | **Numerical identifiability** | the joint OLS design `[1, u, cos φ, sin φ]` is full rank and the infinity-norm condition number of its 4×4 normal matrix is ≤ **1e8** |

The centred and scaled `u` defined normatively in the evaluation design is the one used here.

### 6.1 Reason mapping and deterministic precedence

- Conditions 1 and 4 → proposed `INSUFFICIENT_CYCLE_COVERAGE`
- Conditions 2, 3 and 5 → proposed `PERIOD_NOT_RESOLVABLE`

When more than one condition fails, the reported reason is fixed by this precedence, so no
implementation can choose the flattering one:

```
1. insufficient cycle span          (condition 1)
2. insufficient phase-bin coverage  (condition 4)
3. maximum-gap violation            (condition 3)
4. p95-gap violation                (condition 2)
5. rank failure                     (condition 5, rank)
6. conditioning failure             (condition 5, condition number)
```

The first matching entry wins. Failures below the reported one are still **counted** in the
diagnostic tally, so precedence changes what is reported, never what is measured.

### 6.2 Cadence preflight (owner ruling — required before authorization)

Before the replay is authorized, an **outcome-blind metadata preflight** runs per
subject × target. It reads exported observation timestamps only; no forecast is produced and
no result may influence which series are included.

Verified from the actual exported observations:

| Field | Why |
|---|---|
| native / source scrape interval, where available | the resolution the data was collected at |
| export or query step | the resolution the data was *delivered* at, which may be coarser |
| whether downsampling or aggregation occurred | an aggregated series is not the raw one |
| p95 positive consecutive event-time gap | the ratified §6 condition 2 |
| maximum positive consecutive event-time gap | the ratified §6 condition 3 |
| 49-day continuous-history availability | §4 |
| daily phase-bin coverage | §6 condition 4 |

The replay is authorized **only** for subject × target series that already satisfy the
ratified limits — p95 gap ≤ 120 s, maximum gap ≤ 900 s, and every other cycle-coverage and
resolvability gate in §6.

**No interpolation, forward-fill, upsampling or synthesis of intermediate observations** may
be used to make a coarse export appear eligible. Manufacturing samples would not recover the
missing cycle information; it would only hide its absence from the resolvability checks.

**If no subject × target series qualifies, the replay is not run**, and `harmonic_phase` is
recorded as **unevaluable on the approved export** — explicitly not as a modelling loss and
not as a win. That outcome says something about the export's resolution, not about the model.

The relevant fact is the **actual export/query resolution**, which is what the preflight
measures. It is not assumed from any collector's configuration default.

## 7. Regime breaks and uncertainty calibration (Amendment 3)

### 7.1 Regime-break exclusion — none is applied

**Ruling: this evaluation applies no regime-break exclusion.**

The repository has no canonical regime-break record carrying both an effective event time and
an independent knowledge timestamp (§10.1). No new export-contract requirement is created to
rescue the experiment, and `DeploymentState`, `ObservationProvenance.collected_at`,
`TopologySnapshot.as_of` and every other nearby timestamp are **not** treated as equivalent to
a `recorded_at`.

Consequences, recorded:

- Every otherwise-eligible cutoff is **retained**, including those spanning deployments,
  incidents and configuration changes.
- No post-hoc removal using later-known labels is permitted, at any stage.
- This is the **conservative direction**: it keeps the difficult origins rather than removing
  them, so no arm's skill is inflated by quiet-period selection.
- **No regime-specific performance may be claimed** from this run, in either direction.
- If H fails because periodicity breaks during operational changes, **that failure counts**.
  Operational reality is part of what is being tested.
- Adding regime-break exclusion later defines a **different evaluation**, requiring a new
  preregistered amendment and a new replay. It is not a re-analysis of this run.

### 7.2 Bounded causal prequential residual bank

**Ruling: the seven-day feature lookback is not shortened and the interval-coverage gate is not
withdrawn.** The nested per-forecast rolling-origin expansion is replaced, **for this
evaluation only**, by a causal prequential residual bank applied identically to P, T, N and H.

This is an **evaluation protocol ruling, not a claim about shipped behavior**. The production
uncertainty path is unmodified by this document, and §10.2 records what would be needed to run
the protocol at all.

**Calibration origins.** The already-ratified UTC quarter-hour schedule of §5 — minute
∈ {00, 15, 30, 45}, second 00. One calibration origin every **900 seconds**, not one per
60-second observation.

**Banks.** One bank per `(subject_hash, target, horizon, arm)`.

**Admission (as-of rule, non-negotiable).** A residual from origin `o` may enter the bank used
at a later cutoff `c` only when **all** hold:

```
the forecast at o was produced without abstention
its actual match is unique and valid
the matched actual's event time <= c
all provenance and subject-matching rules pass
o < c
```

A residual whose outcome is not yet observable at `c` must never enter the interval. This is
the reason a bank is required rather than an in-window computation: for the 60-minute horizon
near a window edge, an origin's actual may fall outside that origin's own seven-day window
while still being observed at or before `c`.

**Bank bound.** At most the **672** most recent eligible residuals per bank
(7 days × 96 quarter-hour origins/day). Eviction is deterministic: oldest forecast origin
first, with event time and the canonical replay tie-breaker applied if origins collide.

**Configuration.** The preregistered `UncertaintyConfig` values for method, requested coverage,
minimum calibration samples, match tolerance and calibration-window identity are used
unchanged. `allow_point_only_when_uncalibrated` is **false** — which is also the shipped
default (`.../forecasting/uncertainty.py:69`). An origin without enough causal calibration
residuals is **not eligible for the interval-coverage gate** and is accounted for explicitly;
it is never accepted as a point-only success.

**Interval mathematics.** After the bounded residual set exists, the repository's existing
construction is reused verbatim — sort, `alpha = 1 − requested_coverage`, type-7 quantiles at
`alpha/2` and `1 − alpha/2`, interval `point + [lower_offset, upper_offset]`
(`.../forecasting/uncertainty.py:222-236`). **No second interval formula is invented.**

### 7.3 Scoring semantics

The seven-day calibration block is excluded from **all** gates: MAE, signed bias, interval
coverage, abstention rate and the 4-of-5 week-consistency gate. Only the five scoring weeks
count toward ratification.

During scoring the bank continues to update **causally** from eligible quarter-hour forecasts
whose actuals have become observable. A residual is never computed from the current or a
future outcome.

The same calibration schedule, bank size, minimum-sample rule and interval method apply to all
four arms.

### 7.4 Cost in evaluation meaning

- Preserves the seven-cycle point-model lookback.
- Preserves the interval-coverage gate.
- Reduces calibration origins from every 60-second sample to every 15 minutes.
- Interval estimates therefore describe the error distribution **at the preregistered
  decision-origin schedule**, not at every raw telemetry timestamp.
- It changes the uncertainty-evaluation protocol away from the shipped nested rolling-origin
  implementation, so **a successful replay does not by itself ratify production uncertainty
  implementation**.
- If H passes, production interval calibration requires a **separate implementation and
  conformance decision**.

## 8. Target × horizon matrix and paired-set rule

Inherited unchanged from the evaluation design: four gating targets
(`cpu_utilization`, `memory_utilization`, `queue_depth`, `running_replicas`) ×
three horizons (`HORIZON_5M`, `HORIZON_15M`, `HORIZON_60M`) = **12 gating cells**;
`p99_latency` and `error_rate` are reported, non-gating.

**Four-arm paired set:** only cutoffs where all four arms produced an `EVALUATED` record enter
the accuracy comparison. Each arm additionally reports, over the full cutoff list and
independent of the other arms, its eligible-origin count, `forecast_count`,
`abstention_count`, `abstention_rate`, `evaluated_count`, `unmatched_count`,
`subject_mismatch_count` and `ambiguous_count`, so paired-set intersection cannot conceal
operational coverage loss.

## 9. Run size (Amendment 3 — bounded, no multiplicative expansion)

### 9.1 Per fully eligible subject

```
calibration block  7 days × 96 origins/day × 4 targets × 3 horizons × 4 arms =  32,256 calls
five scoring weeks 35 days × 96 origins/day × 4 targets × 3 horizons × 4 arms = 161,280 calls
                                                                       total  = 193,536 calls
```

**There is no multiplicative R expansion.** The nested per-forecast rolling-origin expansion
is replaced by the bounded bank of §7.2, so the earlier ≈ 1.63 × 10⁹ figure no longer applies.

### 9.2 Partial target eligibility

```
Σ_targets eligible(subject, target) × [ 8,064 calibration calls + 40,320 scoring calls ]

  8,064 =   672 calibration origins × 3 horizons × 4 arms
 40,320 = 3,360 scoring origins     × 3 horizons × 4 arms
```

For M fully eligible subjects, `total_calls = 193,536 × M`.

### 9.3 Storage bounds

- **Residual banks:** at most **672** residuals per
  `(subject_hash, target, horizon, arm)` bank, bounded by construction and by eviction.
- **Gating records:** **161,280** evidence + evaluation-record pairs per fully eligible
  subject, one per scored forecast, plus 48 aggregates (one per arm × target × horizon).
- **Calibration records** are stored and reported **separately** from gating records and enter
  no gate (§7.3). Conflating the two would let the calibration block inflate coverage counts.

### 9.4 Sharding

The replay can run in bounded shards **without** changing cutoff order or aggregation
semantics, sharded by `(subject, target, horizon, arm)` — the same key as the residual banks.
Each shard is one ordered pass over the full cutoff sequence, and every cutoff rebuilds its
history from observations by event time rather than from carried state
(`.../forecasting/replay.py:165-175`), so shard boundaries introduce no state coupling.

Two constraints: the residual bank is **ordered state within a shard**, so a shard must be
processed in cutoff order and may not be split across the calibration/scoring boundary; and
the four-arm paired set (§8) can be intersected only once all four arms of a cell complete.

## 10. Execution prerequisites (replacing the closed §10 blockers)

Amendment 3 closes both former run-blocking gaps **for design purposes**. What remains is not
a design gap but an implementation and population prerequisite.

### 10.1 Regime breaks — ruled, closed

Recorded for the record, since the ruling depends on it: `CanonicalCapacityState` carries
`observed_at` only, with **no `recorded_at`** (`.../canonical/state.py:411-427`);
`DeploymentState` (`.../canonical/state.py:231-236`) is a co-timestamped deployment *signal*,
not a record with an independent effective time; there is no incident, scaling-policy-change or
workload-configuration-change record anywhere in the package; and the nearest as-of field,
`ObservationProvenance.collected_at` (`.../canonical/provenance.py:69`), is optional and
observation-scoped, with no regime-break record to timestamp.
`TopologySnapshot.as_of` (`.../planning/topology.py:165`) is a Phase 3 planning effective time,
not a knowledge timestamp.

**Closed by §7.1: no exclusion is applied.** No prerequisite remains.

### 10.2 Residual-supply seam — **built and synthetically tested**

**Status: closed.** The seam is implemented and covered by conformance tests, including a
negative control proving a future-contaminated bank that would flatter interval coverage is
rejected. The four arms (`persistence`, `linear_trend`, `seasonal_naive`, `harmonic_phase`)
exist as evaluation forecasters, and synthetic fixtures demonstrate that H, N, T or no
candidate can each win depending on the data.

What remains is §11 population and the authorization itself — **the run is still prohibited**.

The description below records why the seam was needed, against the pre-implementation state:

- `compute_uncertainty(window, forecaster, point, config)` **unconditionally** computes its own
  residuals by calling `rolling_origin_residuals(window, forecaster, config)`
  (`.../forecasting/uncertainty.py:210`). It has **no parameter** for a caller-supplied
  residual collection.
- `rolling_origin_residuals` (`.../forecasting/uncertainty.py:151-192`) *produces* residuals
  over every in-window sample; it does not *accept* them. It must **not** be reinterpreted as
  already satisfying this ruling — its origin set, its in-window-only matching and its
  unbounded count all differ from §7.2.
- The interval mathematics is **inline** inside `compute_uncertainty`
  (`.../forecasting/uncertainty.py:222-236`) and its quantile helper is module-private and
  absent from `__all__` (`.../forecasting/uncertainty.py:239-249`). There is therefore **no
  public entry point that turns a residual sequence into an `UncertaintyInterval`**, and §7.2's
  requirement to reuse the existing formula cannot currently be met without one.
- The replay path reaches uncertainty through `forecast_with_evidence`
  (`.../forecasting/evidence.py:312`), so any seam must be threaded from
  `run_replay_evaluation` through evidence construction, not introduced at the leaf alone.

**Prerequisite — closed.** The seam is implemented (Amendment 4 selected its shape). It is a
**separate public residuals-to-interval function**: one canonical interval formula, two
residual-production paths (the shipped `rolling_origin_residuals` path and the §7.2 bank), both
delegating to it. `compute_uncertainty` keeps its signature and default behavior. The bank
reaches evidence assembly through one explicitly-typed optional calibration parameter on
`run_replay_evaluation` and `forecast_with_evidence`; the `None` branch is today's path,
unchanged. Full design, candidate comparison, authority constraints and the 14 required
conformance tests:
[`CLOUD_SCALING_RESIDUAL_SUPPLY_SEAM_DESIGN.md`](CLOUD_SCALING_RESIDUAL_SUPPLY_SEAM_DESIGN.md).

Both vocabulary prerequisites were subsequently ratified and implemented:
`UncertaintyMethod.EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK`, and `calibration_input_digest` on both
`UncertaintyInterval` and `CapacityForecastEvidence` at schema version
`capacity-forecast-evidence-2`. Legacy evidence keeps `capacity-forecast-evidence-1` and its
exact historical payload, so committed digests are unmoved.

## 11. Fields to populate immediately before an authorized run

Every field below is **empty by design**. The manifest is incomplete and the run is prohibited
while any remains empty. (The §10.2 seam prerequisite is now closed.)

| Field | To be filled |
|---|---|
| `export_identity` | approved export identifier and its content digest |
| `export_integrity_digest` | digest verified before and after the run |
| `cadence_preflight_summary` | §6.2 metadata per subject × target, and the qualifying set |
| `subject_manifest_digest` | digest of the external anonymized subject list (§2.1) |
| `subject_count_M` | number of eligible non-synthetic subjects |
| `per_target_eligibility_counts` | `eligible(subject, target)` totals for §9.1 |
| `first_observation_event_time` / `last_observation_event_time` | per subject, UTC |
| `first_scored_cutoff` / `last_scored_cutoff` | per subject × target, UTC-aligned per §5 |
| `burn_in_and_calibration_boundaries` | the day-7 and day-14 edges per subject × target |
| `scoring_block_boundaries` | the five 7-day block edges per subject × target |
| `base_forecasts` | exact value from §9.1 |
| `estimated_forecaster_calls` | exact value from §9.1/§9.2 (no R expansion) |
| `estimated_record_volume` | gating and calibration volumes, reported separately (§9.3) |
| `frozen_config_digests` | `FeatureConfig`, `AdmissionPolicy`, `UncertaintyConfig`, normalization and series policy digests, identical across arms |
| `match_tolerance_seconds` | frozen value, identical across arms |
| `cutoff_sequence_digest` | digest of the ordered cutoff list per subject × target |
| `residual_bank_plan` | bank key, 672 bound, eviction order, and the implemented seam (shape selected; implementation blocked by §10.2) |
| `shard_plan` | shard boundaries under §9.4 |

**Manifest incomplete / run prohibited.** The §10.2 seam now exists with its conformance
evidence, but the replay may not be executed until every field above is populated and the
evaluation design's gates are unchanged from their preregistered form. Synthetic tests make
the replay executable in principle; they ratify nothing. No production
uncertainty behavior is changed or ratified by this manifest, and no third baseline is
ratified.
