# Risk Authority RA-7 — Runtime / Trajectory Assurance — Canonical Specification (Ratified)

> **Status:** RATIFIED — canonical, in-repo RA-7 specification.
> **Type:** DOCUMENTATION / ARCHITECTURE ONLY. This document changes no
> production code, starts no RA-7 implementation, creates no package, adds no
> port to source, adds no persistence, adds no telemetry infrastructure,
> modifies no envelope / ActionGate / Agent Runtime / RA-6 / Decision Authority,
> implements no ACP or RA-8, and opens no PR.
> **Verdict:** `RA7_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION` (§29).
> **Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
> default head `e6aa6edf` (merge of PR #1412 — RA-6). RA-1→RA-4, RA-4.5, RA-5,
> and RA-6 are merged and treated as stable and closed. RA-7 reopens none of them.
> **Supersedes the discovery verdict.** The architecture-discovery companion
> (`RISK_AUTHORITY_RA7_RUNTIME_TRAJECTORY_ASSURANCE_PLAN.md`, verdict
> `RA7_ARCHITECTURE_DECISION_REQUIRED`) is now a superseded discovery input; its
> seven open decisions D1–D7 are ratified here (§4–§10).

RA-7 is the **runtime / trajectory assurance** milestone named in the post-RA-6
roadmap bundle (`packages/risk_authority/README.md:31-33`; RA-5 → RA-8). Every
architectural claim below was re-verified against live code at `e6aa6edf`;
file:line anchors are cited so a reviewer can confirm each one.

RA-7 answers exactly one question:

> **"While an authorized agent/system is operating, is its observed runtime
> trajectory still consistent with the assumptions, constraints, and authority
> under which it was permitted to operate — and if not, can that behavior cause
> the still-valid machine authority to be reassessed?"**

**RA-7 OBSERVES AND ASSESSES. RA-6 OWNS AUTHORITY CONSEQUENCES.** RA-7 is the
missing *producer* of the neutral `AuthorityReassessmentSignal` that the fully
built RA-6 seam already consumes. It is **not** a second authority layer.

---

## 0. Provenance & the central finding

### 0.1 Repository state (verified independently at ratification)

| Item | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default head | `e6aa6edf` (merge of PR #1412 — RA-6) |
| RA-6 merge `e6aa6edf` in default ancestry | **YES** — default head *is* the RA-6 merge |
| Code divergence since RA-6 | **NONE** — discovery assumptions hold exactly |
| Working tree | clean |
| Discovery doc source | `docs/architecture/RISK_AUTHORITY_RA7_RUNTIME_TRAJECTORY_ASSURANCE_PLAN.md` @ `63275f91` |
| PR #1410 | **OPEN** — RA-5 canonical spec docs (docs-only; unrelated to RA-7) |
| Open RA-7 / RA-8 PRs | **NONE** |
| `risk-authority-runtime-assurance` package | **ABSENT** (genuine greenfield) |

No material Risk Authority / RA-6 / Agent Runtime / ActionGate / Decision
Authority change landed after the RA-7 discovery. RA-7 proceeds.

### 0.2 The central finding (re-confirmed against `e6aa6edf`)

**RA-7 is NOT a new authority system.** The RA-6 observer→authority feedback
seam is *fully built but has no producer*. RA-7 is that missing producer.

| Already implemented (reuse, do not duplicate) | Anchor (verified) |
|---|---|
| Neutral, authority-free `AuthorityReassessmentSignal` | `risk_authority/domain/authority_signal.py:79` |
| `SignalChangeType.RUNTIME_RISK_ESCALATED` category | `authority_signal.py:51` |
| `SignalTargetType` = `ENVELOPE` / `SUBJECT` / `MODEL` | `authority_signal.py` (enum) |
| Intake port `AuthorityReassessmentSignalPort.submit` | `integrations/authority_lifecycle.py:199,207` |
| Reference reassessor consuming `RUNTIME_RISK_ESCALATED` | `…status-runtime/reassessor.py:110` |
| Sole authenticated writer (targeted revoke / epoch), tenant-isolated | `…status-runtime/writer.py:112`, cross-tenant write refused `:169-172` |
| `TENANT_EMERGENCY_STOP` **refused** on the observer path | `reassessor.py:177-181` |
| Bounded-stale offline reader + RA-6 §8 pre-effect recheck | `…status-runtime/enforcement.py` |
| Neutral runtime event stream + optional `event_sink` | `agent-runtime/models/events.py:22`, `config.py:62` (default `None`) |
| Self-verifying execution checkpoints | `agent-runtime/runtime/engine.py:741` |
| Cumulative/portfolio budget ledger | `agent-runtime/orchestration/budgets.py:48,149` |
| `trajectory_policy_id` (signed envelope condition) | `domain/envelope.py:32` |
| `trajectory_version` (threaded, unenforced label) | `domain/actions.py:56`, `integrations/actiongate.py:56,77,178` |
| `context_minimization` (signed envelope condition) | `domain/envelope.py:30` |
| Decision-Authority reconciliation primitives (the RA-8 concept) | `decision-authority/execution/execution_record.py`, `services/reconciliation_service.py`, `execution/reconciliation.py` |
| ACP — spec/docs only, no package | `Project_documentation/control_plane/acp/*.md` |
| RA leaf stdlib-only | `packages/risk_authority/pyproject.toml` → `dependencies = []` |

| Absent — the genuine RA-7 greenfield |
|---|
| A runtime-risk / trajectory / drift evaluator |
| A **producer** of `AuthorityReassessmentSignal` (every construction today is in tests; `agent-runtime/src` imports **nothing** from `risk_authority` — grep clean) |
| Sequence-level **risk** typing (as opposed to resource budgeting) |
| A telemetry-trust ingress seam |
| Any wiring from execution behavior back to Risk Authority |

**The loop `runtime behavior → signal → reassess → revoke/epoch → enforce` is
open at the first hop only — the producer. RA-7 is that missing producer.**

---

## 1. Purpose, MUST, MUST-NOT

### 1.1 Purpose

RA-7 is an **event-driven runtime / trajectory observer and risk evaluator**. It
consumes the Agent Runtime event stream (and optionally external telemetry),
assesses whether the observed per-workflow-instance trajectory remains consistent
with the authority under which it was permitted, and — on material deviation —
emits a neutral `AuthorityReassessmentSignal` into the existing RA-6 intake. RA-6
decides and enacts the authority consequence; ActionGate / the pre-effect recheck
enforce it at the next consequential commit.

### 1.2 RA-7 MUST

- **M1.** Consume runtime behavior via the *existing* neutral Agent Runtime
  `event_sink` seam (`config.py:62`), requiring **no** agent-runtime change for
  the core observe→signal loop.
- **M2.** Produce a `TrajectoryAssessment` (§12) that is **evidence/verdict, not
  authorization** — it carries no ALLOW, no scope, no signature that grants power.
- **M3.** On a *material* assessment, emit `AuthorityReassessmentSignal` with
  `change_type = RUNTIME_RISK_ESCALATED` (§9/D6) into the RA-6
  `AuthorityReassessmentSignalPort` (`authority_lifecycle.py:207`).
- **M4.** Route **every** authority consequence through RA-6's authenticated
  `AuthorityLifecycleService` — the sole writer.
- **M5.** Default consequence granularity is a **targeted envelope reassessment**
  (`target_type = ENVELOPE`; §8/D5).
- **M6.** Validate telemetry bindings (tenant / workflow / envelope / event id /
  observed_at / source) and reject anything that does not bind cleanly (§10/D7).
- **M7.** Be **additive and event-driven by default** — never a mandatory
  synchronous hot-path dependency (§7/D4).
- **M8.** Reference the trajectory policy by its authority-bound identity; never
  substitute policy content (§5/D2).

### 1.3 RA-7 MUST-NOT

- **N1.** Mint a `RiskAuthorizationEnvelope` or any signed machine-authority
  artifact. `RiskAuthorizationEnvelope` (Ed25519) remains the *sole* one.
- **N2.** Widen authority, return a binding ALLOW, or create a second authority
  token.
- **N3.** Directly mutate revocation / epoch state (only the RA-6 writer does).
- **N4.** Trigger `TENANT_EMERGENCY_STOP` — the reassessor refuses it on the
  observer path (`reassessor.py:177-181`); emergency stop stays a separately
  privileged control (`EMERGENCY_STOP_CAPABILITY`, `writer.py:52`).
- **N5.** Become a second ActionGate (per-action exact-scope matching) or a
  second enforcer.
- **N6.** Become ACP (per-tick actuator clearance) — §15.
- **N7.** Absorb RA-8 (post-effect reconciliation) — §19/D1.
- **N8.** Import RA into `agent-runtime`, or push RA-specific policy into
  `agent-runtime` — §17.
- **N9.** Add any dependency to the stdlib-only RA leaf.

---

## 2. Current-vs-RA-7-vs-future map (read before implementing)

**CURRENT / ALREADY IMPLEMENTED (reuse, do not rebuild):**
- RA-6 neutral signal + intake + reassessor + sole authenticated writer +
  targeted revoke / tenant epoch + bounded-stale enforcement / pre-effect recheck.
- Agent Runtime event stream (`PROVIDER_INVOKED/COMPLETED`, `TASK_*`,
  `CHECKPOINT_COMMITTED`), optional `event_sink`/`event_store`, self-verifying
  checkpoints, canonical execution-state journal.
- Agent Runtime `PortfolioBudget`/`BudgetCoordinator` resource ledger.
- `trajectory_policy_id` (signed envelope condition) / `trajectory_version`
  (threaded, unenforced) plumbing.
- Decision-Authority reconciliation primitives (`ExecutionRecord`,
  `ReconciliationResult`, `ReconciliationService`) — modeled, unwired.
- ACP — spec-only status.

**RA-7 / TO IMPLEMENT (this milestone):**
- Runtime assurance observer (subscribes to the event stream).
- Trajectory evaluator (risk-types the observed trajectory).
- Trajectory-policy reader + version/digest validation.
- Sequence-level risk interpretation (reads the budget ledger; risk-types it).
- Telemetry-trust ingress seam.
- Neutral `TrajectoryAssessment` output.
- RA-6 signal handoff (`RUNTIME_RISK_ESCALATED`).

**RA-8 / FUTURE (explicitly out of RA-7):**
- Execution receipt / actual-effect verification.
- Wiring Decision-Authority reconciliation to the runtime effect.
- Compensation feedback → RA-6 signal.

**ACP / SEPARATE (never RA-7):**
- Deterministic physical per-tick action clearance.

---

## 3. Ratified RA-7 objective (§3 of charter)

The candidate framing is **ratified as correct**:

> RA-7 OBSERVES AND ASSESSES. RA-6 OWNS AUTHORITY CONSEQUENCES.

This is not merely a policy choice — it is **structurally enforced** by the
existing types: `AuthorityReassessmentSignal` has no ALLOW field and no scope
field; only the authenticated `AuthorityLifecycleService` mutates state; and the
reassessor refuses the one privileged category (`TENANT_EMERGENCY_STOP`) on the
observer path. RA-7 therefore *cannot* become a second authority even by
accident, provided it emits only through the neutral signal seam. The framing
holds; no correction required.

---

## 4. D1 — RA-7 / RA-8 boundary (RATIFIED)

**Decision:** the split is **correct and adopted**.

- **RA-7 owns (DURING execution):** runtime observation; sequence/trajectory
  assessment; pre-completion behavioral deviation; runtime-risk escalation
  signals. RA-7's observation window ends at **provider invocation / execution
  completion events** (`PROVIDER_COMPLETED`, `TASK_COMPLETED`) — the neutral
  runtime events it can already see.
- **RA-8 owns (AFTER execution):** authorized intent vs actual effect; execution
  receipt; effect verification; post-effect reconciliation; compensation
  feedback; third-party/external-effect verification.

**Q1 — Is the split correct?** Yes. RA-7 is behavior-over-time *before the next
consequential commit*; RA-8 is effect-closure *after* the effect landed.

**Q2 — Does Decision-Authority reconciliation belong wholly to RA-8?** Yes. DA
already models `ExecutionRecord` / `ReconciliationResult` / `ReconciliationService`
(`decision-authority/execution/*`, `services/reconciliation_service.py`) and they
are **unwired** from the runtime. Wiring them to the runtime effect and feeding
mismatches back as RA-6 signals is **RA-8's** deliverable. **RA-7 MUST NOT absorb
reconciliation merely because the code already exists** (N7).

**Q3 — What happens to a signal that arrives after effect completion?** RA-7
treats it exactly as RA-6 already treats late/duplicate signals: the reassessor
dedupes by `event_id` and reassesses **current** state. If the envelope is
already revoked/expired, the signal is idempotent and a no-op (grow-only
revocation, RA-6 I5). The completed effect itself is **out of RA-7 scope** — that
is RA-8's reconciliation. RA-7 does not attempt to "undo" an effect; it can only
cause the *next* consequential commit to see a reassessed authority.

**Q4 — Does RA-7 ever consume execution receipts?** **No.** RA-7 consumes runtime
*events* only (the neutral `RuntimeEvent` stream). Execution receipts / effect
records are RA-8 inputs. RA-7 stops at execution-completion events and does not
claim to verify real-world effect (no such verification exists in live code).

**Number assignment:** RA-7 = runtime/trajectory assurance; RA-8 = effect
reconciliation. Ratified.

---

## 5. D2 — Trajectory policy ownership + integrity (RATIFIED)

**Findings (verified):** `trajectory_policy_id` is an `EnvelopeConditions` field
(`envelope.py:32`) — i.e. it is **bound into the signed envelope**, so the *policy
reference* is already authority-bound and tamper-evident. `trajectory_version`
rides on `ActionAuthorization` (`actions.py:56`) and is threaded through the
ActionGate seam (`actiongate.py:56,77,178`) but is **never read in matching
logic** — a passthrough label. **No evaluator consumes either field**, and there
is **no owner or store for the policy content.**

**Decision — ownership:**

- **Policy *content* owner (source):** the **WorkflowIR / workflow policy layer**
  (candidate B). Rationale: a trajectory policy describes the *acceptable shape of
  a workflow's runtime path*, which is a property of the workflow definition, not
  of the Risk Authority leaf. This keeps the stdlib-only RA leaf free of
  telemetry-specific policy implementation (the strong constraint in the charter).
- **Canonical identity:** `trajectory_policy_id` (already the signed reference).
- **Versioning:** `trajectory_version` (already threaded).
- **Integrity binding — REQUIRED but DEFERRED to a non-breaking add:** the policy
  *content* SHOULD be pinned by an immutable **`trajectory_policy_digest`**, bound
  like the existing `workflow_ir_digest` / `model_digest`, so a substituted policy
  is detectable. This is the single genuinely justified schema touch, and it is
  **additive** (a new optional `EnvelopeConditions`/bindings field, signed via the
  existing `signing_payload()` path). Until it lands, RA-7 operates against the
  authority-bound `trajectory_policy_id` alone and treats an unresolvable /
  unknown-version policy as `UNKNOWN` (§10, §20).
- **Risk Authority's role:** RA may **bind/reference** the policy (it already
  does, via the signed `trajectory_policy_id`) but MUST NOT own the
  telemetry-specific policy implementation.

**Are current fields sufficient?** For the reference milestone, `trajectory_policy_id`
+ `trajectory_version` are sufficient to *reference and version* a policy. They
are **not** sufficient to *prove policy-content integrity*; that requires the
additive `trajectory_policy_digest`. Because the digest is additive and
optional-until-populated, adopting it is **compatible** — old envelopes without
the digest remain valid; RA-7 simply cannot assert content-integrity for them and
downgrades to `UNKNOWN` where integrity matters.

**Ratified:** WorkflowIR owns policy content; identity/version already exist;
add a non-breaking `trajectory_policy_digest` binding (deferred, additive, no
required schema break for existing envelopes).

---

## 6. D3 — Sequence-level risk source (RATIFIED)

**The gap is real:** ten individually-authorized `$9,000` transfers = `$90,000`
cumulative exposure is **not** caught by ActionGate (per-action, stateless).

**Building block that already exists:** `PortfolioBudget` / `BudgetCoordinator`
(`orchestration/budgets.py:48,149`) maintain a reserve-before-execute cumulative
ceiling shared across concurrent quanta — but it is a **generic orchestration
budget that decides nothing about governance.**

**Decision — Option A (observe existing state; apply risk policy externally):**

- **Who owns cumulative *facts*:** Agent Runtime (`PortfolioBudget` /
  `BudgetCoordinator` / portfolio checkpoints). RA-7 does **not** re-implement a
  ledger (rejects Option B) and does **not** extend RA scope/accounting (rejects
  Option C). Option D (reuse the ledger + separate evaluator) is the same as A in
  practice; A is the ratified phrasing.
- **Who owns risk *interpretation*:** RA-7. It **reads** the runtime's cumulative
  exposure/reservation state (via the event stream / portfolio checkpoint events)
  and **risk-types** it against the trajectory policy, emitting a signal on breach.
- **What data RA-7 may read:** the neutral runtime event stream, portfolio
  checkpoint events, and reservation/exposure totals exposed through those neutral
  events. RA-7 does **not** reach into agent-runtime internals or import its
  engine.
- **Sequence-level rules that belong in RA-7:** cumulative-exposure-over-threshold;
  repeated near-boundary behavior; retry/loop escalation; data-access-class
  progression; context expansion (§14). These are *risk interpretations*, not
  *accounting*.
- **What stays Agent Runtime's responsibility:** the authoritative cumulative
  accounting itself (reserve/commit/ceiling), scheduling, and concurrency.

**Strong preference honored: do NOT duplicate authoritative accounting.** RA-7
reads and risk-types; Agent Runtime owns the numbers.

---

## 7. D4 — Assurance-required / failure policy (RATIFIED)

**Default model — RA-7 is event-driven and additive:**

Existing valid RA-6 authority remains governed by envelope TTL, revocation
status, status freshness, ActionGate, and the Agent Runtime pre-effect recheck.
**RA-7 unavailability does not block the hot path** — the runtime is unaffected
because the observation seam (`event_sink`) is optional and read-only (S11 in
discovery). This is the ratified default and it satisfies "avoid a global
fail-closed dependency on observer health."

**Optional high-assurance mode — IN SCOPE as an opt-in policy, NOT a default:**

For specific high-risk/consequential operations a deployment MAY mark an action
or workflow **`assurance-required`**, meaning current runtime assurance must be
present/fresh before the effect commits.

- **Is assurance-required mode in RA-7 scope now?** **Yes, as an opt-in,
  policy-bound condition — never as a default synchronous dependency.**
- **Where is it expressed?** As a **signed envelope condition** (the same
  authority-owned mechanism as `context_minimization` and `trajectory_policy_id`),
  so the requirement is authority-issued and tamper-evident. It is *not* invented
  outside the authority model. Concretely: a future additive
  `EnvelopeConditions.assurance_required: bool` (or a tier field), signed like the
  existing conditions. **This binding is deferred**; the reference milestone ships
  the default additive observer and specifies the condition, without requiring the
  schema field to exist first.
- **Is `trajectory_policy_id` enough to express it?** No — presence of a policy
  reference is not the same as *requiring live assurance before commit*. The
  assurance-required condition is a distinct, explicit flag/tier.
- **Absent assurance under assurance-required: DENY or ERROR?** When
  `assurance_required` is set and current assurance is **absent/stale**, the
  pre-effect recheck path treats it as **`ERROR_NON_EXECUTABLE`** (fail-closed,
  *not executable*), consistent with RA-6's F-1 "fail closed on authority recheck
  errors" (`agent-runtime` F-1 seam). It is **not** a silent DENY and it is **not**
  authority widening. Where a deployment prefers an explicit deny verdict, that is
  a `DENY_IF_ASSURANCE_REQUIRED` outcome (§20) — semantically equivalent
  (fail-closed), naming per deployment.
- **Granularity:** per **action** or per **workflow**, selectable by risk tier;
  bound in the envelope condition. Not global.

**Ratified:** additive event-driven default; opt-in `assurance_required` as a
signed condition; absence under that condition ⇒ fail-closed
(`ERROR_NON_EXECUTABLE` / `DENY_IF_ASSURANCE_REQUIRED`); never a global observer
health dependency.

---

## 8. D5 — Consequence granularity (RATIFIED)

**RA-7 does NOT choose the consequence.** It emits enough context for RA-6 to
decide. The ratified *defaults RA-7 requests* and RA-6's escalation latitude:

- **Default target granularity:** **targeted `revoke_envelope`** on the specific
  drifting envelope (`target_type = ENVELOPE`) — already supported by the writer.
  This invalidates the one bad trajectory without nuking the tenant.
- **Escalation rules (RA-6's decision, informed by RA-7 context):**
  - subject-wide revocation (`SUBJECT`) only if reassessment shows the issue is
    the subject, not one envelope;
  - model revocation (`MODEL`) only if the evidence implicates the model;
  - tenant epoch advance only if the issue is tenant-wide.
  RA-7 supplies references/reason codes; **RA-6 chooses breadth.**
- **Workflow-specific epoch:** **NOT needed now.** RA-6 epoch is per-tenant;
  per-workflow/per-policy epoch is a documented FUTURE item. Targeted
  `revoke_envelope` already isolates a single trajectory, so **no new workflow
  epoch is introduced.** (Prefer NO new workflow epoch — honored.)

**Ratified:** default = targeted envelope revocation via RA-6; broader
consequences only on RA-6's reassessment; no new workflow epoch.

---

## 9. D6 — Signal categories (RATIFIED)

**Decision:** **reuse the single existing category `RUNTIME_RISK_ESCALATED`** for
the reference milestone, carrying a **structured `reason` / metadata** payload
(reason codes such as `CUMULATIVE_EXPOSURE`, `NEAR_BOUNDARY_REPEAT`,
`RETRY_LOOP`, `DATA_CLASS_PROGRESSION`, `CONTEXT_EXPANSION`,
`TRAJECTORY_POLICY_DEVIATION`, `MODEL_BEHAVIOR_CHANGED`).

Rationale: `RUNTIME_RISK_ESCALATED` already exists (`authority_signal.py:51`) and
is already handled by the reference reassessor (`reassessor.py:110`). All RA-7
conditions are *runtime risk escalations*; the reassessment consequence
(reassess current state → targeted revoke / no-op) is **identical** regardless of
sub-reason, so distinct top-level categories would be **taxonomy for taxonomy's
sake**. Audit granularity is preserved by the structured reason codes.

- **When to add a category:** only if a specific condition must drive a
  *materially different reassessment policy or audit path*. None does today.
  Additional categories (e.g. `TRAJECTORY_DEVIATION`, `MODEL_BEHAVIOR_CHANGED`,
  `EXECUTION_ANOMALY`) remain a **non-breaking, additive** option for a later
  milestone if such a divergence appears.
- **Hard exclusion:** RA-8's `EXECUTION_EFFECT_MISMATCH` (or equivalent) **MUST
  NOT** be introduced by RA-7 (N7).

**Ratified:** one category (`RUNTIME_RISK_ESCALATED`) + structured reason codes;
additive expansion only on demonstrated policy divergence.

---

## 10. D7 — Telemetry producer trust (RATIFIED)

Telemetry is a **new trust boundary**. Ratified minimum trust model:

**Required bindings on every ingested observation (rejected fail-closed if
missing/unparseable):**

| Field | Purpose |
|---|---|
| `tenant_id` | tenant isolation — cross-tenant telemetry cannot affect another domain |
| `workflow_instance_id` | trajectory key (§11) |
| `envelope_id` (authority correlation) | ties the observation to the authority being assessed |
| `action_id` / `task_id` | positions the event within the trajectory |
| `event_id` | dedupe / replay defense (reuses RA-6 intake dedupe semantics) |
| `observed_at` | staleness evaluation |
| `source` + `source_version` | producer identity + policy/version pinning |
| `sequence_number` (when ordering matters) | out-of-order / gap detection |
| `trajectory_policy_id` / `trajectory_version` | policy pinning |
| `payload_digest` (when payload integrity matters) | tamper-evidence for the event body |

**Producer authentication — Option B (authenticated deployment ingress seam):**

Producer authentication is **delegated to a deployment ingress seam**, mirroring
RA-5 trusted-evidence ingress and RA-6 lifecycle-write authorization posture. The
reference milestone does **NOT** claim cryptographic per-event telemetry signing
(Option A) — that would be an overclaim, since no such signing is implemented.
Option C (trusted process-local channel) is a valid *deployment* of the same
seam; Option D (configurable) is the umbrella. Ratified as **B, configurable to C
in trusted-colocated deployments** — stated openly.

**Telemetry behavior semantics (fail-safe, never authority-widening):**

- **Replay / duplicate:** deduped by `event_id` (RA-6 intake semantics reused) ⇒
  `IGNORE_EVENT`.
- **Out-of-order:** ordered by `sequence_number` / `observed_at`; a late event
  reassesses current state ⇒ converges, never widens.
- **Stale telemetry:** past a freshness bound ⇒ observation is `UNKNOWN`; under
  `assurance_required` this drives fail-closed (§7), otherwise additive-ignore.
- **Wrong tenant / workflow / envelope:** binding mismatch ⇒ **rejected**, cannot
  touch another authority domain (I7).
- **Untrusted / unauthenticated producer:** rejected at the ingress seam;
  worst-case forged-but-authenticated telemetry can only cause an *unnecessary*
  revocation (fail-safe over-revocation), never authority widening (I6).

**Ratified:** authenticated ingress seam (B), explicit minimum bindings,
RA-6-style dedupe/replay defense, no crypto-telemetry overclaim.

---

## 11. Canonical definition of "trajectory"

> A **trajectory** is the **ordered sequence of runtime events and
> authority-relevant state transitions for a single workflow instance**, derived
> from the existing Agent Runtime `RuntimeEvent` stream, comprising: proposed
> action → authorized action → attempted action → completion/failure; tool
> usage; destinations; data-access-class progression; cumulative resource /
> exposure consumption (read from the portfolio ledger); autonomy changes;
> retries / loops; context expansion; and the bound `trajectory_policy_id` /
> `trajectory_version`.

**It explicitly excludes post-effect reconciliation** — that is RA-8 (D1).

- **Canonical trajectory key:** `(tenant_id, workflow_instance_id)`, correlated to
  `envelope_id`. Agent Runtime is the canonical owner of *execution trajectory
  identity* (`models/execution_state.py`).
- **Required event ordering:** ordered by `sequence_number` / `observed_at`;
  out-of-order events are re-sequenced, gaps are detectable.
- **Partial trajectories are VALID.** RA-7 is event-driven; it assesses on the
  events it has. A partial view yields `NORMAL` or `UNKNOWN`, never a fabricated
  escalation.
- **Events may be missing.** Missing segments ⇒ `UNKNOWN` for the affected window
  (never authority widening).
- **Persistent trajectory storage is NOT required** for the reference evaluator
  (§24). RA-7 derives the trajectory from the existing runtime event history /
  external telemetry store and stays stateless where possible.

**Deriving from existing events — not a second execution ledger — is ratified.**

---

## 12. Trajectory assessment semantics

RA-7 produces a **`TrajectoryAssessment`** — **evidence/verdict, not machine
authority.** It uses a neutral result vocabulary (**not** ALLOW/DENY):

- `NORMAL` — trajectory consistent with authority assumptions.
- `ESCALATED` — material deviation; RA-7 emits a signal.
- `UNKNOWN` — insufficient/stale/missing observation; no fabricated verdict.

**Fields (only those with trust/audit purpose):**

| Field | Purpose |
|---|---|
| `assessment_id` | idempotent identity / audit |
| `tenant_id`, `workflow_instance_id` | trajectory key |
| `envelope_id` | authority correlation |
| `trajectory_policy_id` / `trajectory_version` (`+ digest` when D2 lands) | policy pinning |
| `observed_window` | which events were considered |
| `risk_level` (§13) | observation, not authority |
| `reason_codes` | structured cause (feeds signal metadata, §9) |
| `supporting_event_refs` | `event_id`s substantiating the verdict |
| `produced_at` | ordering / staleness |
| `evaluator_identity` + `evaluator_version` | provenance / reproducibility |

**Persistence:** RA-7 **remains event-driven / stateless** for the reference
milestone (§24). An assessment is a transient verdict; only its emitted signal
(if material) becomes durable, inside RA-6's audited intake. **The assessment
itself is never machine authority** (I9).

---

## 13. Runtime risk level (minimal)

Ratified enum — the **three-value** form:

- `NORMAL` — no deviation.
- `ESCALATED` — material deviation warranting a signal.
- `UNKNOWN` — cannot assess.

Intermediate levels (`ELEVATED` / `CRITICAL`) are **rejected for now**: they
create no *real policy difference*, because RA-6's consequence for any material
escalation is the same (reassess current state → targeted revoke / no-op).
Introducing severity tiers would duplicate Risk Authority's own risk
classification without changing behavior. **RA-7 risk level is an observation, not
authority** (I9). If a future consequence genuinely differs by severity, a tier
may be added additively.

---

## 14. Context Minimization boundary (RATIFIED)

- **Context Minimization owns context policy/enforcement.** `context_minimization`
  is a *signed envelope condition* (`envelope.py:30`) — authority-owned, enforced
  via runtime `required_conditions`.
- **RA-7 may OBSERVE context expansion/deviation** beyond the minimized set and
  *signal* it (reason code `CONTEXT_EXPANSION`).
- **RA-7 does NOT become the context-policy owner** and does not enforce it.
- **In the minimum RA-7 trajectory policy?** Context expansion is included as an
  **observable dimension** but its enforcement remains authority/runtime-owned; a
  breach *may* produce a runtime-risk signal. Deep context-policy integration is a
  **future** refinement, not a reference-milestone requirement.

---

## 15. ACP boundary (RATIFIED — separate)

ACP is **spec-only/unimplemented** (`Project_documentation/control_plane/acp/*.md`).

- **Risk Authority:** "Is the system permitted to operate within this capability
  boundary?"
- **RA-7:** "Is observed runtime behavior still consistent with the
  assumptions/policy behind that authority?" (observe → signal)
- **ACP:** "For a physical autonomous control loop, what exact safe control action
  should be taken *now*?"

**RA-7 MUST NOT** choose actuator commands, perform per-tick motion/control
optimization, or replace ACP safety constraints (N6). Future ACP may *consume* RA
authority and RA-7 live assurance/risk state, and may *emit* runtime observations;
ACP nonetheless **remains a separate subsystem** — two distinct consumers, neither
granting the other's authority.

---

## 16. ActionGate boundary (RATIFIED)

- **ActionGate:** "Does *this exact action* fit the signed authority?" (per-action,
  read-only, stateless w.r.t. history).
- **RA-7:** "Does the *sequence* of otherwise-authorized actions remain
  acceptable?" (stateful, sequence-level).

RA-7 MUST NOT duplicate exact-scope matching, duplicate envelope verification, or
authorize actions (N5). ActionGate MAY *eventually* consume a current
runtime-assurance requirement/state — **only** under the D4 `assurance_required`
opt-in (§7) — but that is a consumer relationship, not RA-7 becoming a gate.

---

## 17. Agent Runtime boundary (RATIFIED)

Agent Runtime remains the **execution/orchestration owner** and stays
concrete-free (its `src` imports nothing from `risk_authority` — grep clean). It
**provides** (all already present): the neutral event sink; workflow-instance
identity; event ordering; budget/resource state; checkpoint/recovery events.

Agent Runtime **MUST NOT**: contain Risk-Authority-specific policy; contain the
trajectory-risk evaluator; mint RA-7 signals directly; or depend concretely on
Risk Authority packages. **RA-7 integration subscribes/observes through the
existing neutral `event_sink` seam** — no agent-runtime change is required for the
core observe→signal loop. (An optional neutral "assurance-required" hook is the
*only* possible future agent-runtime touch, and only under D4.)

---

## 18. RA-6 signal handoff (RATIFIED — reuse as-is)

```
TrajectoryAssessment (RA-7, neutral evidence)
   → if material →
AuthorityReassessmentSignal
     change_type = RUNTIME_RISK_ESCALATED
     target_type = ENVELOPE            (default; SUBJECT/MODEL only on RA-6 reassessment)
     references  = assessment_id + supporting_event_refs
     reason      = structured reason codes (§9)
   → AuthorityReassessmentSignalPort.submit  (authority_lifecycle.py:207)
   → AuthorityReassessor (validate + dedupe by event_id + reassess CURRENT state)
   → AuthorityLifecycleService (sole authenticated writer) → targeted revoke / no-op
   → StatusAwareActionGate / pre-effect recheck enforce at next consequential commit
```

**No direct call from RA-7 to `revoke_envelope` / `advance_epoch` /
`revoke_subject` / `revoke_model`.** All consequence flows through the writer via
the reassessor (I3, I4).

---

## 19. RA-8 boundary / reconciliation (RATIFIED — future, separate)

RA-8 owns **effect-level closure.** Candidate inputs: `ExecutionRecord`,
`ExecutionReceipt`, actual effect, authorized intent/action, provider result,
external system state. Candidate output: reconciliation / effect-mismatch →
`AuthorityReassessmentSignal` → RA-6.

**RA-7 stops at provider-invocation / execution-completion events** and does NOT
claim to verify real-world effect (no such verification exists in live code, N7).
RA-8 = wire DA's already-modeled reconciliation to the runtime effect + feed
mismatches back as RA-6 signals. Not implemented here.

---

## 20. Canonical failure matrix

No failure may cause authority widening (I5, I6). Outcomes reuse existing
terminology where possible.

| Condition | Outcome | Rationale |
|---|---|---|
| Telemetry producer unavailable | `CONTINUE_UNDER_RA6` (additive) / `DENY_IF_ASSURANCE_REQUIRED` | default additive; fail-closed only under D4 |
| Observer unavailable | `CONTINUE_UNDER_RA6` | observation seam is optional/read-only (S11) |
| Trajectory policy unavailable | `UNKNOWN_ASSESSMENT` → `NO_SIGNAL` / `DENY_IF_ASSURANCE_REQUIRED` | cannot assess; fail-closed only under D4 |
| Unknown trajectory-policy version | `UNKNOWN_ASSESSMENT` | cannot pin policy; never fabricate escalation |
| Telemetry stale | `UNKNOWN_ASSESSMENT` (+ D4 fail-closed) | freshness bound exceeded |
| Telemetry malformed | `IGNORE_EVENT` | rejected at ingress; cannot mutate |
| Wrong tenant | `IGNORE_EVENT` | binding mismatch (I7) |
| Wrong workflow | `IGNORE_EVENT` | binding mismatch |
| Wrong envelope | `IGNORE_EVENT` | binding mismatch |
| Duplicate event | `IGNORE_EVENT` | deduped by `event_id` (I8) |
| Out-of-order event | re-sequence → reassess current state | converges (S12) |
| Missing sequence segment | `UNKNOWN_ASSESSMENT` for the window | never widen |
| Evaluator error | `UNKNOWN_ASSESSMENT` / `ERROR_NON_EXECUTABLE` under D4 | fail-safe |
| RA-6 signal sink unavailable | retry/queue; assessment stands as evidence | consequence deferred, authority unchanged |
| RA-6 reassessment unavailable | `NO_SIGNAL` effect; existing RA-6 gates still govern | never widen |

Outcome vocabulary: `IGNORE_EVENT`, `UNKNOWN_ASSESSMENT`, `NO_SIGNAL`,
`SIGNAL_REASSESS`, `ERROR_NON_EXECUTABLE`, `CONTINUE_UNDER_RA6`,
`DENY_IF_ASSURANCE_REQUIRED`.

---

## 21. Security invariants (ratified)

- **I1.** RA-7 never mints machine authority.
- **I2.** `RiskAuthorizationEnvelope` remains the sole signed machine authority.
- **I3.** RA-7 never mutates RA-6 lifecycle state directly.
- **I4.** All authority consequences route through RA-6's authenticated writer.
- **I5.** Observer failure cannot widen authority.
- **I6.** Malformed telemetry cannot grant/widen authority.
- **I7.** Wrong-tenant/workflow/envelope telemetry cannot affect another authority
  domain.
- **I8.** Duplicate/out-of-order telemetry cannot create authority.
- **I9.** Trajectory assessment is evidence/verdict, not authorization.
- **I10.** ActionGate remains exact-action authority enforcement.
- **I11.** Agent Runtime remains execution owner.
- **I12.** ACP remains separate.
- **I13.** RA-8 remains the post-effect/reconciliation boundary.
- **I14.** Risk Authority leaf remains provider/telemetry independent (stdlib-only).
- **I15.** No new signed authority artifact.
- **I16.** RA-7 cannot trigger `TENANT_EMERGENCY_STOP` (refused on observer path).

---

## 22. Package ownership (ratified)

**Location: `packages/integration/risk-authority-runtime-assurance/`** — a sibling
integration package, identical posture to `risk-authority-status-runtime`.

Dependency direction:

```
risk_authority (stdlib-only leaf)
      ▲
risk-authority-status-runtime            (RA-6; neutral signal + reassessor + writer)
      ▲
risk-authority-runtime-assurance         (RA-7; observer + evaluator + telemetry ingress)
      │  observes ▼ (through neutral event interfaces / stable data contracts only)
agent-runtime                            (never imports RA)
```

- RA-7 depends on `ugence-risk-authority` (for the neutral signal types) and the
  RA-6 status-runtime intake — **not** the reverse.
- **DO NOT** create `risk_authority → runtime-assurance`.
- **DO NOT** force `agent-runtime` to import RA. If RA-7 needs Agent Runtime domain
  contracts, prefer **neutral/stable protocol/data contracts** (the event schema),
  not concrete engine ownership.

---

## 23. Minimum contracts (architecture only — no code)

| Contract | Owner | Producer | Consumer | Persisted? | Trust | Replay | Authority | Failure |
|---|---|---|---|---|---|---|---|---|
| `RuntimeAssuranceObserver` | RA-7 pkg | subscribes to `event_sink` | internal evaluator | transient | reads neutral events | dedupe by `event_id` | none | observer down ⇒ additive |
| `TrajectoryObservation` | RA-7 pkg | telemetry ingress / event sink | evaluator | transient | validated bindings (§10) | dedupe/order | none | malformed ⇒ `IGNORE_EVENT` |
| `TrajectoryAssessment` | RA-7 pkg | evaluator | signal handoff / audit | transient (stateless ref) | evidence only | idempotent by `assessment_id` | **none (I9)** | error ⇒ `UNKNOWN` |
| `RuntimeRiskLevel` | RA-7 pkg | evaluator | assessment | value | observation | n/a | none | n/a |
| `TrajectoryPolicyRef` | RA (bound) / WorkflowIR (content) | authority-signed | evaluator (reader) | signed in envelope | authority-bound id (+ digest, D2) | n/a | references, not grants | unknown ⇒ `UNKNOWN` |
| Telemetry ingress port | RA-7 pkg | deployment producers | observer | transient | authenticated seam (B, §10) | dedupe/order | none | untrusted ⇒ reject |
| Trajectory policy reader | RA-7 pkg | reads WorkflowIR policy | evaluator | n/a | integrity via digest (D2) | n/a | none | missing ⇒ `UNKNOWN` |
| **Handoff:** `AuthorityReassessmentSignal` | **RA-6 (reuse as-is)** | RA-7 | RA-6 reassessor | durable (RA-6 audit) | neutral, no ALLOW/scope | dedupe by `event_id` | **routes consequence, does not grant** | sink down ⇒ retry/queue |

**No contract grants authority.**

---

## 24. Persistence decision (ratified)

**RA-7 needs no canonical state store for the reference milestone.** It reuses the
existing Agent Runtime event history / external telemetry store and keeps the
reference evaluator **stateless** where possible.

- Dedupe / ordering: reuse RA-6 intake semantics (`event_id`) and telemetry
  `sequence_number` — no new ledger.
- Trajectory window / cumulative risk state: derived on demand from the event
  stream + portfolio ledger; may be held **transiently** in a bounded in-memory
  window.
- Assessment audit: the *material* outcome is already durably recorded inside
  RA-6's audited intake; the transient assessment need not be separately persisted.

**Do NOT create a second canonical execution ledger** (N-equivalent to N8). If a
deployment needs durable assessment history, that is deployment-local persistence,
defined as minimum state only, and still not a second authority artifact.

---

## 25. Signal latency / maturity (honest terminology)

Ratified claim: **"event-driven runtime assurance that can cause previously-valid
machine authority to be reassessed and invalidated."** **NOT** "continuous
real-time authority" or "zero-window revocation."

```
behavior event → observer/evaluator → signal → RA-6 reassessment → lifecycle
update → status-cache propagation → enforcement at next consequential commit
```

Latency is **bounded but non-zero.** The revocation *bites* at the next pre-effect
recheck / freshness re-read, not instantaneously. This is stated openly; RA-7 does
not claim zero-window revocation.

---

## 26. Threat model

| Threat | Owner | Mitigation | Residual | RA-7 / deploy / future |
|---|---|---|---|---|
| Forged telemetry | RA-7 ingress + RA-6 authz | authenticated ingress seam; worst case = fail-safe over-revocation | availability, not authority breach | RA-7 + deploy |
| Compromised observer | RA-6 | neutral signal (no ALLOW); writer authz | over-revocation only | RA-6 (structural) |
| Delayed telemetry | RA-7/RA-6 | reassess current state; freshness bound | bounded-latency window | RA-7 |
| Missing telemetry | RA-7 | `UNKNOWN`; D4 fail-closed if required | blind window (additive default) | RA-7 + deploy |
| Replayed telemetry | RA-7/RA-6 | dedupe by `event_id` | none | RA-7 |
| Out-of-order telemetry | RA-7 | re-sequence; converge | none | RA-7 |
| Trajectory-policy substitution | RA (D2) | authority-bound `trajectory_policy_id` + digest | pre-digest envelopes ⇒ `UNKNOWN` | future (digest) |
| Stale policy version | RA-7 | version pin; `UNKNOWN` on mismatch | none | RA-7 |
| Adversarial retry loops | RA-7 | retry/loop reason code → signal | detection latency | RA-7 |
| Many-safe-actions cumulative unsafe | RA-7 | read portfolio ledger; risk-type; signal | threshold tuning | RA-7 |
| Monitor gaming | RA-7 + deploy | multiple observation dimensions; policy tuning | sophisticated evasion | future |
| False-positive escalation | RA-6 | fail-safe: only restricts/reassesses | availability cost | RA-6 (structural) |
| False-negative assessment | RA-7 + deploy | additive default + RA-6 gates still govern | undetected drift | RA-7 + future |
| Signal flooding | RA-7/RA-6 | dedupe + rate control at ingress | availability | RA-7 + deploy |
| Cross-tenant telemetry injection | RA-7 | tenant binding check ⇒ reject (I7) | none | RA-7 |
| Old-envelope telemetry replay | RA-6 | idempotent grow-only revocation | none | RA-6 |
| Observer unavailable | — | additive default; runtime unaffected | blind window | RA-7 |
| Policy store unavailable | RA-7 | `UNKNOWN`; D4 fail-closed if required | additive default | RA-7 + deploy |

---

## 27. Future adversarial (deny-heavy) test matrix — for the eventual implementation

1. normal trajectory → no signal
2. explicit deviation → assessment `ESCALATED`
3. escalated assessment → RA-6 signal emitted
4. observer cannot revoke directly (structural)
5. observer cannot mint authority (structural)
6. malformed telemetry → `IGNORE_EVENT`
7. stale telemetry → `UNKNOWN`
8. duplicate telemetry → deduped
9. out-of-order telemetry → re-sequenced, converges
10. wrong tenant → rejected
11. wrong workflow → rejected
12. wrong envelope → rejected
13. wrong policy version → `UNKNOWN`
14. missing policy → `UNKNOWN`
15. policy substitution → detected via digest (D2)
16. cumulative-risk violation ($9k×10) → signal
17. repeated near-boundary → signal
18. retry-loop escalation → signal
19. context-expansion deviation → signal
20. model-behavior change → signal (reason code)
21. telemetry unavailable → additive default / D4 fail-closed
22. observer unavailable → runtime unaffected
23. RA-6 unavailable → no widen; existing gates govern
24. false-positive signal only restricts/reassesses
25. recovery to normal does NOT resurrect old envelope (grow-only)
26. new reassessment may issue a *new* envelope
27. signal after envelope revoked → idempotent
28. signal after envelope expired → idempotent
29. RA-4.5 / RA-5 / RA-6 unchanged
30. Agent Runtime unchanged without observer
31. ActionGate remains exact-action gate
32. ACP remains separate
33. RA-8 reconciliation not pulled into RA-7
34. no second authority artifact
35. RA leaf independently installable (stdlib-only)

---

## 28. Platform value (no overclaim)

Beyond logging / APM / SIEM / observability (passive record), static agent
guardrails (per-prompt), per-action ActionGate, and IAM/session tokens (identity,
not behavior), the RA-6 + RA-7 pair enables one property those do not:

> **Runtime behavior can trigger reassessment of previously-valid, cryptographically
> signed machine authority** — a closed loop from observed trajectory to authority
> lifecycle.

**Not claimed:** real-time continuous authorization; zero-latency revocation;
physical control safety (ACP); post-effect correctness (RA-8);
cryptographically-attested telemetry. RA-7 is **event-driven and reference-grade**
(delegated persistence and producer trust).

---

## 29. Architecture verdict

**`RA7_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`.**

All seven authority-critical decisions are fully resolved with no vague
authority-critical placeholders:

| Decision | Resolution |
|---|---|
| **D1** RA-7/RA-8 boundary | RA-7 = pre-completion trajectory observation; RA-8 = post-effect reconciliation (DA primitives); RA-7 consumes runtime events only, never receipts (§4) |
| **D2** trajectory-policy ownership/integrity | WorkflowIR owns content; `trajectory_policy_id`/`version` already authority-bound; add non-breaking `trajectory_policy_digest` (deferred, additive) (§5) |
| **D3** sequence-risk source | Option A — observe existing portfolio ledger, risk-type externally; do not duplicate accounting (§6) |
| **D4** assurance-required failure policy | additive event-driven default; opt-in signed `assurance_required` condition ⇒ fail-closed; no global observer dependency (§7) |
| **D5** consequence granularity | default targeted `revoke_envelope`; RA-6 chooses breadth; no new workflow epoch (§8) |
| **D6** signal categories | reuse `RUNTIME_RISK_ESCALATED` + structured reason codes; additive expansion only on demonstrated divergence (§9) |
| **D7** telemetry producer trust | authenticated ingress seam (Option B); explicit minimum bindings; no crypto-telemetry overclaim (§10) |

RA-7 is ready for implementation as a sibling integration package that observes
the existing neutral runtime event seam and emits neutral signals into the
already-built RA-6 intake. No RA-leaf / Agent-Runtime / ActionGate / RA-6 change is
required for the core observe→signal loop.

---

*Documentation only. No production code changed; no RA-7 implementation started;
no RA-leaf / Agent-Runtime / ActionGate / RA-6 modification; no RA-8 or ACP
implementation; no telemetry infrastructure added; no PR opened.*
