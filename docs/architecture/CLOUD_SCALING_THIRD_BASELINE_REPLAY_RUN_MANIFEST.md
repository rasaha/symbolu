# Cloud Scaling — Third-Baseline Replay Run Manifest (preregistration template)

**Status:** **MANIFEST INCOMPLETE — RUN PROHIBITED.** This is a preregistration template
carrying ratified rules and frozen thresholds. It is not a run authorization, and the fields
in §11 are deliberately unpopulated.
**Date:** 2026-08-27
**Governing design:** [`ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md`](ADR_CLOUD_SCALING_THIRD_BASELINE_REPLAY_EVALUATION.md)
**Governing ADR:** [`ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md`](ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md)

> **No telemetry access or replay execution is authorized by this document. No third baseline
> is ratified.** Two run-blocking repository gaps are recorded in §10; the run is prohibited
> while either stands, independently of §11.

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
| `INSUFFICIENT_SPAN` | fewer than 42 consecutive days of history (§4) |
| `TARGET_NOT_PRESENT` | the subject never carries this `ForecastTarget` |
| `TARGET_UNIT_INCONSISTENT` | the target appears under more than one unit across the span |
| `SYNTHETIC_SUBJECT` | harness-validation subject; excluded from ratification |
| `EXPORT_INTEGRITY_FAILURE` | the export fails its own integrity check for this subject |

## 4. Historical span, burn-in and scoring blocks

A subject × target requires **at least 42 consecutive days** of available history:

```
day  0  ..  6   burn-in / calibration only — never scored
day  7  .. 41   five consecutive 7-day scoring blocks
```

The first possible scored cutoff is:

```
first_scored_cutoff = first_observation_event_time + 604800 seconds
```

rounded **forward** to the next aligned cutoff instant under §5.

The burn-in is a **fixed 7-day boundary**, not a percentage. It exists because the harmonic
arm cannot fit before its lookback is populated, and the rolling-origin calibration inside
`compute_uncertainty` draws only on in-window samples. The boundary must not be moved after
results are inspected; doing so voids the run.

The five 7-day blocks are the unit of the existing 4-of-5 week-consistency gate in the
evaluation design.

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

## 7. Regime-break exclusion

A regime-break record may affect a cutoff only when **both** hold:

```
recorded_at <= cutoff
effective_event_time ∈ ( cutoff − lookback_seconds , cutoff + forecast_horizon_seconds ]
```

The first condition is the as-of test: it permits a scheduled *future* change that was already
recorded and knowable at the cutoff, and forbids later-created incident labels, post-hoc
deployment annotations and every other form of future knowledge. The second is the relevance
window.

**Required record classes:** deployments · incidents · scaling-policy changes · material
workload-configuration changes. Each requires an effective event time **and** a distinct
`recorded_at`.

**Repository state — see §10.1.** No canonical record type for these exists in the package,
and no canonical `recorded_at` exists on `CanonicalCapacityState`. This section is therefore
specified but **not satisfiable from repository contracts today**, which is recorded as a
run-blocking gap rather than worked around.

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

## 9. Run size

### 9.1 Base point forecasts

One fully eligible subject, five 7-day scoring blocks:

```
35 days × 96 cutoffs/day                      =     3,360 cutoffs
3,360 × 4 targets × 3 horizons × 4 arms       =   161,280 base arm-cell forecasts
```

For M fully eligible subjects:

```
base_forecasts = 161,280 × M
```

With partial target eligibility:

```
base_forecasts = Σ_subjects Σ_targets eligible(subject, target) × 3,360 × 3 × 4
               = Σ_subjects Σ_targets eligible(subject, target) × 40,320
```

### 9.2 Uncertainty expansion — R is not a configuration value

```
estimated_forecaster_calls = base_forecasts × (1 + R)
```

R is **not** a field of `UncertaintyConfig` (`.../forecasting/uncertainty.py:50-71`, whose
fields are `method`, `requested_coverage`, `min_calibration_samples`,
`match_tolerance_seconds`, `allow_point_only_when_uncalibrated`, `calibration_window_id`).
`rolling_origin_residuals` iterates over **every sample in the window**
(`.../forecasting/uncertainty.py:151-192`), so R is determined by window size:

```
R = |{ origins i : i ≥ min_history − 1 and a matched in-window actual exists }|
R ≤ n_samples − (min_history − 1)
```

For the ratified seven-day window at 60-second cadence, `n_samples ≈ 10,080`, so
**R ≈ 1.0 × 10⁴**, and per fully eligible subject:

```
estimated_forecaster_calls ≈ 161,280 × 10,078 ≈ 1.63 × 10⁹
```

R is statically knowable in form but is a consequence of the ratified lookback, not a knob.
The 15-minute stride reduces base forecasts; it does **not** reduce R. See §10.2.

### 9.3 Report-record volume

