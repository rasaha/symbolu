# Dispatch & Observation Linkage

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Defines the immutable linkage chain from
clearance receipt through reconciliation, and whether the existing **neutral** external-execution
contracts can carry the required correlation or whether a product-owned execution envelope supplies it.
**No neutral contract is modified in this phase.**

## Required chain

```text
ClearanceReceipt
    ↓ clearance_receipt_ref
ExecutionReservation
    ↓ reservation_id, execution_key
ExecutionDispatchRequest
    ↓ dispatch_request_id
ExecutionDispatchResult
    ↓ external_request_id
ExecutionObservation
    ↓ observation_ref, provider_operation_id
ReconciliationRecord
```

## Immutable linkage fields

| Field | Lives on | Neutral contract carries it? |
|---|---|---|
| `reservation_id` | reservation | no (product/ledger record) |
| `execution_key` | reservation | maps to `idempotency_key` |
| `clearance_receipt_ref` | reservation | no (product envelope) |
| `authorization_ref` | reservation | no (product envelope) |
| `action_fingerprint` | reservation | no (product envelope) |
| `dispatch_request_id` | dispatch | partially — `correlation_id` on `ExecutionDispatchRequest` |
| `provider_descriptor_ref` | dispatch | no (product/registry) |
| `provider_operation_id` | observation | yes — `external_request_id` / `provider_trace_id` on `ExecutionObservation` |
| `observation_ref` | observation | derivable from `ExecutionObservation.fingerprint` |
| `reconciliation_ref` | reconciliation | no (product record — `ReconciliationResult`) |

## Neutral contracts (as they exist today — unchanged)

From `packages/governance-contracts/src/ugence_governance_contracts/contracts/execution.py`:

- `ExecutionDispatchRequest(action_type, parameters, idempotency_key, correlation_id)` — a **transport**
  request. Carries `idempotency_key` (→ execution key) and `correlation_id`, but **not**
  `clearance_receipt_ref`, `authorization_ref`, or `action_fingerprint`.
- `ExecutionDispatchResult(accepted, external_request_id, acknowledgement, pending, timed_out,
  transport_error, retryable)` — a **transport** result, "never a business outcome."
- `ExecutionObservation(business_outcome, observed_parameters, final, reason, provider_trace_id,
  fingerprint)` — an **observed business outcome**; `business_outcome ∈ ExecutionBusinessOutcome
  {SUCCEEDED, FAILED, REJECTED, PENDING, DUPLICATE, UNKNOWN}`.

## Conclusion (decision)

The neutral contracts **cannot carry the full correlation directly** — by design they are transport/
outcome primitives that deliberately exclude authorization, receipt, and action-identity references
(keeping the neutral seam free of product concepts). Therefore a **product-owned execution envelope**
supplies the missing correlation:

```text
ExecutionReservation (product) wraps:
  execution_key, clearance_receipt_ref, authorization_ref, action_fingerprint,
  and links out to the neutral ExecutionDispatchRequest via idempotency_key + correlation_id.
```

This is exactly how the decision-authority `ExecutionIntent` already works: it holds
`authorization_id`, `cer_id`, `execution_idempotency_key`, and `content_hash`, and links to observed
`ExecutionRecord`s — a **product record** carrying references the neutral contract omits. The Action
Clearance reservation reuses this shape (`EXISTING_EXECUTION_REPOSITORY_ASSESSMENT.md`) rather than
widening the neutral contract.

**Do not modify neutral contracts during this phase.** Adding `clearance_receipt_ref` to
`ExecutionDispatchRequest` is explicitly out of scope; the product envelope carries it.

## Closure

**CLOSED_BY_FUTURE_ADAPTER_CONTRACT** — the correlation is carried by a product execution envelope
(reusing `ExecutionIntent`'s pattern); the neutral contracts stay unchanged.
