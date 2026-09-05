# Changelog — ugence-control-plane-root

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
