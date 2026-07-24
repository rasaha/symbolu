# Non-Enforcing Pilot API & Secure Intake (M6)

*`customer_shadow_readiness/pilot_api.py` + `intake.py`. The single shadow-only entry point for a
bounded customer pilot. It composes access control, secure intake, data minimization, kill switches, and
the READ-ONLY pilot orchestrator, returning a `WOULD_*` disposition. It **never enforces** and **never
executes an external action** — `enforced` is always `False`.*

## Secure artifact intake

`intake(text, request_clearance, output_form)` validates before anything enters the runtime and **fails
closed**:

- empty / non-string → `INTAKE.EMPTY`;
- over `MAX_TEXT_CHARS` (20000) → `INTAKE.OVERSIZE`;
- unrecognized output form → `INTAKE.BAD_FORM`;
- artifact class not permitted under the request's clearance → `INTAKE.NOT_PERMITTED` (uses the M5
  clearance lattice);
- otherwise accepted, classified, and **redacted** before use.

## The submit path

`submit(token, tenant, case)` runs, in order, **failing closed at the first failure**:

1. **Kill switches** — pilot-wide or tenant-level trip → refuse with `KILL.*` (no work accepted).
2. **Access control** — `security.check_access(token, "shadow:submit", tenant)` → authn + scope + tenant
   isolation; failure → `CONTRACT_ERROR` + `SEC.*`.
3. **Tenant scoping of the case** — the case's `request.tenant_id` must match the caller's tenant; a
   cross-tenant case → `SEC.CROSS_TENANT_CASE`.
4. **Secure intake** — the model-output artifact is validated/redacted; failure → `CONTRACT_ERROR` +
   `INTAKE.*`.
5. **Read-only orchestration** — the frozen pilot orchestrator runs the case; the response carries the
   final shadow disposition, stage dispositions, reason codes, replay signature, and human-review state.

The response is a `ShadowResponse` with **`enforced = False`** by construction — the API surface cannot
enforce.

## Verified behavior

- authenticated same-tenant submit → `WOULD_ALLOW`, `enforced = False`;
- cross-tenant token → refused (`SEC.CROSS_TENANT_DENIED`);
- tenant kill switch tripped → refused (`KILL.TENANT_KILLED`);
- missing token → refused.

## What this is and is not

- **Is:** a fail-closed, tenant-scoped, shadow-only API that a bounded pilot can expose — every request
  is authenticated, scoped, intake-validated, and run read-only, and every response is a `WOULD_*`
  disposition with a redacted/minimized trace.
- **Is not:** a production service. No HTTP server, rate limiting, request signing at the transport
  layer, or API gateway — those are deployment concerns (M8) and production dimensions (NOT EVALUATED).
  The API is the *logic* of a non-enforcing surface, not a deployed endpoint.
