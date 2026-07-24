# Security Boundary & Tenant Isolation (M4)

*`customer_shadow_readiness/security.py`. A **non-enforcing, shadow-only** authentication / authorization
boundary and tenant-isolation guard for the pilot API surface. It gates access to the shadow runtime and
scopes traces/artifacts to a tenant — it never protects a real resource and never enforces a real
action.*

## Authentication

`authenticate(token)` verifies a deterministic HMAC-signed token against a principal registry and **fails
closed**: a missing, malformed, tampered, or unknown token yields an unauthenticated `Principal` with
empty scopes. (The HMAC key is a labelled stand-in, not a real secret — the real-key interface is in the
data-controls track. `issue_token` produces valid pilot tokens for testing.)

## Authorization (scopes)

`authorize(principal, required_scope)` grants access only if the principal holds the required scope or
`shadow:admin`. Scopes: `shadow:read`, `shadow:submit`, `shadow:review`, `shadow:admin`. A shadow API
endpoint declares the scope it needs; a principal without it is denied with `SEC.MISSING_SCOPE`.

## Tenant isolation

`tenant_permitted(principal, resource_tenant)` enforces that a principal may touch **only its own
tenant's** resources (an `admin` principal — tenant `*` — may touch any). A cross-tenant access is
denied with `SEC.CROSS_TENANT_DENIED`. This closes the pilot's earlier "tenant isolation PARTIAL" gap and
the integration-failure taxonomy's "cross-tenant artifact reference" row.

## Single access check

`check_access(token, required_scope, resource_tenant)` composes the three: authenticate → authorize →
tenant-isolate, **failing closed** at the first failure and returning namespaced reason codes
(`SEC.UNAUTHENTICATED`, `SEC.MISSING_SCOPE`, `SEC.CROSS_TENANT_DENIED`). Verified:

- valid token + own tenant + right scope → allowed;
- cross-tenant → `SEC.CROSS_TENANT_DENIED`;
- missing scope → `SEC.MISSING_SCOPE`;
- tampered token → `SEC.UNAUTHENTICATED:bad_signature`;
- no token → `SEC.UNAUTHENTICATED:missing_or_malformed_token`;
- admin → any tenant.

## What this is and is not

- **Is:** a fail-closed boundary that determines whether a shadow request is even accepted, and scopes
  every request/trace/artifact to a tenant.
- **Is not:** production authn/authz. There is no real IdP, no OAuth, no session management, no
  key-management-service — those are NOT-EVALUATED production dimensions. This is the *shadow-pilot*
  boundary: enough to run a bounded, tenant-scoped external shadow pilot without cross-tenant leakage,
  and no more. It is documented as such in the readiness assessment.
