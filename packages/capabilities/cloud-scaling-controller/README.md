# Ugence Cloud Scaling Controller

`ugence-cloud-scaling-controller` — a deterministic, provider-neutral, **advisory-only**
adaptive scaling controller. It consumes normalized workload/infrastructure
observations and produces explainable scaling **recommendations**. It is an
independent, installable capability with no dependency on Governance Studio, Decision
Governance, ActionGate, Agent Runtime, Hybrid LLM, LLM Steering, AI Hiring, or the
Ugence control plane.

- **Distribution:** `ugence-cloud-scaling-controller`
- **Import namespace:** `ugence_cloud_scaling_controller`
- **Version:** `0.1.1`
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
