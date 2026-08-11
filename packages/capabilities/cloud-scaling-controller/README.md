# Ugence Cloud Scaling Controller

`ugence-cloud-scaling-controller` — a deterministic, provider-neutral, **advisory-only**
adaptive scaling controller. It consumes normalized workload/infrastructure
observations and produces explainable scaling **recommendations**. It is an
independent, installable capability with no dependency on Governance Studio, Decision
Governance, ActionGate, Agent Runtime, Hybrid LLM, LLM Steering, AI Hiring, or the
Ugence control plane.

- **Distribution:** `ugence-cloud-scaling-controller`
- **Import namespace:** `ugence_cloud_scaling_controller`
- **Version:** `0.3.0`
- **Authority class:** ADVISORY · **Execution capability:** NONE (no code in the wheel can apply the advice)
- **Core dependency:** NumPy only · **Network required (core):** no · **Cloud credentials required:** no
- **Determinism:** decision-deterministic; identity diagnostics vary before bootstrap.

```python
from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation

ctrl = CloudScalingController()
rec = ctrl.recommend(ScalingObservation(
    metrics={"cpu": 0.92, "memory": 0.88, "latency_p99": 0.81, "error_rate": 0.2, "queue_depth": 0.7},
    current_replicas=4,
    phase="peak",
    correlation_id="req-123",
))
print(rec.recommendation, rec.replica_delta)   # e.g. scale_out_1 1
print(rec.advisory_only, rec.actuation_performed)  # True False
print(rec.to_json(indent=2))
```

Command line (offline, no credentials, no network):

```console
$ ugence-cloud-scaling demo
$ echo '{"metrics": {"cpu": 0.9}, "current_replicas": 3}' | ugence-cloud-scaling evaluate --input -
$ ugence-cloud-scaling version
```

## What it provides

- Provider-neutral scaling analysis of normalized workload/infrastructure
  observations (`cpu`, `memory`, `latency_p99`, `error_rate`, `queue_depth`; unknown
  signals are accepted and do not drive the decision).
- Adaptive controller state (plasticity gate, adaptive gain, damping, coherence,
  identity EMA, replay buffer, trend/staleness/latency/recovery detectors).
- Explainable scaling recommendations with a full component breakdown and a
  human-readable explanation.
- Offline evaluation, trace replay, and read-only shadow comparison.
- An advisory CLI. No direct actuation.

## Canonical Capacity Intelligence (Phase 1)

Version 0.2.0 adds a provider-neutral **observation → normalization/projection →
recommendation-evidence** layer *around* the unchanged controller. The rich canonical
state does **not** change the controller's five-signal decision model — an explicit,
deterministic projection maps only the controller's established inputs and reports
everything else as ignored context.

```text
Provider / Monitoring Source
        ↓
CanonicalCapacityState          (rich, immutable, versioned, provider-neutral)
        ↓
Normalization / Projection      (explicit, deterministic, policy-driven)
        ↓
existing ScalingObservation
        ↓
existing CloudScalingController (unchanged decision kernel)
        ↓
ScalingRecommendation  +  CapacityDecisionEvidence  (immutable, sha256 content-identity)
```

```python
from datetime import datetime, timezone
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacitySubject, InfrastructureState, PerformanceState,
    ReliabilityState, WorkloadState, CapacityState, Measurement, Unit,
    NormalizationPolicy, NormalizationMethod, recommend_with_evidence,
)

state = CanonicalCapacityState(
    subject=CapacitySubject(workload_id="checkout-api", tenant_id="acme"),
    observed_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
    correlation_id="req-123", time_phase="peak",
    infrastructure=InfrastructureState(cpu_utilization=Measurement(92.0, Unit.PERCENT),
                                       memory_utilization=Measurement(88.0, Unit.PERCENT)),
    performance=PerformanceState(latency_p99=Measurement(810.0, Unit.MILLISECONDS)),
    reliability=ReliabilityState(error_rate=Measurement(0.2, Unit.RATE)),
    workload=WorkloadState(queue_depth=Measurement(70, Unit.COUNT)),
    capacity=CapacityState(running_replicas=4),
)
policy = NormalizationPolicy(
    policy_id="default-slo-v1",
    method_by_signal={
        "cpu": NormalizationMethod.PERCENT_TO_RATIO,
        "memory": NormalizationMethod.PERCENT_TO_RATIO,
        "latency_p99": NormalizationMethod.LATENCY_MS_TO_THRESHOLD,
        "error_rate": NormalizationMethod.RATIO_PASSTHROUGH,
        "queue_depth": NormalizationMethod.QUEUE_TO_CAPACITY,
    },
    thresholds={"latency_p99": 1000.0, "queue_depth": 100.0},
)
rec, evidence = recommend_with_evidence(state, policy)
print(rec.recommendation, rec.replica_delta)          # advisory recommendation (unchanged kernel)
print(evidence.digest())                              # sha256: content identity
print(evidence.ignored_canonical_fields)              # honest: what did NOT drive the decision
```

