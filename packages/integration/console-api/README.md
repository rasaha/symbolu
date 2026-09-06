# Ugence Console API

`ugence-console-api` — the packaged control-plane governed-loop service. It runs one
proposed action through the consolidated control plane in **shadow**, records the trail,
and serves that trail back.

Scoped and ratified by
[`ADR_UGENCE_CONSOLE_PACKAGING_SCOPING.md`](../../../docs/architecture/ADR_UGENCE_CONSOLE_PACKAGING_SCOPING.md)
§8, rulings CP-1 to CP-5.

It is intentionally separate from `symbolu.service.api_server` (the Symbol-U research
pipeline) and imports each platform module only through its **frozen public API
surface** — the canonical distribution, never a legacy root namespace.

## Install and run

```bash
pip install packages/integration/console-api[serve]
python -m ugence_console_api          # serves on :8090 (CONSOLE_API_PORT to override)
```

The four platform packages are **required** dependencies, not extras (CP-5). A missing
one is an install-time failure. There is no configuration under which this service
answers while the governance it advertises is absent.

## What it serves — and what it does not (CP-3)

Five routes. Not eleven.

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Service version, per-module availability, the audit ceiling |
| POST | `/v1/governed-loop/shadow` | The governed loop over a supplied request |
| POST | `/v1/governed-loop/scenario/{scenario_id}` | The governed loop over a frozen scenario |
| GET  | `/v1/audit` | Known correlation ids |
| GET  | `/v1/audit/{correlation_id}` | Reconstruct one decision chain |

The four non-health routes are exactly the set the studio's frozen allowlist already
names. Six routes the pre-packaging source served are **withheld** — three governance
verbs (`/v1/assertions/evaluate`, `/v1/actions/authorize`, `/v1/actions/clear`) and
three introspection reads (`/v1/modules`, `/v1/scenarios`, `/v1/gateway/minimize`).

The underlying capabilities still exist, and the loop still runs all four of them in
order. That is the ruling's point: **a capability does not become public API because the
underlying function exists.** Restoring any of the six takes an owner ruling, not an
added decorator. `app.SERVED_ROUTES` and `app.WITHHELD_ROUTES` record both sets, and the
suite asserts the running application matches them.

Nothing this service serves grants, authorizes, clears or executes.

## The audit ceiling is on every answer (CP-4)

The audit store is in-memory and stays that way at this reference-grade, shadow-only
stage. So every answer says so:

* the `X-Ugence-Audit-Ceiling` header, on all five routes and on error responses;
* an `audit_ceiling` field inside `/health`, `GovernedLoopResult` and `AuditChain` —
  the three bodies that describe the service or carry a decision trail.

The words are one constant, `models.AUDIT_CEILING`, so the header and the body cannot
drift apart. `ugence-control-plane-root` 0.2.0 remains the durable alternative for a
later ruling; it is deliberately **not** a dependency here.

## The governed loop

```
Gateway   -> Context Minimization      what may enter
Verify    -> Truth Assurance Platform  is the assertion supported
Authorize -> ActionGate                may THIS exact action execute (CER-bound)
Clear     -> Autonomous Control Plane  is it operationally safe right now
Record    -> Audit                     reconstructable decision chain
```

Deployment mode governs consequence, not evaluation. In **shadow** the loop evaluates
and records but changes nothing; `would_execute` still reports what enforcement would
have done. Gates are non-compensatory.

## Dependency direction

One-way. The console imports the platform; nothing in the platform imports the console,
and the boundary tests across the tree that forbid `ugence_console_api` keep forbidding
the same name — the packaging move left the namespace unchanged (CP-2).

```
ugence-context-minimization            <- structural_minimize
ugence-governance-provider-framework   <- the two neutral request types
ugence-actiongate-provider             <- build_actiongate_provider
ugence-tap-provider                    <- build_tap_provider
    ▲
ugence-console-api (this package)
```

`apps/console/` — the React frontend — remains an independently deployable app and is
not part of this distribution (CP-1).

## Tests

```bash
python -m pytest packages/integration/console-api/tests -q
```
