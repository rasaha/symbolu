# Ugence Governed Review

**Binds a human approval to a parked governed proposal and consumes it exactly once
before the durable engine advances.** GAS-7, step HR-A, under owner rulings HR-1 to
HR-5 (`docs/architecture/ADR_UGENCE_HUMAN_REVIEW_DURABLE_RESUME_SCOPING.md`).

    THIS PACKAGE BINDS AND CONSUMES AN APPROVAL.
    IT NEVER APPROVES, AUTHENTICATES, MINTS AUTHORITY, SIGNALS, RESUMES OR EXECUTES.

## Maturity — read this before citing the package

`REFERENCE_GRADE_SHADOW_ONLY`, `ENFORCEMENT_ENABLED = False`. The approval ledger and
the authority directory it composes carry the same label; the runtime it feeds
invokes fixture providers; no credential broker or IdP integration exists, so a
recorded approver is a presented reference, not a proven identity. Nothing here is
pilot-validated or production-certified, and the ADR's ceiling for the whole GAS-7
sequence is exactly this label.

## What it is

One class, `ApprovalBoundInputSource`, satisfying Agent Runtime governance's
`GovernanceInputSource` protocol. It wraps a deployment's real input source and looks
at one thing: whether the Decision Authority result is a HOLD carrying
`required_approvals`. That, and only that, is what the governance hook projects to
ESCALATE and what a human may review (HR-5). Every other result passes through
untouched.

For an ESCALATE-bound proposal, in order:

1. derive the approval identity from the proposal fingerprint (HR-3):
   `subject_kind = "agent_runtime_proposal"`, `subject_digest = <fingerprint>`,
   `consumer_ref = "<instance_id>:<task_id>"`;
2. if no approval exists, raise the request in the ledger and present it for
   decision; return the inputs unchanged, so the instance parks and the queue now
   shows why;
3. if an approval is GRANTED, consume it under the per-instance, per-task
   consumption key; a first consumption, or an `ALREADY_CONSUMED` whose holder is
   this same instance and task, satisfies the obligation; anything else does not;
4. when satisfied, return the inputs with the Decision Authority result changed to
   `NO_VETO` and its `required_approvals` emptied, reason code
   `GR_APPROVAL_CONSUMED:<approval_id>`. Every other restriction the authority
   contributed stays as tightening as it was. Composition, projection,
   `validate_clearance` and the RA-6 last-mile recheck then run unchanged.

Consumption happens in the SQLite ledger before the engine's Postgres transaction
commits. A crash between the two leaves a CONSUMED approval whose holder names this
instance; the re-drive resolves `ALREADY_CONSUMED` with that holder and is satisfied.
The approval is used exactly once and the action runs exactly once.

## What it is not

No queue listing surface, no decision route, no screen, no signal, no resume. Those
are HR-C and HR-D. It does not change the DBOS adapter's resume shape (HR-B) and it
does not link receipts (HR-E). It reads no clock: every instant comes from the
injected `clock`, which a composition root supplies from the runtime's own time base.

## Evidence

`tests/test_binding.py` — the binding against the real SQLite ledger: pass-through
for CLEAR, DENY and a HOLD without labels; request on park; consume on grant; one
consumption event across re-drives; another instance cannot use a consumed approval;
rejected, expired and wrong-approver cases; clock discipline.

`tests/test_matrix_rows.py` — failure-matrix rows 2, 3, 6, 8 and 10 of the ADR,
inside the real DBOS adapter against a real PostgreSQL, with the real ledger: a
changed subject never reuses a standing decision; an expired approval is refused and
the instance stays parked; an approval for one instance does not resume another; a
process that consumes and is SIGKILLed before advancing is followed by exactly one
run; a revocation after approval still blocks at the last mile with the approval
consumed. CI runs them on a runner-hosted PostgreSQL 16 and fails if any row skips.

`tests/test_boundaries.py` — the import set, no clock, no capability package, no
network, no credential, no LIVE mode, no surface that could approve, signal, resume or
execute, and that the only field a consumed approval changes is the Decision
Authority veto and its label set.

## Dependencies

`ugence-approval-workflow`, `ugence-authority-directory`,
`ugence-agent-runtime-governance`, `ugence-risk-authority-runtime`,
`ugence-governance-contracts`, and the standard library. `ugence-durable-execution`
and `ugence-agent-runtime` are test dependencies only: the rows run the source inside
the adapter, the source never imports it. Nothing under `packages/capabilities`.

## Known gaps `[G]`

- `required_approvals` labels are opaque; this release maps every label to one
  configured `required_role`. A per-label resolver waits on the authority directory's
  deferred label vocabulary (its D-2).
- A request that nobody decides within its window expires in the ledger and is not
  re-requested automatically; the instance stays parked until a new ordinal is raised
  by a later step.
- `decided_by` is what the caller of the ledger presented. Identity proof is the
  review service's IdP session, which does not exist yet (HR-C).
- The adapter's `resume` drains the whole workflow inside one durable step; the rows
  here observe that and do not depend on it. Bounding it is HR-B.
