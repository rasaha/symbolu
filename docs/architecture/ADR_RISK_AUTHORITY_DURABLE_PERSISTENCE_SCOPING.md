# Risk Authority durable persistence — scoped and ratified

**Status:** ratified 2026-09-04 by the repository owner. Sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 1) and required by
`ADR_RISK_AUTHORITY_PHASE5_ENVELOPE_ISSUANCE_RATIFICATION.md` D-5, which allowed
production issuance only in the application instance that evaluated the decision
because the repositories were in-memory. Backend posture inherits Benchmark
Registry ruling D-22 (Posture B) as restated in
`ADR_UGENCE_EXECUTION_RESERVATION_SCOPING.md` D-3. This record authorizes no code
change; it fixes what the implementation must do.

## The question

What does it take for a Phase 5 envelope to be issued by a process other than
the one that evaluated the decision? **A stdlib `sqlite3` adapter set behind the
existing repository ports, plus a strict codec, because Risk Authority has no
rehydration path at all today.** The seam already finds the decision by tenant
and id through a port; what is missing is a store that survives a restart and a
way to rebuild the frozen domain objects from what it stored.

## What exists `[V]`

| Finding | Where |
|---|---|
| Seven repository Protocols; the application depends on them, not on a store | `packages/risk_authority/src/risk_authority/persistence/repositories.py` |
| The only implementations are in-memory dicts; the Postgres factory raises on every method and records target DDL only | `persistence/in_memory.py`; `persistence/postgres.py:42-67` |
| Production mode admits the in-memory stores silently: every repository defaults and no production flag is checked on any of them | `api/dependencies.py:189-195` |
| Encoding is free: `to_canonical_obj` renders every domain dataclass, dropping fields marked `canonical=False` (the envelope signature) | `crypto/canonical.py:82-87`; `domain/envelope.py:113` |
| Decoding does not exist: no domain type has `from_dict`; `RiskDecisionCase` is a plain class holding its hash-linked event list privately | `domain/risk_case.py:54-100,109-121` |
| Ids come from a per-process counter and `save` overwrites silently, so a restart re-issues `rae_000001` over a persisted envelope | `api/dependencies.py:75-84`; `in_memory.py:53-60` |
| Revocation and epochs are one mutable in-memory object consulted by issuance and verification; RA-6 delegates its durable form to the unbuilt Postgres adapter | `services/revocation.py`; `ADR_RISK_AUTHORITY_RA6_AUTHORITY_LIFECYCLE.md:27` |
| The key ring is built from the one injected key, so an envelope signed under a rotated key is unverifiable after restart | `api/dependencies.py:187,791` |
| The shape to copy: WAL, `BEGIN IMMEDIATE`, `meta`, append-only hash-linked `ledger_events`, annotation-driven `decode_dataclass` | `policy-authority/src/ugence_policy_authority/core/registry_sqlite.py`, `core/codec.py:87-165`; `execution-reservation/src/ugence_execution_reservation/sqlite.py` |
| No Risk Authority test references the Postgres factory or a concrete store; one test relies on a counter-derived id | `tests/adversarial/test_gate_integrity.py:127` |

## What issuance needs `[I]`

Decisions, envelopes, cases with their events, and revocation state. Controls,
evidence and grants are not read by the issuance seam, but a decision cannot be
re-evaluated from a rehydrated case without them, so they join the same adapter.

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Backend | **D-22 Posture B**, exactly as execution-reservation: one SQLite file on stdlib `sqlite3`, WAL, `BEGIN IMMEDIATE` around every write, a `meta` table, and append-only hash-linked `ledger_events` copying the storygraph `durable_audit.py` shape without importing it. Distributed strong consistency stays disclaimed. The Postgres skeleton remains as DDL documentation and keeps raising. Risk Authority stays a zero-dependency leaf. |
| D-2 | Codec | A strict annotation-driven decoder in **`risk_authority.persistence.codec`**, copying Policy Authority's `decode_dataclass` shape and never importing it, extended with `Mapping[str, str]` for event attributes and `bytes` for the signature stored beside the canonical body. `RiskDecisionCase` gains `snapshot()` and `from_snapshot()`; loading replays the event list and refuses a broken `prev_digest` chain. Unknown fields refuse; a stored value the domain type rejects is a typed `PersistenceStorageError`. |
| D-3 | Identity | Every durable store **refuses an id that already exists** (`INSERT` without `ON CONFLICT`, surfaced as a typed error), and a **store-backed allocator** behind the same `next(prefix)` shape replaces the in-memory counter under durable mode. Digest-derived ids were considered and rejected: envelope ids are RA-8's correlation key and stay opaque. |
| D-4 | Revocation | The SQLite adapter persists **epochs and the three revocation sets as append-only rows** and rebuilds `RevocationState` on open, so issuance, verification and the RA-6 lifecycle writer see one durable state. This closes the RA-6 delegation inside Risk Authority; the status runtime's reference store is unchanged. |
| D-5 | Production posture | **`production_mode=True` refuses** in-memory repositories, the in-memory event store and the in-memory revocation state unless the injected adapter declares `is_production_authoritative = True`, mirroring the pattern already used for evidence admission and decision authority. The SQLite adapters declare it; the in-memory ones never do. Key rotation is out of scope: the key ring persists nothing, and the gap is named below. |

## Gaps that survive `[G]`

Multi-node consistency; HSM or KMS custody; key rotation across restarts; the
Phase 5 ADR's same-instance restriction is lifted only once these adapters ship;
consumers' own stores migrate nothing.

## Next step

Implement `risk_authority.persistence.codec`, `persistence/sqlite.py` and the
production-mode refusal under D-1 … D-5, with the seam issuing from a reopened
store as the acceptance test.
