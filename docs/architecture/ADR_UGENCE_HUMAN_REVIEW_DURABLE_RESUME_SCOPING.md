# Ugence human review and durable resume — scoping record

**Status: SCOPED AND RULED — nothing here is implemented.** The five owner decisions
in §5 were ruled on 2026-09-05. This record still authorizes no code change, adds no
dependency, opens no route and ships no package: each step of §6 is entered only by
its own implementation prompt. It maps the path a
parked governed workflow would have to travel to be seen by a human, decided, and
resumed under fresh governance, states what already exists on that path, and records
the five owner decisions. It reopens none of: DBOS ratified as the initial engine (OD-3),
Langflow deferred (GAS-5), Temporal gated (GAS-6), SD-1, SD-2.

Evidence labels: `[V]` verified against this repository at the merge of PR #1611,
`[I]` inferred, `[R]` requires owner ratification, `[G]` gap.

## 1 — The question

Every restrictive governance outcome already parks a workflow durably and refuses to
let it move. **Where does a human see it, decide, and have that decision reach the
next governance evaluation — without any surface minting authority?** Today: nowhere.
The runtime, the durable engine, the governance hook, the approval ledger and the
authority directory each do their part correctly, and no code joins them. The
governance package says so itself: "HOLD, DEFER, ESCALATE and MANUAL_REVIEW still have
no sink" `[V]` (`packages/integration/agent-runtime-governance/src/ugence_agent_runtime_governance/__init__.py:76-80`;
`packages/integration/durable-execution/README.md:197-199`).

## 2 — The path, stage by stage

