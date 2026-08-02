# Prerequisite B — ClearanceReceipt Persistence Interface

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Closes design open question **Q2**
(ownership half). Defines the durable interface for storing Action Clearance outcomes, following the
append-only/immutable/versioned convention of the existing
`ugence_decision_authority` repositories.

## Interface (protocol)

Naming follows the repository's existing repository ports (`ExecutionRepository`,
`ActionRequestRepository`, `DecisionCaseRepository` in
`packages/capabilities/decision-authority/src/ugence_decision_authority/repositories/`), which are
`@runtime_checkable Protocol`s with in-memory reference adapters.

```text
ClearanceReceiptRepository (Protocol)

  put_receipt(receipt) -> PutReceiptResult
      # idempotent, content-addressed on receipt_id = acr_<result_fingerprint>
      # PutReceiptResult ∈ { CREATED, ALREADY_EXISTS_IDENTICAL, CONFLICT_DIFFERENT_BODY }

  get_receipt(receipt_id) -> ClearanceReceipt | None

  get_receipt_by_result_fingerprint(result_fingerprint) -> ClearanceReceipt | None

  list_receipts_for_authorization(authorization_ref) -> Sequence[ClearanceReceipt]
      # lineage/audit reads for one authorization

  supersede_receipt(receipt_id, reason, superseding_ref) -> SupersessionResult
      # appends a SUPERSEDED lifecycle event linking receipt_id -> superseding_ref
      # never rewrites the superseded body

  revoke_receipt(receipt_id, reason, upstream_ref) -> RevocationResult
      # appends a REVOKED lifecycle event; body untouched
```

`put_receipt` returning `CONFLICT_DIFFERENT_BODY` when a different body is presented under an existing
`receipt_id` is the mechanism behind acceptance scenario 13 (same id, different body → conflict).

## Ownership (decision)

| Candidate owner | Verdict |
|---|---|
| **Code Governance Workflow Service** | **chosen** — owns the repository interface and persistence lifecycle |
| neutral workflow persistence capability | acceptable future generalization of the same interface |
| dedicated Action Clearance receipt repository | rejected for MVP — would pull persistence into the capability boundary |
| Decision Authority storage | rejected — DA owns decision/execution records, not clearance receipts; keeping them separate preserves the authority boundary |
| existing append-only record store | the *pattern* is reused (append-only, versioned, `content_hash`); a receipt-specific repository is added behind the same port |

**Preferred default (chosen):** the **Workflow Service owns the `ClearanceReceiptRepository` interface
and persistence lifecycle.** The **Action Clearance package defines only the receipt schema and the
reference requirements** (which fields, which fingerprints, immutability) — it does **not** import or
depend on a concrete database. This matches the merged persistence boundary
(`docs/design/action_clearance/PERSISTENCE_BOUNDARY.md`): "The Workflow Service persists the
ClearanceReceipt."

## No concrete-database dependency

The Action Clearance package may define the **schema** (`clearance_receipt.schema.json`) and, at most, a
`Protocol` describing the port — with an in-memory reference adapter for tests only, mirroring
`InMemoryExecutionRepository`. It must **never** depend on SQL, a document store, or any durable backend;
that dependency lives entirely in the Workflow Service implementation. This preserves the package
dependency floor (`ugence-governance-contracts` only) from
`docs/design/action_clearance/PACKAGE_BOUNDARY.md`.

## Closure

Prerequisite B is **CLOSED_BY_NEW_PRODUCT_INTERFACE** — the interface is defined; the concrete durable
implementation is owned by the Workflow Service and is an **enforcement** deliverable (Phase E), not a
package-core blocker.
