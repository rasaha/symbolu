# ADR — Cloud Scaling: Predictive Capacity Intelligence (Phase 2)

**Status:** **ACCEPTED.**
**Date:** 2026-08-11
**Package:** `packages/capabilities/cloud-scaling-controller` (`ugence-cloud-scaling-controller`), v0.2.0 → **v0.3.0**.
**Scope:** Additive, deterministic, provider-neutral, **shadow-only** forecasting and
replay-evaluation layer built *around* the Phase-1 canonical layer. The controller's
advisory authority, provider neutrality, and five-signal decision algorithm are unchanged,
and forecasts never feed the controller.

---

## Context

Phase 1 established a trustworthy, provider-neutral representation of *current* capacity
state (`CanonicalCapacityState`), explicit normalization/projection onto the unchanged
`ScalingObservation`, and immutable recommendation evidence (`CapacityDecisionEvidence`).

Phase 2 answers a forward-looking question **without touching the live decision path**:

> Given the capacity history available *at event time*, what capacity pressure is likely at
> a future horizon, how uncertain is that prediction, and how well has the forecasting
> method performed in replay?

The naive path — feed a forecast into the controller as a hidden signal, or let a
predicted value trigger a scaling action — would (a) silently change the tested five-signal
decision model, (b) entangle an unproven prediction with real authority, and (c) risk
leakage (training/scoring on data that would not have been available at decision time). We
reject it. Phase 2 is **descriptive shadow intelligence only**.

## Decision

Add a leaf subpackage `ugence_cloud_scaling_controller.forecasting` (pure standard library,
no new dependency, no network/subprocess/credential/LLM) implementing this flow:

```text
CanonicalCapacityState history
        ↓  series validation + strict event-time ordering (explicit construction policy)
CanonicalCapacitySeries
        ↓  leakage-safe input window (event_time <= cutoff, invariant-checked)
ForecastInputWindow
        ↓  deterministic baseline forecaster (persistence / linear trend)
CapacityForecast          (point estimate + uncertainty  OR  typed abstention)
        ↓  controlled service path binds real window + config + output
CapacityForecastEvidence  (immutable, sha256 content-identity digest)
        ↓  shadow replay against strictly-later actual observations
ForecastEvaluationRecord  + deterministic aggregate evaluation report
```

The existing live path — `ScalingObservation → CloudScalingController → ScalingRecommendation`
— is **byte-for-byte unchanged**, and forecast results are never a hidden input to it.

### Event-time semantics

Event time is `CanonicalCapacityState.observed_at` — *when the measurement was taken* —
never `collected_at` (record production) or evidence-production time. Every ordering,
windowing, staleness, cadence, and matching decision uses event time. Timestamps must be
timezone-aware (safe default; a policy may opt into naive-as-UTC). This is the single most
important rule for leakage safety: a record inserted late but *observed* early is placed by
its event time, and a record collected late for an early observation still uses its event
time.

### Series construction policy

`CanonicalCapacitySeries.build(states, policy)` binds one `CapacitySubject` (tenant/scope
included), the ordered observations, the event-time range, the observation count, a schema
version (`capacity-series-1`), and a deterministic content digest. It **fails closed** on:
subject/tenant/scope inconsistency (cross-subject or cross-tenant contamination), naive
timestamps (unless permitted), invalid event-time ordering, and **conflicting duplicates**
(same timestamp, different content — *always* rejected, not a knob). Non-identity
transformations require explicit opt-in and are disclosed: `OrderingPolicy.SORT` (records
`applied_sort`) and `DuplicateTimestampPolicy.COLLAPSE_IDENTICAL` (records
`collapsed_duplicate_count`). Missing capacity signals are **never** imputed.

### Supported targets and horizons

Targets are read from the *same* canonical fields the Phase-1 projection uses, so a
forecast can never silently substitute a different semantic:

| Target | Canonical field |
| --- | --- |
| `CPU_UTILIZATION` | `infrastructure.cpu_utilization` |
| `MEMORY_UTILIZATION` | `infrastructure.memory_utilization` |
| `P99_LATENCY` | `performance.latency_p99` |
| `ERROR_RATE` | `reliability.error_rate` |
| `QUEUE_DEPTH` | `workload.queue_depth` |
| `RUNNING_REPLICAS` | `capacity.running_replicas` (the SAME field the projection maps to `ScalingObservation.current_replicas` — never desired/ready/healthy) |

