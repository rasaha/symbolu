# Ugence Risk Authority Status Runtime (RA-6)

Post-issuance **authority lifecycle** — revocation / epoch propagation — around
the sole Risk Authority machine-authority artifact. RA-6 makes the leaf's
already-present but operationally-inert lifecycle mechanism *operate*. It
introduces **no second authority artifact**: the Ed25519-signed
`RiskAuthorizationEnvelope` remains the sole machine-execution authority.

Ratified design: `docs/architecture/RISK_AUTHORITY_RA6_SPEC.md` (SHA `e4b548a1`).

## Model (SPEC §4)

```
SHORT TTL  +  MONOTONIC AUTHORITY EPOCH  +  TARGETED REVOCATION

material change
    → AuthorityReassessmentSignal      (neutral; carries no authority)
    → AuthorityReassessor              (validate + dedupe + reassess CURRENT state)
    → AuthorityLifecycleService        (authenticated writer; the sole mutator)
    → advance epoch / targeted revoke / idempotent no-op
    → ReferenceAuthorityStore  →  AuthorityStatusCache (bounded-stale, offline)
    → StatusAwareActionGate / pre-effect recheck observe invalid authority
    → DENY / stop execution
```

Observers **signal**; Risk Authority **reassesses**; a single authorized writer
**mutates**; ActionGate/runtime enforce **read-only**.

## Contracts (owned by the `ugence-risk-authority` leaf, implemented here)

| Port | Direction | This package's implementation |
|---|---|---|
| `AuthorityStatusReader` | READ | `AuthorityStatusCache` (bounded-stale, offline) |
| `AuthorityLifecycleWriter` | WRITE | `AuthorityLifecycleService` (authenticated, idempotent, audited) |
| `AuthorityReassessmentSignalPort` | INTAKE | `AuthorityReassessor` (validate + dedupe + reassess) |

Read/write are **segregated** so the hot path can never hold write capability.

## Dependency direction (one-way)

```
risk_authority  (stdlib-only leaf: ports + domain + pure RevocationState predicate)
      ▲
ugence_risk_authority_status_runtime  (this package)
```

The only declared dependency is `ugence-risk-authority`. **No** SQLAlchemy /
FastAPI / Redis / Kafka / cloud SDK / DB driver / framework — the reference
persistence and in-process propagation are stdlib-only; production infrastructure
is delegated behind the ports (`postgres.py`). The Agent Runtime last-mile seam is
satisfied structurally (a neutral callable), so no runtime dependency is added.

## Freshness policy (SPEC §3, Policy C)

`age = now − snapshot.as_of`; UNINITIALIZED (globally or for a tenant) ⇒ DENY for
every tier; `age > max_staleness(tier)` ⇒ DENY; otherwise ALLOW (annotated
`ALLOW_WITH_BOUNDED_STALE_STATUS` when `age > 0`). Bounds are tenant-governance
configuration under a **platform ceiling**; unknown tier fails closed as CRITICAL.
Ship values are fail-closed defaults, not canonized business policy.

## Maturity (no overclaim, SPEC §22)

Implemented: **code-level authority-lifecycle enforcement** with a **reference
in-memory** persistence adapter, in-process propagation, and a **delegated**
authentication/authorization seam (`ReferenceWriterAuthorizer` is refused in
production — the RA-5 F-1 pattern; a deployment injects its authenticated
authorizer). Production Postgres persistence and real signal transport are
delegated (`postgres.py`). This is **not** globally-consistent,
cryptographically-attested, multi-region, or zero-window revocation.

## Verify

```
python -m pytest packages/integration/risk-authority-status-runtime/tests
python packages/integration/risk-authority-status-runtime/scripts/verify_isolated_install.py
```
