# RA-7 — Runtime / Trajectory Assurance — Architecture Discovery Plan

> **Status: DISCOVERY (not ratified).** This is an architecture-discovery companion, **not** a
> canonical implementation-ready specification. It records what RA-7 *could* be, grounded in the
> live post-RA-6 codebase, and enumerates the authority-critical decisions that must be ratified
> before any RA-7 SPEC/ADR is written or any code is implemented.
>
> **Verdict of this discovery: `RA7_ARCHITECTURE_DECISION_REQUIRED`.** The direction is clear
> (an observer that *signals*, never a second authority); several scope decisions remain open (§13).
>
> **Baseline:** default branch `claude/setup-symbolu-monorepo-…` @ `e6aa6edf` (RA-6 merge, PR #1412;
> merge parents `ad3a2a46` + audited head `948f1018`). RA-6 smoke on this baseline: RA leaf 113,
> status-runtime 72, agent-runtime `authority_recheck` (F-1) 21 — green.

---

## 0. Why this document exists (and what it is not)

There is **no canonical RA-7 definition anywhere in the repo.** RA-7 is never written as "RA-7 = X".
The roadmap names a single *undivided* post-RA-6 capability bundle — Runtime Assurance, Trajectory
Control, Context Minimization, Third-Party Gateway, ACP, Reconciliation, GRC dashboards — without
assigning any item to RA-7 vs RA-8 (`packages/risk_authority/README.md:31-33`;
`docs/architecture/RISK_AUTHORITY_RA5_SPEC.md:108-110`;
`docs/architecture/RISK_AUTHORITY_RA6_SPEC.md:675-682` §18;
`docs/architecture/RISK_AUTHORITY_RA6_IMPLEMENTATION_PLAN.md:84-87` §D). The consolidated
"spec §35 roadmap" that these docs cite **does not exist in-repo**
(`RISK_AUTHORITY_RA5_TAP_CONTROL_ASSURANCE_PLAN.md:60-63`).

Therefore **"RA-7 = Runtime/Trajectory Assurance" is a plausible but uncanonized reading.** We are
*defining*, not rediscovering. This document deliberately produces discovery material only.

**Candidate one-line framing (to be tested, not assumed):**
> *"While an authorized agent/system is operating, is its runtime trajectory still consistent with
> the assumptions, constraints, and authority under which it was allowed to operate — and if not,
> can that behavior cause the still-valid machine authority to be reassessed?"*

RA-7 answers a **behavior-over-time** question. It is distinct from:
- **ActionGate** — "is *this one action* inside the signed scope?" (per-action, offline, read-only).
- **RA-6** — "is the authority *still valid* (revoked / stale-epoch / expired)?" (authority lifecycle).
- **ACP (Autonomous Control Plane)** — "for a real-time physical actuator, which *single* control
  action is safe *right now*?" (per-control-tick robotics; §8).
- **RA-8 (candidate)** — "did the *completed effect* match what was authorized?" (reconciliation; §11).

---

## 1. The gap RA-7 fills (the one real finding)

The RA-6 observer→authority feedback **seam is fully built but has no producer**:

- `AuthorityReassessmentSignal` — the neutral, authority-free type an observer may emit toward Risk
  Authority (`risk_authority/domain/authority_signal.py:78-133`). Its docstring already names
  *"Runtime Assurance, telemetry"* as intended emitters.
- `SignalChangeType.RUNTIME_RISK_ESCALATED` already exists as a category
  (`authority_signal.py:37-52`) and is already handled by the reference decider
  (`…status-runtime/reassessor.py:107-126`).
- `AuthorityReassessmentSignalPort.submit` exists and `AuthorityReassessor` implements it
  (`authority_lifecycle.py:199-207`, `reassessor.py:150-205`), routing every consequence through the
  authenticated `AuthorityLifecycleService` (the sole writer).

**But every construction of a signal and every `.submit()` call is in tests.** No non-test producer
exists; `agent-runtime` imports **nothing** from `risk_authority`. The loop
`runtime behavior → signal → reassess → revoke/epoch → enforce` is **open at the first hop only** —
the producer. **RA-7 is that missing producer.**

---

## 2. What already exists (reuse, do not duplicate)

