# Human review — screen and API audit (Review Queue, Run Detail)

**Status: implemented by HR-D (2026-09-05).** The two screens, the five v2 relay
routes and the review-service client below now exist, as proposed here and under
HR-1 `DISPLAY_AND_TRANSMIT`: `api/v2/review.py`, `clients/review.py`
(`REVIEW_ALLOWED_ROUTES`, five entries, refused before a socket opens),
`services/studio_v2.py::ReviewRelayService`, `frontend/src/features/studio/ReviewQueueScreen.tsx`
and `RunDetailScreen.tsx`. Evidence: `backend/tests/test_review_relay.py` (the decision
body reaches a real local HTTP stand-in for the review service byte-for-byte; an
unreachable service is a gap; a HOLD is filtered and counted; the client refuses any
route outside the five), `frontend/tests/review-screens.test.tsx`, the a11y suite for
both screens, and the unchanged SD-2 prohibition, console-allowlist, v1 byte-freeze and
frontend verb-scan tests. The text below is the audit as written; where it says a thing
is missing, read it as the state before HR-D. Ruled by
`docs/architecture/ADR_UGENCE_HUMAN_REVIEW_DURABLE_RESUME_SCOPING.md` (HR-1 to HR-5).

Evidence labels: `[V]` verified, `[I]` inferred, `[R]` requires ratification, `[G]` gap.

## The load-bearing constraint

SD-2 (`GOVERNED_AGENT_STUDIO_V1_SCREEN_AUDIT.md`, ruling table): the studio never
issues, activates, revokes, grants, authorizes, clears or executes, enforced by the
operation-id and path prohibition test `[V]`
(`backend/tests/test_v2_operation_ids.py:24-26,41-62`) and the four-route console
allowlist `[V]` (`clients/console.py:34-39`). A review surface must therefore be
**read plus verbatim relay**: it renders what other services hold, and at most
transmits a human's decision to a service that authenticates the human and owns the
record. It never consumes an approval, never signals, never resumes.

## Screen 7 · Review Queue

| | |
|---|---|
| **Shows** | Every parked ESCALATE instance for the tenant: instance id, workflow id, task id, proposal fingerprint, operation and provider, disposition and reason codes, `required_approvals` labels, park time, approval state (`REQUESTED`/`PENDING`/`GRANTED` and so on), and the eligible approver set for the required role. |
| **Source that exists** `[V]` | Approval queue: `ApprovalWorkflowPort.list_open(tenant_id, required_role, as_of)` (`approval-workflow/.../ports.py:61-62`). Eligible set: `ApproverEligibilityPort.eligible_approvers` via the directory adapter (`authority-directory/.../eligibility_adapter.py:116-123`). Instance status: `DbosExecutionAdapter.status(instance_id)` returns known/workflow/digest/write and event counts (`durable-execution/.../dbos_engine.py:337-363`). Parked evaluation: the execution-state journal in the checkpoint carries `governance_disposition`, `evaluation_reference`, `proposal_fingerprint`, `valid_until` (`agent-runtime/.../runtime/execution_state.py:67-84`). |
| **Missing** `[G]` | No join exists between a parked instance and an approval: the approval subject has no instance field (`approval-workflow/.../subject.py:29-52`), and no request is raised when an instance parks. The queue cannot be listed until HR-3's binding (`subject_digest` = proposal fingerprint) and a request-on-park step exist. `required_resolution` is not persisted (`agent-runtime/.../governance/interfaces.py:90`), so "why it parked" must be read from the `TASK_WAITING` event detail, not the checkpoint. No per-approver filtering exists. |
| **Never** | A resume, release, continue, retry or clear control. Under HR-1 (`DISPLAY_AND_TRANSMIT`) a decision control is permitted and relays the human's decision verbatim to the review service. |
| **Gap rendering** | With no review service configured: the standard `GapNotice` naming `review_service`, not an empty queue. An empty queue must be distinguishable from an unreachable one, as Observe already does for the console. |

## Screen 8 · Run Detail

