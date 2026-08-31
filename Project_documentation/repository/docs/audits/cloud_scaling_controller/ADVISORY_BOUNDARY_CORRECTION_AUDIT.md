# Cloud Scaling Controller — Advisory Boundary Correction Audit

Corrective phase for **PR #1328** (merged as commit
`c2229fe6c097237a6963041fef7f5c4b36975e22` on the default branch
`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`).

## What PR #1328 did correctly

Canonicalized the Cloud Scaling implementation into one source tree and published
the independent distribution `ugence-cloud-scaling-controller` with legacy
compatibility shims, a package test suite, a distribution verifier, and CI. This
corrective phase **preserves** all of that.

## The defect

The manifest/docs declared `authority_class: ADVISORY`,
`execution_capability: NONE`, "does not modify infrastructure" — but the **wheel
shipped execution-capable code**. Dry-run defaults do not remove capability from a
distribution.

### Execution/operations modules found in the 0.1.0 wheel (AST + call-site analysis)

| Module | Capability found | Classification |
|--------|------------------|----------------|
| `action/k8s_actuator.py` | `patch_namespaced_deployment_scale` (K8s scale write) | ACTUATOR / MUTATION_CLIENT |
| `action/gate_actuator.py` | ArgoCD sync + bearer-token POST mutation | ACTUATOR / MUTATION_CLIENT |
| `action/rollback.py` | rollback execution | ROLLBACK_EXECUTOR |
| `action/policy.py`, `readiness.py`, `outcome.py`, `feedback.py` | admission/policy + actuation support | EXECUTOR support |
| `orchestrator.py` | production orchestration loop | PRODUCTION_ORCHESTRATOR |
| `main.py` | production entrypoint driving the orchestrator | PRODUCTION_ORCHESTRATOR |
| `recommend/engine.py` | approval → execute via `K8sActuator.scale(...)` | APPROVER → EXECUTOR |
| `recommend/approval.py` | approval lifecycle (auto/manual) | APPROVER |
| `recommend/webhook.py` | outbound Slack/PagerDuty/OpsGenie POST | MUTATION_CLIENT (egress) |
| `observability/metrics_server.py` | HTTP listener (`HTTPServer`/`start_http_server`) | network listener |
| `observability/exporter.py` | `push_to_gateway` egress | telemetry egress |
| `observability/otel_exporter.py` | OTLP export egress | telemetry egress |
| `shadow/runner.py` | hosts a `RecommendEngine` that can actuate | EXECUTOR-capable |
| `shadow/live_efficiency.py` | wraps `ShadowRunner` (live-cluster runner) | EXECUTOR-capable |

18 modules total (incl. `action/__init__.py`).

## Correction

These 18 modules are **moved out of the distributed package** into a monorepo-only
namespace `cloud_scaling_operations/`. They are **not** packaged in this PR. The
advisory package retains the 47 modules that only observe, assess, explain, replay,
read inputs, and recommend.

Dependency direction after correction:

```
cloud_scaling_operations  ──imports──▶  ugence_cloud_scaling_controller
```

The advisory package never imports `cloud_scaling_operations`. Import-graph analysis
confirms **zero** advisory→operations edges (the only edges were three re-exporting
`__init__.py` files, which are trimmed to advisory-only).

`confidence.py` and `safety.py` (advisory scoring / bound-clamping — no execution)
remain in the advisory package.

## Result

`artifacts/wheel_authority_inventory.json` classifies every packaged module as one
of CORE_ADVISORY / READ_ONLY_INPUT_ADAPTER / READ_ONLY_SHADOW_EVALUATION /
OFFLINE_REPLAY / OBSERVABILITY_ONLY / CLI_ADVISORY. No packaged module has a network
listener, network egress, or infrastructure-mutation capability. Version bumped
0.1.0 → 0.1.1.
