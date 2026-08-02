# Execution Reservation State Machine

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Defines the reservation lifecycle,
validation, TTL/abandonment, and the uncertain-outcome rule. This state machine is **distinct** from the
Action Clearance receipt lifecycle, the provider dispatch state, and the workflow state.

## Minimal necessary states (decision)

```text
AVAILABLE          # no reservation exists for the execution key
RESERVED           # a caller holds the executable reservation (pre-dispatch)
DISPATCHED         # dispatch has been sent to the provider
OBSERVED_SUCCESS   # provider-confirmed business success
OBSERVED_FAILURE   # provider-confirmed business failure
OUTCOME_UNCERTAIN  # dispatch sent, outcome unknown (timeout / lost response)
RECONCILED_SUCCESS # reconciliation confirmed success
RECONCILED_FAILURE # reconciliation confirmed failure (safe to consider re-execution per policy)
RELEASED           # reservation released; key returns to AVAILABLE (only under safe conditions)
```

All nine are retained: each maps to a real transition in the existing decision-authority execution model
(`ExecutionStatus`, `BusinessOutcome`, `ReconciliationStatus`, `Finality`) and each governs a distinct
"may another caller reserve?" answer.

## Four separate machines — do not conflate

| Machine | Values | Owner |
|---|---|---|
| Action Clearance **receipt lifecycle** | ISSUED/EXPIRED/SUPERSEDED/REVOKED/INVALIDATED | Workflow Service |
| **execution reservation** state (this doc) | AVAILABLE…RELEASED | execution ledger |
| provider **dispatch** state | transport: accepted/pending/timed_out/transport_error | provider |
| **workflow** state | product orchestration | Workflow Service |

## Per-state definition

| State | Transition owner | Idempotency | Retry | Timeout | Reconciliation required? | Another caller may reserve? |
|---|---|---|---|---|---|---|
| `AVAILABLE` | ledger | n/a | n/a | n/a | no | **yes** (first to `reserve_once` wins) |
| `RESERVED` | ledger (atomic acquire) | same key → same reservation | re-`reserve_once` returns `ALREADY_RESERVED` | TTL → abandoned handling | no | no |
| `DISPATCHED` | execution boundary | dispatch is at-most-once per reservation | no fresh dispatch | dispatch deadline → `OUTCOME_UNCERTAIN` | no | no |
| `OBSERVED_SUCCESS` | observation | duplicate observation is idempotent | none | n/a | no | **never** (permanent) |
| `OBSERVED_FAILURE` | observation | idempotent | policy-gated | n/a | maybe | only per policy after reconciliation |
| `OUTCOME_UNCERTAIN` | execution boundary | idempotent | **no** re-dispatch before reconciliation | escalates to reconciliation | **yes** | **no** |
| `RECONCILED_SUCCESS` | reconciliation service | idempotent | none | n/a | done | **never** |
| `RECONCILED_FAILURE` | reconciliation service | idempotent | controlled retry per policy | n/a | done | per policy (new reservation) |
| `RELEASED` | ledger | idempotent | n/a | n/a | must have been safe | **yes** |

## Validation (checks that must pass before `ACQUIRED`)

Before returning `ACQUIRED`, the ledger/execution boundary validates:

1. receipt exists,
2. receipt body is intact (recomputed `result_fingerprint` matches `receipt_id`),
3. receipt status is `CLEAR`,
4. receipt lifecycle permits execution (`ISSUED`, not `EXPIRED`/`SUPERSEDED`/`REVOKED`/`INVALIDATED`),
5. receipt has not expired (`evaluation/dispatch time ≤ valid_until`),
6. receipt authorization matches `expected_authorization_ref`,
7. receipt action fingerprint matches `expected_action_fingerprint`,
8. target and operation match the execution key,
9. tenant matches,
10. no prior reservation or completion exists for the key,
11. upstream authorization remains valid, where the architecture supports atomic verification.

**Inside the atomic transaction:** checks (10) — the uniqueness decision on the execution key — and the
durable state read that decides `ACQUIRED` vs `ALREADY_*`. **Preconditions (verified with no TOCTOU
window):** checks (1)–(9) and, where possible, (11). Because (1)–(9) are computed over the **immutable**
receipt body and the caller-supplied dispatch time, they cannot change between validation and the atomic
insert — there is no state to race. The only racing decision is the uniqueness insert, which is atomic.
This avoids the check-then-act TOCTOU of the current `lookup + create` pattern.

## TTL & abandoned execution

- **reservation creation time** and **reservation TTL** bound how long `RESERVED` may persist without
  progressing to `DISPATCHED`.
- **dispatch deadline** bounds `DISPATCHED` before it becomes `OUTCOME_UNCERTAIN`.
- **heartbeat/lease:** a long dispatch may renew a lease; a lapsed lease in `RESERVED` (pre-dispatch)
  makes the reservation abandoned.
- **abandoned reservation (pre-dispatch only):** a `RESERVED` reservation whose TTL lapsed **with no
  dispatch attempted** may be safely released to `AVAILABLE`.
- **never auto-release:** a reservation in `DISPATCHED` or `OUTCOME_UNCERTAIN` must **never** be released
  automatically.

## The critical uncertain-outcome rule

> A timed-out caller does not imply the external action did not occur.

Therefore a reservation associated with **uncertain dispatch** (`OUTCOME_UNCERTAIN`) requires
**reconciliation before reuse**. It may not transition to `RELEASED`/`AVAILABLE` on a timeout. Only
`RECONCILED_FAILURE` (confirmed no-op) may permit a controlled retry per policy; `RECONCILED_SUCCESS`
permanently prevents duplicate execution. This mirrors the decision-authority reconciliation model:
unknown finality is `INDETERMINATE`, not success.

## Closure

**CLOSED_BY_NEW_PRODUCT_INTERFACE** for the state set and transitions; the durable implementation is the
enforcement deliverable in `EXECUTION_RESERVATION_CONTRACT.md`.
