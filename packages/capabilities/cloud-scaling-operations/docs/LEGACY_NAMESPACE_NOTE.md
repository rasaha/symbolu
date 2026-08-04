# cloud_scaling_operations (MONOREPO-ONLY)

Execution / approval / orchestration / live-telemetry / live-shadow code for the
Cloud Scaling Controller. This namespace was separated **out** of the advisory
distribution `ugence-cloud-scaling-controller` (v0.1.1) so that wheel stays
advisory-only (no code capable of applying scaling advice).

**Status**

- **MONOREPO-ONLY** — not packaged, not on PyPI, not importable from a wheel install.
- **NOT a stable API** — subject to change/removal until separately packaged,
  reviewed, and governed (a future, separate `ugence-cloud-scaling-operations`
  distribution). It is **not** built or published in this phase.

**Dependency direction**

```
cloud_scaling_operations  ──imports──▶  ugence_cloud_scaling_controller
```

The advisory package never imports this namespace.

**Contents**

- `action/` — Kubernetes / gate actuators, rollback, policy, readiness, outcome, feedback
- `orchestrator.py`, `main.py` — production orchestration loop + entrypoint
- `recommend/` — approval → execute engine, approval manager, notification webhooks
- `observability/` — live telemetry (HTTP metrics server, Prometheus push, OTLP export)
- `shadow/` — live-cluster shadow runners

**Legacy compatibility**: `cloud_controller.action.*`, `cloud_controller.orchestrator`,
`symbolu.cloud_controller.action.*`, etc. resolve here (object identity preserved) via
the `cloud_controller` compatibility shim — monorepo-only.
