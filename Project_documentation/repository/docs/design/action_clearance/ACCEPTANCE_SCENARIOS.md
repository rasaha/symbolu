# Acceptance Scenarios

Deterministic behavioral matrix. Machine-readable: [`acceptance_scenarios.json`](acceptance_scenarios.json).
Columns: expected `status`, key `reason_codes`, retry allowed, and required owner response.

| # | Scenario | Status | Reason (key) | Retry? | Owner response |
|---|---|---|---|---|---|
| 1 | valid authorization + all signals valid | `CLEAR` | `CLEARANCE_GRANTED` | n/a | dispatch (reserve one-time use) |
| 2 | ActionGate denied | *no evaluation* | `NON_RETRYABLE_ERROR` | no | not clearable; re-authorize upstream |
| 3 | authorization expired | `BLOCK` | `AUTHORIZATION_EXPIRED` + `UPSTREAM_REAUTHORIZATION_REQUIRED` | no | re-authorize |
| 4 | action fingerprint mismatch | `BLOCK` | `ACTION_FINGERPRINT_MISMATCH` | no | new authorization + clearance |
| 5 | target mismatch | `BLOCK` | `TARGET_MISMATCH` | no | correct target; re-authorize |
| 6 | active freeze | `HOLD` | `ACTIVE_CHANGE_FREEZE` | yes | retry after freeze lifts |
| 7 | active incident | `HOLD` or `ESCALATE` (policy) | `ACTIVE_INCIDENT` | yes (HOLD) | wait / human decision |
| 8 | actor disabled | `BLOCK` | `ACTOR_INVALID` | no | restore actor or re-authorize |
| 9 | actor status unknown | `HOLD` (fail closed) | `ACTOR_STATUS_UNKNOWN` | yes | refresh actor signal |
| 10 | required signal missing | `HOLD` (fail closed) | `SIGNAL_MISSING` | yes | supply the signal |
| 11 | signal stale | `HOLD` (BLOCK by policy) | `SIGNAL_STALE` | yes | refresh signal |
| 12 | signal untrusted | `BLOCK` | `SIGNAL_UNTRUSTED` | no | fix provenance/integrity |
| 13 | policy version rejected | `BLOCK` | `POLICY_VERSION_REJECTED` | no | re-authorize under current policy |
| 14 | prior consumption recorded | `BLOCK` | `ALREADY_CONSUMED` | no | none (already executed) |
| 15 | target temporarily unavailable | `HOLD` | `TARGET_UNAVAILABLE` | yes | retry when available |
| 16 | conflicting signals | `ESCALATE` (BLOCK by policy) | `SIGNAL_CONFLICT` | no | human resolves |
| 17 | clearance validity shortened by signal expiry | `CLEAR` | `CLEARANCE_GRANTED` | n/a | dispatch before the (shortened) `valid_until` |
| 18 | caller retries identical request | *same as first* | identical `result_fingerprint` | n/a | idempotent |
| 19 | reason-code order varies in input | *unchanged* | identical `result_fingerprint` | n/a | order-independent |
| 20 | attempt to widen authorization permissions | `ESCALATE`/`BLOCK` | `CONSTRAINT_CONFLICT` | no | cannot widen; re-authorize if needed |
| 21 | new head SHA | `BLOCK` | `GITHUB_HEAD_SHA_CHANGED` | no | new authorization + clearance |
| 22 | regenerated merge group | `BLOCK` | `GITHUB_MERGE_GROUP_MISMATCH` | no | clear the new merge-group artifact |
| 23 | clearance expired before dispatch | *dispatch prohibited* | `EXPIRED` receipt state | no (fresh clearance) | re-evaluate |
| 24 | two concurrent dispatches | one reserves, one `DUPLICATE` | `DISPATCH_DUPLICATE` (ledger) | no | ledger arbitrates |
| 25 | upstream authorization superseded | *old clearance unusable* | `REVOKED_BY_UPSTREAM_CHANGE` | no | re-authorize + fresh clearance |

## Notes

- **Scenario 2** is an *error*, not a result: an ActionGate denial is never presented as a clearable
  authorization; the request is malformed (`NON_RETRYABLE_ERROR`).
- **Scenarios 18/19** are the determinism guarantees: identical request → identical `result_fingerprint`,
  independent of reason-code input order (reason codes are canonically ordered before fingerprinting).
- **Scenarios 20/21/22** are the monotonicity/identity guarantees: no widening; any action-identity or
  merge-group change requires a new clearance.
- **Scenarios 23/24/25** are execution/ledger-boundary guarantees: expiry, one-time-use race, and
  supersession are enforced at the execution boundary and the receipt state, not by the pure evaluator.
