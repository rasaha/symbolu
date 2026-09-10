# ADR — Model Egress Unit, reference vertical slice

**Status:** implemented under delegated authority, and **conformed to the rulings of
2026-09-10**. Ratifies nothing.
**Package:** `packages/integration/model-egress-unit` (`ugence-model-egress-unit` 0.1.0)
**Maturity:** `REFERENCE_GRADE_SHADOW_ONLY` · `ENFORCEMENT_ENABLED = False` · `LIVE_VENDOR_EGRESS = False`

Evidence labels: `[V]` verified against this repository, `[I]` inferred,
`[R]` requires ratification, `[G]` gap.

## The load-bearing question

**What does this package implement, and what does it still not authorize?**

It implements the exchange the rulings of 2026-09-10 specify: the schema, the three
roles, forced row-level security over a required tenant, the authorization binding,
the ordered minimized context and its digests, the two retention clocks, the
tombstone, the ambiguous-dispatch record, and a deterministic fake adapter. It
authorizes nothing: no live provider, no credential, and no second deployment unit.

## History, because it explains the shape

This package was written **before** `SPEC_MODEL_EGRESS_UNIT.md` and
`OWNER_RATIFICATION_MEU_EXCHANGE_TENANCY.md` existed, against a ballot in which
D-1 to D-5 were open. Those decisions were **ratified on 2026-09-10** `[V]`, and
the package has been brought into conformance rather than merged as it stood.

A striking amount needed no change. The tenancy ruling independently requires
mandatory application validation *backed by* forced RLS, three logical roles with a
non-login owner, no runtime identity owning the protected tables, column-scoped
worker grants, a required non-empty tenant on every row, terminal
`OUTCOME_UNKNOWN`, and a fake adapter that cannot be mistaken for genuine — all of
which were already here. The ruling also records that `TWO_ROLES_BY_MIGRATION` was
declined only because "a migration mechanism does not exist" `[V]`; this package
has one.

**What did change is recorded below**, because a reader comparing this package to
the spec deserves to know which parts were convergent and which were corrections.

## Conformance, item by item

| Ruling | How it is met |
| --- | --- |
| §4.1 authorization binding | `AuthorizationBinding` carries clearance reference and digest, tenant, authorized vendor and model, policy identity and reservation identity. The unit **verifies**; there is no method that mints, widens or re-derives one |
| §4.1 ordered minimized context | `MinimizedUnit(unit_id, text, token_count)` in run order; `minimized_context_digest` binds identifiers and exact text, and order moves the value |
| §4.1 exchange schema version | A field, bound into the request digest, so a request cannot be reinterpreted under a later schema |
| §4.4 what the request digest binds | Tenant, schema version, content digest, vendor/model binding, parameters, clearance identity, correlation, `not_valid_after`. `submitted_at` is bound (immutable); lease, claim, dispatch and terminal timestamps are excluded |
| §4.2 `trust` | Constant `UNTRUSTED_EVIDENCE`, in the record *and* as a database CHECK |
| §4.2 four outcomes | `ANSWERED`, `REFUSED`, `FAILED`, `OUTCOME_UNKNOWN` |
| §4.2 dispatch-attempt provenance | `DispatchAttempt` is a distinct record type; provider receipt, acceptance, completion, billing, tokens, cost and response existence are written as explicit `UNKNOWN`. A CHECK makes `OUTCOME_UNKNOWN` and `DISPATCH_ATTEMPT` inseparable |
| §4.3 lease expiry | Before dispatch the request becomes claimable again; after possible dispatch it is terminal `OUTCOME_UNKNOWN`. The requeue is guarded by `dispatched_at IS NULL` *inside its own UPDATE* |
| §4.3 tenant in identity | Primary key is `(tenant_id, request_id)`, so the dedup key is tenant-scoped by construction rather than by every query remembering |
| §4.4 retention | Earlier of acknowledgement + 1h and creation + 24h, **per artifact**, evaluated in SQL. A missing or late acknowledgement never extends the hard deadline |
| §4.4 tombstone | Identities, digests, terminal outcome, acknowledgement and purge times, correlation, clearance reference, reservation identity, vendor/model binding, non-content provenance. `tombstone()` selects no column that could carry content |
| D-5 reservation | Never released. `reservation_released` exists only so a CHECK can make "released" unrepresentable — purging the content does not purge the obligation |
| §5.2 grants | Three roles, non-login owner, column-scoped worker writes, forced RLS |
| §5.3 no credential | The unit composes, claims, validates and refuses with `CREDENTIAL_NOT_COMMISSIONED` — never a generic error, never a fabricated answer |
| Tenancy §4 cross-tenant | Reads and leases indistinguishable from unknown; writes rejected by the database and mapped internally to `TENANT_SCOPE_REFUSED` without disclosing whether another tenant's row exists |

