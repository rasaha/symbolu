# External-Execution Mapping — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§4.7, §11).
> Verified against live code at commit `3ec11e4e`.

## 1. Neutral execution contract (exact fields)

`ExecutionDispatchRequest` (`contracts/execution.py:31`): `action_type` · `parameters:
Mapping[str,str]` · `idempotency_key` · `correlation_id`. **No governance-reference fields.**

`ExecutionDispatchResult` (`:39`): `accepted` · `external_request_id` · `acknowledgement` ·
`pending` · `timed_out` · `transport_error` · `retryable`. "A *transport* result — never a business
outcome."

`ExecutionObservation` (`:54`): `business_outcome: ExecutionBusinessOutcome` (`SUCCEEDED · FAILED ·
REJECTED · PENDING · DUPLICATE · UNKNOWN`) · `observed_parameters` · `final` · `reason` ·
`provider_trace_id` · `fingerprint`.

`ExternalExecutionProvider` (`:66`): `dispatch` / `observe` / `cancel`.

**The only EXTERNAL_EXECUTION implementation present is the framework test-double**
`reference/execution.py:25` `DeterministicExecutionProvider`. There is **no** GitHub (or any
business) execution provider; there is **no baseline execution provider** either.

## 2. GPF execution adapter and the DA execution layer

The neutral provider is adapted onto the frozen kernel port by
`adapters/execution_to_external_system.py:70` `ExternalExecutionAdapter` (kernel
`ExternalExecutionPort`): `dispatch(intent)` builds the neutral request from the kernel intent
(`action_type`, `parameters=dict(intent.authorized_parameters)`, `idempotency_key`,
`correlation_id`) and normalizes transport outcomes; `query_status()` calls `provider.observe()` and
maps `ExecutionBusinessOutcome` → kernel `BusinessOutcome` (note `PENDING → UNKNOWN`).

**Governance binding lives above the neutral contract**, in the Decision Authority execution layer
(`ugence_decision_authority/execution/`):
- `ExecutionIntent` (`execution_intent.py:24`) — an immutable authorized-attempt snapshot carrying
  `action_request_id`+`action_request_version`, `authorization_id`, `cer_id`, `authority_ref`,
  `policy_refs`, `authorized_parameters`, `execution_idempotency_key`, and its own `content_hash`.
- `ExecutionAttempt` (`execution_attempt.py:23`) — one transport-only dispatch (payload hashed;
  timeout → UNKNOWN, never auto-fail).
- `ExecutionRecord` (`execution_record.py:24`) — the observed outcome, with `external_result_id`,
  `business_outcome`, `observed_parameters`, `evidence_refs`, `content_hash`.
- `ReconciliationResult` (`reconciliation.py:23`) — immutable comparison.

The full chain **DecisionCase/`decision_id` → `ActionRequest` → CER → `Authorization` →
`ExecutionIntent` → `ExecutionAttempt` → `ExecutionRecord`** is materialized as references at the DA
layer. `execution_service.create_execution_intent()` enforces: request authorized, latest executable
authorization resolved, authz+CER expiry checked, and **params must be a subset of authorized**
(`:139-145`).

## 3. Audit answers

- **Correlation IDs** propagate verbatim end-to-end: `ActionRequest.correlation_id` → `cer.correlation_id`
  → `ExecutionIntent.correlation_id` → `ExecutionDispatchRequest.correlation_id` →
  `ExecutionAttempt`/`Record`/`ReconciliationResult` and every audit emit.
- **Idempotency**: two distinct keys — action-request (`ActionRequest.idempotency_key` +
  `content_key()`) and execution (`ExecutionIntent.execution_idempotency_key`, deduped by
  `lookup_by_execution_idempotency_key`; conflict → `ExecutionIdempotencyConflictError`). The
  execution key flows into the neutral request for provider-side dedup.
- **Provider descriptor resolution**: deterministic precedence (`resolution.py:resolve`), never
  guesses among ties; emits an auditable `ResolutionRecord`.
- **Arbitrary operation parameters**: yes — `parameters: Mapping[str,str]` is an open string map.
- **Governance references attachable?** Not natively on the neutral request.
- **Duplicate merges**: prevented at three layers — execution-idempotency lookup before intent
  creation; monotonic immutable attempts with `RetryClassification` (no retry without explicit
  classification); observation-time `external_result_id` duplicate detection → `DUPLICATE` →
  `DUPLICATE_EFFECT` → `MANUAL_REVIEW_REQUIRED` + `compensation_required`.
- **Reconciliation**: `_compare()` classifies SUCCEEDED (per-key `PARAM_MISMATCH`), PARTIAL,
  FAILED/REJECTED (`COMPENSATION_REQUIRED`), UNKNOWN (INDETERMINATE), DUPLICATE.
- **Merge commit/tree digest**: not part of the execution machinery. The execution layer's
  integrity digests are `ExecutionIntent`/`ExecutionRecord`/`ReconciliationResult.content_hash` and
  `ExecutionAttempt.request_payload_hash`. The **merge-tree/commit digest is product data** carried
  in `observed_parameters`/`evidence_refs` and reconciled against the expected value.

## 4. Governance-chain binding without modifying the neutral contract (§4.7)

The neutral `ExecutionDispatchRequest` deliberately does not carry `decision_id`/`cer_hash`/
`fingerprint`/`clearance`. Two non-invasive seams provide the binding:

1. **Above the contract (preferred).** Use the DA `ExecutionIntent`, which already holds
   `action_request_id/version, authorization_id, cer_id, authority_ref, policy_refs, content_hash`.
   The GPF adapter deliberately forwards only the four neutral fields to the provider, so the
   binding is retained kernel-side (in the `ExecutionAttempt`/`Record` chain + audit), and provider
   trust is re-anchored on return via `ExecutionObservation.fingerprint`/`provider_trace_id`.
2. **Within the contract, no schema change.** Carry the references through the `parameters` map with
   reserved keys (e.g. `gov.decision_id`, `gov.cer_hash`, `gov.action_fingerprint`,
   `gov.acp_clearance`) and/or fold the same digest into `idempotency_key`.

The **Workflow Service fails closed** unless, at dispatch time, it can reconstruct
`DecisionRecord → CER content_hash → ActionGovernanceRequest → ActionGovernanceResult fingerprint →
ACP clearance → ExecutionDispatchRequest`. Any missing/mismatched link → **no dispatch**;
terminal `CHAIN_INCOMPLETE`.

## 5. Execution provider responsibility (must stay narrow)

The GitHub Execution Provider must **not** interpret governance policy. Its responsibility is:
validate the dispatch envelope → perform the already-authorized GitHub operation → observe the
result → return immutable outcome references. Model it on `actiongate_provider/` (pure offline core;
thin `BaseProvider` adapter; `errors/translate_error`; versioned `mapping/`; `conformance/` suite).

## 6. Verdict

The neutral execution contract is **sufficient** — it needs a **provider implementation** (GitHub),
not a contract change. Governance-chain binding is fully expressible via the DA `ExecutionIntent`
(preferred) or reserved `parameters` keys. Reconciliation, idempotency, duplicate-prevention, and
correlation are **already implemented** at the DA layer; the merge-tree/commit-digest binding is
**product data** to record and reconcile. Persistence of these records is the open dependency
(see `DURABLE_AUDIT_AND_RECONSTRUCTION.md`).
