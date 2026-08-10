# Failure & Retry Semantics

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Classifies every failure mode across the
four prerequisites. Extends the merged failure classification
(`Project_documentation/repository/docs/design/action_clearance/STATUS_AND_REASON_SEMANTICS.md`).

## Classification legend

- `FAIL_CLOSED` — resolve to a non-executable result; never `CLEAR`, never dispatch.
- `RETRY_SAME_REQUEST` — a transient error; retry with the same idempotent request/key.
- `RECONCILE_BEFORE_RETRY` — uncertain external outcome; reconcile before any reuse.
- `ESCALATE` — human decision required.
- `REAUTHORIZE` — the authorization must be renewed upstream first.
- `PERMANENT_BLOCK` — this receipt/reservation is dead.

## Failure table

| Failure | Classification | Notes |
|---|---|---|
| receipt store unavailable | `FAIL_CLOSED` (+ `RETRY_SAME_REQUEST`) | no receipt ⇒ no dispatch; retry the read/write, never proceed |
| reservation store unavailable | `FAIL_CLOSED` (+ `RETRY_SAME_REQUEST`) | cannot atomically reserve ⇒ do not dispatch |
| source registry unavailable | `FAIL_CLOSED` | cannot verify source trust ⇒ `SIGNAL_UNTRUSTED`/hold |
| signal provenance verification failure | `FAIL_CLOSED` | `SIGNAL_UNTRUSTED → BLOCK` |
| reservation transaction timeout | `RETRY_SAME_REQUEST` | same `execution_key` retry is idempotent; if a reservation was created, the retry observes `ALREADY_RESERVED`/`ALREADY_DISPATCHED` |
| provider dispatch timeout | `RECONCILE_BEFORE_RETRY` | `OUTCOME_UNCERTAIN`; the external action may have occurred |
| provider returned unknown outcome | `RECONCILE_BEFORE_RETRY` | `BusinessOutcome.UNKNOWN` / `INDETERMINATE`; never treated as success |
| observation unavailable | `RECONCILE_BEFORE_RETRY` | outcome uncertain until observed/reconciled |
| reconciliation delayed | `FAIL_CLOSED` (hold reservation) | key stays reserved/uncertain; not released |
| duplicate callback | idempotent (no-op) | duplicate observation is idempotent |
| out-of-order callback | deterministic ordering | order by provider event time / sequence; a stale callback never downgrades a terminal state |

## Hard rules

- **No failure may silently become executable permission.** Every uncertain or error path resolves to a
  non-executable state.
- **Timeout ≠ no-op.** A dispatch timeout is `OUTCOME_UNCERTAIN`, not failure; it requires reconciliation
  before any retry (`EXECUTION_RESERVATION_STATE_MACHINE.md`).
- **Terminal success is permanent.** `OBSERVED_SUCCESS`/`RECONCILED_SUCCESS` can never be reopened by a
  late/duplicate/out-of-order callback.
- **Store outages fail closed *and* retry.** Unavailability of the receipt or reservation store blocks
  dispatch and is retried at the same idempotent request/key; it never defaults to proceed.

## Interaction with evaluator vs workflow

- Evaluator-level failures (malformed request, unsupported profile) are `NON_RETRYABLE_ERROR` exceptions,
  per the merged design — they are programming/contract errors, not operational results.
- Operational failures (store down, provider timeout) are **not** evaluator concerns; they occur in the
  Workflow Service / execution boundary and follow the table above.

## Closure

**CLOSED_BY_NEW_PRODUCT_INTERFACE** — the classifications are fixed; enforcement lives in the Workflow
Service and execution boundary, which own the failing components.
