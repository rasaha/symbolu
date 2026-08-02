# Prerequisite D — Atomic One-Time Execution Reservation

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Closes design open question **Q4**. This is
the **P0 enforcement prerequisite**. It defines the atomic reservation contract that guarantees at most
one executable reservation per execution key. It defines **no backend** and changes **no** neutral
contract.

## The contract

```text
reserve_once(
    execution_key,                 # canonical, EXECUTION_KEY.md
    clearance_receipt_ref,         # acr_<result_fingerprint>
    expected_authorization_ref,    # must match the receipt
    expected_action_fingerprint,   # must match the receipt
    reservation_ttl,               # bound on how long the reservation holds pre-dispatch
) -> ReservationResult
```

`ReservationResult` distinguishes:

| Result | Meaning |
|---|---|
| `ACQUIRED` | this caller holds the sole executable reservation |
| `ALREADY_RESERVED` | another caller holds an unexpired reservation for this key |
| `ALREADY_DISPATCHED` | a dispatch is in flight for this key |
| `ALREADY_COMPLETED` | a terminal success/observed outcome exists; execution is done |
| `CONFLICT` | reservation state is inconsistent (split brain / needs reconciliation) |
| `INVALID_RECEIPT` | receipt missing, body altered, or not `CLEAR` |
| `EXPIRED_CLEARANCE` | receipt past `valid_until` at reservation time |
| `STALE_AUTHORIZATION` | receipt's authorization has been superseded/revoked upstream |

These map to the existing repository's outcome vocabulary where possible: `ALREADY_COMPLETED`/duplicate
corresponds to `BusinessOutcome.DUPLICATE`, and the ledger's `TERMINAL_EXECUTION_STATUSES`
(`CANCELLED`, `SUPERSEDED`) inform when a key is free to reserve again.

## Required atomic property

> **At most one caller may acquire an executable reservation for the same execution key.**

## Behavior for two concurrent calls

```text
Caller A ── reserve_once(key) ─┐
                               ├─▶ ledger atomic conditional insert on execution_key
Caller B ── reserve_once(key) ─┘
   → exactly one returns ACQUIRED
   → the other returns ALREADY_RESERVED (or ALREADY_DISPATCHED / ALREADY_COMPLETED
     if it observes a later state)
```

**Exactly one may return `ACQUIRED`.** This is the property the current
`lookup_by_execution_idempotency_key` + `create_execution_intent` pair does **not** guarantee under
concurrency (it is check-then-act — see `EXISTING_EXECUTION_REPOSITORY_ASSESSMENT.md`). `reserve_once`
replaces that race-prone pattern with a single atomic conditional insert.

## Database-neutral required semantics (step 26)

The contract fixes *semantics*, not a backend. Any backend that provides these is acceptable:

| Required semantic | Provided by (examples) |
|---|---|
| atomic conditional insert | SQL `INSERT … ON CONFLICT DO NOTHING` under a UNIQUE(execution_key); CAS document write; append-only event store with a unique execution_key; distributed lock + durable record |
| unique execution key | UNIQUE constraint / partition key |
| durable state | real store (SQL/document); **not** the in-memory reference impl for enforcement |
| linearizable (or equivalent) reservation decision | single-writer per key / serializable isolation |
| tenant isolation | `tenant_id` in the key and every row |
| idempotent reads & retries | same `execution_key` retry returns the same reservation |
| reconciliation-safe updates | uncertain outcomes never auto-release (see below) |

Candidate implementations evaluated: **SQL uniqueness constraint + transaction** (recommended default if
the repository standardizes on SQL), **compare-and-swap document store**, **append-only event store with
unique execution key**, **distributed lock + durable record**, and an **in-memory implementation for
tests only** (mirroring `InMemoryExecutionRepository`, single-process atomicity). The repository does
**not** standardize a database today, so backend selection is an `OPEN_IMPLEMENTATION_DECISION`
(enforcement blocker); this phase implements none.

## Validation before `ACQUIRED`

The reservation checks in `EXECUTION_RESERVATION_VALIDATION` (below and in the state-machine doc) must
pass **inside** the atomic step or as verified preconditions with no TOCTOU window. See
`EXECUTION_RESERVATION_STATE_MACHINE.md` §Validation.

## Closure

Prerequisite D's **contract** is **CLOSED_BY_NEW_PRODUCT_INTERFACE** (the `reserve_once` shape and result
set). The **atomic durable backend** is `EXTEND_BEHIND_EXISTING_INTERFACE` over the existing
`ExecutionRepository` port with an `OPEN_IMPLEMENTATION_DECISION` on the backend — an **enforcement
blocker**, explicitly *not* a package-core blocker. Schema: `execution_reservation.schema.json`.
