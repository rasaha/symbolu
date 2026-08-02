# Status & Reason-Code Semantics

## Top-level statuses (`ClearanceStatus`) — four

| Status | Meaning |
|---|---|
| `CLEAR` | the exact authorized action is clear to execute now, under `effective_constraints`/`obligations` |
| `HOLD` | not clear now, but transiently — a fresh clearance later may succeed with no upstream change |
| `BLOCK` | not clear; a permanent mismatch or definite-invalid condition under current operational state |
| `ESCALATE` | not clear; ambiguity/conflict requires a human decision before proceeding |

`STALE`, `EXPIRED`, `INCOMPLETE`, `CONFLICT`, `UNTRUSTED` are **reason codes**, not statuses.
Programming errors and malformed contracts are **exceptions** (see Failure handling). **`DENY` is not a
status** — ActionGate owns authorization denial. A `BLOCK` explicitly means: *execution is not clear
under current operational conditions; the underlying ActionGate authorization is neither broadened nor
replaced.*

### Status combination

Least-permissive-wins with precedence **`BLOCK > ESCALATE > HOLD > CLEAR`**. The final status is the
highest-precedence contribution across all reason codes; `CLEAR` only when there is no non-`CLEAR`
contribution.

### Per-status semantics

| Status | Execution permitted? | Retry allowed? | Fresh request required? | Human review? | Upstream reauthorization? | Authorization still valid? |
|---|---|---|---|---|---|---|
| `CLEAR` | yes (this action, now, within `valid_until`) | n/a | no | no | no | yes |
| `HOLD` | no | yes (after refreshing signals) | yes (new evaluation) | no | no | yes (unchanged) |
| `BLOCK` | no | no (same inputs) | yes, only after the mismatch is fixed | no | if `UPSTREAM_REAUTHORIZATION_REQUIRED` reason present | depends: valid but not-clear, unless `AUTHORIZATION_EXPIRED` |
| `ESCALATE` | no | no (pending human) | yes, after human resolution | yes | possibly | yes (pending) |

## Distinguished conditions

| Condition | Represented as | Status |
|---|---|---|
| transient hold | `HOLD` status + reason (e.g. `SIGNAL_STALE`, `ACTIVE_CHANGE_FREEZE`) | `HOLD` |
| permanent mismatch | `BLOCK` + `ACTION_FINGERPRINT_MISMATCH` / `TARGET_MISMATCH` | `BLOCK` |
| expired authorization | `BLOCK` + `AUTHORIZATION_EXPIRED` + `UPSTREAM_REAUTHORIZATION_REQUIRED` | `BLOCK` |
| missing mandatory signal | `HOLD` + `SIGNAL_MISSING` (fail closed) | `HOLD` |
| human escalation | `ESCALATE` + conflict reason | `ESCALATE` |
| system error | exception (not a result) or `RETRYABLE_ERROR` | — |

## Reason-code catalog (curated, closed)

UPPER_SNAKE, no `ACP`/`AC_` prefix, aligned with Decision Authority's governed-catalog discipline.
Existing ActionGate (`policy_*`) and Decision-Authority (`ReasonCode`) codes are **referenced, not
duplicated**.

