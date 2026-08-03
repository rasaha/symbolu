# Public API

The single stable, supported product surface is `ugence_procurement.api`. It
re-exports product-level contracts and entry points from their canonical
implementation modules — object identity is preserved, so the names here **are**
the canonical objects. Internal repositories, helpers, and kernel plumbing are
deliberately not exported here.

```python
import ugence_procurement.api
```

The exact set of 48 names is **frozen against `artifacts/public_api.json`** and
enforced by a test. Adding or removing a public name is a deliberate, reviewed API
change.

## Surface by area

| Area | Names |
|---|---|
| Requests & items | `PurchaseRequest`, `PurchaseItem`, `SupplierReference`, `BudgetReference`, `Urgency`, `RequestStatus` |
| Validation | `ProcurementRequestValidator` |
| Assessment | `PolicyAssessment`, `PolicyCheck`, `AssessmentStatus`, `ProcurementAssessmentService`, `InMemoryProcurementAssessmentRepository`, `BudgetAuthorityAdapter`, `ProcurementPolicyAdapter` |
| Approvals / recommendations | `PurchaseRecommendation`, `PurchaseApproval`, `RECOMMENDATION_TO_PROPOSED`, `APPROVAL_TO_DECISION`, `proposed_outcome_for`, `decision_outcome_for` |
| Actions | `PROCUREMENT_DECISION_TYPE`, `SUPPLIER_SYSTEM_TYPE`, `CREATE_PURCHASE_ORDER`, `CANCEL_REQUEST`, `ROUTE_TO_SENIOR_APPROVER`, `REQUEST_MORE_INFORMATION`, `all_mappings` |
| Suppliers | `SupplierExecutionAdapter`, `SupplierOutcome`, `SUPPLIER_TO_BUSINESS`, `business_outcome_for` |
| Adapters | `ProcurementAssessmentLinkedRecordAdapter` |
| Errors | `ProcurementError`, `DomainValidationError`, `PurchaseRequestValidationError`, `AssessmentNotFinalizedError`, `SupplierNotKnownError`, `BudgetNotKnownError` |
| Configuration / platform / facade | `ProcurementConfiguration`, `DEFAULT_CONFIGURATION`, `ProcurementPlatform`, `build_in_memory_platform`, `ProcurementAPI`, `ProcurementRunResult` |
| Version / maturity | `version_info`, `VersionInfo`, `product_maturity`, `ProductMaturity` |

## Notes on selected names

- `BudgetAuthorityAdapter` implements the kernel `ActionControlPlanePort` (a control plane, **not** ActionGate).
- `SupplierExecutionAdapter` is the deterministic, **offline** reference execution adapter — not a real supplier/ERP connector.
- `version_info()` / `product_maturity()` always report `pilot_validated=False` and `production_certified=False`.

## Top-level convenience surface

`ugence_procurement` itself lazily (PEP 562) exposes a small subset —
`ProcurementPlatform`, `build_in_memory_platform`, `ProcurementConfiguration`,
`ProcurementAPI`, `version_info`, `VersionInfo`, `PRODUCT_VERSION`, `__version__` —
resolving to the identical canonical objects. For the full, stable surface, import
`ugence_procurement.api`.