Extraction is **raw** — value and unit are preserved unchanged (no silent unit conversion).
Horizons are explicitly configured `ForecastHorizon` durations (e.g. 5m / 15m / 60m);
**no horizon-specific scaling behavior is hardcoded**. Each forecast binds its target,
horizon, cutoff, and forecast-for time.

### Baseline models

Two deterministic baselines ship: **persistence** (last observed value; the canonical
hard-to-beat baseline) and **linear-trend** (closed-form OLS over event-time seconds,
extrapolated to the forecast-for time; requires ≥ 2 distinct timestamps and a configurable
`min_history`). Each has a stable `model_id`/`model_version`, an explicit configuration
with a digest, a minimum-history requirement, declared supported targets/horizons,
deterministic output, and typed abstention. No training or mutation occurs during a
forecast. A **third baseline is deliberately deferred** until replay evaluation on
representative data justifies it (the spec permits a third "only if justified by replay
evaluation"). No neural networks, model services, hyperparameter search, or automatic
promotion.

### Uncertainty limitations

Uncertainty is an **empirical rolling-origin residual interval** (`UncertaintyMethod`
`EMPIRICAL_ROLLING_ORIGIN_RESIDUAL`): the forecaster is replayed over rolling origins
*inside the leakage-safe window*, signed horizon-ahead residuals are collected, and the
interval is `point + [q(α/2), q(1-α/2)]` from empirical residual quantiles at the requested
coverage. **No Gaussian assumption is made.** Because the interval is centered on the
residual quantiles rather than symmetric around the point, a biased forecaster yields an
off-center interval that faithfully reflects its observed error. If fewer than
`min_calibration_samples` residuals exist, the interval is a typed **unavailable** contract;
the forecast is retained as point-only *only* if the config explicitly permits it, otherwise
the layer abstains (`INSUFFICIENT_CALIBRATION_HISTORY`). A heuristic score is never
presented as a probability.

### Abstention semantics

An abstention is a **first-class, evidence-producing** output — not an error and not a
fabricated prediction. Typed reasons include: insufficient history, stale history, excessive
missingness, subject mismatch, tenant/scope mismatch, invalid time order, conflicting
duplicate, unsupported target, unsupported horizon, irregular cadence, missing normalization
policy, invalid/non-finite measurement, inconsistent unit, insufficient calibration history,
and forecast outside permitted domain. Safe defaults reject/abstain. The domain gate never
silently clamps: an out-of-domain forecast abstains unless an explicit
`allow_out_of_domain` policy retains it *with a disclosed warning*.

### Evidence identity boundary

`CapacityForecastEvidence` is produced only through the controlled `forecast_with_evidence`
service path, which runs the real window construction, the real forecaster, and the real
uncertainty calibration, then binds their outputs. The `sha256:` digest covers **all
authoritative fields**: schema versions; subject/tenant; source-series and input-window
digests; cutoff/forecast-for; target/horizon; model id/version and config digest; feature-
config digest; normalization-policy digest; the forecast-or-abstention output; and the
uncertainty method/config. It **excludes** only `evidence_produced_at` (a production
timestamp) and `diagnostic_annotation` (a non-authoritative human note that must not
contradict the structured evidence). Changing any authoritative input, model, configuration,
provenance, output, or uncertainty field changes the digest. The digest is a **content
identity** — not a signature, an authorization, or any proof of forecast accuracy.

### Replay / evaluation method and leakage prevention

`run_replay_evaluation` advances through cutoffs; at each cutoff it builds history from
**only** observations with `event_time <= cutoff`, constructs the series, forecasts, then
matches the forecast against a **strictly-later** actual observation of the same subject that
carries the target, within an explicit horizon + timestamp tolerance. Two independent guards
enforce leakage safety: the input window's own construction-time invariant (no sample after
the cutoff), and a harness assertion that the constructed series ends at or before the
cutoff. The matched actual is drawn only from `event_time > cutoff`, so the scored value can
never have been a feature. The harness is robust to adversarial input — future records
preloaded into the source, randomized input order, duplicate timestamps, collection-time
later than observation-time, and an early-inserted future-event-time record — because it
filters by event time, not input position, and **fails closed** on any residual leakage.
Each match yields an immutable `ForecastEvaluationRecord`; the aggregate reports forecast
count, abstention count/rate, MAE, RMSE, mean signed error (bias), empirical interval
coverage, average interval width, and unmatched count. **Percentage-error metrics
(MAPE/SMAPE) are intentionally omitted** — several targets (queue depth, error rate,
replicas) are legitimately zero, which invalidates a percentage denominator.

