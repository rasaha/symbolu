# Ugence approval workflow — scoping record and ratification

**Status:** ratified 2026-09-04 by the repository owner. Scoping only: no package
exists yet, and this record amends no package ADR, port, test or manifest.
Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 2, "Human
approval and exception workflow", line 53) under its decision D-2 (line 37):
approval state lives in Ugence, ServiceNow and Jira are mirrors, and Decision
Authority 1.0.0 stays frozen and consumes the artifact.

## The question

Ugence records approvals in three places and runs a workflow in none of them. Is
the workflow a new package, and if so what may it own without taking a noun an
existing README or NEXT_PHASES already reserves? **A new integration package that
owns the queue, the state machine, expiry and the exception path — and never
approval authority.** Approval *authority* is reserved (Decision Authority), and
policy-pack *review flow* is reserved (Policy Workflow Compiler). Neither reserves
routing, expiry, exception, or once-only consumption, so the prohibition in the
sequencing ADR (line 85) is satisfied by scope, not by name alone.

## What the repository already fixed

| Finding | Where |
|---|---|
| `HumanApprovalRecord` carries decision, reviewer id/role, a non-secret authority *reference*, a status-independent pack digest, accepted gap and warning ids, justification, signature reference, `is_fixture` `[V]` | `packages/tooling/policy-workflow-compiler/src/ugence_policy_workflow_compiler/models/approvals.py:26-54` |
| It is a terminal decision, not a workflow: no requested or pending state, no tenant, no quorum, no delegation, no exception, no consumption marker; `approved_at` is "recorded metadata, not policy logic" `[G]` | same, `:40` |
| It addresses only a policy pack, so it cannot name a decision case or a scaling recommendation `[G]` | same, `:31` |
| `ApprovalService` verifies and never approves: pack status, decision, digest binding, reviewer presence, no self-approval `[V]` | `.../approval/service.py:32-59` |
| The compiler's own NEXT_PHASES reserves "governed review / diff approval workflows" — bounded to the pack diff and `HUMAN_APPROVAL.md` `[V]` | `packages/tooling/policy-workflow-compiler/docs/NEXT_PHASES.md:27-34` |
| Decision Authority's README reserves "human/policy approval" ownership and excludes "workflow execution" `[V]` | `packages/capabilities/decision-authority/README.md:22-27` |
| A second, incompatible approval machine already ships: `PENDING → APPROVED / DISMISSED / EXPIRED` on `time.time()`, in-memory, no reviewer authority, no digest `[V]` | `packages/capabilities/cloud-scaling-operations/src/ugence_cloud_scaling_operations/recommend/approval.py:26-31,157` |
| Decision Authority reads no approval artifact today; readiness blocks only on a `PENDING` `ReviewTask` `[V]` | `.../services/case_validation_service.py:32,152-159` |
| `reserve_once` validates a `ClearanceReceipt` specifically, so an approval cannot be reserved through the execution ledger `[V]` | `packages/integration/execution-reservation/src/ugence_execution_reservation/reservation.py:258-299` |
| What is reusable is the ledger *shape*: canonical key → `IdempotencyKey` projection, the single racing head insert, the append-only hash-linked SQLite tables `[V]` | `.../execution_key.py:33-75`; `packages/integration/execution-reservation/README.md` |
| `Validity.status_at(as_of)` is the expiry primitive; every instant is a caller input `[V]` | `packages/governance-contracts/src/ugence_governance_contracts/contracts/validity.py:123-196` |

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Package and home | **`packages/integration/approval-workflow`, distribution `ugence-approval-workflow`.** It composes contracts with a durable store and is not a domain capability, so it belongs beside the other integration packages, not under `capabilities/`. |
| D-2 | Exception path | **A bounded, time-boxed exception grant, never an open one.** `EXCEPTION_GRANTED` carries its own `Validity` and expires by the same rule as an approval; an exception is a recorded, scoped deviation with a stated justification, not a waiver of the approval requirement and not a second approval route. |
| D-3 | Record shape | **Re-shaped generically inside this package; the compiler's record is untouched.** The workflow's artifact binds to a neutral `(tenant_id, subject_kind, subject_digest)` instead of `policy_pack_id`, and carries the compiler record's proven fields — reviewer id and role, authority reference, digest binding, accepted findings, justification, signature reference, `is_fixture`. `ugence_policy_workflow_compiler` is neither imported nor amended, and its `HumanApprovalRecord` keeps its pack-bound meaning. |
| D-4 | Backend in 0.1.0 | **Both adapters, following the execution-reservation precedent**: an in-memory reference store refused when `production_mode` is set, and a single-node stdlib `sqlite3` store (WAL, `BEGIN IMMEDIATE`, unique head per consumption key, one append-only hash-linked events table whose UPDATE and DELETE triggers refuse). Shipping the shape later would let a non-atomic consumption path harden first. Distributed consistency stays disclaimed. |
| D-5 | Decision Authority seam | **`DecisionCaseService.complete_review` plus `VersionedRef(kind="approval")`; Decision Authority 1.0.0 changes in no class** — not behavioural, lifecycle, serialization, hash, port, removal or enum (`.../version.py:60-76`). |

