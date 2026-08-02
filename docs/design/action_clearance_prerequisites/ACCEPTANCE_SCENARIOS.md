# Acceptance Scenarios (Prerequisite Closure)

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Deterministic scenarios for all four
prerequisites. Each row: input → expected result, owner, persistence effect, retry behavior, security
property proven. Machine-readable: `acceptance_scenarios.json`. These are **design scenarios**, not
executed tests (no runtime package exists).

## A — Signal provenance (Prerequisite A)

| # | Input | Expected result | Owner | Persistence effect | Retry | Security property |
|---|---|---|---|---|---|---|
| 1 | approved adapter + valid digest | **trusted** → evaluate | evaluator | none (core) | n/a | trusted-ingestion admits only approved sources |
| 2 | unknown adapter/source | `SIGNAL_UNTRUSTED → BLOCK` | evaluator | none | no | forged source rejected |
| 3 | unapproved adapter version | `SIGNAL_UNTRUSTED → BLOCK` | evaluator | none | no | version pinning enforced |
| 4 | digest mismatch | `SIGNAL_UNTRUSTED → BLOCK` | evaluator | none | no | payload tamper detected |
| 5 | tenant mismatch | `TENANT_MISMATCH → BLOCK` | evaluator | none | no | cross-tenant substitution blocked |
| 6 | stale signal (past `valid_until`) | `SIGNAL_STALE → HOLD` (BLOCK by policy) | evaluator | none | yes (refresh) | stale replay blocked |
| 7 | missing provenance on required signal | **fail closed** `SIGNAL_UNTRUSTED`/`SIGNAL_MISSING` | evaluator | none | no | missing trust evidence fails closed |
| 8 | conflicting authoritative signals | `SIGNAL_CONFLICT → ESCALATE` | evaluator | none | no | no averaging of contradictions |
| 9 | identical signal replayed | same `signal_content_fingerprint` | evaluator | none | n/a | determinism; dedup |
| 10 | bundle omits a signal | different `signal_bundle_fingerprint` + `SIGNAL_MISSING → HOLD` | evaluator | none | yes | truncation detected |

## B — Receipt persistence (Prerequisite B)

| # | Input | Expected result | Owner | Persistence effect | Retry | Security property |
|---|---|---|---|---|---|---|
| 11 | first `put_receipt` | `CREATED` | Workflow Service | receipt row written (immutable body) | n/a | durable evidence created |
| 12 | identical `put_receipt` repeated | `ALREADY_EXISTS_IDENTICAL`, same `receipt_id` | Workflow Service | no new row | idempotent | content-addressed idempotency |
| 13 | same `receipt_id`, different body | `CONFLICT_DIFFERENT_BODY` | Workflow Service | no write | no | id collision / tamper rejected |
| 14 | attempt to mutate receipt body | rejected | Workflow Service | none | no | immutability |
| 15 | retrieval of stored receipt | byte-identical content | Workflow Service | read | n/a | exact-content preservation |
| 16 | referenced signal missing at reconstruction | `CLEARANCE_CHAIN_INCOMPLETE` | execution boundary | none | fail closed (enforced) | chain completeness |
| 17 | supersession | `SUPERSEDED` event links old→new; both bodies immutable | Workflow Service | append event | n/a | atomic lineage |
| 18 | revocation | `REVOKED` event; original body unchanged | Workflow Service | append event | n/a | no body rewrite |

## C — Receipt lifecycle (Prerequisite C)

| # | Input | Expected result | Owner | Persistence effect | Retry | Security property |
|---|---|---|---|---|---|---|
| 19 | issued receipt, before expiry, `CLEAR` | executable | Workflow Service | none | n/a | valid clearance executable |
| 20 | exact expiry boundary (`t == valid_until`) | **non-executable** (expired) | execution boundary | derived `EXPIRED` | fresh request | boundary-at-expiry = expired |
| 21 | upstream authorization superseded | receipt `INVALIDATED`/`REVOKED` | Workflow Service | append event | reauthorize | upstream invalidation |
| 22 | fresher clearance for same lineage | earlier receipt `SUPERSEDED` | Workflow Service | append event | use successor | supersession |
| 23 | changed action fingerprint | **new lineage**, not supersession | Workflow Service | new lineage | new clearance | no silent replacement |
| 24 | active freeze after issuance | prior receipt unusable while freeze active | Workflow Service / evaluator | hold | re-evaluate later | freeze respected |
| 25 | lifecycle event ordering | deterministic (sequence/time ordered) | Workflow Service | ordered events | n/a | deterministic lifecycle |

## D — Atomic reservation (Prerequisite D)

| # | Input | Expected result | Owner | Persistence effect | Retry | Security property |
|---|---|---|---|---|---|---|
| 26 | first `reserve_once(key)` | `ACQUIRED` | execution ledger | reservation row | n/a | reservation acquired |
| 27 | concurrent second `reserve_once(key)` | `ALREADY_RESERVED` | execution ledger | no new row | observe state | **at most one executes** |
| 28 | retry same idempotency key | same reservation (idempotent) | execution ledger | no new row | idempotent | retry-stable key |
| 29 | receipt expired before reservation | `EXPIRED_CLEARANCE` (rejected) | execution boundary | none | fresh clearance | expiry enforced at reservation |
| 30 | action fingerprint mismatch | rejected (`INVALID_RECEIPT`) | execution boundary | none | no | action binding |
| 31 | target mismatch | rejected | execution boundary | none | no | target binding |
| 32 | dispatch timeout | `OUTCOME_UNCERTAIN` | execution boundary | reservation stays | reconcile first | timeout ≠ no-op |
| 33 | uncertain outcome | cannot release before reconciliation | execution ledger | no release | reconcile | no false release |
| 34 | confirmed no-op (`RECONCILED_FAILURE`) | controlled retry permitted | reconciliation | reconciliation record | policy retry | safe retry only after reconcile |
| 35 | confirmed success (`RECONCILED_SUCCESS`) | duplicate execution permanently prevented | reconciliation | terminal | none | one-time-use |
| 36 | duplicate observation | idempotent (no-op) | observation | idempotent write | n/a | duplicate callback safe |
| 37 | out-of-order observation | deterministic; terminal state not downgraded | observation | ordered | n/a | ordering safety |
| 38 | reservation store unavailable | **fail closed** (no dispatch) | execution boundary | none | retry same key | store outage never proceeds |

## Determinism note

Scenarios 9, 10, 25, 28 assert **fingerprint/ordering determinism**; scenarios 27, 33, 35, 38 assert the
**one-time-use / fail-closed** invariants that gate enforcement. All D-scenarios that assert atomicity
(27, 33, 35, 38) depend on the durable atomic backend (enforcement blocker).
