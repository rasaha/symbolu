# Boundaries

- **Execution-capable, not advisory.** `authority_class: CONTROLLED_EXECUTION`,
  `execution_capability: INFRASTRUCTURE_MUTATION`. In LIVE mode it patches Kubernetes
  deployment scale and triggers ArgoCD syncs.
- **Advisory dependency is one-directional:** `ugence_cloud_scaling_operations`
  imports `ugence_cloud_scaling_controller`; the advisory package never imports this
  one. The advisory implementation is a dependency, not vendored.
- **Import has no side effects:** no listener, orchestrator loop, thread, subprocess,
  network request, credential discovery, or kubeconfig load at import time.
- **Default mode is DRY_RUN.** LIVE must be selected explicitly and requires an
  external authorization, target allowlists, credentials, readiness, an audit sink,
  and idempotency storage.
- **Mutation entrypoints:** `ControlledScalingExecutor.execute` (LIVE) and
  `GateExecutor.sync` (LIVE). Both fail closed without authorization.
- **The orchestrator loop is contained.** `approve()` is non-mutating; the recommendation
  engine refuses a mutating actuator at construction; the actuators discover no
  credentials (`docs/AUTHORITY_MODEL.md`, containment ruling).
- The Kubernetes SDK, ArgoCD access, metrics, and OTLP are optional extras / injected
  clients — none are core dependencies.