| # | Stage | What exists `[V]` | What is missing `[G]` |
|---|---|---|---|
| 1 | **Disposition** | `FinalDisposition` has four members: GRANT, DENY, HOLD_NON_EXECUTABLE, ERROR_NON_EXECUTABLE (`risk-authority-runtime/.../contracts.py:78-88`). Decision Authority `DEFER` becomes veto `HOLD` before composition (`decision_authority_adapter.py:64,69`; `composition.py:157-162`). `MANUAL_REVIEW` exists nowhere as code. | No `MANUAL_REVIEW` disposition. Whether one is needed is answered by HR-5, not by adding an enum member. |
| 2 | **Projection** | `HOLD_NON_EXECUTABLE` + non-empty `required_approvals` → ESCALATE with `required_resolution="EXTERNAL_APPROVAL"`; otherwise HOLD with `"GOVERNANCE_HOLD_RELEASE"` (`agent-runtime-governance/.../dispositions.py:117-120`; `hook.py:354-360`). `required_approvals` is a `frozenset[str]` of opaque labels combined by union only; its sole consumer is a truthiness test (`dispositions.py:76`). | Labels are never compared to an approver, never satisfied, never emptied. Their vocabulary is unratified; the authority directory deferred its resolver to 0.2.0 (`ADR_UGENCE_AUTHORITY_DIRECTORY_SCOPING.md` D-2). |
| 3 | **Parked state** | HOLD → task WAITING, workflow WAITING, reason `governance_hold`; ESCALATE → task WAITING, workflow PAUSED, reason `governance_escalate` (`agent-runtime/.../runtime/engine.py:519-535`). `advance_workflow` on a parked instance is a no-op `REQUIRES_RESUME` (`:373-380`). | `required_resolution` is a free `Optional[str]` the runtime never stores, exposes or checks (`governance/interfaces.py:90,111`; absent from `runtime/execution_state.py:72-84` and every checkpoint field). The park reason lives only in the event detail, not the checkpoint (`persistence/checkpoints.py:114-126`). |
| 4 | **Durability** | The parked checkpoint and its execution-state journal persist in `ugence_art.runtime_state` on the DBOS application database in one transaction with the step record (OD-1). Recovery restores WAITING as WAITING and RUNNING as PAUSED (`persistence/recovery.py:146-169`). Matrix row 9 proves a parked instance never progresses across six re-drives and invokes nothing (`durable-execution/tests/test_matrix.py:719-767`). | Row 9 never calls `resume`; its "post-resume" fingerprint assertion (`:769-773`) compares the single pre-signal evaluation to itself. The park → decision → resume → re-evaluation round trip is proven only for crash recovery (`_dbos_harness.py:241-253`, row 1), not for a human decision. |
| 5 | **Approval ledger** | `ugence_approval_workflow` 0.1.0: eleven states, forward-only, `EXPIRED` derived at read time, exactly-once `GRANTED → CONSUMED` under a canonical consumption key, duplicate decision refused with `IllegalTransitionError`, `list_open` queue read, decision record with `decided_by/decided_role/decided_authority_reference/decided_at/justification` (`states.py:38-97`; `consumption.py:39-95`; `workflow.py:85-95`; `ports.py:61-62`; `records.py:52-83`). SQLite Posture B store, 12-way concurrency proven (`tests/test_concurrency.py`). Maturity `REFERENCE_GRADE_SHADOW_ONLY` (`version.py:9-17`). | Imported by nothing on this path; boundary tests in three packages assert it is *not* imported. `ApprovalSubject` has no action, run or instance field — binding to a proposal is by `subject_digest` only (`subject.py:29-52`). No per-approver queue, no assignment, no pagination. Signs nothing. |
| 6 | **Eligibility** | `ugence_authority_directory` 0.1.0 answers `ApproverEligibilityPort` without importing it: time-bounded role grants, one-hop delegation, committees reported without vote counting, wrong approver refused with a typed reason (`eligibility_adapter.py:125-154`; walkthrough `test_wave_2_walkthrough.py:258-282`). | Never authenticates; `decided_by` is whatever the caller presents. Identity proof stays with the IdP behind Decision Authority. No IdP, SCIM or LDAP adapter. |
| 7 | **Human decision** | The record shape exists (stage 5). Decision Authority's `complete_review` seam is proven at the composition root (`test_decision_authority_seam.py:110-123`). | ~~No service, route, screen or client anywhere lists the queue, presents a parked proposal, or records a decision~~ — the service exists since HR-C (`governed-review-service`) and the studio screens and client since HR-D. Studio v2 has twelve routes and none of them (`api/v2/*.py`); the console client reaches four routes (`clients/console.py:34-39`); the console API has no approval, review or resume concept (`ugence_console_api/app.py`). |
| 8 | **Signal / resume** | `DbosExecutionAdapter.signal` appends `EXTERNAL_SIGNAL:<name>` under the per-instance lock and grants nothing (`engine/dbos_engine.py:278-319`); `resume` delegates to `resume_workflow` (`:321-335`). `resume_workflow` re-arms WAITING tasks and drives; `continue_workflow` re-arms and stops (`engine.py:200-241`). | Both take only an `instance_id`: no approval id, no approver, no evidence. A duplicate signal is recorded twice by design (`postgres/schema.py:48-57`); a signal for an unknown instance is accepted (no FK, no lookup). ~~`resume()` drains to a stable state inside one durable step~~ — closed by HR-B: the adapter now delegates to `continue_workflow`, one bounded quantum per durable step. |
| 9 | **Re-evaluation** | The next quantum rebuilds the proposal and calls the hook again; no cached evaluation exists; the pre-park clearance is never reused (`engine.py:489-500, 511, 590`; `validate_clearance` at `decisions.py:132-154`). | The re-evaluation asks `GovernanceInputSource.inputs_for`, and **no production implementation of that protocol exists** — the three that exist are test fixtures (`agent-runtime-governance/tests/_fakes.py:125,136`; `durable-execution/tests/_production.py:86`), none reading an approval store. Nothing turns a GRANTED approval into a changed Decision Authority result or an emptied `required_approvals`. |
| 10 | **Last mile** | RA-6 recheck re-verifies signature, window, tenant, session, epoch and targeted revocation; revocation or epoch advance while suspended blocks the resume (`risk-authority-status-runtime/.../enforcement.py:157-207`; `tests/test_ra6_last_mile_resume.py:148-192`). A CLEAR whose hook record is gone fails closed (`recheck.py:149-157`). | The recheck knows nothing of approvals: `PreEffectContext` has five fields and none is an approval (`enforcement.py:140-154`). Correct: an approval must enter at stage 9, before composition, never at the last mile. |
| 11 | **Receipts** | Clearance receipts are owned by `execution-reservation` and carry no approver or approval field (`receipts.py:78-96`); the approval ledger's own hash-linked `ledger_events` chain is the approval's evidence (`sqlite.py:73-82,166-183`); the runtime emits `WORKFLOW_RESUMED`, `TASK_WAITING`, `WORKFLOW_PAUSED` events (`models/events.py:25-28`). | No single artifact links proposal fingerprint, approval id, consumption id, resume event and resumed evaluation. The chain is reconstructible only by joining three stores on ids, as the wave-2 walkthrough does by hand (`test_wave_2_walkthrough.py:243-250`). |