| Capability | Where it lives | RA-7 relevance |
|---|---|---|
| Neutral observer→authority signal + intake + reassessor + `RUNTIME_RISK_ESCALATED` | `risk_authority/domain/authority_signal.py`, `…status-runtime/reassessor.py` | **The RA-7 handoff. Reuse as-is.** |
| Sole authenticated writer (epoch/targeted revoke), tenant-isolated, idempotent, audited | `…status-runtime/writer.py:112` | RA-7 consequence path — **RA-7 never writes; the writer does.** |
| Bounded-stale offline status reader + pre-effect recheck (RA-6 §8) | `…status-runtime/enforcement.py` | Makes an RA-7-triggered revocation *bite* at the next consequential commit point. |
| Deterministic neutral runtime event stream (`PROVIDER_INVOKED/COMPLETED`, `TASK_*`, `CHECKPOINT_COMMITTED`, …), digest-sealed | `agent-runtime/models/events.py:14-66`; optional `event_sink`/`event_store` (`config.py:61-62`, default `None`) | **The RA-7 observation input — consumable via the existing `event_sink` with zero runtime changes.** |
| Canonical execution-state journal + self-verifying checkpoints | `agent-runtime/runtime/engine.py:686-742` | Trajectory identity + replay; "Agent Runtime is the canonical owner of *execution trajectory identity*" (`models/execution_state.py:4-5`). |
| Cumulative/portfolio budget ledger (reserve-before-execute, shared ceiling) | `agent-runtime/orchestration/budgets.py:48-285`, `portfolio.py`, `resources.py`, `scheduling.py`, `concurrency.py` | Sequence/cumulative accounting exists — but as generic orchestration budget that "decides nothing about governance." (§10) |
| Effect record + intent-vs-effect **reconciliation** + compensation | `capabilities/decision-authority/execution/*`, `services/reconciliation_service.py` | This is the **RA-8** concept (completed-effect verification) — already modeled, **unwired** from the runtime. (§11) |
| `trajectory_policy_id` (envelope condition), `trajectory_version` (authorization), threaded through ActionGate | `envelope.py:32`, `actions.py:56`, `integrations/actiongate.py:56,77,178` | **Declared and threaded, but consumed by no evaluator.** ActionGate treats `trajectory_version` as a passthrough label. (§9) |
| `context_minimization: bool` as a signed **envelope condition** | `envelope.py` (`EnvelopeConditions`) | Context policy is **authority-owned**, not RA-7-owned. (§12) |

**Absent (the genuine RA-7 greenfield):** a runtime-risk / trajectory / drift / anomaly *evaluator*;
a *producer* of `AuthorityReassessmentSignal`; sequence-level *risk* (as opposed to resource) typing;
and any wiring from execution behavior back to Risk Authority.

---

## 3. Current post-authorization runtime flow (traced from code)

```
RiskAuthorizationEnvelope (Ed25519, sole signed authority)
  → RA-4.5 governance composition  (GovernedExecutionDecision; FinalAuthority ≤ RiskAuthority)
  → ActionGate / StatusAwareActionGate  (per-action, READ-ONLY; freshness gate + envelope verify)
  → Agent Runtime engine  (concrete-free; governance_hook + optional authority_recheck seams)
      → validate_clearance  (fingerprint/expiry/correlation + LAST: pre-effect authority_recheck)  ← last authority contact
      → provider.execute (execute_with_policy)  ← irreversible effect
      → PROVIDER_COMPLETED / TASK_COMPLETED events (digests only) + self-verifying checkpoint
  → [ nothing re-touches authority after the effect ]
```

Key properties (all verified in code):
- **Concrete-free runtime.** `agent-runtime/src` imports nothing from `risk_authority`/`decision_authority`/`actiongate`.
- **Pre-effect recheck is the last authority touch** (`engine.py:546-548` → before `_execute` at `562`/`637`). After `provider.execute` returns, the output is held **in memory only** (`ti.result`); there is **no receipt, no effect record, no reconciliation, nothing signed** on the runtime side (checkpoints are *hash-sealed*, not signed).
- **Sole writer confirmed.** Only `AuthorityLifecycleService` mutates epoch/revocation; enforcement + reassessor are structurally read-only / route-through-writer.

---

## 4. Defining "trajectory" precisely (minimum representation)

"Trajectory" must not be used vaguely. In Ugence the **minimum RA-7 trajectory** can be *derived from
signals that already exist* — RA-7 needs **no large new telemetry schema**:

