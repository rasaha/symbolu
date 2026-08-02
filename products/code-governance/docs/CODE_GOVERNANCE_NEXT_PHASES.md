# Code Governance — Next Phases (out of scope for MVP 1B)

MVP 1B stops at shadow Action Clearance evaluation + explainable intervention routing +
chain reconstruction. The following are **not** implemented and must not be started
under this phase:

| Item | Owner / phase |
|---|---|
| Durable, enforcement-grade `ClearanceReceipt` persistence + lifecycle | Workflow Service (later) |
| Atomic one-time execution **reservation** / `reserve_once` | execution / idempotency ledger |
| GitHub execution provider (`EXTERNAL_EXECUTION`) | provider (later) |
| Enforced merge (direct + squash), merge queue, rebase | Code Governance MVP 1C+ |
| Live operational-signal adapters (identity / incident / change-management / GitHub) | product/integration |
| Production database | later |

Invariants every later phase must preserve: ActionGate authorization required before
clearance; Action Clearance never creates authority, broadens, persists durably,
reserves, or dispatches; CLEAR is never execution; DecisionRecord remains the binding
decision; no new `ProviderKind`; no neutral-contract change; the canonical Action
Clearance package stays unmodified; the bare acronym "ACP" never appears in new
technical surfaces.
