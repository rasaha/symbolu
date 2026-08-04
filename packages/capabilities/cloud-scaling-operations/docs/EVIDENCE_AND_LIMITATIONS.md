# Evidence & Limitations

## Evidence tiers
| Tier | Status |
|------|--------|
| Implemented | ✅ authority boundary, controlled executors, K8s/ArgoCD/rollback/idempotency/audit, CLI |
| Unit-tested | ✅ package suite (authority/execution/modes/security/boundaries/packaging/cli) using fakes |
| Fake-execution tested | ✅ Kubernetes/ArgoCD/rollback via injected fakes; no real cluster |
| Clean-wheel installable | ✅ distribution verifier (isolated venv, advisory dep resolved locally) |
| Advisory-boundary regression | ✅ advisory package remains advisory-only and green |
| Live-cluster validated | ❌ not performed |
| Production-certified | ❌ not performed |

## Limitations
- Contains infrastructure-mutation capability; **installation alone does not authorize
  execution.** Dry-run is default; LIVE requires external authorization + credentials +
  target allowlists + readiness + audit + idempotency.
- `InMemoryIdempotencyStore` / `InMemoryAuditSink` are process-local reference
  implementations — **not durable**, not multi-process safe; no exactly-once guarantee
  across distributed processes; no durable audit guarantee.
- Not live-cluster validated; not production-certified. No cost-saving, reliability, or
  production-safety claim is established by packaging tests.
- Kubernetes/ArgoCD/webhook/metrics/OTLP integrations require optional extras or
  injected clients.

## Not claimed
Production readiness, zero-risk scaling, autonomous safe execution, exactly-once
distributed execution, durable audit from in-memory stores, real-cluster validation,
or customer validation.
