# Ugence Governed Review Service

**Lists the review queue, renders a run, and records a human's decision, then re-arms
the instance it binds to.** GAS-7, step HR-C, under owner rulings HR-1 to HR-5
(`docs/architecture/ADR_UGENCE_HUMAN_REVIEW_DURABLE_RESUME_SCOPING.md`), with the
routes the screen/API audit proposed
(`apps/ugence-governance-studio/docs/HUMAN_REVIEW_SCREEN_API_AUDIT.md`).

    THIS SERVICE RECORDS A DECISION A HUMAN ALREADY MADE.
    IT NEVER APPROVES, AUTHENTICATES, MINTS AUTHORITY, CLEARS OR EXECUTES.

## Maturity — read this before citing the package

`REFERENCE_GRADE_SHADOW_ONLY`, `ENFORCEMENT_ENABLED = False`, `IDENTITY_PROOF =
"PRESENTED_UNPROVEN"`. The approver on every decision is a reference the caller
presented. No identity provider integration exists, so nothing here proves who decided;
the ledger's eligibility port, answered by the authority directory, decides only whether
that reference *may* decide. Every decision feeds a runtime that invokes fixture
providers. Nothing is pilot-validated or production-certified.

## What it does

One class, `ReviewService`, over four seams a composition root supplies: the approval
ledger (`ApprovalWorkflowPort`), the DBOS adapter (`signal`, `resume`, `status`), a
read-only `RunReader` over the adapter's tables (`DbosRunReader`), and an injected
tz-aware clock. Optionally the directory's eligibility adapter, to show who may decide.

- `list_queue(required_role="")` — every open approval whose subject is a governed
  proposal (HR-3), joined to the instance's durable checkpoint: instance, task,
  fingerprint, workflow and task status, provider and operation, disposition, eligible
  approvers. A parked HOLD is never listed, even if something raised a request for it
  (HR-5).
- `read_run`, `read_run_events`, `read_approval` — the checkpoint view, the engine's
  neutral status, the full event log with attempt tokens and `EXTERNAL_SIGNAL:*` rows,
  the approval record and its hash-linked event chain.
- `submit_decision(approval_id, decision, presented_approver, justification)` — in
  order: the refusals that change nothing (unknown, not a proposal, not open, already
  decided); the ledger's own `decide`, one SQLite transaction, refused by the
  eligibility port before any record changes; then the adapter's `signal`
  (`EXTERNAL_SIGNAL:review_decision`, data, granting nothing) and, for a GRANT, the
  adapter's bounded `resume` for that instance only. A REJECT is signalled and leaves
  the instance parked.

**Re-arming is not permission.** Since HR-B the adapter's `resume` runs nothing: it
re-arms the parked instance and stops. Whether the instance proceeds is decided inside
its next quantum, where `ugence_governed_review`'s input source consumes the GRANTED
approval exactly once against the proposal fingerprint, and composition, projection,
`validate_clearance` and the RA-6 last-mile recheck run unchanged. A decision the
ledger refused delivers nothing. The service exposes no resume, release or continue of
its own, and takes no approver or evidence into the adapter call.

**Duplicate decisions (row 1).** An identical resubmission — same approval, same
presented approver, same outcome — is answered `REPLAYED` with the standing record and
re-delivers the signal and, if the instance is still parked, the resume. Any other
second decision is `REFUSED_ALREADY_DECIDED`; the first stands.

## HTTP

`build_app(service)` returns a FastAPI application (the `http` extra, imported inside
that function only) with exactly the five audited routes:

| Route | operationId |
|---|---|
| `GET /review/queue` | `review_list_queue` |
| `GET /review/runs/{instance_id}` | `review_read_run` |
| `GET /review/runs/{instance_id}/events` | `review_read_run_events` |
| `GET /review/approvals/{approval_id}` | `review_read_approval` |
| `POST /review/decisions` | `review_submit_decision` |

No path or operation id carries an SD-2 verb. The decision body is
`{approval_id, decision: "GRANT"|"REJECT", presented_approver: {approver_id,
approver_kind, role, authority_reference}, justification}`; the answer is the typed
outcome, 200 when recorded or replayed, 409 with the reason and the standing record when
refused, 422 when malformed. A deployment that fronts this app with an identity provider
replaces the body's approver with the session principal in its own composition root.

## Evidence

`tests/test_service.py` — over the real SQLite ledger and an adapter double: rows 1 and
5 of the ADR matrix, every refusal, HR-5 filtering, run detail, clock discipline.

`tests/test_matrix_rows.py` — rows 7, 8 and 9 (and 5) inside the real DBOS adapter
against a real PostgreSQL, with the real ledger and the real approval-bound source in
the hook: a process SIGKILLed before decision persistence records nothing and leaves
the queue unchanged; one SIGKILLed after it is replayed by the next identical
submission and resumes exactly once with one invocation; two submissions for one
decision record two signal rows, one resume, one resumed evaluation, one invocation.
CI runs them on a runner-hosted PostgreSQL 16 and fails if any row skips.

`tests/test_http.py` — the OpenAPI surface is exactly the five routes; relay, refusal
and malformed bodies.

`tests/test_boundaries.py` — the import set, no clock, no capability package, no
identity provider, credential, network or LIVE token, no prohibited verb in any route,
no surface that could approve, authenticate, clear or execute, and that every adapter
call names the instance the approval binds to and nothing else.

## Dependencies

`ugence-governed-review`, `ugence-approval-workflow`, `ugence-authority-directory`,
`ugence-durable-execution`, `ugence-governance-contracts`, SQLAlchemy. `fastapi` and
`starlette` are the `http` extra. `ugence-agent-runtime` and
`ugence-agent-runtime-governance` are test dependencies only. Nothing under
`packages/capabilities`.

## Known gaps `[G]`

- No identity provider: `decided_by` is what the caller presented. The eligibility
  port bounds who may decide; nothing proves who did.
- Requests that expire undecided are not re-requested; the instance stays parked until
  a later step raises a new ordinal.
- `required_approvals` labels are mapped to one configured role by the binding
  (governed-review's own gap).
- The queue joins ledger and checkpoint by the `instance:task` reference; there is no
  single audit artifact joining proposal, approval, consumption and resumed evaluation
  (HR-E).
- No screen: HR-D.