## Boundary: what Phase 2 does NOT own or do

Phase 2 preserves `FORECAST != RECOMMENDATION != RISK EVALUATION != AUTHORITY !=
EXECUTION`. It does **not** add: live predictive scaling; any change to the controller
decision kernel; forecast-fed live recommendations; AWS/Azure/GCP/Kubernetes write APIs or
provider actuation adapters; cost/dependency optimization or cross-cloud placement; Risk
Authority integration, risk evaluation, authorization, ActionGate matching, execution
clearance/receipts, effect verification, or rollback; online learning or automatic model
selection/promotion. Forecasted pressure is **not** "Risk Authority risk"; it is descriptive
shadow capacity intelligence. Every forecast and evidence artifact carries
`advisory_only=True`, `shadow_only=True`, `actuation_performed=False`,
`authority_class=ADVISORY`, `execution_capability=NONE`.

## Relationship to Phase 1

Phase 2 is strictly additive on top of Phase 1. It consumes `CanonicalCapacityState`,
reuses the Phase-1 canonical serialization/digest conventions and the `CapacitySubject`,
`Measurement`/`Unit`, and `NormalizationPolicy` contracts, and reads targets from the exact
canonical fields Phase-1 projection uses. It changes no Phase-1 public contract. The
independent schema versions are new (`capacity-series-1`, `capacity-forecast-window-1`,
`capacity-forecast-1`, `capacity-forecast-evidence-1`, `capacity-forecast-evaluation-1`,
plus feature/uncertainty/admission config schemas); `ScalingObservation`,
`ScalingRecommendation`, and all Phase-1 canonical schemas are untouched.

## Consequences

- The capability now offers deterministic shadow forecasting + replay evaluation as a
  clearly-bounded, provider-neutral, dependency-free additive surface, with content-identity
  evidence a future separately-governed integration could reference.
- Two failure modes are made explicit and non-negotiable: **leakage** (prevented by
  event-time windowing + strictly-later matching + fail-closed guards) and **overclaiming**
  (prevented by first-class abstention, empirical-only uncertainty, and the maturity split
  below).
- No new runtime dependency; the wheel remains numpy-core + optional read-only `requests`.

## What Phase 2 does and does NOT prove

Passing tests and CI prove the **implementation** is correct — contracts, invariants,
leakage prevention, digest identity, and determinism. They do **not** prove the forecasts
are production-accurate. Synthetic fixtures are chosen to exercise contracts, not to
demonstrate accuracy (a low error on a synthetic ramp is a property of the fixture). Two
maturity axes are reported separately:

- **Implementation maturity:** `IMPLEMENTED_AND_LOCALLY_VERIFIED` (→ `IMPLEMENTED_AND_CI_VERIFIED`
  once every required Phase-2-relevant merge-gating check is green on the exact head).
- **Forecasting-model quality:** `BASELINE_FORECASTING_IMPLEMENTED` and, because the
  baselines have **not** been evaluated on representative external workloads against
  preregistered acceptance thresholds, `PREDICTIVE_QUALITY_NOT_ESTABLISHED`.

## Verification

Package suite (controller + Phase-1 canonical + Phase-2 forecasting/replay/leakage),
behavior-baseline parity (unchanged), compatibility/contract/boundary/side-effect/
provider-neutrality suites, the advisory distribution verifier (wheel build, isolated
install, packaged-source scans, and an **installed-wheel forecasting smoke** exercising the
full chain and confirming the live recommendation path is unchanged), manifest/authority
inventory, public-API stability, and version single-source consistency across `version.py`,
`module_manifest.json`, `artifacts/wheel_authority_inventory.json`, and the verifier's
`EXPECTED_VERSION`. Exact figures are recorded in the Phase-2 PR.