## The state machine

```
REQUESTED → PENDING → GRANTED | REJECTED | CHANGES_REQUIRED | EXPIRED | WITHDRAWN
                                   ↓
                               CONSUMED            (exactly once)

PENDING → EXCEPTION_REQUESTED → EXCEPTION_GRANTED | EXCEPTION_DENIED
                                        ↓
                                    CONSUMED       (exactly once)
```

`REQUESTED` is the raised request before an eligible approver set is resolved;
`PENDING` is awaiting decision. Transitions are forward-only, so any arrival order
converges. `CHANGES_REQUIRED` returns to `REQUESTED` only as a **new** request bound
to the new subject digest — a changed subject never reuses a standing decision, the
digest-binding rule the compiler already enforces (`approval/service.py:52-54`).
`REJECTED`, `EXCEPTION_DENIED`, `EXPIRED`, `WITHDRAWN` and `CONSUMED` are terminal.
`EXPIRED` is derived at read time from `Validity`, never written by a sweeper.

`GRANTED → CONSUMED` is the only racing decision and happens inside one write
transaction, as the head insert does in the execution ledger. The consumption key is
canonical over `(tenant_id, approval_id, subject_digest, consumer_ref)`, serialized
`approval_key.v1:<sha256hex>`, and projects neutrally to
`IdempotencyKey(key=<serialized>, scope=GLOBAL, partition=tenant_id)` `[I]`. A first
consumption resolves `FIRST`; a repeat resolves `DUPLICATE` naming the holding
consumption; a store fault resolves `UNKNOWN` and fails closed. A `GRANTED` approval
whose `Validity` has expired at the caller's `as_of` is refused, not consumed.

## Expiry and the clock

Every expiry is `ugence_governance_contracts.contracts.validity.Validity` evaluated
by `status_at(as_of)` with a caller-supplied, timezone-aware instant: the approval
request's own window, the exception grant's window, and the reviewer-assignment
lease. `NOT_YET_VALID` and `EXPIRED` are refusals; `STALE` is reportable and does not
by itself refuse. **The package reads no clock** — no `time.time()`, no
`datetime.now`, no `utcnow` — and a test asserts it over the AST of every source
file, as `test_no_clock_is_read_anywhere` does at
`packages/integration/execution-reservation/tests/test_boundaries.py:68`. This is
also what separates the canonical machine from the float-clock one already in
cloud-scaling-operations, which this package neither imports nor replaces in place.

## Who may approve

Eligibility is a port, never an identity check:

```
ApproverEligibilityPort.eligible_approvers(tenant_id, subject_kind, subject_digest,
                                           required_role, as_of) -> tuple[ApproverRef, ...]
ApproverEligibilityPort.is_eligible(tenant_id, approver_ref, required_role,
                                    scope, as_of) -> EligibilityDecision
```