| Dimension | Already observable from | Notes |
|---|---|---|
| Sequence of authorized/executed actions | `PROVIDER_INVOKED/COMPLETED` + `ActionAuthorization` verdicts | ordered, per workflow-instance |
| Scope consumption vs envelope scope | `CanonicalAction` fields vs `RiskAuthorizationEnvelope` scope | amount / destination / data-class progression |
| Cumulative exposure across the sequence | `PortfolioBudget`/`BudgetCoordinator` reservations | resource-typed today, not risk-typed |
| Workflow-stage progression | `TASK_*`/`WORKFLOW_*` events + WorkflowIR | stage graph already exists |
| Retry / loop behavior | `ti.attempts`, `FailureCategory` (`RETRY_EXHAUSTED`, `TIMEOUT`) | adversarial-retry signal |
| Context expansion | `EnvelopeConditions.context_minimization` + required_conditions | deviation = context growth (§12) |
| Trajectory-policy conformance | `trajectory_policy_id` (signed condition) vs observed path | policy currently unenforced (§9) |
| Model-behavior change | model_digest + external model telemetry | needs a producer; maps to `MODEL_INVALIDATED`/new category |

**Minimum RA-7 trajectory = the ordered per-workflow-instance action/scope/exposure sequence derived
from the existing `RuntimeEvent` stream + envelope scope + portfolio ledger.** Anything beyond this is
opt-in and must be justified per deployment.

---

## 5. Central scenarios (S1–S15): what happens today

| # | Scenario | Today | Safe? | Who sees it | Missing capability |
|---|---|---|---|---|---|
| S1 | Valid authority, action sequence drifts toward prohibited outcome | Each action re-checked by ActionGate; **no sequence view** | Partial — a *single* out-of-scope action is denied; a *drift within scope* is not seen | ActionGate (per action only) | trajectory evaluator + signal |
| S2 | Each action individually authorized, cumulative sequence risky ($9k×10) | Portfolio budget *could* cap cumulative spend if configured, but it is orchestration budget, "decides nothing about governance" | Partial/No | orchestration budget (non-authority) | sequence-level **risk** typing + signal |
| S3 | Repeated near-ceiling behavior | Not detected (each action passes) | No | none | near-boundary pattern detector → signal |
| S4 | Tool sequence deviates from expected workflow trajectory | `trajectory_policy_id` carried but **unenforced** | No | nobody (field unused) | trajectory-policy evaluator |
| S5 | Data-access path moves into more sensitive domain | ActionGate checks each action's data-class; **progression** unseen | Partial | ActionGate per-action | progression detector → signal |
| S6 | Model behavior changes post-deployment | `MODEL_INVALIDATED` / model-revoke exist as *consequences*; no detector | No (no producer) | none | model-behavior observer → signal |
| S7 | Telemetry reports anomaly while authority valid | No intake of runtime anomaly today | No | none | `EXECUTION_ANOMALY` producer → signal |
| S8 | Unusual retry/loop increasing risk | `ti.attempts`/`RETRY_EXHAUSTED` recorded; **not** risk-signaled | Partial (fails the task on exhaustion) | agent-runtime | retry-risk observer → signal |
| S9 | Autonomy-escalation attempt | Out-of-scope action denied by ActionGate; *gradual* escalation unseen | Partial | ActionGate | escalation-pattern observer |
| S10 | External environment changes mid-task | Evidence/policy invalidation categories exist; **no producer** wired | No | RA-6 (if signaled) | environment observer → signal |
| S11 | Runtime-assurance observer unavailable | No dependency exists yet; runtime unaffected | Safe (additive) | n/a | fail-closed *policy* if assurance required (§13-D4) |
| S12 | Telemetry delayed/out-of-order | RA-6 intake dedupes by `event_id`, reassesses current state → converges | Safe (by RA-6 design) | reassessor | reuse RA-6 intake semantics |
| S13 | Compromised/false-alarm producer | RA-6 signal is neutral — worst case = *unnecessary* revocation (fail-safe), never widening | Safe-ish (availability risk, not authority breach) | reassessor + writer authz | producer trust seam (§14) |
| S14 | Risk rises then returns to normal | Targeted revoke is **grow-only**; recovery needs a **new envelope** (RA-6 I5) | Safe (no silent un-revoke) | RA-6 | new-envelope issuance path |
| S15 | Trajectory signal arrives after the effect already happened | Pre-effect recheck already passed; effect is done; next consequential action will see the revocation | Bounded — RA-7 is **event-driven, not zero-window** (§ latency) | RA-6 status cache | RA-8 reconciliation for the *completed* effect |

