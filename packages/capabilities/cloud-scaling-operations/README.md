# Ugence Cloud Scaling Operations

`ugence-cloud-scaling-operations` — the **controlled-execution** layer for cloud
scaling. Unlike the advisory `ugence-cloud-scaling-controller` (which only recommends),
this package **contains infrastructure-mutation capability**: in `LIVE` mode, with
credentials and an explicit external authorization, it can patch Kubernetes deployment
scale and trigger ArgoCD syncs.

- **Distribution:** `ugence-cloud-scaling-operations` · **Import:** `ugence_cloud_scaling_operations` · **Version:** `0.1.0`
- **Authority class:** `CONTROLLED_EXECUTION` · **Execution capability:** `INFRASTRUCTURE_MUTATION`
- **Advisory-only:** false · **Contains concrete executor:** true · **Requires external authorization:** true
- **Default execution mode:** `dry_run` · **Live execution enabled by default:** no

> **Installation alone does not authorize execution.** Dry-run is a runtime *mode*, not
> an absence of capability. Live mutation requires an external `ExecutionAuthorization`,
> target allowlists, credentials, readiness, an audit sink, and idempotency storage.

## Authority model

```
ADVISORY_RECOMMENDATION → POLICY_AND_SAFETY_EVALUATION → HUMAN_OR_EXTERNAL_GOVERNANCE_APPROVAL
    → EXECUTION_AUTHORIZATION → READINESS_CHECK → CONTROLLED_EXECUTION → OUTCOME_AND_AUDIT
```

Every infrastructure change requires an immutable `ExecutionAuthorization` minted by an
external authority. **A recommendation, an approval Boolean, or a confidence score is
NOT execution authority.** All mutation paths fail closed (missing/expired/wrong-tenant/
wrong-target/wrong-action/out-of-bounds/replayed/untrusted-issuer → denied). The
recommendation engine can never mint its own authority: `auto_approve_threshold` is
refused when it would drive a non-dry-run actuator.

## Execution modes

| Mode | Mutates? | Needs authorization | Needs credentials |
|------|----------|---------------------|-------------------|
| `DRY_RUN` (default) | no — proposes only | no | no |
| `SIMULATION` | no — deterministic local fakes | yes | no |
| `SHADOW` | no — read-only observation | no | (read-only) |
| `LIVE` | **yes** | yes | yes |

Importing the package starts **no** listener, orchestrator loop, thread, subprocess,
network request, credential discovery, or kubeconfig load.

## What it provides
Authority-gated `ControlledScalingExecutor`, injected-client `KubernetesScalingExecutor`,
`GateExecutor` (ArgoCD/admission), `RollbackCoordinator`, readiness/outcome/audit, and
idempotency — plus the legacy operations modules (orchestrator, recommend pipeline,
observability, shadow runners) as monorepo-migrated code.

## What it does **not** claim
Not production-certified; not live-cluster validated; no cost/reliability/safety claim
established by packaging tests. The in-memory idempotency and audit stores are **not**
durable and do not provide exactly-once execution across distributed processes.

## Installation

```console
pip install ugence-cloud-scaling-operations              # core: advisory dep only (dry-run/simulation)
pip install ugence-cloud-scaling-operations[kubernetes]  # + Kubernetes SDK for LIVE clients
pip install ugence-cloud-scaling-operations[metrics]     # + Prometheus export
pip install ugence-cloud-scaling-operations[otel]        # + OpenTelemetry export
```

The core install needs no cloud SDK — dry-run, simulation, and import require none.

## CLI (non-mutating by default)

```console
$ ugence-cloud-scaling-operations version
$ ugence-cloud-scaling-operations inspect-capabilities
$ ugence-cloud-scaling-operations dry-run --input request.json
$ ugence-cloud-scaling-operations simulate --input request.json --authorization authz.json
# live requires an explicit command + flags and an operator-configured backend:
$ ugence-cloud-scaling-operations execute --mode live --authorization authz.json --confirm
```

`demo`, `run`, and an empty invocation never mutate infrastructure.

## Legacy imports (monorepo-only)
`cloud_scaling_operations.*`, `cloud_controller.action.*`, `cloud_controller.orchestrator`,
`symbolu.cloud_controller.action.*` resolve to `ugence_cloud_scaling_operations` with
object identity preserved. These are monorepo-only compatibility surfaces, not a stable
distributed API — see [`docs/LEGACY_IMPORT_MIGRATION.md`](docs/LEGACY_IMPORT_MIGRATION.md).

See [`docs/AUTHORITY_MODEL.md`](docs/AUTHORITY_MODEL.md), [`docs/SECURITY.md`](docs/SECURITY.md),
[`docs/BOUNDARIES.md`](docs/BOUNDARIES.md), [`docs/FAILURE_AND_ROLLBACK.md`](docs/FAILURE_AND_ROLLBACK.md),
and [`docs/EVIDENCE_AND_LIMITATIONS.md`](docs/EVIDENCE_AND_LIMITATIONS.md).
