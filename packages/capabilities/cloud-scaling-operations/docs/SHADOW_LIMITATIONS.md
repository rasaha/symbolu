# Shadow Harness — Claims and Limitations

## What this phase establishes

- The read-only shadow harness is implemented and locally verified.
- The read-only transport barrier blocks every write method before transmission.
- Mutation canaries confirm no operations entrypoint transmits a write under shadow config.
- Fixture decisions are all shadow / proposed-only / not-executed.
- Authorization, staleness, HPA, network-failure, and redaction behavior are exercised
  with local fakes and are reproducible.

## What this phase does NOT establish

- Real cluster compatibility, RBAC compatibility, real workload/HPA observation, or real
  network compatibility.
- Safe live scaling, exactly-once execution, durable idempotency, durable audit,
  successful Kubernetes mutation, successful rollback, or ArgoCD integration.
- Production readiness/certification, customer validation, or any cost/reliability/
  performance improvement.

All committed evidence is **fake/local fixture** evidence. **No genuine Kubernetes
environment was observed.** Real-environment shadow validation remains **resource
blocked**. No infrastructure mutation occurred. **Live execution remains unauthorized.**

The next phase (separately authorized) is a real-environment read-only shadow run per
`REAL_ENVIRONMENT_RUNBOOK.md`, requiring explicit non-production cluster access.