| Reason code | Default status | Classification | Notes |
|---|---|---|---|
| `CLEARANCE_GRANTED` | `CLEAR` | CORE_NEUTRAL | positive reason on CLEAR |
| `AUTHORIZATION_EXPIRED` | `BLOCK` | CORE_NEUTRAL | `authorization.expires_at < evaluation_time`; → reauth |
| `AUTHORIZATION_STALE` | `HOLD` | CORE_NEUTRAL | older than policy max-age, not past expiry |
| `ACTION_FINGERPRINT_MISMATCH` | `BLOCK` | CORE_NEUTRAL | authorized action fingerprint ≠ presented |
| `TARGET_MISMATCH` | `BLOCK` | CORE_NEUTRAL | target ref/identity changed |
| `ACTOR_INVALID` | `BLOCK` | CORE_NEUTRAL | actor disabled/removed |
| `ACTOR_STATUS_UNKNOWN` | `HOLD` | CORE_NEUTRAL | fail-closed; refresh actor signal |
| `POLICY_VERSION_REJECTED` | `BLOCK` | CORE_NEUTRAL | policy version no longer accepted |
| `ACTIVE_CHANGE_FREEZE` | `HOLD` | CORE_NEUTRAL | change-freeze window active |
| `ACTIVE_INCIDENT` | `HOLD` (or `ESCALATE` by policy) | CORE_NEUTRAL | blocking incident active |
| `TARGET_UNAVAILABLE` | `HOLD` | CORE_NEUTRAL | target temporarily unavailable |
| `REQUIRED_CONTROL_UNSATISFIED` | `BLOCK` (or `HOLD` if re-evaluable) | CORE_NEUTRAL | a required control is not satisfied |
| `ALREADY_CONSUMED` | `BLOCK` | CORE_NEUTRAL | prior-consumption signal present |
| `SIGNAL_MISSING` | `HOLD` | CORE_NEUTRAL | mandatory signal absent (fail closed) |
| `SIGNAL_STALE` | `HOLD` | CORE_NEUTRAL | signal past freshness/`valid_until` |
| `SIGNAL_UNTRUSTED` | `BLOCK` | CORE_NEUTRAL | integrity proof missing/invalid |
| `SIGNAL_CONFLICT` | `ESCALATE` | CORE_NEUTRAL | contradictory signals |
| `TENANT_MISMATCH` | `BLOCK` | CORE_NEUTRAL | signal/request tenant differ |
| `SUBJECT_MISMATCH` | `BLOCK` | CORE_NEUTRAL | signal subject not bound to action |
| `CONSTRAINT_CONFLICT` | `ESCALATE` | CORE_NEUTRAL | authorization vs clearance constraint conflict |
| `CLEARANCE_POLICY_CONFLICT` | `ESCALATE` | CORE_NEUTRAL | no deterministic merge rule (fail closed) |
| `GITHUB_HEAD_SHA_CHANGED` | `BLOCK` | PROFILE_SPECIFIC | GitHub manifestation of action-identity change |
| `GITHUB_BASE_ADVANCED` | `BLOCK` | PROFILE_SPECIFIC | base branch advanced; merge tree changed |
| `GITHUB_MERGE_TREE_MISMATCH` | `BLOCK` | PROFILE_SPECIFIC | expected merge tree ≠ computed |
| `GITHUB_MERGE_GROUP_MISMATCH` | `BLOCK` | PROFILE_SPECIFIC | merge-group SHA ≠ cleared artifact |
| `GITHUB_MERGE_METHOD_CHANGED` | `BLOCK` | PROFILE_SPECIFIC | merge method differs from authorized |
| `GITHUB_TARGET_BRANCH_MISMATCH` | `BLOCK` | PROFILE_SPECIFIC | target branch differs |
| `GITHUB_REQUIRED_CHECK_PENDING` | `HOLD` | PROFILE_SPECIFIC | a required check not yet green |
| `GITHUB_REQUIRED_CHECK_FAILED` | `BLOCK` (or `HOLD` if re-runnable) | PROFILE_SPECIFIC | a required check failed |
| `GITHUB_APPROVAL_WITHDRAWN` | `BLOCK` | PROFILE_SPECIFIC | required approval withdrawn/dismissed |
| `DISPATCH_DUPLICATE` | — | WORKFLOW_ONLY | belongs to the execution ledger, not the evaluator |
| `RECEIPT_SUPERSEDED` | — | WORKFLOW_ONLY | belongs to the workflow/receipt store |
| `DENY` | — | UNNECESSARY | ActionGate owns denial; not emitted |
| `ACP_*` (any) | — | UNNECESSARY | acronym prohibited (§Terminology) |

Adapter-specific codes (e.g. a specific incident-system's sub-reason) are `ADAPTER_SPECIFIC` and carried
in an adapter extension map, not the neutral catalog.

## Failure handling classification

| Class | Produced when | Form |
|---|---|---|
| `RESULT` | expected policy/operational outcome | a `ClearanceResult` (CLEAR/HOLD/BLOCK/ESCALATE) |
| `RETRYABLE_ERROR` | signal-adapter/persistence/ledger transient failure (outside the core) | typed error raised by the adapter/workflow |
| `NON_RETRYABLE_ERROR` | invalid request, missing reference, malformed contract, unsupported profile | typed exception from the core |
| `ESCALATION` | conflict/ambiguity | `ESCALATE` result |
| `UPSTREAM_REAUTHORIZATION_REQUIRED` | expired/superseded authorization | `BLOCK` result carrying this reason |

Expected operational problems produce **fail-closed results**, not uncontrolled exceptions. Only
programming errors and malformed contracts raise exceptions (see [`STATE_MACHINE.md`](STATE_MACHINE.md)
and the errors module in [`PACKAGE_BOUNDARY.md`](PACKAGE_BOUNDARY.md)).