**Conclusion:** for almost every scenario the *consequence machinery already exists in RA-6*; what is
missing is the **observation + signal production** and, for S2/S3, **sequence-level risk typing**.

---

## 6. Observer-vs-authority ownership (preserved invariant)

```
Runtime/Trajectory observer (RA-7)  →  AuthorityReassessmentSignal (neutral)
   →  RA-6 AuthorityReassessor (validate + dedupe + reassess CURRENT state)
   →  AuthorityLifecycleService (sole authenticated writer)  →  targeted revoke / epoch / no-op
   →  StatusAwareActionGate / pre-effect recheck enforce at next consequential commit
```

The RA-7 observer **MUST NOT**: mint a `RiskAuthorizationEnvelope`; widen scope; return a binding
ALLOW; create a second authority token; or mutate revocation/epoch directly. This is already
*structurally* enforced: the signal type has no ALLOW/scope field, and only the authenticated writer
mutates state.

**Emergency stop:** RA-6 already separates a privileged direct-write `emergency_stop`
(`writer.py`, `EMERGENCY_STOP_CAPABILITY`) from the ordinary observer intake, and the reassessor
**refuses `TENANT_EMERGENCY_STOP` on the observer path** (`reassessor.py`). Therefore an ordinary RA-7
observer signal **cannot** trigger emergency stop. If deployments want observer-initiated emergency
stop, it must go through a **separately privileged emergency-control path** (a principal holding
`EMERGENCY_STOP_CAPABILITY`), *not* the signal path. **Recommendation: keep RA-7 on the signal path
only; emergency stop stays a separate privileged control.**

---

## 7. Is RA-7 "Trajectory Control"? — Option analysis