| | |
|---|---|
| **Shows** | One instance: the workflow definition digest, each task's status and attempts, the full event log including `GOVERNANCE_EVALUATION_REQUESTED`, `GOVERNANCE_DISPOSITION_RECEIVED`, `TASK_WAITING`, `WORKFLOW_PAUSED`, `WORKFLOW_RESUMED` and `EXTERNAL_SIGNAL:*` rows, the execution-state journal (fingerprint, disposition, references, `valid_until` per quantum), the approval record and its event chain when one is bound, and the audit chain by correlation id. |
| **Source that exists** `[V]` | Runtime events with attempt tokens: `PostgresRuntimeEventStore.events` and `attempt_tokens` (`durable-execution/.../postgres/stores.py:161-193`). Checkpoint history: `PostgresCheckpointStore.history` (`:113`). Approval record and events: `get_approval`, `approval_events` (`ports.py:57,64`). Audit chain: the existing Observe route `GET /api/v2/observe/audit/{correlation_id}` (`api/v2/observe.py:19`). |
| **Missing** `[G]` | No read surface over the durable stores exists outside the adapter's own `status()`; the store classes are session-provider based and would need a read-only façade in the composition package (HR-2), never a database import in the studio (the architecture test prohibits DB drivers, `backend/tests/test_architecture.py:20-53`). The instance ↔ correlation id ↔ approval id join is by convention only. |
| **Never** | Render a HOLD as awaiting a human (HR-5). Present a pre-park CLEAR as still valid: `valid_until` and the fingerprint are shown as history, never as a live permission. |

## Proposed v2 surface, under SD-1 and SD-2 `[R]`

All read routes are additive to the v2 contract and byte-freeze it anew; v1 stays
byte-identical. Every route delegates to a public entry point of the composition
package from HR-2 and re-implements no governance logic.

| Route | operationId | SD-2 check | Depends on |
|---|---|---|---|
| `GET /api/v2/review/queue` | `v2_review_list_queue` | read; no prohibited verb | HR-2, HR-3 |
| `GET /api/v2/review/runs/{instance_id}` | `v2_review_read_run` | read | HR-2 |
| `GET /api/v2/review/runs/{instance_id}/events` | `v2_review_read_run_events` | read | HR-2 |
| `GET /api/v2/review/approvals/{approval_id}` | `v2_review_read_approval` | read | HR-2 |
| `POST /api/v2/review/decisions` | `v2_review_submit_decision` | relay only; the path and id carry no prohibited verb; the body's `decision` is the human's word, forwarded verbatim; the studio adds no identity and reads no result other than the service's typed answer | HR-1 ruled `DISPLAY_AND_TRANSMIT`: permitted, not yet built |

The prohibition test must keep failing on `grant`, `clear`, `execute` and the rest in
any operation id or path, so no proposed id may be named `…grant…` or `…resume…`; the
decision route is named for the act of submitting, not for its outcome. There is no
`resume`, `release`, `continue` or `signal` route under any ruling: resume is the
composition's consequence of consumption, not a request the studio can make.

**Console client.** The four-route allowlist is unchanged. The review service is a
separate HTTP client with its own explicit allowlist of at most the five routes above,
enforced before a socket opens, exactly as `clients/console.py:95-101` does today.
Authentication of the human is the review service's IdP session. Under owner ruling
ID-1 (`ADR_UGENCE_APPROVER_IDENTITY_SCOPING.md`) the studio may forward one IdP-issued
token that is audience-bound to the review service, and it never parses, logs, persists
or reuses it; it holds no identity of its own.

**SD-1 allowlist additions** `[R]` (the entries themselves await HR-D): the public
entry points of `ugence_governed_review` (HR-2) only. `ugence_approval_workflow`, `ugence_authority_directory` and
`ugence_durable_execution` stay off the studio's allowlist; the last is already a
prohibited import (`test_architecture.py:20-53`).

## Frontend consequences `[I]`

- Two screens under `/studio/review` and `/studio/review/:instanceId`, on the
  existing `ScreenFrame`, `GapNotice` and `Json` primitives; no new dependency.
- `approved-v2-api-operations.json` grows by four or five operations; the
  `verify-v2-api-boundary.mjs` verb scan and the "no raw fetch in a screen" test apply
  unchanged (`tests/studio-security.test.ts:47-79`).
- The a11y suite extends to both screens; the decision form requires a justification
  and shows the approver as reported by the review service, never as typed in the
  browser.
- The maturity flag `human_review_implemented` is `True` as of the HR-D commit and
  asserted by `test_operational.py`; `authentication_implemented` stays `False`, and
  every decision the screens relay is labelled `PRESENTED_UNPROVEN` by the review
  service.

## What is settled, and what is not

HR-1 to HR-5 are ruled (ADR §5): the studio may display and transmit; the composition
is `packages/integration/governed-review`; approvals bind to the proposal fingerprint
and are consumed before the engine advances; resume stays bare in the runtime and
bounded in the adapter; only ESCALATE is reviewable. HR-A to HR-E have shipped: the
screens have their data source (`governed-review-service`) and their routes, and Run
Detail renders the receipt linkages the service returns since its 0.2.0 (HE-5). What is
still not settled is HR-E, the receipt linkage, and an identity provider, which no
step of this sequence builds.