Calibration predictions produce no records. Per fully eligible subject the run emits
**161,280 `CapacityForecastEvidence` + `ForecastEvaluationRecord` pairs**, one per base
forecast, plus one `AggregateEvaluation` per (arm, target, horizon) — 48 aggregates per
subject. Record volume scales with §9.1, compute with §9.2; the two must not be conflated.

### 9.4 Sharding

The replay can run in bounded shards **without** changing cutoff order or aggregation
semantics, sharded by `(subject, target, horizon, arm)`. Each such shard is one
`run_replay_evaluation` invocation over the full ordered cutoff sequence, and every cutoff
rebuilds its history from observations by event time rather than from carried state
(`.../forecasting/replay.py:165-175`), so shard boundaries introduce no state coupling.

Two constraints on sharding: aggregation must be computed over the records of a *complete*
shard, and the four-arm paired set (§8) can only be intersected once **all four arms** of a
cell have completed. Sharding within a single cell's cutoff sequence is permitted but gains
nothing and complicates the paired-set join.

## 10. Run-blocking repository gaps

Both must be resolved by a further owner ruling before any run. Neither is worked around here.

### 10.1 No canonical regime-break source and no as-of timestamp

- `CanonicalCapacityState` carries `observed_at` only. There is **no `recorded_at`** and no
  ingestion timestamp on the state (`.../canonical/state.py:411-427`).
- `DeploymentState` (`.../canonical/state.py:231-236`) carries `deploy_active`,
  `rollout_phase`, `canary_active`, `version` and `deployment_age`. These are *state
  co-timestamped with the observation*, so they are knowable at the cutoff — but they are a
  deployment **signal**, not a deployment **record** with an independent effective time.
- There is **no** incident record, **no** scaling-policy-change record and **no**
  workload-configuration-change record anywhere in the package.
- The nearest as-of field in the package is `ObservationProvenance.collected_at`
  (`.../canonical/provenance.py:69`), documented as "when this record was produced (optional;
  distinct from observed)". It is **optional**, and it is provenance for an observation — there
  is no regime-break record for it to timestamp. `TopologySnapshot.as_of`
  (`.../planning/topology.py:165`) is a Phase 3 planning effective time, not a knowledge
  timestamp, and is not a regime-break source.

**Consequence.** §7's `recorded_at <= cutoff` test cannot be evaluated from repository
contracts. Until the approved export contract supplies both a regime-break record type and a
distinct `recorded_at`, **no regime-break exclusion may be applied at all** — and applying
none is the safe direction, since it retains the hardest origins rather than removing them.
The alternative, inferring breaks from co-timestamped `DeploymentState`, would cover only
deployments and is not authorized here.

### 10.2 Calibration expansion is unbounded by the ratified rulings

At R ≈ 10⁴, a single fully eligible subject implies ≈ 1.63 × 10⁹ forecaster calls (§9.2), and
each harmonic call is an OLS over up to 10,080 points. `rolling_origin_residuals` also runs an
O(n²) inner match loop per forecast. The ratified stride bounds §9.1 but not §9.2, and
`UncertaintyConfig` exposes no origin cap.

Reducing R would mean changing shipped calibration behavior — production code this
documentation change may not touch — or ratifying a different lookback or an origin-subsample
rule. Recorded, not resolved.

## 11. Fields to populate immediately before an authorized run

Every field below is **empty by design**. The manifest is incomplete and the run is prohibited
while any remains empty or while either §10 gap stands.

| Field | To be filled |
|---|---|
| `export_identity` | approved export identifier and its content digest |
| `export_integrity_digest` | digest verified before and after the run |
| `subject_manifest_digest` | digest of the external anonymized subject list (§2.1) |
| `subject_count_M` | number of eligible non-synthetic subjects |
| `per_target_eligibility_counts` | `eligible(subject, target)` totals for §9.1 |
| `first_observation_event_time` / `last_observation_event_time` | per subject, UTC |
| `first_scored_cutoff` / `last_scored_cutoff` | per subject × target, UTC-aligned per §5 |
| `scoring_block_boundaries` | the five 7-day block edges per subject × target |
| `base_forecasts` | exact value from §9.1 |
| `resolved_R` and `estimated_forecaster_calls` | exact values from §9.2 |
| `estimated_record_volume` | exact value from §9.3 |
| `frozen_config_digests` | `FeatureConfig`, `AdmissionPolicy`, `UncertaintyConfig`, normalization and series policy digests, identical across arms |
| `match_tolerance_seconds` | frozen value, identical across arms |
| `cutoff_sequence_digest` | digest of the ordered cutoff list per subject × target |
| `regime_break_source` | blocked by §10.1 |
| `shard_plan` | shard boundaries under §9.4 |

**Manifest incomplete / run prohibited.** The replay may not be executed until every field
above is populated, both §10 gaps are resolved by owner ruling, and the evaluation design's
gates are unchanged from their preregistered form.