**Net finding.** Every stage is individually correct and fail-closed. The missing
pieces are three: a **composition** that binds an approval to a proposal fingerprint
and consumes it inside the re-evaluation (stage 9), a **presentation and decision
surface** (stage 7), and a **resume that is a consequence of consumption**, not a
human button (stage 8).

## 3 — Boundaries

**Authority stays where it is.** Risk Authority composes, Decision Authority governs
the case, the approval ledger records the human decision, the directory reports
eligibility, the runtime evaluates and the engine schedules. The new work composes
these and owns none of their verdicts.

**The approval enters before composition.** The only place a GRANTED approval can
change an outcome is `GovernanceInputSource.inputs_for`, by changing what Decision
Authority reports for that proposal. It never bypasses `validate_clearance`, never
touches the RA-6 recheck, and never edits `required_approvals` after composition.

**The proposal fingerprint is the subject.** An approval binds to
`subject_kind="agent_runtime_proposal"` and `subject_digest=<proposal fingerprint>`.
A resumed re-evaluation that produces a different fingerprint finds no approval and
parks again. This reuses the ledger's own rule that a changed subject never reuses a
standing decision.

**Consumption is the resume.** A human records a decision; the composition consumes a
GRANTED approval exactly once at re-evaluation and only then does the engine advance.
No screen sends a resume. Lifting a park is a recorded consequence of a recorded
decision, the same asymmetry the incident-response record keeps for containment.

**Two stores, one order.** The approval ledger is SQLite Posture B; runtime state is
the DBOS Postgres. They cannot commit together, and OD-1 forbids engineering around a
split commit. The order is therefore fixed: consume first under a consumption key
whose `consumer_ref` is `<instance_id>:<task_id>`, then advance. A crash between the
two leaves a CONSUMED approval whose holder names this instance; the re-drive resolves
`ALREADY_CONSUMED` with that holder and treats it as satisfied. The ledger already
returns the holding consumption id for exactly this purpose (`consumption.py:87-95`).

**What the studio may do under SD-2.** Read and render: the open queue, a parked
proposal, its evaluation, the approval record and the audit chain. Transmit: a
human-authored decision, verbatim, to a separate service that owns the approval
ledger, authenticates the approver at the IdP and applies the eligibility port. The
studio holds no approver identity, computes no eligibility, consumes nothing, signals
nothing and resumes nothing. Whether "transmit" is permitted at all is OD-1.

**Prohibitions, stated once.** No surface on this path may mint authority, grant,
authorize, clear, execute, resume, revoke, or self-resolve a HOLD or ESCALATE; the
runtime's `resume_workflow` is never exposed to a human; the runtime package gains no
import and no changed signature except by a separate owner ruling; no credential, no
LIVE mode, no Temporal, no Langflow.

## 4 — Failure matrix

Each row names the property, what already holds, and the test that would prove the
row. A row is green only against a real PostgreSQL and a real SQLite ledger.

