# Code Governance — Next Phases (out of scope for MVP 1C)

MVP 1C adds an opt-in **durable shadow audit store**, **restart-safe recovery**,
and **integrity-verified reconstruction** on top of the 1A/1B shadow workflow. It
is a persistence phase: it changes how the shadow record is stored, not what the
product is allowed to do. Execution remains `DISABLED`.

The following are **not** implemented and must not be started under this phase:

| Item | Owner / phase |
|---|---|
| Enforcement-grade / replicated durability (fsync/quorum/HA) | later (infrastructure) |
| Atomic one-time execution **reservation** / `reserve_once` | execution / idempotency ledger |
| Authoritative execution-consumption ledger | later |
| GitHub execution provider (`EXTERNAL_EXECUTION`) + merge credential | provider (later) |
| Enforced merge (direct + squash), merge queue, rebase | later |
| Auto-resume / auto-continuation of a workflow after restart | later (with a human/authority in the loop) |
| Durable, enforcement-grade `ClearanceReceipt` lifecycle | Workflow Service (later) |
| Live operational-signal adapters (identity / incident / change-management / GitHub) | product/integration |
| External database (PostgreSQL/MySQL/Redis/Kafka/cloud) | later |

## What a future enforcement phase would build on this foundation

The 1C store already provides the audit substrate an enforcement phase needs:
content-addressed records, a hash-linked event journal, atomic per-stage commits,
restart-safe recovery, and offline-verifiable bundles. An enforcement phase would
add — **separately, and without weakening any 1C boundary** — a reservation
primitive, an authoritative consumption ledger, and a real execution provider,
each behind its own explicit authority and credential boundary.

## Invariants every later phase must preserve

- `execution_status()` stays `DISABLED` until an explicit, separately-authorized
  execution phase; the durable store never becomes an execution ledger.
- ActionGate authorization is required before Action Clearance; Action Clearance
  never creates authority, broadens, reserves, or dispatches; `CLEAR` is not
  execution.
- The `DecisionRecord` remains the binding governance decision; the durable store
  holds projections, never re-issued authority.
- No new `ProviderKind`; no neutral-contract change; the canonical Action
  Clearance package, ActionGate, TAP, Decision Authority, GPF, StoryGraph, and
  robotics ACP stay unmodified.
- Persistence stays confined to `persistence/`; stdlib `sqlite3` only until an
  external store is a deliberate, separately-scoped decision.
- The bare acronym "ACP" never appears in new technical surfaces.