The package never authenticates anyone, never resolves a directory, never holds a
credential and never decides that a principal *is* who they claim. Authentication
stays with the IdP behind Decision Authority's `IdentityProvider`
(`.../identity/provider.py:24-32`); the wave 2 organizational authority directory is
the intended adapter, and until it exists a composition root supplies its own. The
package enforces only structural rules over what the port returns: an approver must
be eligible at the decision instant, the requester may not be the sole approver, and
an AI principal may never appear as an approver — the same no-self-approval shape the
compiler applies to `COMPILER_PRINCIPAL` (`approval/records.py:15-17`).

## Dependencies

`ugence-governance-contracts>=0.4.0` (`Validity`, `ValidityStatus`, `IdempotencyKey`,
`IdempotencyResolution`) and the Python standard library, `sqlite3` included. Nothing
else: not Decision Authority, not the Policy Workflow Compiler, not
cloud-scaling-operations, not execution-reservation, not `ugence_storygraph`, no
product, no network client, no cloud SDK, no pydantic. The ledger shape is **copied
from** `packages/integration/execution-reservation`, never imported — the same
relationship that package has to the storygraph durable audit log. A boundary test
asserts the import set over the AST and the pyproject dependency list.

**What may import it:** composition roots, products and applications. No capability
package may import it, and Decision Authority must keep importing no Ugence package
at all (`packages/capabilities/decision-authority/README.md:59-61`).

## How the artifact reaches Decision Authority

Decision Authority is frozen and is not amended. The composition root, not this
package, performs both steps `[V]`:

1. Where the approval precedes the case, `create_case(..., policy_refs=(...
   VersionedRef(ref_id=<approval_id>, version=<n>, kind="approval") ...))`. `kind` is
   a free label the kernel never interprets (`.../decisions/subject.py:33-34`) and
   `policy_refs` is caller-supplied (`.../services/decision_case_service.py:95`).
2. Where the approval follows, the root calls
   `DecisionCaseService.complete_review(case_id=…, task_id=…, actor=<approver>)` once
   the approval reaches `GRANTED` (`.../services/decision_case_service.py:181-194`).
   That clears the `PENDING` `ReviewTask` the kernel already blocks readiness on
   (`.../services/case_validation_service.py:152-159`).

`[G]` `ReviewTask` has no metadata field and `complete_review`'s audit metadata is
fixed (`.../services/decision_case_service.py:191-193`), so Decision Authority has
nowhere to hold an approval digest after case creation. The binding — decision case
id, task id, approval id, subject digest, consumption key — therefore lives in this
package's ledger and is reconstructed by joining on those ids. Moving it into the
kernel would be a serialization change and therefore MAJOR; it is not proposed.

## ServiceNow and Jira

Adapters are **mirrors, written from the ledger, never read back into it**. A mirror
projects a request or a state change outward as a notification or task; an inbound
webhook, ticket transition or comment is at most an *event to be presented to an
eligible approver through this package's own decision call*, and never itself a state
transition. No mirror may create, grant, deny, extend or consume an approval; a
mirror outage degrades notification only and never blocks or advances the record.
Mirrors ship as separate integration packages, not in 0.1.0.

## Gaps that survive this package `[G]`

- No organizational authority directory exists, so `ApproverEligibilityPort` has no
  production adapter and eligibility is composition-supplied.
- The package signs nothing; `signature_reference` stays a non-secret reference, and
  the platform trust-anchor and custody posture (DD-10b) is still unresolved.
- The float-clock `ApprovalManager` in cloud-scaling-operations remains in place;
  migrating that domain onto this package is a later, separately scoped change.
- Single-node durability only; distributed consistency stays disclaimed, as under
  D-22 Posture B.
- No enterprise mirror, no console surface, and no end-to-end LIVE test.

One prohibition: the package never approves, never authenticates, never mints
authority and never executes. A `GRANTED` approval is an input to a governed
decision, not a decision.

## Next step

Implement `packages/integration/approval-workflow` 0.1.0 under the decisions above.