| # | Failure | Required property | Holds today `[V]` | Gap `[G]` | Proving test |
|---|---|---|---|---|---|
| 1 | **Duplicate decision** on one approval | Second decision refused; first stands | `IllegalTransitionError` on any decision after a terminal state (`states.py:129-137`; `test_state_machine.py:122-128`) | No idempotent replay: a retried identical decision is an error, not a no-op; the transmitting service must treat "already decided by the same actor with the same outcome" as success without re-deciding | Two GRANTs, then a REJECT, all after the first: one GRANTED record, one decision event |
| 2 | **Stale approval** — subject changed after grant | Refused, not consumed | `SUBJECT_MISMATCH` on consumption (`consumption.py:127-152`; seam test `:288-303`) | Nothing yet re-derives the fingerprint at consumption time | Approve fingerprint A; re-evaluation proposes B; instance parks again with reason naming the mismatch, zero invocations |
| 3 | **Approval expiry** | A GRANTED approval past its window is refused, not consumed | `EXPIRED` derived at read; `EXPIRED_APPROVAL` on consume (`records.py:127-133`; seam test `:220-237`) | The composition must pass the runtime's clock as `as_of`; two clocks would reopen ADR §8 row 11 | Grant with a one-hour window; advance at hour two; parked, zero invocations |
| 4 | **Revocation** after approval, before effect | Envelope revocation or epoch advance blocks at the last mile; role-grant revocation stops the decision | RA-6 resume tests (`test_ra6_last_mile_resume.py:148-192`); revoked grant → `EligibilityRefused` (`test_wave_2_walkthrough.py:258-282`) | An approval cannot be revoked once GRANTED (`states.py:86`); only consumption or expiry ends it | Grant; revoke envelope; resume; blocked with `CLEAR_REJECTED_AUTHORITY_STALE`, approval still unconsumed |
| 5 | **Wrong approver** | Refused with a typed reason before any record changes | `EligibilityRefused`; record stays PENDING (`eligibility_adapter.py:125-154`; `test_approval_workflow_seam.py:133-144`) | `decided_by` is caller-presented; identity proof is the transmitting service's IdP session, which does not exist | Present an approver with no grant, a lapsed grant, the wrong role, the requester; all refused |
| 6 | **Correlation mismatch** | An approval for one instance cannot resume another | Consumption key includes `consumer_ref`; runtime rejects a clearance whose correlation differs (`decisions.py:150-154`) | Nothing binds an approval to an instance today; the `consumer_ref` convention is proposed, not implemented | Two parked instances with identical actions; approve for A; B stays parked |
| 7 | **Crash before decision persistence** | Nothing recorded; queue unchanged; instance still parked | Ledger writes are single `BEGIN IMMEDIATE` transactions (`sqlite.py:135`) | Unproven end to end with a killed process | SIGKILL the review service mid-`decide`; record PENDING, no event |
| 8 | **Crash after decision persistence, before resume** | Decision survives; re-drive consumes and resumes exactly once | Approval durability holds; DBOS step atomicity holds (OD-1) | The cross-store order in §3 is unimplemented; nothing resolves `ALREADY_CONSUMED`-by-self as satisfied | Grant; SIGKILL after consume before advance; re-drive advances once, one invocation |
| 9 | **Duplicate resume signals** | A second signal or resume is recorded and changes nothing | Signals append under the instance lock (`dbos_engine.py:293-302`); resume on a RUNNING instance raises (`engine.py:207-210`) | Duplicates are recorded, never deduplicated; a signal for an unknown instance is accepted | Two signals and two resumes for one decision: one resumed evaluation, one invocation, two signal rows |
| 10 | **Clearance changes before resumed execution** | The resumed evaluation is fresh; a pre-park CLEAR is never reused; a post-approval revocation still blocks | Fresh proposal and hook call per quantum (`engine.py:489-500,590`); clearance record consumed and fail-closed (`recheck.py:149-157`) | Row 9 does not exercise resume; the property is proven only for crash recovery | Park; approve; revoke envelope; resume; blocked, approval consumed, no invocation |
| 11 | **Unbounded resume inside a durable step** | Resume advances one quantum, so the engine's step boundary matches the runtime's | `continue_workflow` exists and is bounded (`engine.py:219-241`) | The adapter calls `resume_workflow`, which drains (`dbos_engine.py:333`; `engine.py:216`) | Resume a three-task workflow; exactly one task advances per durable step |

## 5 — Owner decisions (ruled 2026-09-05)

| # | Ruling |
|---|---|
| **HR-1** | **`DISPLAY_AND_TRANSMIT`.** The studio renders the queue and run detail and relays a verbatim human decision to a separate review service that authenticates the approver and owns the ledger. The studio holds no approver identity, computes no eligibility, consumes nothing, signals nothing and resumes nothing; the relay route's operation id and path carry none of the SD-2 verbs, and the verb in the body is the human's. |
| **HR-2** | **`NEW_PACKAGE_GOVERNED_REVIEW`.** `packages/integration/governed-review` owns the production `GovernanceInputSource` over the approval ledger and the directory, the consume-then-advance order, and the review service. It imports approval-workflow, authority-directory and durable-execution and nothing under `capabilities/`. The console API is not the home: its audit store is an in-memory prototype (`ugence_console_api/audit.py:8-10`) and the studio may not import it. |
| **HR-3** | **`RATIFY_FINGERPRINT_BINDING`.** `subject_kind="agent_runtime_proposal"`, `subject_digest=<proposal fingerprint>`, `consumer_ref=<instance_id>:<task_id>`; consume in the SQLite ledger first, then advance in Postgres; `ALREADY_CONSUMED` whose holder is this instance and task is satisfied. No second ledger in Postgres. |
| **HR-4** | **`BARE_RUNTIME_BOUNDED_ADAPTER`.** `resume_workflow` keeps its signature and is never exposed to a human; the DBOS adapter moves to `continue_workflow`, one bounded quantum per durable step; consumption is the only trigger. The adapter change re-runs the full §8 matrix of the DBOS ADR; GAS-R5 is untouched. |
| **HR-5** | **`ESCALATE_ONLY`.** Only ESCALATE (`required_approvals` non-empty) enters the review queue. A HOLD is released solely by an upstream authority change. `MANUAL_REVIEW` is the label of the ESCALATE queue, not a new disposition. |

