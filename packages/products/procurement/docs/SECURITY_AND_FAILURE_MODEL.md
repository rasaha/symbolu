# Security and Failure Model

Ugence Procurement **fails closed**. No unknown, malformed, stale, mismatched,
timed-out, or unavailable condition is ever allowed to become an authorization or a
success. Uncertainty resolves to a non-success outcome, never an optimistic one.

## Fail-closed table

| Condition | Where | Result (never authorization / success) |
|---|---|---|
| Unknown supplier | request validation | `SupplierNotKnownError` (request rejected) |
| Unknown budget | request validation | `BudgetNotKnownError` (request rejected) |
| Malformed amount | budget authority | non-numeric amount treated as `0`; over-limit still denies; never auto-authorizes |
| Missing / non-finalized assessment | linked-record link | case cannot advance on a blocked/non-finalized assessment; `AssessmentNotFinalizedError` |
| Stale / expired authorization (CER past `expires_at`) | budget authority | `EXPIRED` (no constraints, no authorization) |
| Mismatched decision | action request → CER binding | action request must bind to the exact approved decision; a mismatch does not authorize |
| Tenant mismatch | kernel case/validation | rejected by kernel governance; never crosses tenant |
| Restricted supplier or budget | budget authority | `DENIED` |
| Amount above `hard_limit` | budget authority | `DENIED` |
| Provider timeout | supplier dispatch | `TIMED_OUT` (outcome unknown, not success) |
| Adapter transport unavailable | supplier dispatch | `TRANSPORT_FAILED` (no acknowledgement) |
| Malformed / unknown status | supplier query | `Finality.UNKNOWN`; business outcome `UNKNOWN` |
| Missing mandatory constraint / obligation | authorization | `AUTHORIZED_WITH_CONSTRAINTS` carries the required obligation; it is not dropped |

## Outcome distinctions

Different negative results carry different meaning and must not be collapsed:

| Outcome | Meaning |
|---|---|
| `DENIED` | Authorization refused by policy (restricted, over-limit) — a definite no. |
| `EXPIRED` | The authorization window has passed; the request is stale. |
| `INDETERMINATE` / `UNKNOWN` | The result cannot be established (e.g. supplier `UNKNOWN`) — not success. |
| `TIMED_OUT` | No acknowledgement/outcome within the window — outcome unknown. |
| `TRANSPORT_FAILED` | The dispatch did not reach the supplier — no acknowledgement at all. |

`SupplierOutcome` maps `TIMED_OUT` and `UNKNOWN` to the kernel's neutral
`BusinessOutcome.UNKNOWN` and sets `Finality.UNKNOWN`; only `ACCEPTED` maps to
`SUCCEEDED`.

## Supplier acknowledgement is NOT business completion

A `TransportStatus.ACKNOWLEDGED` from the supplier adapter means only that the
transport accepted the dispatch. It is **not** a business outcome. Business
completion is established solely by a subsequent observed status
(`ExternalStatusResponse`) with a final business outcome. The kernel
`ExecutionRecord` remains authoritative; reconciliation may yield
`COMPENSATION_REQUIRED`.

## Security posture

- No credentials, network calls, or external state are used anywhere.
- Human approval is required for binding decisions; automation cannot approve.
- Authorization is bound to the exact approved purchase and may only narrow it.
- All governance operations are authorized and audited inside kernel services.