**Newly implemented in Phase 1:** canonical capacity-state representation; typed
measurements + explicit units; policy-driven normalization; deterministic controller
projection; first-class observation provenance; immutable recommendation evidence with a
deterministic content-identity digest; a read-only observation-source boundary. See the
[Phase-1 ADR](../../../docs/architecture/ADR_CLOUD_SCALING_CANONICAL_CAPACITY_INTELLIGENCE_PHASE1.md).

**Implemented elsewhere, NOT integrated here:** the canonical Risk Authority RA-1→RA-8
authority lifecycle (risk artifacts, scope, expiry/revocation, integrity, downstream
enforcement) lives in separate packages. Phase 1 produces *upstream recommendation
evidence only*; the evidence digest is a stable identity a **future, separately governed**
integration package could reference. This package performs no risk evaluation, authority,
or authorization.

**Future / not implemented in this phase:** native AWS/Azure/GCP collectors; predictive
forecasting; dependency-aware scaling; economic optimization; cross-cloud placement; a
CapacityDecisionEvidence→RA integration adapter; authority-bound scaling; provider
execution; execution receipts; effect verification; closed-loop learning.

## Predictive Capacity Intelligence (Phase 2 — shadow forecasting)

Version 0.3.0 adds a deterministic, provider-neutral, **shadow-only** forecasting and
replay-evaluation layer *around* the Phase-1 canonical layer. It answers: *given the
capacity history available at event time, what capacity pressure is likely at a future
horizon, how uncertain is that prediction, and how well has the method performed in
replay?* **Forecasts never feed the live controller and never actuate anything.**

```text
CanonicalCapacityState history
        ↓  series validation + strict event-time ordering
CanonicalCapacitySeries
        ↓  leakage-safe input window (event_time <= cutoff, invariant-checked)
ForecastInputWindow
        ↓  deterministic baseline forecaster (persistence / linear trend)
CapacityForecast          (point + empirical uncertainty  OR  typed abstention)
        ↓  controlled service path binds window + config + output
CapacityForecastEvidence  (immutable, sha256 content-identity digest)
        ↓  shadow replay against strictly-later actual observations
ForecastEvaluationRecord  + deterministic aggregate (MAE / RMSE / bias / coverage)
```

```python
from datetime import datetime, timedelta, timezone
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacitySubject, InfrastructureState, CapacityState,
    Measurement, Unit, NormalizationPolicy, NormalizationMethod,
)
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries, ForecastTarget, ForecastHorizon,
    PersistenceForecaster, UncertaintyConfig, forecast_with_evidence,
)

subj = CapacitySubject(workload_id="checkout-api", tenant_id="acme")
t0 = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
history = [CanonicalCapacityState(
    subject=subj, observed_at=t0 + timedelta(seconds=60 * i),
    infrastructure=InfrastructureState(cpu_utilization=Measurement(70.0 + i, Unit.PERCENT)),
    capacity=CapacityState(running_replicas=4)) for i in range(8)]

series = CanonicalCapacitySeries.build(history)
policy = NormalizationPolicy(policy_id="slo-v1",
                             method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})
evidence = forecast_with_evidence(
    series, ForecastTarget.CPU_UTILIZATION, series.end_event_time, ForecastHorizon.minutes(5),
    PersistenceForecaster(), normalization_policy=policy,
    uncertainty_config=UncertaintyConfig(min_calibration_samples=3, match_tolerance_seconds=5.0),
)
fc = evidence.forecast
print(fc.status, fc.point_estimate, fc.uncertainty.available)  # forecast / point / interval?
print(fc.advisory_only, fc.shadow_only, fc.actuation_performed) # True True False
print(evidence.digest())                                        # sha256: content identity
```

**Baseline models:** persistence (last value) and deterministic linear-trend (OLS). A
third baseline is deferred until replay evaluation justifies it. **Uncertainty:** an
empirical rolling-origin residual interval (non-Gaussian; explicitly *unavailable* when
residuals are insufficient). **Abstention** is a first-class, evidence-producing output
(insufficient/stale history, excessive missingness, irregular cadence, subject/tenant
mismatch, unsupported target/horizon, missing normalization policy, out-of-domain
forecast, insufficient calibration, …). See the
[Phase-2 ADR](../../../docs/architecture/ADR_CLOUD_SCALING_PREDICTIVE_CAPACITY_INTELLIGENCE_PHASE2.md).

> **Maturity:** `IMPLEMENTED_AND_LOCALLY_VERIFIED` · `BASELINE_FORECASTING_IMPLEMENTED` ·
> `PREDICTIVE_QUALITY_NOT_ESTABLISHED`. Passing tests/CI prove implementation
> correctness, **not** forecast accuracy — the baselines have not been evaluated on
> representative external workloads against preregistered acceptance thresholds. A
> FORECAST is descriptive capacity intelligence: it is not a recommendation, a risk
> evaluation, an authority, or an execution instruction.

