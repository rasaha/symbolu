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
| `__version__` | str | `"0.1.1"`. |

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
