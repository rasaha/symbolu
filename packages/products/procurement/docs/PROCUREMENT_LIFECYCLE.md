# Procurement Lifecycle

The full governed lifecycle, stage by stage. `ProcurementAPI` (in
`ugence_procurement.routes`) orchestrates it over the unchanged kernel; every
governance operation is authorized and audited inside kernel services.

```
purchase request → deterministic validation → deterministic policy assessment
→ advisory recommendation → HUMAN approval decision → governed action request
(exactly bound to the approved supplier / budget / amount) → neutral authorization
→ EXPLICIT supplier dispatch → observed supplier outcome → reconciliation
→ compensation-when-required
```

## Stages and records

| Stage | Call | Record produced | Fail-closed branch |
|---|---|---|---|
| Purchase request | construct `PurchaseRequest` | `PurchaseRequest` (validated pydantic model) | Invalid fields raise `DomainValidationError` |
| Deterministic validation | `request_validator.validate` | (raises on failure) | Unknown supplier/budget → `SupplierNotKnownError` / `BudgetNotKnownError`; bad request → `PurchaseRequestValidationError` |
| Deterministic policy assessment | `assessment_service.assess` | `PolicyAssessment` (FINALIZED, with `PolicyCheck`s) | A failed **blocking** check sets `blocked=True` |
| Case open + link | `submit_and_assess` | kernel decision case; linked assessment snapshot | Blocked/non-finalized assessment blocks the case at link time |
| Advisory recommendation | `recommend` | `RecommendationRecord` | Advisory only — never becomes a decision |
| HUMAN approval decision | `decide` | `DecisionRecord` | Requires `HUMAN_APPROVER` authority |
| Governed action request | `request_action` | action request bound to `amount` / `supplier_id` / `budget_id` | Mapping selected by decision outcome |
| Neutral authorization | `authorize` (validate → bind CER → submit) | `ActionAuthorizationResponse` | `DENIED` / `EXPIRED` / restricted / over-limit fail closed |
| Explicit supplier dispatch | `dispatch_and_observe` (create intent → dispatch) | execution intent + `ExternalDispatchResponse` | `TRANSPORT_FAILED` / `TIMED_OUT` never mean success |
| Observed supplier outcome | `query_external_status` | `ExternalStatusResponse` (business outcome) | Ack ≠ completion; `UNKNOWN`/`TIMED_OUT` → `Finality.UNKNOWN` |
| Reconciliation | `reconcile_execution` | reconciliation status | May be `COMPENSATION_REQUIRED` |
| Compensation | `compensation_service` | compensation record | Invoked only when required |

## Decision → action mapping

The action request created depends on the decision outcome:

| Decision outcome | Mapping | Action |
|---|---|---|
| ADVANCE | `proc.create_po` → `CREATE_PURCHASE_ORDER` | carries exact amount / supplier / budget |
| REJECT | `proc.cancel` → `CANCEL_REQUEST` | carries `request_id` only |
| HOLD | `proc.route_senior` → `ROUTE_TO_SENIOR_APPROVER` | carries `request_id` only |
| DEFER | `proc.request_info` → `REQUEST_MORE_INFORMATION` | carries `request_id` only |

## End-to-end

`ProcurementAPI.run(...)` walks the entire chain and returns a
`ProcurementRunResult` (`case_id`, `assessment_id`, `recommendation`, `decision`,
`action_request_id`, `authorization_outcome`, `reconciliation_status`,
`compensation_required`). The workflow is fully deterministic and offline (see
[DETERMINISM.md](DETERMINISM.md)); it never executes anything for real.
