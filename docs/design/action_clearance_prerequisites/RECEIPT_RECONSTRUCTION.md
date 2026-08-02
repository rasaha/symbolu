# Receipt Reconstruction

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Defines how an auditor reconstructs the
full chain from authorization to reconciliation, and the fail-closed semantics when a link is missing.

## The chain

```text
authorization (ActionGovernanceResult, ActionGate)
  → Action Clearance request (ClearanceRequest)
    → trusted signals (SignalBundle, signal_bundle_fingerprint)
      → clearance result (ClearanceResult, result_fingerprint)
        → ClearanceReceipt (receipt_id = acr_<result_fingerprint>)
          → execution reservation (reservation_id, execution_key)
            → dispatch (ExecutionDispatchRequest/Result)
              → observation (ExecutionObservation)
                → reconciliation (ReconciliationResult)
```

## Mandatory references per link

| From → To | Reference that must be present |
|---|---|
| receipt → authorization | `authorization_ref`, `action_governance_result_fingerprint` |
| receipt → decision/CER | `decision_record_ref`, `context_envelope_ref`, `context_envelope_hash` |
| receipt → signals | `signal_refs`, `signal_bundle_fingerprint` |
| result → request | `request_fingerprint` |
| reservation → receipt | `clearance_receipt_ref` (= `receipt_id`) |
| reservation → authorization/action | `authorization_ref`, `action_fingerprint` (must match receipt) |
| dispatch → reservation | `reservation_id`, `execution_key` |
| observation → dispatch | `dispatch_request_id`, `provider_operation_id` |
| reconciliation → observation | `observation_ref`, `reconciliation_ref` |

Reconstruction is a **walk of content-addressed references**, not a shared mutable store
(`docs/design/action_clearance/PERSISTENCE_BOUNDARY.md`). Each hop is verified: the referenced
fingerprint/hash must match the value recorded downstream.

## Failure semantics

When a required record or reference is missing or mismatched, reconstruction is **incomplete**. The
signal:

```text
CLEARANCE_CHAIN_INCOMPLETE
```

(repository-consistent with Code Governance §4.7 "prove the chain"; carried as a workflow-level reason,
not an evaluator status).

## Disposition of incomplete reconstruction (decision)

| Mode | Behavior on incomplete chain |
|---|---|
| **shadow** | permitted to report only; the incompleteness is recorded and surfaced, no dispatch occurs anyway |
| **recommendation** | recommendation is emitted with an explicit `CLEARANCE_CHAIN_INCOMPLETE` caveat; not treated as clear |
| **enforced execution** | **fail closed** — no reservation, no dispatch; the reservation contract's precondition ("receipt exists, chain reconstructs") is unmet |
| **any mode, integrity mismatch** (a reference resolves but the hash disagrees) | **fail closed + human escalation** — a mismatched link is a tamper indicator, not a gap |

**For enforced execution, incomplete reconstruction must fail closed** — this is a hard rule. A missing
link never becomes executable permission (see `FAILURE_AND_RETRY_SEMANTICS.md`).

## Who checks

The **Workflow Service / execution boundary** performs the reconstruction check *before* calling
`reserve_once` (`EXECUTION_RESERVATION_CONTRACT.md` §validation). The Action Clearance evaluator does not
reconstruct the chain — it produces the `result_fingerprint` that anchors it.

## Closure

**CLOSED_BY_NEW_PRODUCT_INTERFACE** — the mandatory references are fixed and the fail-closed disposition
is decided; the reconstruction routine is a Workflow Service / execution-boundary deliverable.
