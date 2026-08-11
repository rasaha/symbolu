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

## Canonical Capacity Intelligence layer (Phase 1) — boundary

The `canonical` subpackage (v0.2.0) is an **additive, advisory-only** observation and
evidence layer. It preserves every invariant above:

- It is pure-stdlib — it adds **no** runtime dependency (no cloud SDK, no network).
- It performs **no** actuation, opens **no** socket, spawns **no** subprocess, and reads
  **no** credentials (asserted by `tests/canonical/test_sources_and_side_effects.py`).
- Provider semantics terminate at the observation/normalization boundary. Provider labels
  live only in provenance; the projection is provider-neutral and contains **no**
  `provider == "..."` decision branch. Two states differing only by provider project
  identically.
- The decision kernel is **unchanged**: the projection maps only the five established
  signals plus `deploy_active`, `recent_pod_restarts`, `current_replicas`, `phase`,
  `correlation_id`, and `timestamp`. Every other canonical field is reported as ignored.
- `CapacityDecisionEvidence` always carries `advisory_only=True`,
  `actuation_performed=False`, `authority_class="ADVISORY"`, `execution_capability="NONE"`.

### Risk Authority boundary (strict, one-directional)

The canonical layer produces **upstream recommendation evidence only**. It must not, and
does not:

- import any Risk Authority / Decision Authority / action-gate / Agent Runtime / Runtime
  Assurance / operations implementation (AST-asserted by
  `tests/canonical/test_ra_boundary.py`);
- construct a risk evaluation, verdict, authorization, or authority-lifecycle record;
- evaluate controls or claim controls were satisfied;
- perform expiry, revocation, or action-gate matching.

The evidence `digest()` is a **content identity** (`sha256:` over a documented canonical
form) — never a signature, authorization, or risk verdict. A future, separately governed
integration package may reference this digest/identity to bind capacity evidence into the
canonical RA-1→RA-8 lifecycle; that adapter is **not** part of this phase, and neither
leaf package depends on the other.

### Read-only observation sources

`CapacityObservationSource` is a read-only `Protocol` (`observe() -> CanonicalCapacityState`).
No write-capable client is reachable through it. Phase 1 ships only fixture / replay
sources; network-backed adapters (Prometheus, CloudWatch, Azure Monitor, GCP Monitoring,
Kubernetes read APIs) are future work and, like the existing `prometheus`/`shadow` extras,
must remain opt-in, read-only, lazily imported, and off the default import path.
