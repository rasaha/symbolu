# ugence-approval-workflow

**Reference-grade, shadow-only, not enforcement-ready.** The canonical human approval
and exception queue: the state machine, derived expiry, the bounded exception path,
and once-only consumption of a granted approval. Scoped and ratified by
`docs/architecture/ADR_UGENCE_APPROVAL_WORKFLOW_SCOPING.md`; sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 2) under its decision
D-2 — approval state lives in Ugence, ServiceNow and Jira are mirrors, and Decision
Authority 1.0.0 stays frozen and consumes the artifact.

> This package records and reports an approval. It **never approves**,
> authenticates, mints authority, or executes. A `GRANTED` approval is an input to a
> governed decision, not a decision.

## What it does and does not own

It owns the queue, the state machine, expiry, the exception path and once-only
consumption. It does **not** own approval *authority* — reserved to Decision
Authority (`packages/capabilities/decision-authority/README.md:22`) — nor the
policy-pack review flow reserved to the Policy Workflow Compiler
(`packages/tooling/policy-workflow-compiler/docs/NEXT_PHASES.md:27`). Neither
package is imported or amended.

## The state machine

```
REQUESTED → PENDING → GRANTED | REJECTED | CHANGES_REQUIRED | EXPIRED | WITHDRAWN
                          ↓
                      CONSUMED                              (exactly once)

PENDING → EXCEPTION_REQUESTED → EXCEPTION_GRANTED | EXCEPTION_DENIED
                                        ↓
                                    CONSUMED                (exactly once)
```

`REQUESTED` is the raised request before an eligible approver set is resolved;
`PENDING` is awaiting decision. Transitions are **forward-only** — each strictly
increases `STATE_RANK` — so any arrival order converges and a decision is never
walked back. `REJECTED`, `CHANGES_REQUIRED`, `EXPIRED`, `WITHDRAWN`,
`EXCEPTION_DENIED` and `CONSUMED` are terminal.

`CHANGES_REQUIRED` is terminal for *that* request. Re-review is a **new** request
bound to the new subject digest, recorded with `supersedes`; resubmitting an
unchanged subject is refused, because a changed subject must never inherit a
standing decision.

## The subject

An approval binds to `(tenant_id, subject_kind, subject_digest)` — a policy pack, a
decision case, a scaling recommendation, anything. `subject_kind` is a free label
recorded and never interpreted; `subject_digest` is the caller's content digest, so
approval binds to substance. The approval id is derived from the subject, the
requester and a request ordinal: no UUID, no clock.

## Expiry

Every window is a `ugence_governance_contracts.contracts.validity.Validity`, and
`state_at(as_of)` **derives** `EXPIRED` at read time from `Validity.status_at(as_of)`.
Nothing is swept, so no background job has to run for a request to lapse, and a read
at an earlier instant still reports what was true then. A lapsed request refuses
every transition. A granted exception carries its own bounded window and expires by
the same rule.

**The package reads no clock** — no `time.time()`, no `datetime.now`, no `utcnow`,
no `uuid4` — and `tests/test_boundaries.py::test_no_clock_is_read_anywhere` asserts
it over the AST of every source file. Every instant is a caller input.

## Who may approve

Eligibility is a **port**, never an identity check:

```python
ApproverEligibilityPort.eligible_approvers(tenant_id, subject_kind, subject_digest,
                                           required_role, as_of) -> tuple[ApproverRef, ...]
ApproverEligibilityPort.is_eligible(tenant_id, approver, required_role,
                                    scope, as_of) -> EligibilityDecision
```

The package authenticates nobody, resolves no directory, holds no credential and
never decides that a principal *is* who they claim. Authentication stays with the
IdP behind Decision Authority's `IdentityProvider`; the wave 2 organizational
authority directory is the intended adapter, and until it exists a composition root
supplies its own. Over whatever the port reports, the package enforces structure: the
approver must be eligible at the decision instant, must hold the required role, may
not be the requester, and must be of a kind that may ever approve — `HUMAN` or
`COMMITTEE`. An AI principal, a service account and a delegated policy are refused.

## Exactly once

Consumption is the only racing decision, so it is one unique insert inside one write
transaction. The consumption key is canonical over `(tenant_id, approval_id,
subject_digest, consumer_ref)`, serialized `approval_key.v1:<sha256hex>`, and
projects neutrally to `IdempotencyKey(key=<serialized>, scope=GLOBAL,
partition=tenant_id)`. `CONSUMED_FIRST` resolves `FIRST`; `ALREADY_CONSUMED` resolves
`DUPLICATE` naming the holder; `UNKNOWN` resolves `UNKNOWN` and fails closed. The
refusals — `NOT_GRANTED`, `EXPIRED_APPROVAL`, `SUBJECT_MISMATCH` — are not
resolutions and project to `None`.

