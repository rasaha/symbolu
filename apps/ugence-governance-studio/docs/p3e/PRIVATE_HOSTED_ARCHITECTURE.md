# Private Hosted Architecture (P3E)

One OCI container packages the frozen Governance Studio frontend (`0.2.0`) and the
frozen P3B backend (`0.1.0`, `governance_studio.api.v1`) behind a single HTTPS listener
on `8443/tcp`. A single ASGI process serves the SPA (`/`, `/assets/*`), the frozen API
(`/api/v1/*`, `/health`, `/ready`, `/version`) and deployment health (`/healthz`,
`/readyz`). Request path: TLS → trusted-host → access gate → origin/header guard →
security headers + 1 MiB cap → SPA static or frozen backend (synthetic-only catalog).

**P3E is:** single-tenant · synthetic-data-only · HTTPS-only · authenticated.
**P3E is not:** a public SaaS, a multitenant platform, an enterprise identity system, a
real-data deployment, a runtime-execution environment, a permission-provisioning or
business-action-authorization service. It does not grant permissions, provision
credentials, authorize business actions, execute agents, or integrate production systems.
