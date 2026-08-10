# Prerequisite C — Receipt Lifecycle Ownership

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Closes design open question **Q2**
(lifecycle half) and completes `Project_documentation/repository/docs/design/action_clearance/STATE_MACHINE.md`. Separates the
*evaluator status* (transient, in the pure core) from the *durable receipt lifecycle* (in the workflow
layer), and forbids the evaluator from mutating stored receipts.

## Two distinct axes

| Axis | Values | Owner |
|---|---|---|
| **Evaluator status** (transient) | `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE` | pure evaluator |
| **Receipt lifecycle** (durable) | `ISSUED` / `EXPIRED` / `SUPERSEDED` / `REVOKED` / `INVALIDATED` | Workflow Service |

The evaluator status is a property of a single evaluation. The receipt lifecycle is a property of a
durable record over time. They must never be conflated.

## Minimal lifecycle enum (decision)

```text
ISSUED        # a CLEAR result was persisted as a usable receipt
EXPIRED       # evaluation_time has passed valid_until (see expiration treatment)
SUPERSEDED    # a newer clearance for the same lineage replaced this one
REVOKED       # an upstream authorization/policy/identity event invalidated it
INVALIDATED   # chain or integrity failure detected for this receipt
```

Five states. `ISSUED` is set only for a `CLEAR` result (a non-`CLEAR` result may be recorded for audit
but is never an `ISSUED`, usable receipt).

## Explicitly excluded from the receipt lifecycle

`CONSUMED`, `EXECUTING`, `EXECUTED`, `FAILED` are **not** receipt lifecycle states. They belong to the
**execution reservation, dispatch, and observation** records
(`EXECUTION_RESERVATION_STATE_MACHINE.md`). Repository evidence supports this: the decision-authority
`ExecutionStatus` enum (16 states, including dispatch/observed/reconciled) lives on `ExecutionIntent`,
**not** on any clearance record. Keeping consumption out of the receipt preserves the merged invariant
that Action Clearance never owns the authoritative consumption ledger.

## Per-state definition

| State | Owner | Trigger | Body changes? | New event/linked record? | Execution still permitted? | New clearance request required? | Upstream reauthorization required? |
|---|---|---|---|---|---|---|---|
| `ISSUED` | Workflow Service | a `CLEAR` result is persisted | no (body is written once) | the receipt itself | yes, while `valid_until` holds and no later event | no | no |
| `EXPIRED` | derived (read-time) + optional event | `evaluation_time > valid_until` | no | optional `EXPIRED` marker event | no | yes (fresh evaluation) | no |
| `SUPERSEDED` | Workflow Service | a newer clearance for the same lineage issued | no | `SUPERSEDED` event linking `superseded_by` | no (use the successor) | use the successor receipt | no |
| `REVOKED` | Workflow Service | authoritative upstream invalidation event | no | `REVOKED` event with `revocation_ref` | no | yes | yes (re-authorize) |
| `INVALIDATED` | Workflow Service / audit | chain or integrity failure | no | `INVALIDATED` event | no | yes | depends on the cause |

## Immutability rule

The receipt **body is immutable**. Effective lifecycle is **derived from immutable lifecycle events plus
time** (`RECEIPT_LIFECYCLE.md` model). The Action Clearance evaluator **must not** mutate a stored
receipt — it has no persistence and no write path at all. Every transition is an append-only event or a
linked record authored by the Workflow Service.

## Expiration treatment (decision)

`EXPIRED` is **derived at read time** from `valid_until` and the caller's evaluation/dispatch time; an
optional persisted `EXPIRED` marker event may be appended for audit clarity, but the derived check is
authoritative. This avoids a background mutator and keeps expiry a pure function of the immutable body
plus time (matching the merged decision that expiry "is derived from `valid_until` — no separate store
needed"). Acceptance scenario 20 (exact expiry boundary → non-executable) follows from the derived check
with boundary-at-expiry = expired.

## Closure

Prerequisite C is **CLOSED_BY_NEW_PRODUCT_INTERFACE** — the minimal five-state lifecycle, the
derived-expiry rule, and the append-only-event model are fixed; the Workflow Service owns the transitions.
Machine-readable: `receipt_lifecycle_events.schema.json`.