## Two adapters

| Adapter | Store | Posture |
|---|---|---|
| `InMemoryApprovalWorkflowStore` | process-local dict under one lock | tests and local composition; refused in production mode |
| `SqliteApprovalWorkflowStore` | single-node stdlib `sqlite3` | WAL, `BEGIN IMMEDIATE`, `UNIQUE(consumption_key)` with `INSERT … ON CONFLICT DO NOTHING`, one append-only hash-linked `ledger_events` table whose triggers refuse UPDATE and DELETE |

Both call the same pure transition functions in `workflow.py`, so the durable store
and the reference store cannot drift apart; every test in `test_state_machine.py` and
`test_consumption.py` runs against both. The ledger shape is that of
`packages/integration/execution-reservation` — **copied, never imported**.
Distributed strong consistency stays disclaimed (D-22 Posture B): this is
single-node, and a `:memory:` path is refused in production mode because it is not
durable.

The current snapshot in `approvals` is updated in place; the history is the
append-only `ledger_events` chain, and `verify_chain()` recomputes it end to end. A
stored artifact that no longer re-derives its digest is refused on read.

## How the artifact reaches Decision Authority

Decision Authority **1.0.0 is frozen and changes in no class** — not behavioural,
lifecycle, serialization, hash, port, removal or enum. The composition root, not this
package, performs both steps:

1. Where the approval precedes the case, pass
   `VersionedRef(ref_id=<approval_id>, version=<n>, kind="approval")` in `policy_refs`
   to `DecisionCaseService.create_case`. `kind` is a free label the kernel never
   interprets.
2. Where the approval follows, call
   `DecisionCaseService.complete_review(case_id=…, task_id=…, actor=<approver>)` once
   `consume` returns `CONSUMED_FIRST`, clearing the `PENDING` `ReviewTask` the kernel
   already blocks readiness on.

`ReviewTask` has no metadata field, so the binding — decision case id, review task
id, approval id, subject digest, consumption key — lives **here**, in `consumer_ref`
and the consumption row, and is reconstructed by joining on those ids. Putting it in
the kernel would be a serialization change and therefore MAJOR.

```python
outcome = store.consume(approval_id, consumer_ref="decision_case:case_1/review_task:rev_1",
                        subject_digest=digest, as_of=now)
if outcome.is_consumed:
    decision_cases.complete_review(case_id="case_1", task_id="rev_1", actor=approver_id)
```

`tests/integration/test_decision_authority_seam.py` proves this end to end against the
real kernel: a granted approval clears a `SECONDARY_APPROVAL` task and readiness
passes, while a lapsed, already-consumed, ungranted or changed-subject approval
produces no `complete_review` call at all and the case stays blocked on
`REQUIRED_REVIEW_OUTSTANDING`. Those tests are the only place the kernel is imported;
they skip when pydantic is absent, so the default suite stays dependency-free.

## ServiceNow and Jira

Mirrors are **written from the ledger and never read back into it**. A mirror
projects a request or a state change outward as a notification or task; an inbound
webhook, ticket transition or comment is at most an event to be presented to an
eligible approver through this package's own decision call, never itself a state
transition. No mirror may create, grant, deny, extend or consume an approval, and a
mirror outage degrades notification only. **No mirror ships in 0.1.0**, and a
boundary test asserts that none is present.

## Dependencies

`ugence-governance-contracts>=0.4.0` and the standard library, `sqlite3` included.
Nothing else — not Decision Authority, not the Policy Workflow Compiler, not
cloud-scaling-operations, not execution-reservation, not `ugence_storygraph`, no
product, no network client, no cloud SDK, no pydantic. A boundary test asserts the
import set over the AST and the declared dependency list. Composition roots, products
and applications may import this package; no capability package may.

## Gaps that survive this release

- No organizational authority directory exists, so `ApproverEligibilityPort` has no
  production adapter and eligibility is composition-supplied.
- The package signs nothing; `signature_reference` stays a non-secret reference, and
  the platform trust-anchor and custody posture is unresolved.
- The float-clock `ApprovalManager` in cloud-scaling-operations remains in place;
  migrating that domain onto this package is a later, separately scoped change.
- Single-node durability only, no enterprise mirror, no console surface, and no
  end-to-end LIVE test.
