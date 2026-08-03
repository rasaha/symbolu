# Integration Ports

Ugence Procurement integrates with the outside world only through the kernel's
**neutral ports**. Procurement supplies deterministic, offline adapters for each
today; a future enterprise system would connect through the same seams without ever
taking over governance authority.

## The neutral ports

| Port (kernel) | Procurement adapter (today) | Role |
|---|---|---|
| `LinkedRecordPort` | `ProcurementAssessmentLinkedRecordAdapter` | Projects a finalized `PolicyAssessment` onto a neutral `LinkedRecordSnapshot`. Only governance-relevant fields cross (identity, tenant, version, finalized status, subject, blocked flag) — no purchase-request content. |
| `ActionControlPlanePort` | `BudgetAuthorityAdapter` | Supplies procurement **policy** (spending limits, approval threshold, restrictions) to the kernel `ActionAuthorizationService`. This is a control plane, **not** ActionGate. |
| `ExternalExecutionPort` | `SupplierExecutionAdapter` | Dispatches the authorized action to the supplier (external system) and reports observed outcomes. Offline and deterministic today. |

The kernel's `ActionAuthorizationService` remains the authorization **engine**; the
budget-authority adapter only provides the policy it consults. There is no
procurement-specific authorization engine.

## How a future enterprise system would connect

An enterprise procurement system (SAP Ariba, Coupa, ServiceNow, Oracle, or an ERP)
would attach as a new adapter implementing one of these ports — **replacing the
offline reference adapter, not the governance chain**. Design constraints:

1. **Read-only first.** A production connector begins as a read-only snapshot adapter (e.g. reading supplier/budget records) before any write path is considered. Purchase-order writes are explicitly out of scope for the first integration phase.
2. **No transfer of governance authority.** The connector implements a port; it does not decide, authorize, or approve. The four authority boundaries ([AUTHORITY_MODEL.md](AUTHORITY_MODEL.md)) stay enforced by the kernel and procurement services, never delegated to the connector.
3. **Fail-closed preserved.** A connector's unknown/timeout/unavailable responses must map to the neutral non-success outcomes; a transport acknowledgement from the enterprise system is still not business completion.
4. **Neutral boundary.** Only the neutral snapshot/outcome shapes cross the port; enterprise-specific payloads stay inside the adapter.

## Not shipped today

**None** of these production connectors ship in this distribution. There is no
SAP Ariba, Coupa, ServiceNow, or Oracle adapter, no ERP SDK, and no network path of
any kind. Only the deterministic, offline reference adapters exist. Enterprise
snapshot-adapter design is future work (see [NEXT_PHASES.md](NEXT_PHASES.md)).