## What it does **not** provide

- Does not scale Kubernetes / mutate the HPA.
- Does not synchronize ArgoCD.
- Does not automatically approve recommendations.
- Does not perform admission control.
- Does not execute rollbacks.
- Does not run production orchestration.
- Does not provision or terminate cloud resources.
- Does not authorize infrastructure changes.
- Does not make cloud-provider API calls, guarantee cost savings, or replace the HPA.
- Is not automatically production-safe, is not a self-operating cloud platform, is
  not an LLM, and is not part of Governance Studio runtime operation.

Execution/approval/orchestration code is **not shipped in this distribution**. It
exists only as **monorepo-only legacy/research operations code** (the
`cloud_scaling_operations` namespace) until separately packaged, reviewed, and
governed. This package is **not** a production autoscaler.

See [`docs/BOUNDARIES.md`](docs/BOUNDARIES.md) for the full authority/safety boundary.

## Installation

```console
pip install ugence-cloud-scaling-controller             # core (NumPy only)
pip install ugence-cloud-scaling-controller[prometheus] # + read-only Prometheus ingest (requests)
pip install ugence-cloud-scaling-controller[shadow]     # + read-only HPA/state reads via Prometheus (requests)
```

The single optional runtime dependency is `requests` (read-only Prometheus/shadow
adapters). No Kubernetes/AWS/Azure/GCP SDK is a dependency. Optional extras are never
required for the advisory core.

## Public API

`CloudScalingController`, `Controller`, `InfraControllerConfig`, `ScalingObservation`,
`ScalingRecommendation`, `ActionResult`, `evaluate`, `__version__`. See
[`docs/API.md`](docs/API.md).

`Controller` is the low-level compatibility API; `CloudScalingController` is the stable
independent-package facade.

Phase 1 also exports the canonical capacity-intelligence layer (subpackage
`ugence_cloud_scaling_controller.canonical`): `CanonicalCapacityState`, `CapacitySubject`,
`Measurement`, `Unit`, `ObservationProvenance`, `ObservationSourceType`,
`NormalizationPolicy`, `NormalizationMethod`, `ControllerProjection`,
`project_to_scaling_observation`, `CapacityDecisionEvidence`, `recommend_with_evidence`,
`CapacityObservationSource`.

Phase 2 exports the shadow forecasting layer (subpackage
`ugence_cloud_scaling_controller.forecasting`): `CanonicalCapacitySeries`,
`SeriesConstructionPolicy`, `ForecastTarget`, `ForecastHorizon`, `ForecastInputWindow`,
`FeatureConfig`, `build_input_window`, `BaselineForecaster`, `PersistenceForecaster`,
`LinearTrendForecaster`, `UncertaintyConfig`, `UncertaintyMethod`, `AbstentionReason`,
`CapacityForecast`, `AdmissionPolicy`, `CapacityForecastEvidence`, `generate_forecast`,
`forecast_with_evidence`, `ForecastEvaluationRecord`, `AggregateEvaluation`,
`evaluate_forecast`, `aggregate_evaluations`, `run_replay_evaluation`.

## Legacy imports

Advisory legacy imports (`from cloud_controller.controller import Controller`,
`from symbolu.cloud_controller.controller import Controller`) keep working with object
identity preserved. Legacy **operational** imports
(`cloud_controller.action.k8s_actuator`, `cloud_controller.orchestrator`, …) resolve
to the monorepo-only `cloud_scaling_operations` namespace and are **not** part of this
distribution. See [`docs/LEGACY_IMPORT_MIGRATION.md`](docs/LEGACY_IMPORT_MIGRATION.md).

## Evidence status

Claims are separated by evidence tier — see
[`docs/EVIDENCE_AND_LIMITATIONS.md`](docs/EVIDENCE_AND_LIMITATIONS.md). In short:

- **Implemented & unit-tested:** the control algorithm, contracts, CLI, legacy
  compatibility, and packaging (package-local suite + the pre-existing regression
  suite).
- **Simulation-tested / trace-replay tested:** synthetic scenario/benchmark harnesses
  and the replay harness (seeded).
- **Behavior-baseline verified:** post-packaging output reproduces the frozen
  pre-packaging behavior baseline exactly (decision-deterministic projection).
- **Determinism:** decision fields are deterministic; `identity_deviation` is a
  diagnostic that varies before deterministic bootstrap (disclosed in the output's
  `determinism` block). The complete JSON result is **not** claimed fully
  deterministic.
- **Not** live-cluster validated by this package; **not** production-certified. No
  customer-validation, production-savings, or real-cluster-superiority claims are made.
