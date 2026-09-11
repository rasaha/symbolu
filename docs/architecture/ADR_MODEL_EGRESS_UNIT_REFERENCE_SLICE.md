# ADR — Model Egress Unit, reference vertical slice

**Status:** implemented under delegated authority, **conformed to the rulings of
2026-09-10**, and **merged (#1743)**. Its one open divergence — what the request
digest binds — was **ratified by the owner on 2026-09-11** and is closed below.
This ADR ratifies nothing itself; it records what was ruled and what is built.
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

**CR-4 and CR-5 were amended on 2026-09-10** (`ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md`
§5, merged as #1747) `[V]`. Two consequences for this package. The MEU's egress is
now **declared rather than inherited**: the unit carries its own
`EXTERNAL_DEPLOYMENT_EVIDENCE` naming two permitted destinations — the exchange
schema under its own role, and approved provider endpoints only where a credential
has been commissioned. This package reaches the first and *cannot* reach the second,
having no provider egress at all. And `production` is pinned as a composition switch,
never a deployment-wide LIVE switch, which is the reading this package already
assumed when it made the reference adapter refuse a production posture outright.

CR-5's worker clause was never contradicted here in any case: it scopes *the
worker's* egress, and this is a different unit — which is what `SEPARATE_EGRESS_UNIT`
means in D-2 and why that option preserved CR-5 rather than amending it.

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

## Decisions taken, and two divergences — both now closed

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

**Closed, ratified 2026-09-11: the request digest binds a content digest, not the
inline text.** This was carried as an open divergence from D-4's letter — "ordered
minimized unit identifiers and exact text" — and referred to the owner. The owner
ratified the merged construction as satisfying D-4, on the reading that it is a
**composed cryptographic commitment to the exact text** rather than an
identifiers-only commitment, which is what D-4's "not merely unit identifiers"
(`SPEC_MODEL_EGRESS_UNIT.md:425`) forbids `[V]`. Inlining plaintext into the outer
preimage is **not required**, and **no `model_egress_unit.exchange.v2` is
authorized**.

The ratification carries four conditions. Each is met, and each is now pinned:

| Condition | Where it holds |
| --- | --- |
| 1 — preimage is the canonical, ordered `[unit_id, exact_text]` sequence | `canonical.py:216`, `entries = [[u.unit_id, u.text] for u in units]`, never reordered `[V]` |
| 2 — encoding, ordering, hash algorithm and schema/version pinned | Rules in the `canonical` module docstring; `MEU_CANONICALIZATION_VERSION` and `EXCHANGE_SCHEMA_VERSION` bound into the preimages; **frozen vectors** in `tests/test_digest_vectors.py` `[V]` |
| 3 — bound in a domain-separated, unambiguous field | `digest_body()["content_digest"]`, framed under `EGRESS_REQUEST_DIGEST_DOMAIN` and type `EgressRequest` `[V]` |
| 4 — identifiers alone can never satisfy it | Substituted text under unchanged identifiers moves both the context digest and the request digest `[V]` |

**What a tombstone can and cannot do after purge.** Recorded explicitly, because
the earlier wording overclaimed it. The tombstone can verify the **integrity and
linkage of the retained digest chain** — the request digest recomputes from the
surviving fields and commits to the recorded content digest — and it can test a
*candidate* context a reader already holds. It **cannot** reconstruct the deleted
plaintext, and it cannot independently re-prove what that plaintext was to a reader
holding no candidate. Post-purge plaintext verification is not claimed and is not
available.

**Divergence, resolved: `submitted_at` is inside the digest.** D-4 excludes "mutable
lease, claim, attempt and processing timestamps". A creation instant is none of
those and never changes, so it stays bound; the four mutable ones are excluded and
a test asserts their absence.

## Three findings the tests produced

**Every digest test was a relative comparison, so the encoder was unpinned.**
Found while verifying ratification condition 2. The suite asserted only that
changing a *field* moves a digest; nothing pinned the bytes. Measured: changing
`EXCHANGE_CONTENT_DIGEST_DOMAIN` from `…/v1` to `…/v9` moves every content and
context digest in the exchange, and the pre-existing **150 tests pass clean** `[V]`.
The domain tag is the mechanism that stops a content digest validating as a request
digest, and it could have been altered silently. Frozen vectors now pin it, and a
positive control (reordering must move the vector) stops a constant-returning
encoder from satisfying them. The two findings below are from the earlier revision.

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
| **CR-1** `[G]` | Amended nowhere. It admits one companion deployment unit, named, and the MEU is a second — so after the CR-4/CR-5 amendments the MEU's boundary is specified and the unit's **existence** is not. This package ships no deployment unit, so it does not depend on that further amendment; nothing here may be read as authorizing one to run |

## What this does not do

It composes nothing into the worker, changes no signed field, no canonical
serialization of any other package, no digest and no signature format. It adds no
external destination, no credential, no vendor dependency and no Railway migration.
It marks no gate identifier satisfied and changes no ratified pin.

It is not production-capable, and it does not make live egress closer to
authorized — only better prepared for, if it ever is.

## Addendum, 0.2.0 (2026-09-11): the custody port, the ledger kinds, transport protection

Documentation-only record of what release 0.2.0 adds; it ratifies nothing and depends
on no ruling that has not been made. Each piece is inside what D-3 expressly permits
("provider-adapter interfaces using deterministic fakes") or what the specification
lists as unbuilt mechanism with no decision pending.

| Added | Where | What it closes |
|---|---|---|
| `ModelCredentialCustodyPort`, `CredentialRequest`, `CredentialLease`, `CustodyAuditEvent`, `ReferenceCustodyAdapter`, `materialize_with_audit` | `custody.py` | The shape of D-3's commissioned custody, mirroring `cloud-scaling-credential-broker`'s port. The secret in a lease is reachable only through `use`, never from `repr`, records, equality, pickling or the audit event. The reference adapter leases an inert marker outside production and refuses a production posture. Not a credential, not a secret manager, not commissioning `[V]` |
| `MEU_LEDGER_KINDS`, `ledger_payload`, `result_ledger_payload` | `ledger_kinds.py` | Spec §4.4's "kind-specific schema that refuses content-bearing keys", previously recorded as unbuilt `[G]` → built `[V]`. The control plane's `LedgerEntry` is unchanged; the refusal happens before an entry is made |
| `require_transport_protection`, `protected_connect`, `sslmode_of` | `postgres/transport.py` | Spec §4.4's transport protection, previously `sslmode` set nowhere `[G]` → a production DSN without `sslmode=verify-full` is refused `[V]`. Not yet composed by any deployment, because none exists (CR-1) |
| `MEU_LIVE_PROVIDER_DESIGNATION.json`, `MEU_LIVE_VALIDATION.json` | beside the package | The owner's designations of 2026-09-11 (vendor OpenAI, host `api.openai.com`; custody Google Secret Manager) with every other field `UNDESIGNATED`, and an eleven-row validation matrix at `BLOCKED_PENDING_OWNER_RULINGS`, pinned by `tests/test_live_records.py` |

| `COMMISSIONING_LIMITS`, `check_request`, `CallBudget`, `is_pinned_snapshot` | `limits.py` | LP-5 bound and enforced before dispatch, non-compensatorily; LP-3's pinned snapshot; four new `RefusalReason` members (`REQUEST_LIMIT_EXCEEDED`, `COMMISSIONING_BUDGET_EXHAUSTED`, `MODEL_NOT_PINNED`, `DESTINATION_NOT_PERMITTED`). The durable reservation row stays unbuilt `[G]` |
| `DesignatedDestination`, `OPENAI_RESPONSES`, `check_destination` | `egress_policy.py` | LP-1 and LP-3: exactly `https://api.openai.com/v1/responses`, checked as a string; the future adapter imports its permission from here |
| `CustodyIdentity`, `is_pinned_secret_version`, `PinnedSecretVersionCustodyAdapter` | `custody.py` | LP-2 and LP-6 step 5: the Secret Manager adapter's shape over an injected reader (fake path only); a service-account-key identity and `latest` are refused at construction; rotation over 90 days refused; production-authoritative only under workload identity federation and never on the fake path |

**What stays exactly as it was.** `LIVE_VENDOR_EGRESS = False`; the boundary tests;
`EgressResult`'s refusal of `genuine_call` other than `False`; `MATURITY`;
`ENFORCEMENT_ENABLED`; the exchange schema and every digest vector of #1749. No
deployment unit, no credential, no vendor SDK, no destination.

**Two questions the designations raise, put to the owner in the commissioning ballot
rather than decided here.** LP-2a: how the unit authenticates to Google Secret Manager
without a long-lived key in the deployment. LP-2b: the record-contract amendment under
which a result may carry `genuine_call: True`.
