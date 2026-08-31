# Clearance Receipt — Schema Closure

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Closes design open question **Q2**
(schema half) and completes `Project_documentation/repository/docs/design/action_clearance/RESULT_AND_RECEIPT_CONTRACT.md`. The evaluator
returns a `ClearanceResult`; the workflow layer persists a `ClearanceReceipt` around it. This document
fixes the complete durable receipt fields and their partitions.

## Complete receipt fields

| Field | Partition | Fingerprinted in `result_fingerprint`? | Notes |
|---|---|---|---|
| `receipt_id` | persistence metadata | **excluded** | see identity decision below |
| `receipt_version` | persistence metadata | excluded | receipt schema version (`action_clearance.receipt.v1`) |
| `tenant_id` | evaluator field | yes | must equal request tenant |
| `request_id` | evaluator field | yes | caller-supplied idempotency handle |
| `correlation_id` | reconstruction ref | excluded | cross-system trace |
| `workflow_id` | reconstruction ref | excluded | owning workflow instance |
| `decision_record_ref` | reconstruction ref | yes | Decision Authority `DecisionRecord` id |
| `context_envelope_ref` | reconstruction ref | yes | `cer_id` |
| `context_envelope_hash` | reconstruction ref | yes | CER `content_hash` |
| `authorization_ref` | evaluator field | yes | ActionGate authorization id |
| `action_governance_result_fingerprint` | evaluator field | yes | frozen `ActionGovernanceResult.fingerprint` |
| `authorized_action_fingerprint` | evaluator field | yes | exact-action identity |
| `clearance_status` | evaluator field | yes | `CLEAR`/`HOLD`/`BLOCK`/`ESCALATE` |
| `reason_codes` | evaluator field | yes (canonically ordered) | order does not change fingerprint |
| `effective_constraints` | evaluator field | yes | `= authorization ∩ clearance` |
| `obligations` | evaluator field | yes | `⊇ authorization obligations` |
| `signal_refs` | evaluator field | yes | references/fingerprints of evaluated signals |
| `signal_bundle_fingerprint` | evaluator field | yes | bundle identity |
| `policy_refs` | evaluator field | yes | clearance-policy versions |
| `evaluated_at` | evaluator field | yes | equals `request.evaluation_time` |
| `valid_until` | evaluator field | yes | `≤ authorization.expires_at` and `≤ min(signal valid_until)` |
| `request_fingerprint` | evaluator field | yes | binds result to request |
| `result_fingerprint` | evaluator field | n/a (it *is* the digest) | content address of all fingerprinted fields |
| `created_at` | persistence metadata | **excluded** | wall-clock issue time |
| `lifecycle_state` | lifecycle metadata | **excluded** | see `RECEIPT_LIFECYCLE.md` |
| `supersedes` | lifecycle metadata | excluded | prior receipt id (lineage) |
| `superseded_by` | lifecycle metadata | excluded | successor receipt id |
| `revocation_ref` | lifecycle metadata | excluded | upstream event that revoked |

## The four partitions

1. **Deterministic evaluator fields** — everything the pure evaluator produces. These are exactly the
   `ClearanceResult` fields and feed `result_fingerprint`. Byte-identical across replays.
2. **Persistence metadata** — `receipt_id`, `receipt_version`, `created_at`. Storage identity and wall
   clock; **excluded** from `result_fingerprint` so storage never perturbs evaluation identity.
3. **Lifecycle metadata** — `lifecycle_state`, `supersedes`, `superseded_by`, `revocation_ref`. Mutable
   *effective* state expressed as append-only events (`RECEIPT_LIFECYCLE.md`); the receipt **body** is
   immutable.
4. **Reconstruction references** — `correlation_id`, `workflow_id`, `decision_record_ref`,
   `context_envelope_ref`/`_hash`. Ids/hashes for chain reconstruction; never the referenced records
   themselves.

## Prohibited contents

No credentials, no provider commands, no mutable external state, no secrets, no live tokens. The receipt
is an evidence record, not an execution instruction.

## Receipt identity (decision)

`result_id = "acr_" + result_fingerprint` is the **content-addressed evaluation identity** and is
sufficient to reference the *result*. A **separate storage-record identity** `receipt_id` is still
required because:

- two receipts can carry the *same* `result_fingerprint` (an idempotent re-put, or a re-issue after a
  transient store failure) yet be distinct storage rows;
- lifecycle events (`SUPERSEDED`, `REVOKED`) attach to a **storage record**, not to the immutable
  content address.

**Chosen design:**
- **Evaluation identity:** `acr_<result_fingerprint>` (deterministic, content-addressed).
- **Storage identity:** `receipt_id = acr_<result_fingerprint>` as the **primary** id, with an optional
  monotonic storage sequence for lifecycle-event ordering. Idempotent `put_receipt` is therefore
  content-addressed: putting the same result twice returns the same `receipt_id` (acceptance scenario 12).
- The receipt **body is immutable**; lifecycle transitions are **append-only events or linked records**,
  never a mutation of the body.

## Closure

Prerequisite B (schema half) is **CLOSED_BY_NEW_PRODUCT_INTERFACE**. Schema:
`clearance_receipt.schema.json`.