## Decisions taken, and two divergences named

**A bespoke digest-pinned migration runner rather than Alembic.** A migration is
identified by the digest of its own text, and an already-applied migration whose
text changed is refused at startup. Editing an applied migration is the classic way
two deployments diverge silently. It adds no dependency, and the ruling's own
objection to `TWO_ROLES_BY_MIGRATION` was the absence of a mechanism.

**Raw psycopg3 rather than SQLAlchemy Core.** `durable-execution` uses SQLAlchemy
because DBOS requires it `[V]`; this package does not use DBOS, needs precise
control over `SET LOCAL` and role-scoped connections, and is eight statements long.

**Migration 1 was edited rather than superseded.** The v1 schema was never applied
anywhere, so a v2 migration would leave a shape in history that no database ever
had. The digest pin exists to prevent editing an *applied* migration, and this one
is not.

**Divergence, flagged for the owner rather than decided: the request digest binds a
content digest, not the inline text.** D-4's letter says "ordered minimized unit
identifiers and exact text". Inlining would make the request digest unrecomputable
the moment content is purged, leaving a tombstone whose central claim could no
longer be checked — the same reasoning the retention ruling itself uses. Binding a
content digest satisfies the intent (a substituted prompt still fails verification,
and this is tested) while diverging from the letter. **This is the owner's call.**

**Divergence, resolved: `submitted_at` is inside the digest.** D-4 excludes "mutable
lease, claim, attempt and processing timestamps". A creation instant is none of
those and never changes, so it stays bound; the four mutable ones are excluded and
a test asserts their absence.

## Two findings the tests produced, from the earlier revision

**`CREATE SCHEMA ... AUTHORIZATION` does not own the tables.** It sets the schema's
owner and nothing else. The migrating superuser owned them, so `FORCE ROW LEVEL
SECURITY` bound a role nobody used and "the owner cannot log in" was a true
statement about a role that owned nothing. Fixed with an explicit `SET ROLE` `[V]`.

**`SET LOCAL` is scoped to a transaction, not to a savepoint.** A connection handed
in mid-transaction leaks tenant identity past the savepoint's release — a
cross-tenant read no policy can catch, because the session genuinely *is* that
tenant. Measured both directions; the exchange refuses a connection it cannot scope
`[V]`.

## What remains unimplemented, and is recorded rather than papered over

The ruling explicitly refuses an unenforced runbook claim as a substitute for a
provisioning mechanism, so these stay visible:

| | |
| --- | --- |
| **Role provisioning in production** `[G]` | This package's migration creates roles for a *test* cluster. It issues no credential, and the runtime roles are created without `LOGIN` precisely so nothing here can be mistaken for a usable identity |
| **Credential custody** `[G]` | None exists, for the runtime roles or the migration identity. `PLATFORM_ENVIRONMENT_VARIABLE` is rejected for production and this ADR does not reopen it |
| **Controlled migrations** `[G]` | A separately controlled migration identity assuming the owner role during reviewed migrations only. `migrate()` is never called at import or at startup, which is necessary and not sufficient |
| **Transport protection** `[G]` | `sslmode` is set nowhere. RLS over an unencrypted connection controls who may read a row, not who may observe it in flight |
| **Tenant-bound database identities** `[G]` | Required before multi-tenancy. This package takes the tenant as a caller argument, which is single-tenant-safe and is **not** an approved multi-tenant design |
| **Vendor-mix reservation counter** `[G]` | Out of scope by instruction. The binding carries a `reservation_id`; nothing here defines, counts or releases it |
| **CR-1** `[R]` | Admits one companion deployment unit, named. The MEU is a second, so its boundary is specified and its **existence** is not. This package ships no deployment unit, so it does not depend on the amendment — but nothing here may be read as authorizing one to run |

## What this does not do

It composes nothing into the worker, changes no signed field, no canonical
serialization of any other package, no digest and no signature format. It adds no
external destination, no credential, no vendor dependency and no Railway migration.
It marks no gate identifier satisfied and changes no ratified pin.

It is not production-capable, and it does not make live egress closer to
authorized — only better prepared for, if it ever is.