| Option | Verdict |
|---|---|
| A. Runtime Assurance observer only | Necessary but incomplete (doesn't state the trajectory dimension). |
| B. Trajectory risk *evaluator* | Core of RA-7. |
| C. Trajectory policy *enforcement* (blocks actions itself) | **Rejected** — would make RA-7 a second enforcer/authority. Enforcement stays with ActionGate/RA-6. |
| D. Runtime control loop that directly stops actions | **Rejected** — violates observer/authority separation; that is ACP's job for physical systems. |
| **E. Observer + evaluator producing signals into the RA-6 seam** | **RECOMMENDED.** "Observe trajectory" ≠ "authorize trajectory" ≠ "control actuators." |

**RA-7 = Option E:** a runtime/trajectory **observer + risk evaluator** that emits neutral signals;
RA-6 owns the authority consequence; ActionGate/runtime own enforcement.

---

## 8. ACP boundary (keep distinct)

ACP = **Autonomous Control Plane**: "the deterministic decision-and-authorization runtime that sits
between a robot's perception/prediction stack and its actuators … what single action is authorized to
execute right now, or is the correct answer 'no safe action'?"
(`Project_documentation/control_plane/acp/ACP_ARCHITECTURE.md:18-31`).

- **Risk Authority:** *what is this system permitted to do?*
- **RA-7 Runtime/Trajectory Assurance:** *is its behavior while operating still consistent with that
  authority?* (observe → signal)
- **ACP:** *for a real-time physical actuator, which exact safe control action occurs this tick?*

**RA-7 must NOT absorb ACP.** They compose: for robotics, an RA-7 observer could *feed* ACP's live
safety state (as one input), but ACP owns the per-tick actuator decision and RA-6 owns machine
authority. A future robotics integration seam would be: `RA-7 assessment → (a) RA-6 signal for
authority, (b) ACP live-safety-state input for actuation` — two distinct consumers, neither granting
the other's authority.

---

## 9. Trajectory-policy ownership (fields exist, enforcement does not)

`trajectory_policy_id` is an `EnvelopeConditions` field — i.e. it is **bound into the signed
envelope** (authority-issued, tamper-evident). `trajectory_version` rides on `ActionAuthorization`
and is threaded through the ActionGate seam but **never read in matching logic** (passthrough label).

Implications:
- The **reference** to a trajectory policy is already authority-bound (good — the observer cannot
  substitute the policy the envelope points at).
- The **policy content** (what trajectory is acceptable) has **no defined owner or store**, and **no
  evaluator consumes it**. Candidate owners to decide (§13-D2): WorkflowIR, a dedicated
  trajectory-policy artifact, or Decision Authority policy. Whatever it is, its *digest* should be
  bound like `workflow_ir_digest`/`model_digest` so a substituted policy is detectable.

**Do not assume a Trajectory Control subsystem exists — it does not.** RA-7 would be the first
consumer of `trajectory_policy_id`.

---

## 10. Action-level vs sequence-level risk (the central addition)

ActionGate is **per-action and stateless** with respect to history. The canonical example — ten
individually-authorized `$9,000` transfers = `$90,000` cumulative exposure — is **not** caught by
ActionGate today.

Partial building block: `PortfolioBudget`/`BudgetCoordinator` (`orchestration/budgets.py`) *does*
maintain a reserve-before-execute cumulative ceiling shared across concurrent quanta — but it is a
**generic orchestration budget** explicitly outside governance. So RA-7's genuine addition is
**sequence-level *risk* typing**, ideally by *observing* the existing portfolio/budget/exposure state
rather than re-implementing a ledger. **Do not duplicate the budget machinery** — read it, risk-type
it, and signal on breach.

---

## 11. RA-7 vs RA-8 boundary (clean split, using what exists)

- **RA-7 = during execution / behavior trajectory.** Observe ongoing behavior; on divergence, emit a
  signal so RA-6 can reassess/revoke *before the next* consequential commit.
- **RA-8 = did the completed effect match what was authorized?** This is **already modeled** in
  Decision Authority: `ExecutionRecord` (observed effect), `ReconciliationResult`
  (`mismatch_codes`, `compensation_required`), `ReconciliationService` — **unwired** from the runtime.

**Recommendation:** RA-8 = wire DA's reconciliation to the runtime effect + feed mismatches back as
RA-6 signals; RA-7 = pre-completion trajectory observation. **Do not implement RA-8 reconciliation
inside RA-7.** (This split is itself a decision to ratify — §13-D1.)

---

## 12. Context Minimization relationship

`context_minimization` is already a **signed envelope condition** (authority-owned). Therefore:
- Context *policy* is **not** RA-7-owned; it is part of authority + runtime `required_conditions`
  enforcement.
- **Context *expansion* can be a trajectory deviation** — RA-7 may *observe* runtime context growth
  beyond the minimized set and *signal* it, but it does not own or enforce the context policy.
- Ownership stays clean: authority declares the condition; runtime enforces `required_conditions`;
  RA-7 observes deviation and signals.

Context Minimization is therefore a **supporting capability**, not RA-7's core.

---

## 13. Authority-critical decisions still OPEN (must ratify before a SPEC)

- **D1 — RA-7/RA-8 boundary.** Given DA already owns reconciliation, ratify: RA-7 = trajectory
  observation (pre-completion); RA-8 = wire DA reconciliation → RA-6 signal (post-completion). Confirm
  the number assignment (the roadmap bundle does not fix 7 vs 8).
- **D2 — Trajectory-policy artifact ownership + integrity.** Who owns/stores the *content* referenced
  by `trajectory_policy_id`? Must its digest be bound into the envelope (like `workflow_ir_digest`)?
- **D3 — Sequence-level risk source.** Reuse `PortfolioBudget` exposure (observe) vs introduce a
  distinct risk budget? Preferred: observe existing state; ratify the risk-typing rule.
- **D4 — "Assurance-required" fail-closed policy.** When RA-7 is *expected* but unavailable, may a
  deployment mark consequential actions as `assurance-required ⇒ DENY-if-absent`? This is the only
  place RA-7 could legitimately touch the hot path, and only as an *opt-in fail-closed policy*, never
  as a default synchronous dependency.
- **D5 — Consequence granularity.** RA-6 epoch is **per-tenant**; per-workflow/per-policy epoch is
  FUTURE (`RA6_SPEC.md:312,430`). To invalidate *one* drifting trajectory without nuking the tenant,
  RA-7 should use **targeted `revoke_envelope`** on the specific envelope (already supported), not a
  tenant epoch bump. Ratify this as the default RA-7 consequence.
- **D6 — New signal categories.** Confirm whether `RUNTIME_RISK_ESCALATED` suffices, or add
  non-breaking `TRAJECTORY_DEVIATION` / `MODEL_BEHAVIOR_CHANGED` / `EXECUTION_ANOMALY` to
  `SignalChangeType` (additive; no format change).
- **D7 — Producer trust seam.** Telemetry is a new trust boundary. Delegate producer authentication
  to a deployment ingress seam (mirroring RA-5 trusted-evidence ingress and RA-6 writer authz);
  **do not** require cryptographic telemetry signing for the reference milestone. State this openly.

---

## 14. Recommended shape (subject to the D-decisions)

- **Ownership: Option B — a sibling integration package**, e.g.
  `packages/integration/risk-authority-runtime-assurance/`, depending on `ugence-risk-authority`
  (for the neutral signal types) only. Dependency direction: `risk_authority ◄ runtime-assurance`
  (identical posture to `risk-authority-status-runtime`). **The stdlib-only RA leaf gains nothing;
  no telemetry/runtime deps enter it.**
- **Input via the existing seam:** RA-7 consumes the Agent Runtime `RuntimeEvent` stream through the
  **already-present** optional `event_sink` (`config.py:61-62`) — **no agent-runtime change required**
  for observation. (An optional, neutral "assurance-required" hook is a *separate* D4 decision.)
- **Handoff via the existing seam:** RA-7 emits `AuthorityReassessmentSignal` into the RA-6
  `AuthorityReassessor`. **No new event bus, no new authority format.**
- **Consequence:** targeted `revoke_envelope` (D5) through the sole writer; enforcement bites at the
  next pre-effect recheck.
- **Persistence/telemetry-trust:** reference in-memory + delegated production ingress (D7), matching
  RA-6's honest-maturity posture.

**Latency honesty:** the path *behavior → telemetry → observe → signal → reassess → write → propagate
→ enforce* is **event-driven, not continuous real-time**. Claim **"event-driven runtime assurance
that can cause previously-valid machine authority to be reassessed and invalidated,"** *not*
"continuous real-time authority" or "zero-window revocation."

---

## 15. RA-6 compatibility (must hold)

`RiskAuthorizationEnvelope` remains the sole signed machine authority · `FinalAuthority ≤
RiskAuthority` · `FinalScope ⊆ RiskAuthorityScope` · RA-6 `AuthorityLifecycleService` remains the sole
revocation/epoch writer · RA-7 observer = signal producer only · no second authority artifact · no
direct RA-7 mutation of revocation state (only through the authorized RA-6 writer).

---

## 16. Future adversarial (deny-heavy) test matrix — for the eventual SPEC

Normal→no-reassessment · explicit deviation→signal · runtime-risk escalation→RA-6 reassessment ·
observer unavailable (runtime unaffected) · malformed/stale/duplicate/out-of-order telemetry
(ignored/deduped, never mutates) · wrong tenant/workflow/envelope · wrong trajectory-policy version ·
forged signal (no mutation) · observer false-positive (fail-safe over-revocation only) · observer
signal **cannot** directly revoke or mint authority · cumulative-sequence violation · repeated
near-boundary · retry-loop escalation · legitimate recovery→normal (needs new envelope) · revocation
latency path · signal after authority already revoked / after expiry (idempotent) · RA-6 unavailable ·
telemetry source unavailable · Agent Runtime unaffected without observer · RA-4.5/RA-5 unchanged · no
second authority artifact · RA leaf remains stdlib-only independent · ACP remains separate.

---

## 17. Platform significance (no overclaim)

Beyond logging/SIEM/APM (passive record), IAM (identity, not behavior), agent guardrails (per-prompt),
and static ActionGate (per-action), the RA-6 + RA-7 pair enables a property those do not:
**runtime behavior can cause previously-valid, cryptographically-signed machine authority to be
reassessed and invalidated** — a closed loop from observed trajectory to authority lifecycle. This
claim is technically supported by RA-6 (targeted revoke / epoch / bounded-stale enforcement) plus the
RA-7 producer proposed here. It is **event-driven and reference-grade** (delegated persistence and
producer trust), **not** globally-consistent, zero-window, or cryptographically-attested telemetry.

---

## 18. Verdict

**`RA7_ARCHITECTURE_DECISION_REQUIRED`.** The direction is clear and low-risk (an observer that
signals into the existing RA-6 seam; a sibling package; no RA-leaf/agent-runtime/ActionGate changes
required for the core observe→signal loop). Seven authority-critical decisions (§13, D1–D7) — chiefly
the RA-7/RA-8 boundary, trajectory-policy ownership/integrity, and the sequence-risk source — must be
ratified before a canonical RA-7 SPEC or any implementation. Until then this remains discovery only.

*Discovery only. No production code, no RA/agent-runtime/ActionGate/ACP/RA-8 implementation, no PR.*
