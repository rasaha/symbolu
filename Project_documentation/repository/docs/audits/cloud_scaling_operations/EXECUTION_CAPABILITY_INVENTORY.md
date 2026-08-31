# Cloud Scaling Operations — Execution Capability Inventory

Packaging audit for the monorepo-only `cloud_scaling_operations/` namespace as the
independently-governed distribution **`ugence-cloud-scaling-operations`** (canonical
import `ugence_cloud_scaling_operations`).

Machine-readable companion:
[`packages/capabilities/cloud-scaling-operations/artifacts/execution_capability_inventory.json`](../../../packages/capabilities/cloud-scaling-operations/artifacts/execution_capability_inventory.json)
(22 modules; per-module public symbols, mutation/network/listener/credential/subprocess
flags, third-party deps, imported advisory interfaces, packaging decision).

## Honest capability declaration

Unlike the advisory wheel (`ugence-cloud-scaling-controller`, `execution_capability:
NONE`), this package **contains concrete infrastructure-mutation capability**:

- `authority_class: CONTROLLED_EXECUTION`
- `execution_capability: INFRASTRUCTURE_MUTATION`
- `advisory_only: false`, `contains_concrete_executor: true`
- `requires_external_authorization: true`, `live_execution_enabled_by_default: false`
- `production_certified: false`, `live_cluster_validated: false`

**Dry-run is a runtime mode, not an absence of capability.** The wheel ships code that
can, in `LIVE` mode with credentials and authorization, patch Kubernetes deployment
scale and trigger ArgoCD syncs.

## Mutation entrypoints (must be authority-gated)

| Module | Capability |
|--------|-----------|
| `action/k8s_actuator.py` | `K8sActuator.scale()` → `patch_namespaced_deployment_scale` (Kubernetes deployment scale mutation) |
| `action/gate_actuator.py` | `GateActuator.execute()` → ArgoCD `POST /sync` (active sync = mutation); admission-gate ALLOW/HOLD/SYNC |

Both currently gate only on a *mode enum* (DRY_RUN vs SCALE_PATCH/ARGOCD_SYNC) — they
do **not** require an external authorization object. This packaging phase wraps them in
a `ControlledScalingExecutor` that **fails closed** without a valid
`ExecutionAuthorization`, enforces target allowlists / replica bounds / idempotency,
and emits audit events. The low-level actuators remain the injected mechanism.

## Auto-approval-to-execution path (must be neutralized in production)

`orchestrator.py` (`auto_approve_threshold`) and `main.py` auto-approve high-confidence
recommendations and then execute them via the actuator — i.e. the engine can mint its
own authority from its own recommendation. In the packaged production (`LIVE`) path this
is **prohibited**: `auto_approve_threshold` is restricted to `DRY_RUN`/`SIMULATION` by a
hard runtime guard, and the controlled executor requires a separate external
`ExecutionAuthorization` regardless of any approval Boolean or confidence score.

## Module groups (22 modules)

- **`action/`** — `k8s_actuator` (mutation), `gate_actuator` (ArgoCD/admission mutation),
  `rollback`, `policy`, `readiness`, `outcome`, `feedback`. Actuation + supporting
  policy/readiness/outcome/rollback logic.
- **`recommend/`** — `engine` (approval→execute pipeline), `approval` (lifecycle),
  `webhook` (Slack/PagerDuty/OpsGenie egress).
- **`observability/`** — `exporter` (Prometheus push egress), `metrics_server`
  (HTTP listener), `otel_exporter` (OTLP egress).
- **`shadow/`** — `runner` (live-loop), `live_efficiency` (Track-A live shadow).
- **`orchestrator.py`** — production orchestration loop. **`main.py`** — production CLI
  entrypoint.

## Capability summary (from the JSON)

- **Mutation:** `action/k8s_actuator.py`, `action/gate_actuator.py`
- **Network egress:** gate_actuator, webhook, exporter, otel_exporter, shadow/live_efficiency, orchestrator, main, policy
- **Network listener:** `observability/metrics_server.py`
- **Credentials referenced:** k8s_actuator, gate_actuator, webhook
- **Subprocess:** none
- **Imported advisory interfaces:** `ugence_cloud_scaling_controller.{controller,config,recommend.confidence,recommend.safety,explain.explainer,observability.*}` — operations depends on advisory (one-directional).

## Dependency direction (enforced)

```
ugence_cloud_scaling_operations  ──imports──▶  ugence_cloud_scaling_controller
```

The advisory package must never import operations. Verified by the operations
distribution verifier and the advisory-boundary regression.

## Packaging decision

All 22 modules move into `ugence_cloud_scaling_operations` (one canonical copy). The
root `cloud_scaling_operations` namespace and the `cloud_controller.*` /
`symbolu.cloud_controller.*` operational legacy paths become monorepo-only, logic-free
compatibility shims routing to the canonical package with object identity preserved.
The advisory implementation is **not** duplicated — operations imports it as a
dependency.
