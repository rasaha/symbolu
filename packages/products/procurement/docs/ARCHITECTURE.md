# Architecture

Ugence Procurement (distribution `ugence-procurement`, canonical namespace
`ugence_procurement`, distribution version 0.1.0, product version 0.1.0) is a
governed **purchase-approval and authorized-supplier-action** product. It is a
thin, domain-specific vertical composed on top of the domain-neutral **Decision
Authority kernel** (distribution `ugence-decision-authority`, namespace
`ugence_decision_authority`). Procurement supplies the purchase domain and the
adapters; the kernel supplies the governance engine.

## Layers

| Layer | Owner | Responsibility |
|---|---|---|
| Governance kernel | `ugence_decision_authority` | Cases, recommendations, decisions, action requests, CER binding, authorization, execution, reconciliation, compensation, audit, identity, policy |
| Procurement domain | `ugence_procurement` (contracts, validation, policy, outcomes) | Purchase-request evidence and deterministic domain logic |
| Procurement application | `ugence_procurement` (platform, configuration, routes) | Composition root and the callable lifecycle facade |

The kernel is treated as an unchanged third-party library. Procurement never
modifies it; it only implements kernel **ports** and drives kernel **services**.

## Composition root: `platform.py`

`ugence_procurement.platform` is the single composition root. `ProcurementPlatform`
is a dataclass holding every wired service; `build_in_memory_platform()` constructs
the in-memory instance. It wires the kernel governance services
(`CaseValidationService`, `DecisionCaseService`, `CaseRecommendationService`,
`CaseDecisionService`, `ActionRequestService`, `CERBindingService`,
`ActionAuthorizationService`, `ExecutionService`, `ReconciliationService`,
`CompensationService`, and their validation and repository collaborators) with the
procurement domain adapters:

- `ProcurementAssessmentService` + `InMemoryProcurementAssessmentRepository` — deterministic policy assessment.
- `ProcurementRequestValidator` — deterministic request validation.
- `ProcurementAssessmentLinkedRecordAdapter` — kernel `LinkedRecordPort`.
- `BudgetAuthorityAdapter` — kernel `ActionControlPlanePort` (a control plane, **not** ActionGate).
- `SupplierExecutionAdapter` — kernel `ExternalExecutionPort` (deterministic, offline).
- `ProcurementPolicyAdapter` — access policy plugged into kernel services.

`ProcurementPlatform.build_api()` returns the callable facade.

## Domain vs. application separation

- **Domain** (`requests/`, `validation/`, `policies/`, `suppliers/`, `adapters/`, `errors.py`): purchase-request contracts and deterministic domain logic. Purchase-request content is never seen by the kernel — only a *finalized assessment* crosses the boundary via the neutral `LinkedRecordPort`.
- **Application** (`platform.py`, `configuration.py`, `routes.py`): wiring and orchestration.

## Module map

```
ugence_procurement/
  __init__.py            # lazy top-level surface (PEP 562)
  api.py                 # curated public API (48 frozen names)
  version.py             # DISTRIBUTION_VERSION, version_info()
  configuration.py       # ProcurementConfiguration, DEFAULT_CONFIGURATION
  platform.py            # composition root
  routes.py              # ProcurementAPI callable facade
  errors.py              # procurement error taxonomy
  requests/contracts.py  # PurchaseRequest, PurchaseItem, references
  validation/            # ProcurementRequestValidator
  policies/              # assessment, budget_authority, policy_adapter
  suppliers/             # adapter (offline), outcomes vocabulary
  adapters/              # linked-record adapter
  actions/               # decision→action mappings
  approvals/             # recommendation/approval vocabulary
  product/               # version (maturity), cli, demo
```

## Relationship to legacy trees

The canonical implementation lives once, under `ugence_procurement`. The monorepo
`domains/procurement/` and `applications/procurement/` trees are logic-free
compatibility facades that re-export the identical canonical objects (object
identity preserved). There are not two implementations. See
[COMPATIBILITY.md](COMPATIBILITY.md).
