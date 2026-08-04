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

Version 0.1.0 ships **no** production write-capable executor wired to the advisory
core, and calls **no** executor automatically.

## Optional read-only adapters (opt-in extras)

Existing Prometheus ingest, Kubernetes HPA/state watching (shadow mode), and
OpenTelemetry export are retained as **optional** adapters behind extras
(`[prometheus]`, `[shadow]`, `[otel]`). They import their SDKs lazily, are never on
the advisory import path, and are never invoked by `CloudScalingController` or the
CLI. Enabling them is an explicit, separately-authorized decision.

### Note on legacy operational modules

The package source retains the controller's pre-existing operational modules
(`action/`, `orchestrator.py`, `main.py`, `recommend/webhook.py`) so the verified
behavior and the full regression suite are preserved. These are **not** part of the
advisory public API, are never imported by the facade/CLI/default import path, and
require optional extras to function. In particular `action/k8s_actuator.py` is a
pre-existing, opt-in module that requires the `shadow` extra's `kubernetes` SDK; it
is **not** wired to or invoked by the capability. No infrastructure-write path was
**added** in this packaging phase.
