# Ugence Cloud Scaling Controller

`ugence-cloud-scaling-controller` — a deterministic, provider-neutral, **advisory-only**
adaptive scaling controller. It consumes normalized workload/infrastructure
observations and produces explainable scaling **recommendations**. It is an
independent, installable capability with no dependency on Governance Studio, Decision
Governance, ActionGate, Agent Runtime, Hybrid LLM, LLM Steering, AI Hiring, or the
Ugence control plane.

- **Distribution:** `ugence-cloud-scaling-controller`
- **Import namespace:** `ugence_cloud_scaling_controller`
- **Version:** `0.1.0`
- **Authority class:** ADVISORY · **Execution capability:** NONE
- **Core dependency:** NumPy only · **Network required (core):** no · **Cloud credentials required:** no

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

## What it does

- Consumes normalized workload and infrastructure observations (`cpu`, `memory`,
  `latency_p99`, `error_rate`, `queue_depth`; unknown signals are accepted and ignored).
- Maintains adaptive controller state (plasticity gate, adaptive gain, damping,
  coherence, identity EMA, replay buffer, trend/staleness/latency/recovery detectors).
- Produces explainable scaling recommendations with a full component breakdown and a
  human-readable explanation.
- Supports offline and shadow evaluation.
- Remains provider neutral — it names no AWS/Azure/GCP concept in its contract.

## What it does **not** do

- Does not directly scale infrastructure.
- Does not replace the Kubernetes HPA by default.
- Does not authorize infrastructure changes.
- Does not make cloud-provider API calls.
- Does not guarantee cost savings.
- Is not automatically production-safe.
- Is not a self-operating cloud platform.
- Is not an LLM.
- Is not part of Governance Studio runtime operation.

See [`docs/BOUNDARIES.md`](docs/BOUNDARIES.md) for the full authority/safety boundary.

## Installation

```console
pip install ugence-cloud-scaling-controller            # core (NumPy only)
pip install ugence-cloud-scaling-controller[prometheus] # + read-only Prometheus adapters
pip install ugence-cloud-scaling-controller[shadow]     # + read-only K8s HPA watcher, YAML config
pip install ugence-cloud-scaling-controller[otel]       # + OpenTelemetry export
```

Optional extras are backed by real code and are never required for the advisory core.

## Public API

`CloudScalingController`, `Controller`, `InfraControllerConfig`, `ScalingObservation`,
`ScalingRecommendation`, `ActionResult`, `evaluate`, `__version__`. See
[`docs/API.md`](docs/API.md).

`Controller` is the low-level compatibility API; `CloudScalingController` is the stable
independent-package facade.

## Legacy imports

`from cloud_controller.controller import Controller` and
`from symbolu.cloud_controller.controller import Controller` keep working (object
identity preserved) during a documented compatibility period. See
[`docs/LEGACY_IMPORT_MIGRATION.md`](docs/LEGACY_IMPORT_MIGRATION.md).

## Evidence status

Claims are separated by evidence tier — see
[`docs/EVIDENCE_AND_LIMITATIONS.md`](docs/EVIDENCE_AND_LIMITATIONS.md). In short:

- **Implemented & unit-tested:** the control algorithm, contracts, CLI, legacy
  compatibility, and packaging (package-local test suite + the pre-existing regression
  suite, 760 passing).
- **Simulation-tested:** synthetic scenario/benchmark harnesses (seeded).
- **Behavior-baseline verified:** post-packaging output reproduces the frozen
  pre-packaging behavior baseline exactly (deterministic projection).
- **Not** live-cluster validated by this package; **not** production-certified. No
  customer-validation, production-savings, or real-cluster-superiority claims are made
  here.
