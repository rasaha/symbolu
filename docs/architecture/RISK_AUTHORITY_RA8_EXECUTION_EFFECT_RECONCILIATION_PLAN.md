# Risk Authority RA-8 — Execution / Effect Reconciliation (Architecture Discovery)

**Status:** DISCOVERY — architecture decision required (not yet ratifiable as a
canonical implementation spec).
**Type:** Read-only architecture discovery. No production code, no RA-8
implementation, no changes to Risk Authority / RA-6 / RA-7 / Agent Runtime /
Decision Authority / ActionGate / ACP. No PR.
**Discovery baseline (frozen default HEAD):** `620955fc` — the merge of PR #1413
(RA-7). Parents: RA-6 baseline `e6aa6edf` + audited RA-7 head `6af019e5`.
**Preceding milestone:** RA-7 (Runtime / Trajectory Assurance), merged.

> This document tests the candidate RA-8 working question — *"After an
> authorized action executes, did the actual execution and resulting effect
> match what was authorized, expected, and claimed?"* — against live code. The
> question is **confirmed** by ratified roadmap evidence and by the code, with
> important refinements recorded below.

---

## 0. Provenance & baseline verification (Stage A)

| Check | Result |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default HEAD | `620955fc` (= PR #1413 merge commit) |
| Working tree | clean |
| PR #1413 state | **merged** (`merged_by: rasaha`, `merged_at: 2026-08-11T09:01:47Z`) |
| Audited RA-7 head `6af019e5` in ancestry | **yes** (it is the second parent of the merge) |
| RA-7 ratification `4d2776e7` in ancestry | yes |
| RA-6 baseline `e6aa6edf` in ancestry | yes (first parent of the merge) |
| Anything landed after the RA-7 merge on default | **no** (default HEAD == merge commit) |
| PR #1410 | open (RA-5 spec ratification, docs-only) |
| Open PRs touching RA / execution / reconciliation / ActionGate / receipts | **none for RA-8/reconciliation/receipts**; #1414 (CM-TA1 token accounting) touches Agent Runtime but is unrelated to execution effect; #1410 is RA-5 docs |

Verdict for Stage A: RA-7 merged cleanly with correct provenance. No
`RA7_NOT_MERGED`, no `RA7_MERGE_PROVENANCE_MISMATCH`.

### RA-7 baseline freeze (Phase 1)

The RA-7 merge changed **only** RA-7 docs, the new
`packages/integration/risk-authority-runtime-assurance/` package, and its CI
workflow. `git diff --name-only e6aa6edf 6af019e5` shows **no** modification to
the RA leaf, RA-6 (`risk-authority-status-runtime`), Agent Runtime, Decision
Authority, or ActionGate — matching the PR's no-touch claim. RA-7 was audited at
merge; per instruction it was not re-audited.

Package present with all required parts:
`packages/integration/risk-authority-runtime-assurance/src/ugence_risk_authority_runtime_assurance/`
— `contracts.py` (TrajectoryObservation, TrajectoryAssessment, RuntimeRiskLevel),
`ingress.py` (trusted telemetry ingress), `policy.py` (TrajectoryPolicyReader),
`evaluator.py` (sequence-risk evaluator), `observer.py`, `handoff.py` (RA-6
neutral signal handoff), `assurance.py`, `event_adapter.py`. No second authority
artifact (confirmed by repo-wide grep — see §36).

Smoke set (this discovery environment):

| Suite | Result |
|---|---|
| RA-7 runtime-assurance | **100 passed** |
| Risk Authority leaf | **113 passed** |
| RA-6 status-runtime | **64 passed** + 1 collection error* |

\* `tests/test_ra6_last_mile_resume.py` fails to *collect* because it imports
`ugence_agent_runtime`, which is not pip-installed in this discovery
environment. It is a cross-package integration test; the RA-7 merge did not
touch it or RA-6. The PR-documented count with Agent Runtime installed is 72.
This is an environment artifact, **not** a regression.

**Frozen RA-8 discovery baseline: `620955fc`.**

---

## 1. Roadmap evidence for RA-8 (Phase 2)

**There is no dedicated RA-8 spec/plan/ADR file.** RA-8 is named only inside the
RA-5/6/7 docs and the RA leaf README. But the naming is **ratified and
consistent**, not merely implicit:

- `packages/risk_authority/README.md:31-33` (roadmap bundle): *"Third-Party
  Gateway, Trajectory Control, ACP and Reconciliation (RA-5 → RA-8) are defined
  here as contracts and layer onto this spine incrementally."*
- `docs/architecture/RISK_AUTHORITY_RA7_SPEC.md` **§4 (D1, RATIFIED)** and **§19
  (RATIFIED — future, separate)** define the RA-7/RA-8 boundary precisely:
  - **RA-7 owns (DURING execution):** runtime observation up to
    `PROVIDER_COMPLETED` / `TASK_COMPLETED`.
  - **RA-8 owns (AFTER execution):** authorized intent vs actual effect;
    execution receipt; effect verification; post-effect reconciliation;
    compensation feedback; third-party/external-effect verification.
  - §19: *"RA-8 = wire DA's already-modeled reconciliation to the runtime effect
    + feed mismatches back as RA-6 signals. Not implemented here."*
  - The spec explicitly flags DA's `ExecutionRecord` / `ReconciliationResult` /
    `ReconciliationService` as *"unwired from the runtime"* and warns RA-7 **must
    not** absorb them just because the code exists (N7).
- `RISK_AUTHORITY_RA7_SPEC.md:410-411`: *"Hard exclusion: RA-8's
  `EXECUTION_EFFECT_MISMATCH` (or equivalent) MUST NOT be introduced by RA-7."*
  Enforced by test (`risk-authority-runtime-assurance/tests/test_contracts.py`
  asserts the category is absent).

**Conclusion:** the candidate working question is the ratified RA-8 charter. The
docs agree; there is no roadmap disagreement to reconcile. RA-8 numbering is
canonical (RA-7 = trajectory/during; RA-8 = effect/after).

---

## 2. Existing post-execution inventory & classification (Phase 3)

`A` = production/package · `B` = integration seam · `C` = reference/conformance ·
`D` = research · `E` = legacy/deprecated · `F` = spec/docs.

| Component | Path | Class | Effect-reconciliation relevance |
|---|---|---|---|
| **DA execution/reconciliation kernel** | `capabilities/decision-authority/src/.../execution/*`, `services/{execution,reconciliation,compensation}_service.py`, `repositories/execution_repository.py` | **A** | The canonical `ExecutionIntent` / `ExecutionAttempt` / `ExecutionRecord` / `ReconciliationResult` / `CompensationRequirement` model + services. ~80 % of RA-8's concern already lives here. **Unwired to runtime and to RA-6.** |
| DA conformance | `decision-authority/.../conformance/{execution,reconciliation}.py` | C | Conformance harness for the above. |
| Neutral external-execution **contract** | `governance-contracts/src/.../contracts/execution.py` (`ExternalExecutionProvider`, `ExecutionObservation`, `ExecutionDispatchResult`) | **B** | The provider-neutral "what actually happened" seam. **No production adapter.** |
| Contract→kernel adapter | `governance-provider-framework/.../adapters/execution_to_external_system.py` (`ExternalExecutionPort`) | B | Where a Third-Party Gateway would plug in. |
| DA offline effect adapter | `decision-authority/.../execution/external_system.py` (`OfflineDeterministicExecutionAdapter`) | C | Deterministic, offline `dispatch`/`query_status` for tests. No real external observation. |
| Agent Runtime | `runtime/agent-runtime/*` | A | Executes via providers; owns intent/authority trajectory (`CanonicalExecutionState`). `execution_reference`/`result_digest` **reserved but always `None`**. **Forbidden** to import DA. |
| ActionGate | `providers/actiongate/*` | A | Authorization ALLOW/DENY only. *"does not dispatch, execute, observe, reconcile, or compensate."* Not effect-related. |
| Action Clearance (**ACP**) | `capabilities/action-clearance/*` | A | Pre-execution operational clearance; has a *clearance* receipt (`ClearanceReceiptBody`), **not** an execution/effect receipt. Pre-effect, not verification. |
| Cloud-scaling ops | `capabilities/cloud-scaling-operations/*`, `cloud-scaling-controller/*` | A | The only component reading **real external state** (k8s replica counts, optimistic concurrency, SHADOW observe mode). Domain-specific, ships `FakeScalingBackend`, unwired to DA/RA. |
| **ai-hiring product** | `products/ai-hiring/*` (`HiringExecutionReceipt` w/ `result_digest`/`execution_reference`, `hiring_reconciliation_service.py`, `hiring_compensation_service.py`, JSON schemas) | A | A **full domain-specific parallel of the RA-8 pattern** — proof the composition works. Via in-memory adapters; no production external effect; not wired to RA-6. |
| `ai_hiring/` (repo root) | `ai_hiring/*` | **E** | Older duplicate of the ai-hiring product. Legacy. |
| RA-5 evidence-runtime | `integration/risk-authority-evidence-runtime/*` | B | Trusted evidence → ControlResult **before** authorization. Not post-execution. |
| RA-6 status-runtime | `integration/risk-authority-status-runtime/*` | B | Authority-lifecycle writer; consumes `AuthorityReassessmentSignal`. RA-8's consequence sink. |
| RA-7 runtime-assurance | `integration/risk-authority-runtime-assurance/*` | B | Observes runtime telemetry → `RUNTIME_RISK_ESCALATED` into RA-6. Template for the RA-8 package shape. |
| RA authorize composition | `integration/risk-authority-runtime/*` | B | Composes DA + ActionGate + RA at the **authorize / effective-action recheck** point. Pre-action. |

**No RA-8 package exists.** **No second-authority artifact** exists anywhere
(`ReconciliationAuthorization` / `EffectGrant` / `ReceiptToken` /
`CompensationAuthority` → zero grep hits).

---

## 3. Current execution → effect flow (Phase 4)

There are **two parallel, deliberately isolated execution worlds**. This is the
central structural fact for RA-8.

### World A — Agent Runtime (the actual runtime executor)

```
RiskAuthorizationEnvelope (signed authority, RA leaf)
  → RA-4.5 GovernedExecutionDecision / clearance (integration/risk-authority-runtime)
  → ActionGate ALLOW/DENY (exact-action authority match)
  → Agent Runtime: validate_clearance + AuthorityRecheck  ← RA-6 §8 last-mile recheck (wired)
  → exact-action re-fingerprint gate (PROPOSAL_INVOCATION_MISMATCH → fail-closed)
  → provider.execute(ToolInvocation) → ToolResult(ok, output, ...)   ← provider return
  → ExecutionOutcome(ok, attempts, result)
  → CanonicalExecutionState snapshot (durable, SHA-256 sealed, checkpointed)
        proposal_fingerprint = attempted-action digest
        execution_reference = None   ← reserved seam, never populated
        result_digest       = None   ← reserved seam, never populated
        (NO tenant_id, NO envelope_id in this package)
  → RuntimeEvent stream: PROVIDER_INVOKED / PROVIDER_COMPLETED / TASK_COMPLETED
        (carry execution_state_digest only — no effect payload, no receipt)
  → [ FLOW STOPS HERE ] — no execution receipt, no effect observation, no reconciliation
```

- Correlation present on `CanonicalExecutionState`: `workflow_id`, `instance_id`,
  `task_id`, `correlation_id`, `proposal_fingerprint` (attempted-action digest),
  authority refs (`evaluation_reference`, `authorization_reference`,
  `clearance_reference`). **Absent: `tenant_id`, `envelope_id`.**
- Idempotency **key** (`instance_id:task_id`) is threaded and folded into the
  fingerprint, but there is **no idempotency ledger and no dedup guard**: retries
  simply re-invoke the provider. Agent Runtime **cannot** today detect "one
  authorized attempt produced two real effects."
- Agent Runtime *"performs no verification or reconciliation"*
  (`docs/AGENT_RUNTIME_CANONICAL_EXECUTION_STATE.md:42`), and importing
  `ugence_decision_authority` is a **hard-forbidden dependency**
  (`agent-runtime/tests/test_import_boundaries.py`,
  `artifacts/agent_runtime_dependency_rules.json`).

### World B — Decision Authority reconciliation (modeled, unwired)

```
ActionRequest (authorized) + executable Authorization + bound CER
  → ExecutionIntent (tenant_id, authorization_id, cer_id, action_type,
        target_system, authorized_parameters ⊆ authorized, authority_ref?,
        execution_idempotency_key, content_hash)   ← authorized intent, with a real
        idempotency ledger (ExecutionIdempotencyConflictError on key reuse)
  → ExecutionAttempt (transport-only: DISPATCHED/ACK/FAILED/TIMED_OUT/UNKNOWN,
        external_request_id, request_payload_hash)  ← execution-attempt receipt (transport)
  → ExternalExecutionPort.dispatch(intent) → ExternalDispatchResponse  (transport ack ≠ success)
  → ExternalExecutionPort.query_status(ext_id) OR external callback
        → ExecutionRecord (observed business_outcome, observed_parameters,
              finality, source, external_result_id, content_hash)  ← EFFECT OBSERVATION
              "what the external system actually did, never inferred from dispatch"
  → ReconciliationService.reconcile_execution
        → ReconciliationResult (status ∈ {RECONCILED, MISMATCHED, PARTIALLY_RECONCILED,
              INDETERMINATE, MANUAL_REVIEW_REQUIRED, COMPENSATION_REQUIRED},
              mismatch_codes, compensation_required, content_hash)
  → CompensationRequirement (PROPOSED; governed proposal, requires fresh authority)
  → AuditEvent (EXECUTION_MISMATCH_DETECTED, ...)   ← FLOW STOPS AT AUDIT
        (NO AuthorityReassessmentSignal, NO RA-6, NO risk_authority import)
```

- The whole of World B is driven by DA's **own** `ExternalExecutionPort`, not by
  Agent Runtime provider results. Only an `OfflineDeterministicExecutionAdapter`
  ships; there is **no production external-effect adapter**.
- World B is bound to DA's own `authorization_id` / `cer_id`. It is
  **envelope-agnostic**: `authority_ref` is an optional passthrough
  (`execution_service.py:167` copies `request.authority_ref`) and is **not**
  wired to the `RiskAuthorizationEnvelope`.
- World B emits **audit events only**. It never reaches Risk Authority / RA-6.

**The RA-8 gap, precisely:** nothing joins World A's realized provider effect to
World B's reconciliation, and nothing carries World B's reconciliation verdict
back to RA-6. Both endpoints exist and are mature; **the two wires between them
do not.**

---

## 4. RA-8 problem definition (Phase 5) — the four concepts, already separated

The DA model already encodes the exact four-way distinction the candidate
question demands (`execution/status.py:1-7`, "*authorization, dispatch, transport
acknowledgement, and business success are four different things*"):

1. **Execution attempted** → `ExecutionAttempt` + `TransportStatus`
   (DISPATCHED/ACK/TIMED_OUT/UNKNOWN). A timeout is `UNKNOWN`, never failure.
2. **Execution completed (transport)** → transport ACK. *Not* success.
3. **Provider-reported result** → `ExecutionRecord.business_outcome` from
   `query_status` or callback (`OutcomeSource`).
4. **Real-world/business effect** → the *observed* `ExecutionRecord` + `finality`;
   `ReconciliationResult` compares it to authorized intent.

The refund example in the brief ("provider says success; ledger shows ₹100,000 to
customer Y") is exactly what `ReconciliationStatus.MISMATCHED` +
`PARAM_MISMATCH:*` / `DUPLICATE_EFFECT` are built to catch — **provided a trusted
effect observation reaches `ExecutionRecord`.** Today, in production, nothing
produces that observation from a real external system (only the offline adapter).
That is the heart of RA-8.

RA-8 scope (confirmed against code): **execution-attempt receipt (owned by the
runtime), effect observation (owned by a trusted effect source), reconciliation
(compose DA), discrepancy classification (DA), compensation trigger (DA
proposal), authority feedback (new → RA-6 signal).** "Receipt" is used
unambiguously below: *execution-attempt receipt* ≠ *effect observation* ≠
*reconciliation result*.

---

## 5. Authorized-intent vs observed-effect comparison model (Phase 6)

| Concept | Authorized side (available today) | Observed side (available today) |
|---|---|---|
| Tenant | DA `ExecutionIntent.tenant_id` ✓ / Agent Runtime ✗ | `ExecutionRecord.tenant_id` ✓ |
| Workflow instance | Agent Runtime `instance_id`/`workflow_id` ✓ / DA via `correlation_id` | — (DA record has `correlation_id`) |
| Action/task id | DA `action_request_id`; AR `task_id` | `ExecutionRecord.execution_attempt_id` |
| Envelope id | **gap** — AR has none; DA `authority_ref` optional/unwired | — |
| Authorized action digest | DA `ExecutionIntent.content_hash`; AR `proposal_fingerprint` | — |
| Attempt id / idempotency | DA `execution_idempotency_key` (+ ledger); AR key (no ledger) | `ExecutionAttempt.external_request_id` |
| Provider | DA `target_system`; AR `provider_id` | `ExecutionRecord.external_system` |
| started_at / completed_at | `ExecutionAttempt.dispatched_at/completed_at` | `ExecutionRecord.observed_at` |
| Result digest | AR `result_digest` (**None**) | `ExecutionRecord.content_hash` |
| Effect reference | — | `ExecutionRecord.external_result_id` |

**Canonical comparison tuple (recommended, all already modeled in DA except the
envelope binding):** `(tenant_id, execution_intent_id, action_request_id/version,
authorized content_hash, execution_idempotency_key, external_request_id,
external_system, observed business_outcome, observed_parameters, finality,
external_result_id)` — plus a **new `authority_ref = envelope_id` binding** so the
reconciliation is traceable to the signed authority. No further fields are needed.

---

## 6. Execution-receipt ownership (Phase 7) — ratified split holds

- **Agent Runtime owns the execution-attempt receipt** ("I invoked provider P
  with payload X and got result Y"). The fields already exist and are reserved:
  `CanonicalExecutionState.execution_reference` / `result_digest`
  (`models/execution_state.py:255-259`, *"neutral seams for a future Runtime
  Assurance / receipt consumer"*, always `None`). Populating them from
  `ToolResult` is a bounded Agent-Runtime seam.
- **RA-8 (a new integration package) owns the effect/reconciliation record** — by
  composing DA, not by owning provider receipts.
- The **Risk Authority leaf must not own provider receipts** (I14: stdlib-only,
  provider/telemetry independent). Confirmed.

---

## 7. Decision Authority reconciliation analysis (Phase 8) — the crux

| Question | Finding (code-grounded) |
|---|---|
| What is `ExecutionRecord`? | An **immutable, observed external outcome** — "*what the external system actually did*", never inferred from dispatch (`execution_record.py:1-9`). Has `business_outcome`, `observed_parameters`, `finality`, `source`, `external_result_id`, `content_hash`, `tenant_id`, `correlation_id`. |
| Who creates it? | `ReconciliationService.record_external_outcome` / `query_external_status` — from an `ExternalExecutionPort` observation or an external callback, under `authorize_execution` (identity + access policy + `RECORD_EXTERNAL_OUTCOME`/`QUERY_EXECUTION_STATUS` permission), tenant-bound, audited. |
| Signed? | **No.** `content_hash` = `canonical_hash(...)` — a SHA-256 content digest (integrity), **not** a signature (authenticity). Honest characterization: hashed, not signed. |
| Observed effect or reported execution? | **Observed effect.** Dispatch ack is explicitly *not* success; business outcomes come only from `query_status`/callback. |
| How is `ReconciliationResult` derived? | `_compare(intent, records, latest)` — deterministic: DUPLICATE_EFFECT (multiple distinct success result ids / any DUPLICATE) → MANUAL_REVIEW; UNKNOWN outcome/finality → INDETERMINATE; FAILED/REJECTED/CANCELLED → COMPENSATION_REQUIRED; PARTIALLY_SUCCEEDED → PARTIALLY_RECONCILED; SUCCEEDED → param-by-param compare → MISMATCHED (`PARAM_MISMATCH:{key}`) or RECONCILED. |
| Discrepancy classes | `ReconciliationStatus` = RECONCILED / MISMATCHED / PARTIALLY_RECONCILED / INDETERMINATE / MANUAL_REVIEW_REQUIRED / COMPENSATION_REQUIRED; `mismatch_codes` include `DUPLICATE_EFFECT`, `OUTCOME_*`, `PARTIAL_COMPLETION`, `PARAM_MISMATCH:*`. |
| Compensation automatic/advisory? | **Advisory.** `CompensationRequirement` is *"a governed proposal, not an auto-rollback… any compensating action must pass through the normal governance chain (a new governed action request)"*. `CompensationType.GOVERNED_ACTION_REQUEST`, `required_authority`, approval PROPOSED→APPROVED/REJECTED/RESOLVED. |
| Can reconciliation grant authority? | **No.** It only records status + audit; no authorization output. |
| Tenant/workflow/action-bound? | Tenant-bound (`tenant_id` on every model, authz keyed by tenant); action-bound via `execution_intent_id`; correlation via `correlation_id`. **Envelope-agnostic** (`authority_ref` optional/unwired). |
| Persisted? | Yes — `ExecutionRepository` (in-memory reference impl; append-only snapshots, idempotency lookups, external-request lookups). Product layers (procurement, ai-hiring) already consume it. |
| Feeds any RA path today? | **No.** Emits `AuditEventType.EXECUTION_MISMATCH_DETECTED` etc. only. No `risk_authority` import, no `AuthorityReassessmentSignal`. |

**Answer to the central session question:** **Yes — RA-8 can largely compose DA
reconciliation rather than rebuild it.** DA already owns the intent/attempt/
record/reconciliation/compensation kernel, with correct non-compensatory and
fail-closed semantics, an idempotency ledger, tenant binding, authz, audit, and
persistence — and it is already reused by product layers. RA-8 is therefore **not
a new reconciliation subsystem**; it is a **thin composition + wiring** milestone.

**Exact gaps DA does not cover (RA-8's real work):**

1. **No trusted production effect source.** Only `OfflineDeterministicExecutionAdapter`
   ships. The generic contract exists (`governance-contracts/.../execution.py`
   `ExecutionObservation`) but has no production adapter. → RA-8's biggest open
   question (§10).
2. **No runtime → DA correlation.** Agent Runtime effects never become DA
   `ExecutionRecord`s (import forbidden; parallel identities; no tenant/envelope
   on AR). → needs a neutral bridge (§9, §11).
3. **No reconciliation → RA-6 feedback.** DA stops at audit. → needs a
   neutral-signal emitter (§13).
4. **No envelope binding.** `authority_ref` is unwired. → RA-8 must carry the
   `RiskAuthorizationEnvelope` id for traceability (§25).
5. **Conflicting-receipt masking risk.** `_compare` uses `latest = records[-1]`
   for the primary outcome; a later favorable `ExecutionRecord` can override an
   earlier unfavorable one for the same external request (duplicates across
   *distinct* result ids are caught, but a FAILED-then-SUCCEEDED sequence on one
   request resolves to the latest). RA-8's fail-safe philosophy (favorable must
   not mask unfavorable) may require a non-compensatory aggregation rule (§21).

---

## 8. Agent Runtime receipt gap (Phase 9)

- `execution_reference` / `result_digest` exist on `CanonicalExecutionState` but
  are **always `None`** — plumbed through serialization, digest, and tests, never
  populated (`runtime/execution_state.py:88-91` hardcodes `None`; field comment
  and `docs/AGENT_RUNTIME_CANONICAL_EXECUTION_STATE.md:136` mark them deferred).
- `ToolResult` (`providers/interfaces.py`) carries `ok/output/error/...` — **no
  digest, no reference, no attempt id, no payload hash.**
- No durable execution-attempt receipt joining invocation payload → result today.
- **Minimum missing seam** (do not implement now): (a) a result-digest/reference
  source populated from `ToolResult` into the reserved fields; (b) optionally a
  realized-effect ledger keyed by idempotency_key/fingerprint for
  one-authorization→one-effect detection. Both respect the import boundary (they
  live in Agent Runtime or in the RA-8 package reading the neutral event stream).

---

## 9. Third-party / effect-source boundary (Phase 10) — the critical open issue

- **"Third-Party Gateway" is roadmap text only** (RA-5→RA-8 bundle); no port,
  class, or module by that name exists in code.
- A **generic effect-observation contract does exist**:
  `governance-contracts/.../contracts/execution.py` — `ExternalExecutionProvider`
  / `ExecutionObservation` ("an observed business outcome") / `ExecutionDispatchResult`
  ("a transport result — never a business outcome"); adapted onto the DA kernel
  via `governance-provider-framework/.../adapters/execution_to_external_system.py`
  (`ExternalExecutionPort`). **No production adapter implements it.**
- **No general trusted external effect source.** The only component that reads
  real external state is `cloud-scaling-operations` (`ControlledScalingExecutor`
  reads/sets k8s replicas with optimistic concurrency + SHADOW observe mode) —
  domain-specific, isolated, ships `FakeScalingBackend`.
- RA-5 / TAP attest **evidence for control PASS before authorization**, not
  post-execution effect.

**Clarification:** the "Third-Party Gateway" is best understood as **the trusted
evidence-source (effect-observation) layer for RA-8** — a generic connector layer
sitting behind `ExternalExecutionPort` / `ExecutionObservation`, **not** an
authority component. Whether it is a distinct milestone or part of RA-8 is an open
decision (§Decisions D-A). External integration must not be conflated with
authority: an effect observation is evidence, never a grant (§36).

RA-8 should adopt the existing `ExecutionObservation` contract as its
`EffectObservationPort`; it does **not** need to invent a new port. What it needs
is (a) a trust model for observations (§15–16, §21) and (b) at least one
production or reference-grade real adapter to be more than offline.

---

## 10. Execution-vs-effect reconciliation model (Phase 11)

- **A. INTENT → EXECUTION** (did the runtime/provider execute the authorized
  action?) — **Agent Runtime's** domain (exact-action re-fingerprint gate +
  authority recheck; `ExecutionAttempt` transport in DA World B).
- **B. EXECUTION → EFFECT** (did execution produce the expected real effect?) —
  **RA-8's** domain, composing DA `ExecutionRecord` + `ReconciliationResult`.
- **C. EFFECT → POLICY** (is the resulting effect still acceptable?) — routes
  through RA-6 reassessment via a neutral signal (§13); RA-8 does not decide
  policy.

**Recommendation (tested against code):** RA-8 owns **B** (and the B→RA-6
feedback), **reusing** Agent Runtime for A (intent→invocation integrity) and DA
for the reconciliation compute. RA-8 = *authorized intent/execution → observed
effect reconciliation → neutral signal.*

---

## 11. RA-7 / RA-8 boundary (Phase 12) — preserved

- **RA-7:** during execution / behavioral trajectory; stops at
  `PROVIDER_COMPLETED` / `TASK_COMPLETED`; consumes runtime *events* only, never
  receipts (SPEC §4 Q4).
- **RA-8:** after execution / actual effect verification; consumes execution
  receipts + effect observations; performs reconciliation.
- **Late events:** a trajectory escalation arriving after provider completion is
  RA-7's (idempotent RA-6 signal, no-op if already revoked). An effect mismatch
  observed seconds/minutes later — or a delayed external receipt, or later
  compensation — is **RA-8's**. No duplicate ownership: RA-7 never verifies
  real-world effect (no such code exists), RA-8 never re-analyzes trajectory. RA-8
  *may* reference an RA-7 assessment id but must not recompute it.

---

## 12. RA-6 feedback model (Phase 13)

```
ReconciliationResult (material mismatch / duplicate / failed effect)
  → RA-8 maps to a neutral AuthorityReassessmentSignal
  → AuthorityReassessmentSignalPort.submit (RA-6 intake — reused as-is)
  → RA-6 reassessor (sole authenticated writer) → revoke / epoch / no-op
  → next consequential action sees reassessed authority
```

- The signal type (`risk_authority/domain/authority_signal.py`) is neutral,
  stdlib-only, leaf-owned; carries `evidence_refs` / `control_refs` /
  `prior_state_ref` — RA-8 can ride the `reconciliation_id` / `execution_record_id`
  on `evidence_refs`. It carries **no authority** by construction.
- Existing `SignalChangeType` categories: EVIDENCE_INVALIDATED, CONTROL_CHANGED,
  POLICY_SUPERSEDED, WORKFLOW_SUPERSEDED, MODEL_INVALIDATED,
  RUNTIME_RISK_ESCALATED, TENANT_EMERGENCY_STOP. **No `EXECUTION_EFFECT_MISMATCH`.**
- The RA-7 spec **reserves** `EXECUTION_EFFECT_MISMATCH` for RA-8 (hard-excluded
  from RA-7). Adding it is a **leaf schema touch** and therefore an
  authority-critical decision (§Decisions D-D). Reuse of an existing category is
  possible but arguably muddies audit semantics — an effect mismatch is a
  distinct consequence class from evidence/control/runtime-risk changes.
- **RA-8 MUST NOT** revoke directly, mint authority, advance epoch, or grant
  replacement authority (mirrors RA-7 I1–I4).

---

## 13. Compensation ownership (Phase 14) — already correct in DA

DA already encodes the safe split, and RA-8 should not change it:

- **Detect mismatch → recommend compensation:** DA `ReconciliationResult`
  (`compensation_required`) + `CompensationRequirement` (PROPOSED).
- **Decide compensation path:** Decision Authority / workflow (approval
  lifecycle).
- **Authorize the compensating action:** normal governance chain — a **new
  governed action request** (`CompensationType.GOVERNED_ACTION_REQUEST`,
  `required_authority`). Rollback is never assumed possible.
- **Execute:** Agent Runtime, under fresh authority.

RA-8 detects and *recommends* (via the reconciliation verdict + the RA-6 signal);
it **must not** execute corrective actions. This is already the DA design; RA-8
composes it.

---

## 14–17. Trust, integrity, outcomes, idempotency (Phases 15–18)

- **Receipt trust model (Phase 15):** DA observation ingestion is an
  **authenticated, tenant-bound, permission-gated, audited seam**
  (`authorize_execution`), with intrinsic binding to `execution_intent_id` and
  `external_request_id` (`ExternalRequestMismatchError` rejects a mismatched
  observation). This is *authenticated-ingestion* maturity — appropriate for
  reference grade. Cryptographic signing of receipts is **not** currently present
  and is **not required** for reference maturity (§16); it is a FUTURE hardening.
- **Integrity vs authenticity (Phase 16):** DA models carry `content_hash`
  (`canonical_hash`) = integrity/content digest. **These are hashes, not
  signatures.** The audit log is append-only; the domain models are immutable.
  There is no external attestation of receipts today. Characterize honestly: RA-8
  reference grade = authenticated ingestion + content-hash integrity + immutable
  append-only records; **not** cryptographically signed receipts.
- **Reconciliation outcomes (Phase 17):** the DA vocabulary already matches the
  candidate neutral set — RECONCILED (≈MATCHED) / MISMATCHED / PARTIALLY_RECONCILED
  (≈PARTIAL) / INDETERMINATE (≈UNKNOWN/UNVERIFIABLE) / MANUAL_REVIEW_REQUIRED /
  COMPENSATION_REQUIRED. No ALLOW/DENY (not authority). Deterministic. RA-8 should
  reuse it; a distinct `UNVERIFIABLE` (effect source unavailable) vs
  `INDETERMINATE` (finality unknown) split may be worth adding (§26).
- **Idempotency / duplicate effects (Phase 18):** DA has a real idempotency
  **ledger** (`ExecutionIntent.execution_idempotency_key` +
  `lookup_by_execution_idempotency_key` → `ExecutionIdempotencyConflictError`) and
  duplicate-effect detection (`DUPLICATE_EFFECT` when distinct success result ids
  > 1). **Agent Runtime has keys but no ledger.** RA-8 should **not** duplicate
  DA's ledger; the "one authorized attempt → two real effects" detection is a
  genuine RA-8 value proposition and is largely **already present in DA** — the
  missing piece is feeding real observations in.

---

## 15–19. Async, timing, conflicts, state, persistence (Phases 19–24)

- **Partial / async (Phase 19):** DA separates `Finality` (FINAL/NON_FINAL/UNKNOWN)
  from outcome, so an unfinished effect is `INDETERMINATE`, never a false mismatch.
  Multiple observations may coexist. RA-8 should keep finality distinct from match
  status (do **not** collapse "pending" into "mismatch").
- **Timing / SLA (Phase 20):** **not modeled** — no `expected_effect_by`,
  `reconciliation_deadline`, or `observation_window` exists. Open: who owns the
  finality timeout (workflow policy vs adapter vs RA-8 policy). Avoid global
  hardcoded deadlines; prefer a per-intent/workflow-policy-owned window carried
  into RA-8. (Additive; not authority-critical.)
- **Conflicting receipts (Phase 21):** partially handled (duplicates across
  distinct result ids escalate) but the primary-outcome path is `latest`-wins for a
  single external request — a favorable later observation **can** mask an earlier
  unfavorable one. RA-8 should adopt a **non-compensatory** aggregation
  (unfavorable/UNKNOWN dominates) to match RA's evidence philosophy. **Finding
  M-1 (§ findings).**
- **State model (Phase 23):** DA `ExecutionStatus` + `ReconciliationStatus` are
  already rich; RA-8 needs no new giant case-management state machine. Keep
  status + finality separate (already the case).
- **Persistence (Phase 24):** DA `ExecutionRepository` already persists intents,
  attempts, records, reconciliations, compensations (append-only, immutable). RA-8
  should **reuse DA persistence** and **not create a third execution ledger**
  (Agent Runtime's checkpoint store is a separate, intent-level store; do not
  conflate). RA-8's own state is a thin correlation/idempotency index at most.

---

## 20. Cross-tenant / cross-action replay (Phase 22)

DA provides intrinsic bindings (not mere storage partitioning): `tenant_id` on
every model + tenant-scoped authz; `execution_intent_id` binding;
`external_request_id` match (`ExternalRequestMismatchError`); idempotency-key
uniqueness per tenant. **Gaps to close in RA-8:** envelope binding
(`authority_ref = envelope_id`) and attempt-id binding across the runtime bridge,
so a receipt for attempt 1 cannot apply to attempt 2, and a Tenant-A observation
cannot touch a Tenant-B intent. The threat model (§ threats) enumerates the
replay cases; DA covers most, RA-8 must cover the envelope and runtime-bridge
edges.

---

## 21. Audit / traceability chain (Phase 25) — the enterprise value

Target chain (RA-8 makes it end-to-end reconstructible):

```
RiskAuthorizationEnvelope (signed)      "what was allowed"
  → ExecutionIntent (authorized content_hash)
  → ExecutionAttempt + Agent Runtime execution receipt   "what was attempted"
  → ExecutionRecord (observed effect, content_hash)       "what actually happened"
  → ReconciliationResult (status, mismatch_codes)         "did it match"
  → AuthorityReassessmentSignal → RA-6 reassessment       "what was done about the difference"
  → CompensationRequirement → governed action (fresh authority)
```

Today the chain is reconstructible **within** DA (intent→record→reconciliation→
compensation, all audited) but **breaks at both ends**: the envelope binding is
unwired at the top, and the RA-6 feedback is absent at the bottom. Closing those
two joins is RA-8's central deliverable and its enterprise differentiator (§38).

---

## 22. Failure semantics (Phase 26)

DA already refuses to let failure become success: timeout → `UNKNOWN` transport;
UNKNOWN outcome/finality → `INDETERMINATE`; malformed/mismatched observation →
error (rejected). RA-8 must extend this to its new seams: effect source
unavailable → `UNVERIFIABLE`/`INDETERMINATE` (never MATCHED); receipt
stale/malformed/untrusted → rejected; RA-6 sink unavailable → assessment stands
as evidence, authority unchanged (queue/retry). **No failure may become MATCHED
by default** — matches the RA-7 §20 failure matrix.

---

## 23. Authority-consequence semantics (Phase 27)

A mismatch must **not** always revoke everything. RA-8 emits **neutral evidence**
(a signal proportioned to materiality — e.g. only *material* mismatch escalates,
exactly as RA-7 gates on *material* deviation); **RA-6 decides the consequence**
(targeted envelope revoke vs no-op vs broader). Strong preference: **yes**, RA-8
is evidence-only, no direct lifecycle mutation. Confirmed against the neutral
signal contract.

---

## 24. GRC / ACP boundaries (Phases 28–29)

- **GRC (Phase 28):** RA-8 is **both** an operational control-plane function
  (real-time mismatch → authority reassessment) **and** an audit-evidence source
  (the immutable chain in §21). GRC **reporting/dashboards** remain separate
  (explicitly out of scope per the RA README roadmap). Do not turn RA-8 into a
  reporting milestone.
- **ACP (Phase 29):** ACP = `capabilities/action-clearance` — pre-effect physical/
  operational clearance (a *clearance* receipt, not an effect receipt). RA-8 =
  post-effect verification. RA-8 may verify that a physical effect matched the
  commanded safe action, but **must not choose** the control action. Boundary
  preserved.

---

## 25. Threat model (Phase 30)

| Threat | Owner | Mitigation (present / RA-8 / FUTURE) | Residual |
|---|---|---|---|
| Forged receipt / forged effect | RA-8 ingestion | authenticated, tenant-bound, permission-gated seam (present); signed receipts (FUTURE) | provider-self-report trust (deployment) |
| Receipt suppression / missing | RA-8 | UNKNOWN/INDETERMINATE, never MATCHED (present); finality timeout (RA-8, §20) | delayed effects |
| Delayed / replayed / duplicate receipt | DA | `external_request_id` match + `DUPLICATE_EFFECT` + idempotency ledger (present) | cross-runtime replay (RA-8 bridge) |
| Conflicting receipts | RA-8 | **M-1**: adopt non-compensatory aggregation (RA-8) — today `latest`-wins can mask | see M-1 |
| Wrong tenant/action/envelope/attempt binding | RA-8 | tenant + intent + external-request bindings (present); envelope + attempt-bridge bindings (RA-8) | — |
| Provider lies / partial reported as success | RA-8 + effect source | independent trusted observation via `ExecutionObservation` (needs real adapter, §10) | provider is sole observer (deployment) |
| Timeout then effect actually happens | DA | UNKNOWN transport + later `query_status`/callback → record (present) | reconciliation timing (§20) |
| Retry causes duplicate real effect | DA + Agent Runtime | idempotency key (AR) + DUPLICATE_EFFECT (DA); AR lacks a ledger (gap, §8) | AR retry semantics |
| Compensation abused | DA | governed proposal, fresh authority required (present) | — |
| Favorable masks unfavorable | RA-8 | **M-1** non-compensatory rule | — |
| Reconciliation DoS / mismatch flooding | RA-8 / deployment | bounded ingestion; dedup by external-request/idempotency (present) | volume (deployment) |
| Old receipt applied to new authority | RA-8 | envelope + attempt-id binding (RA-8) | — |

Most binding threats are already mitigated in DA. The **provider-self-report**
and **effect-source trust** residuals are the honest limit of any reference-grade
RA-8 (§38 — do not overclaim physical-world verification).

---

## 26. Package recommendation (Phase 31/33) — OPTION B

**Recommended: OPTION B — RA-8 is a sibling integration package that composes
Agent Runtime execution receipts + trusted effect observations + DA reconciliation
+ RA-6 signals.** Proposed home:

```
packages/integration/risk-authority-execution-assurance/     (recommended name)
  depends on: ugence-decision-authority (reconciliation kernel),
              ugence-risk-authority-status-runtime (RA-6 intake),
              ugence-risk-authority (leaf signal type),
              governance-contracts (ExecutionObservation / EffectObservationPort)
  observes:   Agent Runtime neutral event stream (duck-typed, no AR import of RA;
              RA-8 may import AR event types or read the neutral RuntimeEventStore)
```

Rationale / why not the alternatives:

- **Not OPTION A (inside DA):** DA cannot import Risk Authority (RA-6 feedback
  would invert the dependency direction) and must remain reusable by non-RA
  products (procurement, ai-hiring already depend on DA reconciliation). The
  reconciliation *kernel* stays in DA; the RA-wiring lives in the integration
  sibling.
- **Not OPTION C (inside Agent Runtime):** importing `ugence_decision_authority`
  from Agent Runtime is a **hard-forbidden** dependency (enforced by test). Agent
  Runtime must own execution but not governance/reconciliation semantics.
- **Not OPTION D (inside RA leaf):** would drag provider/effect/DA dependencies
  into the stdlib-only leaf (violates I14).
- **Not OPTION E (unnecessary):** DA reconciliation alone does **not** close the
  loop — it is unwired to the runtime and to RA-6, has no production effect source,
  and no envelope binding. RA-8 is a real, needed milestone.

Dependency direction (one-way, mirrors RA-7):
```
risk_authority (leaf) ◄─ status-runtime (RA-6) ◄─ execution-assurance (RA-8) ─► decision-authority (DA reconciliation)
                                                          │ observes ▼ neutral event contract
                                                      agent-runtime (never imports RA or DA)
```

**Sizing:** larger than RA-7 (which wired a single signal), because RA-8 must also
(a) generalize/wire a trusted effect source and (b) bridge two import-isolated
execution identities. But **substantially smaller than a from-scratch subsystem**,
because DA already owns the reconciliation kernel, compensation, idempotency, and
persistence, and ai-hiring already demonstrates the composition end-to-end. Net:
**a moderate integration milestone, not another substantial subsystem.**

---

## 27. Minimum contracts (Phase 32)

Prefer **reuse**. New types only where a genuine seam is missing.

| Type | Reuse / New | Owner | Producer → Consumer | Persisted | Integrity/auth | Replay | Authority |
|---|---|---|---|---|---|---|---|
| `ExecutionIntent` | reuse | DA | DA exec service → reconciliation | yes | content_hash | idempotency ledger | none |
| `ExecutionAttempt` | reuse | DA | DA → reconciliation | yes | payload hash | external_request_id | none |
| `ExecutionRecord` (effect observation) | reuse | DA | effect source → DA | yes | content_hash | external_request_id + tenant | none |
| `ReconciliationResult` | reuse | DA | DA → RA-8 | yes | content_hash | intent-bound | none |
| `CompensationRequirement` | reuse | DA | DA → workflow | yes | immutable | intent-bound | requires fresh authority |
| `ExecutionObservation` / `ExternalExecutionPort` (EffectObservationPort) | reuse contract; **new real adapter** | governance-contracts / adapter | effect source → DA | via record | authenticated ingestion | external_request_id | none (evidence) |
| Agent-Runtime **execution receipt** (populate `execution_reference`/`result_digest`) | **new seam (AR)** | Agent Runtime | provider result → reserved fields | AR checkpoint | state_digest | fingerprint + idempotency_key | none |
| **Runtime↔DA correlation record** | **new (RA-8)** | RA-8 pkg | AR receipt + envelope → DA intent id | thin index | derived | tenant+envelope+attempt | none |
| `AuthorityReassessmentSignal` | reuse | RA leaf | RA-8 → RA-6 | transient | fail-closed validate | dedupe by event_id | none (neutral) |
| `SignalChangeType.EXECUTION_EFFECT_MISMATCH` | **new category (decision)** | RA leaf | RA-8 → RA-6 | — | — | — | none |

**No RA-8 type may grant authority.** No `ReconciliationAuthorization`,
`EffectGrant`, `ReceiptToken`, or `CompensationAuthority` (§36).

---

## 28. RA-6 / RA-7 compatibility (Phases 34–35)

- **RA-7 (Phase 34):** unchanged. RA-8 consumes execution-completion events +
  receipts; it does not duplicate trajectory analysis and does not touch RA-7's
  package. RA-8 may reference an RA-7 assessment id as context only.
- **RA-6 (Phase 35):** `AuthorityLifecycleService` remains the sole lifecycle
  writer. RA-8 mismatch → neutral signal → RA-6 reassessment. **No RA-8 direct
  revoke / epoch mutation.** The only RA-6 touch is the possible new
  `EXECUTION_EFFECT_MISMATCH` category (leaf schema), which is a decision, not a
  behavior change to RA-6's writer.

---

## 29. No-second-authority analysis (Phase 36)

`RiskAuthorizationEnvelope` remains the sole signed machine authority
(confirmed: zero grep hits for second-authority artifacts repo-wide; RA-5/RA-7
packaging tests already assert their absence). `ExecutionReceipt` /
`EffectObservation` / `ReconciliationResult` are **evidence** — they must not
authorize execution. Compensation requires normal authority. RA-8 introduces no
`ReconciliationAuthorization` / `EffectGrant` / `ReceiptToken` /
`CompensationAuthority`. The neutral `AuthorityReassessmentSignal` (which carries
no authority by construction) is the only thing RA-8 emits toward authority.

---

## 30. Future test matrix (Phase 37) — deny-heavy (design only; not implemented)

1. authorized execution + matching effect → RECONCILED
2. wrong target → MISMATCHED
3. wrong amount (param) → MISMATCHED (`PARAM_MISMATCH`)
4. wrong resource → MISMATCHED
5. partial effect → PARTIALLY_RECONCILED (finality NON_FINAL → not mismatch)
6. missing receipt → INDETERMINATE/UNVERIFIABLE (never MATCHED)
7. provider success but external state failure → MISMATCHED/CONFLICTED (M-1 rule)
8. effect source unavailable → UNVERIFIABLE, authority unchanged
9. duplicate receipt → DUPLICATE_EFFECT → MANUAL_REVIEW
10. conflicting receipt → non-compensatory: unfavorable dominates (M-1)
11. replay old receipt → rejected (external_request_id + attempt binding)
12. wrong tenant → rejected
13. wrong workflow → rejected
14. wrong action → rejected (intent binding)
15. wrong envelope → rejected (new envelope binding)
16. wrong attempt id → rejected
17. timeout then effect occurs → UNKNOWN transport then later record
18. retry causes duplicate real effect → DUPLICATE_EFFECT
19. partial fill → PARTIALLY_RECONCILED
20. delayed finality → INDETERMINATE until FINAL
21. favorable receipt cannot mask unfavorable → M-1 assertion
22. untrusted receipt rejected
23. malformed receipt rejected
24. reconciliation engine error → fail-closed, never MATCHED
25. mismatch → neutral RA-6 signal emitted
26. RA-8 cannot revoke directly (no revoke path; packaging test)
27. RA-8 cannot mint authority (no envelope/grant; packaging test)
28. compensation recommendation cannot self-execute
29. compensation requires fresh authority
30. RA-7 unchanged
31. RA-6 unchanged
32. Agent Runtime unchanged absent the receipt adapter
33. DA reconciliation reused (not re-implemented)
34. ACP remains separate
35. no second execution ledger (reuse DA persistence)
36. no second authority artifact
37. RA leaf independently installable (stdlib-only)

---

## 31. Platform / competitive significance (Phase 38)

RA-8 adds, beyond logging / APM / SIEM / workflow history / provider success
logs / audit trails: **a verifiable binding of machine authority to a
post-execution chain** — *what was authorized (signed envelope) → what was
attempted (execution receipt) → what actually happened (independent effect
observation) → whether they matched (deterministic reconciliation) → whether the
discrepancy reassessed authority (RA-6).* The differentiator is the **closed loop
from effect back to authority**, not the reconciliation compute itself.

**Honesty constraint:** where the only effect source is a provider self-report,
RA-8 verifies *reported* effect, not physical-world truth. RA-8 must not overclaim
independent physical verification unless a genuinely independent effect source
(e.g. an external ledger, a sensor, a second observer) is wired. The architecture
*supports* that claim only to the strength of the effect source configured.

---

## 32. Findings (Phase 39)

| ID | Sev | Finding |
|---|---|---|
| **B-1** | INFO (not a blocker) | No true blocker. RA-8's direction (compose DA via a sibling integration package) is ratified and code-supported. |
| **H-1** | HIGH | **No production trusted effect source.** Only `OfflineDeterministicExecutionAdapter` ships; the generic `ExecutionObservation` contract has no real adapter. RA-8's verification strength is bounded by this until a real effect source exists. |
| **H-2** | HIGH | **Runtime↔DA are import-isolated parallel worlds.** Agent Runtime effects never become DA `ExecutionRecord`s; AR has no `tenant_id`/`envelope_id` and `result_digest`/`execution_reference` are always `None`. A neutral bridge + AR receipt seam is required. |
| **H-3** | HIGH | **No reconciliation→RA-6 feedback.** DA stops at audit events; no `AuthorityReassessmentSignal`. The authority loop is open at its last hop. |
| **M-1** | MEDIUM | **Conflicting-receipt masking.** DA `_compare` uses `latest`-wins for a single external request; a favorable later observation can mask an earlier unfavorable one. RA-8 needs a non-compensatory aggregation. |
| **M-2** | MEDIUM | **Envelope binding unwired.** DA `authority_ref` is optional/unused; reconciliation is envelope-agnostic. RA-8 must bind `authority_ref = envelope_id` for end-to-end traceability. |
| **M-3** | MEDIUM | **`EXECUTION_EFFECT_MISMATCH` category** is reserved but not present; adding it is a leaf-schema decision (D-D). |
| **L-1** | LOW | **No reconciliation timing/SLA model** (`expected_effect_by`, finality timeout). Additive; ownership undecided (§20). |
| **L-2** | LOW | **Receipts are hashed, not signed.** Acceptable at reference grade; cryptographic signing is FUTURE. |
| **INFO** | INFO | ai-hiring already ships a full domain parallel of the RA-8 pattern (proof it composes); `ai_hiring/` (root) is a legacy duplicate. |

---

## 33. Open architecture decisions (Phase 40 item 40)

| ID | Decision required |
|---|---|
| **D-A** | **Effect-source trust model & ownership.** Where does the trusted effect source / "Third-Party Gateway" live — a generic connector layer behind `ExecutionObservation` (own milestone) vs part of RA-8? What is its minimum trust (authenticated ingestion vs signed)? This is the single biggest open question and gates any production claim. |
| **D-B** | **Runtime bridge.** Does Agent Runtime populate its reserved `execution_reference`/`result_digest` (execution-attempt receipt), and does RA-8 correlate them to DA `ExecutionIntent` — via the neutral event stream or a new neutral seam — without breaking the AR↔DA import boundary? |
| **D-C** | **DA extension vs RA-8 wrap.** Fix M-1 (non-compensatory aggregation) and wire M-2 (envelope binding) inside DA, or wrap them in RA-8? |
| **D-D** | **New signal category.** Add `SignalChangeType.EXECUTION_EFFECT_MISMATCH` (leaf schema touch) vs reuse an existing category. |
| **D-E** | **Package name/home.** `risk-authority-execution-assurance` vs `risk-authority-reconciliation` vs an existing DA integration home. |

Because D-A and D-B are authority-adjacent and unresolved, **this is discovery
output, not a canonical implementation spec.** A spec should follow only after
D-A and D-B are ratified.

---

## 34. Final verdict

**`RA8_ARCHITECTURE_DECISION_REQUIRED`.**

RA-8 is real and needed; its shape is clear and code-supported: **compose the
mature DA reconciliation kernel from a thin sibling integration package (the RA-7
pattern), wiring a trusted effect source and reconciliation→RA-6 feedback.** RA-8
is therefore a **moderate integration milestone, not another substantial
subsystem.** But a canonical spec is gated on the effect-source trust model (D-A)
and the runtime bridge (D-B), plus the envelope-binding and signal-category
decisions. Those are architecture decisions for ratification, not discovery
findings.

*Discovery only. No production code, no RA-8 implementation, no changes to Risk
Authority / RA-6 / RA-7 / Agent Runtime / Decision Authority / ActionGate / ACP,
no PR.*
