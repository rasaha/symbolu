# API Reference

Import namespace: `ugence_cloud_scaling_controller`.

## Public API

| Name | Kind | Purpose |
|------|------|---------|
| `CloudScalingController` | class | Stable package facade: observation → recommendation. |
| `Controller` | class | Low-level compatibility control API (`step(...) -> ActionResult`). |
| `InfraControllerConfig` | dataclass | Controller configuration (see [CONFIGURATION.md](CONFIGURATION.md)). |
| `ScalingObservation` | dataclass | Input contract (normalized observation). |
| `ScalingRecommendation` | dataclass | Output contract (deterministic, JSON-serializable). |
| `ActionResult` | dataclass | Low-level controller result (component breakdown + `explain()`). |
| `ScalingExecutor` | Protocol | Optional actuation seam (interface only; never invoked). |
| `ExecutionReceipt` | dataclass | Result type for an optional executor (never produced here). |
| `ContractError` | exception | Raised on invalid input (fail-closed). |
| `evaluate` | function | One-shot convenience: `evaluate(obs, config=None) -> ScalingRecommendation`. |
| `SCHEMA_VERSION` | str | `"1.1"` (output schema). |
| `__version__` | str | `"0.2.0"`. |

## `CloudScalingController`

```python
CloudScalingController(config: InfraControllerConfig | None = None)
```

- `recommend(observation: ScalingObservation | Mapping) -> ScalingRecommendation`
  Validates/normalizes the input (fail-closed), runs the unmodified control
  algorithm, returns an advisory recommendation.
- `bootstrap(historical_snapshots: list[Mapping[str, float]]) -> None`
  Pre-learn baselines from historical normalized snapshots.
- `reset() -> None` — reset all controller state.
- `bootstrapped: bool`, `config: InfraControllerConfig`, `controller: Controller`.

## `ScalingObservation`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `metrics` | `Mapping[str, float]` | yes | Normalized signals; values expected in `[0, 1]`. |
| `current_replicas` | `int` | yes | `>= 0`. |
| `deploy_active` | `bool` | no (`False`) | Rollout in progress → resistance. |
| `phase` | `str` | no (`"normal"`) | `peak`/`normal`/`off_peak`/`maintenance`; unknown → default. |
| `recent_pod_restarts` | `int` | no (`0`) | `>= 0`; adds resistance. |
| `correlation_id` | `str \| None` | no | Echoed on the recommendation. |
| `timestamp` | `float \| None` | no | Caller-supplied; never generated. |
| `metadata` | `Mapping \| None` | no | Opaque; passed through, never interpreted. |

**Consumed signals** (the only five that affect the decision):
`cpu`, `memory` (infra), `latency_p99`, `error_rate` (app), `queue_depth` (business).
Unknown signals are accepted and ignored by the pressure computation
(see [BOUNDARIES.md](BOUNDARIES.md) for full validation policy).

## `ScalingRecommendation`

Output schema version: **`1.1`**.

Fields: `schema_version`, `correlation_id`, `recommendation`, `replica_delta`,
`current_replicas`, `recommended_replicas`, `action_score`, `pressure`,
`component_breakdown`, `identity_deviation`, `explanation`, `controller_step`,
`metrics_snapshot`, `determinism`, `advisory_only` (always `True`),
`actuation_performed` (always `False`).

`determinism` is a disclosure block, e.g.::

    {"scope": "decision-deterministic",
     "identity_bootstrapped": false,
     "nondeterministic_fields": ["identity_deviation"],
     "note": "..."}

Decision fields (`recommendation`, `replica_delta`, `recommended_replicas`,
`action_score`, `pressure`, `component_breakdown`) are deterministic for a fixed
config + input sequence. `identity_deviation` is a diagnostic that varies before
bootstrap (see [EVIDENCE_AND_LIMITATIONS.md](EVIDENCE_AND_LIMITATIONS.md)); the whole
JSON result is **not** claimed fully deterministic.

Methods: `to_dict()` and `to_json(indent=None)` — deterministic (sorted) field
ordering.

`recommendation` values: `no_action`, `observe_out`, `observe_in`,
`scale_out_<n>`, `scale_in_<n>`. `recommended_replicas == current_replicas + replica_delta`.

## Example

