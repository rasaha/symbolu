# Authority & Safety Boundary

The Cloud Scaling Controller core is a **recommendation engine**. Authority class
**ADVISORY**; execution capability **NONE**.

## Invariants

Every `ScalingRecommendation` carries `advisory_only = True` and
`actuation_performed = False`. These are enforced by the facade and asserted by the
test suite and the distribution verifier.

## The core must not (and does not)

- Modify Kubernetes deployments or call Kubernetes write APIs.
- Change HPA resources.
- Provision or terminate cloud resources.
- Use AWS/Azure/GCP credentials.
- Execute Terraform or run `kubectl`.
- Invoke business actions or grant permissions.
- Call an LLM.
- Depend on ActionGate, Governance Studio, Decision Governance, the Agent Runtime,
  an orchestrator, or a control plane.
- Open a network listener.
- Send telemetry externally by default.

**Verification.** The default import surface loads only NumPy-backed core modules
(no cloud SDK is imported); a full recommend cycle opens no socket, spawns no
subprocess, reads no cloud credentials, writes no unsolicited files, and imports no
forbidden module. See `tests/side_effects/` and
`verify_cloud_scaling_controller_distribution.py`.

## Input validation policy (fail-closed / normalize)

Validation happens in the facade **before** the control algorithm; the algorithm is
never altered to implement validation.

| Condition | Policy |
|-----------|--------|
| Missing known signals | Accepted; simply not counted. |
| Unknown signals | Accepted; **not** part of the weighted pressure groups. Like any provided numeric signal they may marginally enter the controller's variance-based damping term, but they cannot by themselves drive a scaling decision. |
| Non-numeric / bool metric value | **Fail closed** (`ContractError`). |
| `NaN` / `±inf` metric value | **Fail closed** (`ContractError`). |
| Metric value outside `[0, 1]` | Accepted; the algorithm clamps to `[0, 1]` (unchanged legacy behavior). |
| `current_replicas < 0` | **Fail closed** (`ContractError`). |
| `current_replicas == 0` | Accepted; the algorithm treats the effective floor as `>= 1`. |
| `recent_pod_restarts < 0` | **Fail closed** (`ContractError`). |
| Non-string `phase` | **Fail closed** (`ContractError`). |
| Unknown `phase` string | Accepted; handled as the default phase downstream. |
| Unknown top-level field (`from_dict`) | **Fail closed** (`ContractError`). |

## Optional actuation seam (interface only)

A future actuation seam is represented **only** as a protocol:

```python
class ScalingExecutor(Protocol):
    def apply(self, recommendation: ScalingRecommendation) -> ExecutionReceipt: ...
```

Version 0.1.1 ships **no** concrete executor at all. `ScalingExecutor` is an inert
`Protocol` (no implementation in the wheel), the facade never instantiates or invokes
one, and the CLI cannot supply one. There is no code in the wheel capable of applying
a recommendation.

## Optional read-only adapters (opt-in extras)

The read-only Prometheus signal adapter (`signals/prometheus.py`, HTTP GET) and the
read-only shadow HPA/state watcher (`shadow/hpa_watcher.py`, which reads via the
Prometheus client / kube-state-metrics — **not** the Kubernetes SDK) are the only
optional integrations, behind the `[prometheus]` / `[shadow]` extras. Both need only
`requests`. They import it lazily, are never on the advisory import path, and are
never invoked by `CloudScalingController` or the CLI. No Kubernetes/AWS/Azure/GCP SDK
is a dependency of this distribution.

## Execution/operations code is NOT in this distribution

The controller's execution, approval, orchestration, live-telemetry and live-shadow
modules — `action/` (K8s + gate actuators, rollback), `orchestrator.py`, `main.py`,
`recommend/{engine,approval,webhook}.py`, `observability/{metrics_server,exporter,
otel_exporter}.py`, `shadow/{runner,live_efficiency}.py` — were **moved out of the
wheel** into the monorepo-only `cloud_scaling_operations` namespace. They are:

- **MONOREPO-ONLY** — not packaged, not on PyPI, not importable from a wheel install;
- **NOT a stable distributed API**;
- **legacy/research operations code** pending separate packaging, review and
  governance (a future `ugence-cloud-scaling-operations` distribution).

The advisory package never imports `cloud_scaling_operations`; the dependency is
strictly `cloud_scaling_operations → ugence_cloud_scaling_controller`. The
distribution verifier opens every packaged `.py` and fails on any actuator, approver,
orchestrator, mutation call, or concrete executor. No infrastructure-write path is
shipped or was added.