## 6 — Implementation sequence and maturity ceiling

Entry conditions are met; each step below is still entered only by its own
implementation prompt, ships behind its own tests and is labelled honestly at exit.

1. **HR-A · Binding and consumption composition** — the production
   `GovernanceInputSource` over the approval ledger and the directory, the
   consume-then-advance order, matrix rows 2, 3, 6, 8 and 10 against real stores.
   Label at exit: **Core implemented**, reference-grade.
2. **HR-B · Bounded resume** — the adapter moves to `continue_workflow`; row 11; row 9
   rewritten to actually resume. **Implemented** (durable-execution): row 9 resumes for
   real and asserts the post-resume fingerprint equals the pre-park one; a three-task
   chain asserts one task per durable step. Label: **Core implemented**; DBOS stays
   ratified on a green full §8 matrix after the change.
3. **HR-C · Review service** — queue listing, run detail, decision recording with IdP
   session identity and the eligibility port; rows 1, 5, 7, 9. **Implemented**
   (`packages/integration/governed-review-service` 0.1.0): `ReviewService` lists the
   ESCALATE queue joined to the durable checkpoint, renders a run, and records a GRANT
   or REJECT by a *presented* approver through the ledger's own transitions and
   eligibility port, then delivers the adapter signal and, for a GRANT, the bounded
   resume for that instance only; re-arming permits nothing, the next quantum's
   consumption does. Rows 1 and 5 pass at unit level; rows 5, 7, 8 and 9 pass inside
   the real DBOS adapter against a real PostgreSQL. The five audited routes exist over
   FastAPI as an optional extra. `[I]` Packaged as a sibling distribution rather than
   inside `governed-review`, whose boundary tests forbid the durable-execution import
   the service needs; ownership is as HR-2 rules. No IdP exists: `decided_by` is
   `PRESENTED_UNPROVEN`. Label: **Core implemented, shadow-only**, because every
   decision it records feeds a runtime that invokes fixture providers.
4. **HR-D · Studio screens** — Review Queue and Run Detail under SD-1 and SD-2, per
   the screen and API audit. **Implemented**: five v2 relay routes
   (`v2_review_list_queue`, `v2_review_read_run`, `v2_review_read_run_events`,
   `v2_review_read_approval`, `v2_review_submit_decision`) over a standard-library
   review-service client whose five-route allowlist is enforced before a socket
   opens; the decision body is relayed verbatim and the studio adds no identity; an
   unreachable review service renders as a gap, never an empty queue; a HOLD is
   filtered and counted on both sides of the wire (HR-5); fingerprints and
   `valid_until` are rendered as history. The SD-2 prohibition, console allowlist,
   v1 byte-freeze and frontend verb scan pass unchanged; `human_review_implemented`
   is `True`, `authentication_implemented` stays `False`. Label: **Core
   implemented** for the screens.
5. **HR-E · Receipt linkage** — one audit reference joining proposal fingerprint,
   approval id, consumption id and resumed evaluation, into an existing store per the
   sequencing record's D-4. Label: **Contract-only** until the unified ledger exists.

**Ceiling.** Nothing in this sequence can exceed **reference-grade, shadow-only**:
the approval ledger and directory are `REFERENCE_GRADE_SHADOW_ONLY`, the runtime
invokes no live provider, no credential broker exists, and the IdP integration that
would make `decided_by` a proven identity is not built. Pilot validation and
production certification are not reachable from this work and are not claimed.

## 7 — Next step

HR-A to HR-D are implemented. HR-E, one audit reference joining proposal fingerprint,
approval id, consumption id and resumed evaluation, is the last step and is
contract-only until the unified ledger exists. Nothing is implemented by this record.
