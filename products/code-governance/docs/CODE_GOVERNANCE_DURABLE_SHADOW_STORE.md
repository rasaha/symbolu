# Durable Shadow Store

> `DURABLE_SHADOW_REFERENCE` — a **local, append-only, hash-linked,
> integrity-verified** audit store built on stdlib `sqlite3`. It is **not** a
> production enforcement store, an authoritative execution-consumption ledger, a
> distributed transaction system, or a high-availability database. No external
> database dependency is introduced.

Machine-readable companion: `docs/store_schema.json`.

## Design goals

Local · deterministic · transactional · restart-safe · tenant-aware ·
append-oriented · integrity-verifiable · dependency-light.

The pattern (WAL, append-only triggers, hash-linked records/events,
schema-versioned metadata, tenant partitioning, restart recovery) was **adapted,
not copied**, from the StoryGraph `DurableAuditLog` reference. No StoryGraph code
was modified or imported.

## Tables

| Table | Purpose | Mutability |
|---|---|---|
| `store_meta` | schema/serialization/fingerprint versions + classification | init-once, validated on reopen |
| `records` | immutable record envelopes (product records + external projections) | **append-only** |
| `events` | hash-linked workflow-event journal | **append-only** |
| `workflow_index` | last committed state per revision (fast recovery/reconstruction) | upsert (pointer only) |

`records` and `events` each carry `BEFORE UPDATE` and `BEFORE DELETE` triggers
that `RAISE(ABORT, …)`. The historical record is therefore tamper-evident at the
storage layer: an ordinary `UPDATE`/`DELETE` is refused. `workflow_index` is a
derived pointer, not history; it is safely upserted inside the same transaction.

## Schema versioning (fail closed)

`store_meta.schema_version` is written once. On reopen, a store whose version does
not equal the supported `STORE_SCHEMA_VERSION` is rejected with
`SchemaIncompatibleError`. There is no silent migration and no best-effort read of
an unknown schema.

## Integrity model

- **Payload fingerprint** — domain-separated SHA-256 over the canonical payload.
- **Envelope fingerprint** — over the record identity + payload fingerprint +
  `previous_record_fingerprint`.
- **Event fingerprint** — over the event identity + `previous_event_fingerprint`
  + referenced record ids (sorted) + transition.

All three reuse the product-wide `fingerprints.domain_hash`; none includes SQLite
row ids, file paths, insertion order, process ids, or hidden wall-clock values.
`verify_records` and `verify_event_chain` recompute and compare; a mismatch raises
`IntegrityFailure` / `EventChainError`.

## `put_if_absent` semantics

Committing a record id that already exists is:

- **idempotent** if the stored envelope fingerprint is identical (safe re-run), or
- a **`RecordCollisionError`** if the content differs (append-only violation).

The same applies to events by `event_id`.

## Tenant isolation

Every read, verify, recovery, reconstruction, and bundle operation is scoped by
`tenant_id`. Cross-tenant reads return nothing; cross-tenant reconstruction is
`INCOMPLETE`. `tenant_id` is part of every fingerprint, so a record cannot be
re-homed to another tenant without breaking its envelope fingerprint.

## What it is not

- Not enforcement-grade durability (no fsync/replication guarantees claimed).
- Not an execution ledger — it stores audit projections, never authority.
- Not networked — no client/server, no external driver, no cloud backend.
