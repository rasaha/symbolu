# Durability Limitations

> MVP 1C is a **bounded persistence phase**. It makes the shadow governance record
> durable, restart-safe, and integrity-verifiable. It does **not** turn Code
> Governance into an enforcement system. This document states the boundary
> explicitly so the durable store is never mistaken for something it is not.

## Not an enforcement-grade durability claim

The store is a `DURABLE_SHADOW_REFERENCE` audit store. It is local, append-only,
and integrity-verified, but it makes **no** guarantee of fsync-level crash
durability, replication, quorum, or high availability. Do not rely on it as the
system of record for anything with an external effect.

## Explicitly out of scope

- **No execution.** `execution_status()` returns `DISABLED` in every mode. There
  is no `merge()`, `execute()`, or `dispatch()`.
- **No reservation.** No `reserve_once`, no reservation ledger.
- **No execution-consumption ledger.** The store records audit projections, never
  an authoritative "this action was consumed" record.
- **No GitHub write path.** No merge credential, no webhook secret, no execution
  provider, no `ProviderKind`.
- **No auto-resume.** Restart recovery never resumes an external side effect and
  never auto-transitions a workflow.
- **No external infrastructure.** No PostgreSQL, MySQL, Redis, Kafka, cloud
  database, or network client. Only stdlib `sqlite3`, confined to `persistence/`.
- **No authority.** External authoritative records (DecisionRecord, CER, ActionGate
  result, TAP result) are stored only as projections; the store never re-issues
  authority.

## Determinism caveat

An audit bundle re-exported from the **same persisted content** is byte-identical.
A bundle from two independent **full pipeline runs** may differ, because the
upstream Decision-Authority-minted CER carries a wall-clock `issued_at` /
`content_hash`. Determinism over fixed inputs is proven at the
record/envelope/bundle level; it is not claimed across live end-to-end runs.

## Unchanged capabilities

No package outside `products/code-governance/` was modified. The canonical Action
Clearance package, ActionGate, TAP, Decision Authority, governance contracts, GPF,
StoryGraph, and robotics ACP are composed through their public surfaces only. The
StoryGraph `DurableAuditLog` was used as a **reference pattern**, not imported or
changed.

See `CODE_GOVERNANCE_NEXT_PHASES.md` for what a future enforcement/reservation
phase would have to add on top of this shadow foundation.
