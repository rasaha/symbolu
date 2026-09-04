# Ugence execution reservation — scoping record and ratification

**Status:** ratified 2026-09-04 by the repository owner. Scoping only: no package
exists yet, and this record amends no package ADR, port, test or manifest.
Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 1,
Action Clearance phases E and G). Builds on the prerequisites design under
`Project_documentation/repository/docs/design/action_clearance_prerequisites/` and
its machine-readable schemas under `docs/design/action_clearance_prerequisites/`,
reopening none of their closed decisions.

## The question

Is the execution ledger a new package or an extension of the Decision Authority
execution ledger? **Both, in one specific way.** It is a new integration package
whose single durable adapter is the backend of the Decision Authority's existing
execution ledger plus the reservation and receipt tables that ledger lacks. That
preserves the Risk Authority invariant that no third canonical execution ledger
exists (`packages/integration/risk-authority-execution-assurance/.../reconciler.py:18`,
`risk-authority-runtime-assurance/.../observer.py:5`) and leaves Decision
Authority 1.0.0 untouched.

## What the prerequisites design already fixed `[V]`

| Item | Where |
|---|---|
| Execution key = (tenant_id, authorization_ref, authorized_action_fingerprint, target_ref, operation), serialized `exec_key.v1:<sha256hex>`; receipt ref deliberately excluded | `EXECUTION_KEY.md`, `execution_key.schema.json` |
| `reserve_once` → ACQUIRED, ALREADY_RESERVED, ALREADY_DISPATCHED, ALREADY_COMPLETED, CONFLICT, INVALID_RECEIPT, EXPIRED_CLEARANCE, STALE_AUTHORIZATION; exactly one ACQUIRED per key under concurrency | `EXECUTION_RESERVATION_CONTRACT.md` |
| Nine reservation states AVAILABLE … RELEASED; OUTCOME_UNCERTAIN never auto-released; RECONCILED_SUCCESS permanent; abandoned RESERVED releasable pre-dispatch only | `EXECUTION_RESERVATION_STATE_MACHINE.md` |
| Eleven validation checks; only the uniqueness insert races, everything else is over the immutable receipt body | same, §Validation |
| `ClearanceReceiptRepository` protocol: put, get, get by fingerprint, list for authorization, supersede, revoke; `PutReceiptResult` CREATED / ALREADY_EXISTS_IDENTICAL / CONFLICT_DIFFERENT_BODY | `RECEIPT_PERSISTENCE_INTERFACE.md` |
| Five receipt lifecycle states; expiry derived at read time; body immutable; lineage tuple for supersession | `RECEIPT_LIFECYCLE.md`, `RECEIPT_SUPERSESSION.md` |
| Failure classes; store outage fails closed and retries the same key | `FAILURE_AND_RETRY_SEMANTICS.md` |
| Acceptance: scenarios 11–18 (receipt persistence), 19–25 (lifecycle), 26–38 (reservation) | `acceptance_scenarios.json` |
| Reuse ruling: Decision Authority `ExecutionRepository` is check-then-act, not atomic; reuse its record model, add reservation beside it | `EXISTING_EXECUTION_REPOSITORY_ASSESSMENT.md` |
| Gate: durable atomic `reserve_once` backend is the sole P0 enforcement blocker (EB-1); durable receipt store is EB-2 | `implementation_gate.json` |

Action Clearance itself forbids `sqlite3`, persistence and `reserve_once`
(`packages/capabilities/action-clearance/docs/dependency_boundary.json`), so the
ledger cannot live there.

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Port placement | **New `ExecutionReservationPort` in the new package; Decision Authority 1.0.0 untouched.** The design's "extend the existing port" is honoured structurally: the one durable adapter also implements Decision Authority's `ExecutionRepository` protocol, so the same object serves the existing interface. Amending that frozen protocol is rejected because a second implementer already exists (`ai_hiring/repositories/execution_repository.py`) and a new required method would break structural conformance. |
| D-2 | Phase E home | **The `ClearanceReceiptRepository` protocol and its durable adapter live in this package.** The Code Governance Workflow Service composes them. `RECEIPT_PERSISTENCE_INTERFACE.md` already admitted a neutral persistence capability as an acceptable generalization; the Workflow Service does not exist as code, and code-governance's own clearance record states it is not an execution receipt (`products/code-governance/.../clearance/records.py:4`). |
| D-3 | Backend | **D-22 Posture B**: single-node durable persistence on stdlib `sqlite3`, WAL, `BEGIN IMMEDIATE` around `INSERT … ON CONFLICT DO NOTHING` on `UNIQUE(tenant_id, execution_key)`, append-only hash-linked event tables copying the shape of `packages/capabilities/storygraph/src/ugence_storygraph/durable_audit.py` and never importing it. Distributed strong consistency stays disclaimed. The in-memory adapter is for tests and is refused when `production_mode` is set. |
| D-4 | Enforcement gate | **Stays closed.** The package ships reference-grade, shadow-only. Enforcement waits on EB-3 (`PRIOR_CONSUMPTION` at trust Level 2, which needs a key service the repository does not have) and EB-4 (reconciliation wiring beyond the Decision Authority reference reconciler). The package emits the consumption signal at Level 1 now. |
| D-5 | First-release scope | **Receipts, reservation and the consumption signal only.** Dispatch and observation wiring (design PR-10), the GitHub execution provider, and the Code Governance enforced merge (PR-11) are excluded. Cloud-scaling Phase 5D is a later second consumer. |

