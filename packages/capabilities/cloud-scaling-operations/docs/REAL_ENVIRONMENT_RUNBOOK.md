# Real-Environment Read-Only Shadow Runbook (future use)

> **Documentation only.** This runbook is **not executed** in the harness-only phase. It
> requires a separate authorization and a genuine non-production Kubernetes environment.
> Nothing here permits infrastructure mutation.

## Preconditions (all required)

- A genuine **non-production** cluster (dedicated/disposable test, staging, or an isolated
  non-production namespace of a shared cluster). **Never** production or customer clusters.
- An **explicit kubeconfig or injected client** — no auto-discovery, no current-context
  use, no in-cluster/cloud-provider default credentials.
- Explicit **context**, **cluster identifier**, **namespace allowlist**, **resource
  allowlist**, and **maximum target count**.
- A **read-only identity** whose RBAC grants only `get`/`list`/`watch` on approved
  resources (no `create`/`update`/`patch`/`delete`/`deletecollection`/`impersonate`/
  `bind`/`escalate`/`pods-exec`/secret reads).
- **TLS verification enabled**; explicit request timeout; the transport barrier enabled.
- Network reachability from the runner to the cluster API server.

## Preflight STOP conditions (fail closed)

Stop immediately, do not connect, if any of the following hold:

- The cluster is production or customer-facing.
- The identity is admin-scoped, can mutate resources, or can read secrets.
- The context is implicit / auto-discovered.
- TLS verification is disabled.
- The target allowlist is absent or empty.
- The read-only transport barrier is disabled.

If a genuine non-production environment or read-only access is unavailable, stop with
`CLOUD_SCALING_OPERATIONS_READ_ONLY_SHADOW_RESOURCE_BLOCKED`. Do **not** substitute mocks.

## Procedure (read-only)

1. Report the environment manifest (cluster id, redacted server URL, context, identity,
   approved namespaces/resources, credential source, read-only + non-production flags,
   TLS status). Never print tokens/certs/keys/kubeconfig contents.
2. Inspect RBAC via read-only calls; confirm least privilege; flag any mutation authority.
3. Observe only allowlisted targets through the transport barrier; collect only
   scaling-relevant fields; never read secrets/credential-bearing resources.
4. For each target: advisory recommendation → policy/safety → **local** shadow
   authorization → **proposed** decision → audit. Perform **no** mutation.
5. Exercise stale-state, authorization, HPA-interaction, and connectivity-failure paths.
6. Emit sanitized evidence to `artifacts/shadow_validation/` (reserved for real runs) and
   run the shadow integrity verifier. The request-method ledger must show zero transmitted
   write methods.

## Explicit CLI (future)

A future real command would require `--kubeconfig --context --cluster-id --namespace
--allowlist --read-only`. It must never auto-discover credentials and is not implemented
in this phase.