```python
from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation

ctrl = CloudScalingController()
rec = ctrl.recommend(ScalingObservation(
    metrics={"cpu": 0.92, "memory": 0.88}, current_replicas=4, phase="peak",
    correlation_id="req-1",
))
print(rec.to_json(indent=2))
```

## Canonical Capacity Intelligence (Phase 1)

Subpackage `ugence_cloud_scaling_controller.canonical` — an **additive**, pure-stdlib
observation → normalization/projection → recommendation-evidence layer built around the
**unchanged** controller. It adds no dependency, no actuation, and no authority
integration. The five-signal decision kernel is not modified.

### Types

| Name | Kind | Purpose |
|------|------|---------|
| `CanonicalCapacityState` | frozen dataclass | Versioned, immutable, provider-neutral rich observation (`capacity-state-1`). All categories optional (partial observations). |
| `CapacitySubject` | frozen dataclass | Provider-neutral subject/scope identity (workload_id required; tenant/resource/environment/cluster/region/zone optional). |
| `Measurement` / `Unit` | frozen dataclass / enum | A value paired with an explicit unit (ratio, percent, ms, seconds, count, per_second, rate, …); fail-closed validation. |
| `ObservationProvenance` / `ObservationSourceType` | frozen dataclass / enum | First-class provenance; distinguishes `observed_at` (measurement time) from `collected_at` (record time). Missing provenance is explicit (`UNKNOWN`). |
| `WorkloadState`, `PerformanceState`, `InfrastructureState`, `CapacityState`, `ReliabilityState`, `DeploymentState`, `EconomicsState`, `TopologyState`, `ForecastObservation` | frozen dataclasses | Optional observation categories. `economics`/`forecast` are informational and never drive a recommendation. |
| `NormalizationPolicy` / `NormalizationMethod` / `NormalizedSignal` | frozen dataclass / enum / frozen dataclass | Explicit, policy-driven normalization (`capacity-normalization-policy-1`). Never invents a threshold; fails closed on NaN/inf, unsupported units/methods, zero/negative thresholds, out-of-range without clamping. |
| `ControllerProjection` / `project_to_scaling_observation` | frozen dataclass / function | Deterministic projection onto the existing `ScalingObservation` (`capacity-projection-1`). Discloses projected/normalized signals, used/ignored canonical fields, missing controller signals, warnings. |
| `CapacityDecisionEvidence` / `recommend_with_evidence` / `build_capacity_decision_evidence` | frozen dataclass / functions | Immutable recommendation evidence (`capacity-evidence-1`) with a deterministic `sha256:` content-identity digest. Built only through the controlled service path so it binds to the *real* projection and *real* recommendation (unforgeable). |
| `CapacityObservationSource` | Protocol | Read-only observation-source boundary. `FixtureObservationSource` / `ReplayObservationSource` ship; network adapters are future/opt-in. |

### Projection mapping

```text
infrastructure.cpu_utilization     -> metrics["cpu"]
infrastructure.memory_utilization  -> metrics["memory"]
performance.latency_p99            -> metrics["latency_p99"]   (p95 only with explicit opt-in, disclosed)
reliability.error_rate             -> metrics["error_rate"]
workload.queue_depth               -> metrics["queue_depth"]
deployment.deploy_active           -> deploy_active
reliability.restart_count          -> recent_pod_restarts
capacity.running_replicas          -> current_replicas         (REQUIRED; never ready/healthy/desired)
time_phase                         -> phase
correlation_id                     -> correlation_id
observed_at                        -> timestamp (epoch seconds)
```

`current_replicas` maps to the controller's documented *current running replica count*
(`capacity.running_replicas`); `ready`/`healthy`/`desired` are distinct and never
substituted — the projection fails closed if `running_replicas` is absent.

### Evidence digest (identity, not authority)

The `sha256:`-prefixed digest is computed over a documented, domain-separated canonical
form (sorted keys, NFC strings, RFC3339-UTC timestamps, floats round-tripped and
NaN/inf-rejected, nulls preserved). It **excludes** `evidence_produced_at` and the
human-readable `controller_explanation` (which embeds the disclosed nondeterministic
`identity_deviation` line), so it is reproducible for identical
`(state, policy, config, controller history)`. It is a **content identity only** — not a
signature, risk verdict, authorization, control-satisfaction claim, or execution
permission.