## Package

`packages/integration/execution-reservation`, distribution
`ugence-execution-reservation`, per the one-package-per-phase pattern. Dependencies:
`ugence-decision-authority` (record types, `ExecutionRepository` port; pydantic
transitively), `ugence-governance-contracts>=0.4.0`, `ugence-action-clearance`
(`ClearanceReceiptBody`, `ClearanceResult`, `TrustedSignal`, `ConsumptionStatus`,
all on the curated surface), stdlib `sqlite3`. It imports no product, no cloud SDK,
no network client and no `ugence_storygraph`.

## Port surface

| Port | Phase | Methods |
|---|---|---|
| `ClearanceReceiptRepository` | E | `put_receipt`, `get_receipt`, `get_receipt_by_result_fingerprint`, `list_receipts_for_authorization`, `supersede_receipt`, `revoke_receipt`, `lifecycle_state_at(receipt_id, as_of)` |
| `ExecutionReservationPort` | G | `reserve_once(execution_key, clearance_receipt_ref, expected_authorization_ref, expected_action_fingerprint, reservation_ttl, as_of)`, `mark_dispatched`, `renew_lease`, `record_observation`, `record_reconciliation`, `release` |
| `PriorConsumptionSource` | G | `consumption_signal(execution_key, as_of) -> TrustedSignal` of type `PRIOR_CONSUMPTION` |

One SQLite adapter implements all three plus Decision Authority's
`ExecutionRepository`. Every instant is a caller input; no method reads a clock.
`release` is legal only from an abandoned pre-dispatch `RESERVED` or from
`RECONCILED_FAILURE`; from `DISPATCHED` or `OUTCOME_UNCERTAIN` it is a typed
refusal.

Receipt integrity is verified through the public surface: the adapter rebuilds a
`ClearanceResult` from the stored body and compares its `result_fingerprint`
property to the `receipt_id`, so no private fingerprint helper is imported.

## Consumption signal mapping `[I]`

| Reservation state | `ConsumptionStatus` |
|---|---|
| no row, AVAILABLE, RELEASED, RECONCILED_FAILURE | UNUSED |
| RESERVED, DISPATCHED, OBSERVED_FAILURE, OUTCOME_UNCERTAIN | RESERVED |
| OBSERVED_SUCCESS, RECONCILED_SUCCESS | CONSUMED |
| store unavailable, CONFLICT | UNKNOWN |

RECONCILED_FAILURE maps to UNUSED because the state machine permits controlled
retry per policy; the evaluator's policy decides whether a RESERVED signal holds
or blocks, and UNKNOWN already fails closed.

## Use of the governance-contracts 0.4.0 families `[I]`

- The execution key stays canonical. Its neutral projection is
  `IdempotencyKey(key=<exec_key string>, scope=GLOBAL, partition=tenant_id)`; that
  key's `canonical_digest()` fills `ExecutionDispatchRequest.idempotency_key`, and
  Decision Authority's `execution_idempotency_key` carries the `exec_key.v1:` string
  as the design specifies.
- A reserve-once result projects to `IdempotencyResolution`: ACQUIRED → FIRST;
  every ALREADY_* → DUPLICATE with `duplicate_of` = the holding reservation id;
  CONFLICT → UNKNOWN. INVALID_RECEIPT, EXPIRED_CLEARANCE and STALE_AUTHORIZATION
  are refusals, not resolutions.
- Receipt expiry is `Validity(issued_at=evaluated_at, expires_at=valid_until)`; its
  half-open window is exactly the design's boundary-at-expiry rule (scenario 20).
  The reservation lease is `Validity(issued_at=created_at,
  expires_at=created_at + reservation_ttl)`; the dispatch deadline is a separate
  `Validity` whose expiry moves DISPATCHED to OUTCOME_UNCERTAIN.

## Gaps that survive this package `[G]`

- No Workflow Service exists as code; receipt lifecycle detection of upstream
  events (`UPSTREAM_INVALIDATION_EVENTS.md`) remains a Code Governance deliverable.
- No key service, so Level 2 consumption signals and therefore enforcement remain
  blocked (EB-3).
- Reconciliation wiring beyond the reference reconciler is unbuilt (EB-4).
- The trust-anchor and signer posture (DD-10b) is unresolved platform-wide; this
  package signs nothing.

## Acceptance binding

Prerequisites scenarios 11–18 and 26–38 run against the SQLite adapter, including a
multi-process test proving exactly one ACQUIRED. Scenarios 19–25 run for the
derived lifecycle reads the package owns; event *detection* stays with the
Workflow Service. The Decision Authority conformance suite runs unchanged against
the adapter as an `ExecutionRepository`.

One prohibition: the package never dispatches, observes an external system, or
mints authority; CLEAR plus ACQUIRED is still not execution.

## Next step

Implement `packages/integration/execution-reservation` under the decisions above.
