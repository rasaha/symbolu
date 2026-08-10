# Existing Execution Repository Assessment

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Inspects the live Decision Authority
execution repositories, the GPF external-execution flow, and existing idempotency/reconciliation
implementations, and classifies each for reuse. Evidence gathered from the live tree at default HEAD.

## Candidate 1 — `ExecutionRepository` / `InMemoryExecutionRepository`

**Path:** `packages/capabilities/decision-authority/src/ugence_decision_authority/repositories/execution_repository.py`

| Property | Finding |
|---|---|
| public API | `create_execution_intent`, `save_execution_snapshot`, `get_execution_intent`, `get_intent_history`, `record_execution_attempt`, `record_execution_record`, `record_reconciliation_result`, `record_compensation_requirement`, `lookup_by_execution_idempotency_key(tenant_id, key)`, `lookup_by_external_request_id` |
| persistence model | **in-memory dicts** — `_intents`, `_idempotency: (tenant_id, key)→intent_id`, `_records_by_intent`, `_recons_by_intent`, … Reference implementation; no SQL, no durability across restart |
| atomicity | **none beyond single-threaded dict mutation** — no transactions, no locks, no CAS |
| idempotency | **check-then-act**: `lookup_by_execution_idempotency_key` (returns `None` for `TERMINAL_EXECUTION_STATUSES`) followed by `create_execution_intent` (raises `VersionConflictError` on duplicate primary key). Race-prone under concurrency |
| reservation semantics | **none** — no `reserve_once` / compare-and-swap / reservation method exists anywhere in the package |
| observation linkage | `ExecutionRecord` (observed `BusinessOutcome`), `record_execution_record`, `lookup_by_external_request_id` — solid |
| reconciliation | `ReconciliationResult` + `reconcile_execution` service; unknown finality → `INDETERMINATE`, not success — solid |
| tenant behavior | idempotency keyed by `(tenant_id, key)`; every record carries `tenant_id` |
| production maturity | **reference / in-memory** — append-only, immutable, versioned (`content_hash`, `.evolve()`), but not durable |
| **classification** | **`EXTEND_BEHIND_EXISTING_INTERFACE`** — add an atomic `reserve_once` to the port; keep the append-only record model; supply a durable backend for enforcement |

## Candidate 2 — Neutral execution contracts

**Path:** `packages/governance-contracts/src/ugence_governance_contracts/contracts/execution.py`
(mirrored in the GPF package).

| Element | Finding | Classification |
|---|---|---|
| `ExecutionDispatchRequest` (`idempotency_key`, `correlation_id`) | transport request; carries the idempotency key but no receipt/authorization refs | **REUSE_AS_IS** (unchanged) |
| `ExecutionDispatchResult` | transport result, "never a business outcome" | **REUSE_AS_IS** |
| `ExecutionObservation` (`business_outcome`, `provider_trace_id`, `fingerprint`) | observed outcome | **REUSE_AS_IS** |
| `ExecutionBusinessOutcome` {SUCCEEDED, FAILED, REJECTED, PENDING, DUPLICATE, UNKNOWN} | the outcome vocabulary; `DUPLICATE` is the race-loser signal | **REUSE_AS_IS** |
| `ExternalExecutionProvider.dispatch/observe/cancel` | provider port | **REUSE_AS_IS** |
| `ProviderKind` {ASSERTION_GOVERNANCE, ACTION_GOVERNANCE, EXTERNAL_EXECUTION} | unchanged; **no new kind added** | **REUSE_AS_IS** |

## Candidate 3 — decision-authority execution domain models

**Path:** `.../ugence_decision_authority/execution/` (`execution_intent.py`, `execution_record.py`,
`execution_attempt.py`, `reconciliation.py`, `compensation.py`, `status.py`).

| Element | Finding | Classification |
|---|---|---|
| `ExecutionIntent` (`authorization_id`, `cer_id`, `execution_idempotency_key`, `content_hash`, `status`) | the natural carrier of the reservation/execution-envelope correlation | **REUSE_WITH_ADAPTER** — the Action Clearance reservation maps onto this record; add `clearance_receipt_ref` as an attribute |
| `ExecutionStatus` (16 states; `TERMINAL_EXECUTION_STATUSES = {CANCELLED, SUPERSEDED}`) | rich lifecycle; informs the reservation state machine | **REFERENCE_ONLY** for the neutral reservation-state design |
| `BusinessOutcome`, `Finality`, `ReconciliationStatus`, `RetryClassification` | outcome/retry vocabulary | **REUSE_AS_IS** |
| `ReconciliationResult` + `reconcile_execution` | immutable reconciliation | **REUSE_AS_IS** |

## Candidate 4 — `ai_hiring` execution repository

**Path:** `ai_hiring/repositories/execution_repository.py` (+ hiring execution/reconciliation services).
A separate **app-domain** implementation. **Classification: `REFERENCE_ONLY`** — it is not the neutral/
canonical ledger; the decision-authority repository is the canonical one the design points to.

## Bottom line

- The **record model, reconciliation, observation, and neutral contracts are reusable as-is or with a
  thin adapter.**
- The **atomic reserve-once primitive does not exist** and must be added behind the existing
  `ExecutionRepository` port (`EXTEND_BEHIND_EXISTING_INTERFACE`), with a **durable backend**
  (`PRODUCT_SPECIFIC_REPOSITORY_REQUIRED` / `OPEN_IMPLEMENTATION_DECISION`) for enforcement.
- **Do not assume the repository named "execution" provides atomic reservation** — it provides
  check-then-insert idempotency only. This is the single hard gap for enforced one-time execution.

## Closure

Prerequisite D reuse decision is **recorded**: extend the existing port with `reserve_once`; reuse the
record/reconciliation/observation model; add a durable atomic backend as an enforcement deliverable.
