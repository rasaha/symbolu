# Changelog — ugence-control-plane-root

## 0.2.0 — the one read (front-door seam 7, ruling FD-11.2)

- `AuditLedger.read_entries(tenant_id=..., correlation_id=...)`: a tenant's own rows
  for one correlation id, in `tenant_seq` order, as `StoredEntry` objects rebuilt from
  the rows as written (the re-validated `LedgerEntry`, `seq`, `prev_digest`,
  `record_digest`, and so `entry_ref`). Raw and uninterpreted: no join, no ordering
  across tenants, no meaning attached to a `kind`. Refuses a blank tenant or
  correlation id, an in-memory store, and a store whose schema version is not this
  package's, re-checked at read time. Ruled by
  `docs/architecture/ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md` FD-11.2 and recorded as
  an amendment of this package's ADR D-5: a raw read of a tenant's own rows is not the
  reconstruction API the root disclaims. No append, edit or vocabulary added;
  `CONTRACT_VERSION` unchanged (an additive read helper).

## 0.1.1 — the ledger behind a thread pool

- `AuditLedger` opens its one SQLite connection with `check_same_thread=False` and
  serialises every method on one re-entrant lock. Found by the governed runtime worker
  (`deployment/governed-runtime-worker`), the first composition root to serve this
  ledger behind an HTTP server whose handlers run on a thread pool: SQLite's default
  thread check refused every linkage append made from a request thread. The chain
  semantics are unchanged: `BEGIN IMMEDIATE` still binds the head read and the
  extending write, and the lock keeps them in one thread.

## 0.1.0 — wave 3, initial release

Scoped and ratified by `docs/architecture/ADR_UGENCE_CONTROL_PLANE_ROOT_SCOPING.md`.

- `AuditLedger.append(entry, reference_factory=...)` — the whole act. It writes one
  `LedgerEntry` into its tenant's hash-linked chain at the instant the caller
  supplied, and returns the `AuditReference` naming it. Nothing else.
- `LedgerEntry` — tenant, a free `kind`, a caller-supplied instant, an author and an
  uninterpreted payload. Frozen, digest-bound, refusing a naive instant and a payload
  its digest could not cover. No event-type vocabulary is minted: Decision
  Authority's `AuditEventType` is frozen at 1.0.0 and owns those names.
- Durable, append-only, per-tenant hash-linked SQLite in the shape of
  `storygraph`'s `durable_audit` — **copied, never imported**, as D-3 of the
  sequencing ADR already ruled for Policy Authority. `UPDATE` and `DELETE` are
  refused by database triggers rather than by convention, and `verify_chain`
  recomputes a chain. Tamper-**evident**; never tamper-proof.
- **No existing store is unified, read, migrated or mirrored** (D-3). Seven audit
  stores exist and this is an eighth, deliberately; G4's `AuditReference` stays the
  only thing correlating across them.
- `AuditReferenceFactory` — the seam by which governance-contracts is **injected**.
  The package imports it nowhere, and a boundary test asserts that: a root one import
  from the contract layer is one import from a capability.
- Reference-grade (D-1), composing reference-grade parts. Not production-ready.
- Reads no clock, decides nothing, admits nothing, executes nothing — all asserted
  over the AST, with `scripts/mutation_sweep.py` carried over so the coverage claim
  is runnable rather than asserted.
