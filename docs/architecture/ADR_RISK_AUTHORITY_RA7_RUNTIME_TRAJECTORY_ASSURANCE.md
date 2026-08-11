# ADR — RA-7: Runtime / Trajectory Assurance (Observe → Signal) for Risk Authority

- **Status:** Accepted (Ratified)
- **Date:** 2026-08-11
- **Baseline:** default `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` @ `e6aa6edf` (RA-6 merge, PR #1412)
- **Supersedes:** the discovery verdict `RA7_ARCHITECTURE_DECISION_REQUIRED`
  (`RISK_AUTHORITY_RA7_RUNTIME_TRAJECTORY_ASSURANCE_PLAN.md` @ `63275f91`)
- **Canonical spec:** `RISK_AUTHORITY_RA7_SPEC.md`
- **Verdict:** `RA7_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`

## Context

RA-6 shipped the full authority-lifecycle feedback seam — a neutral
`AuthorityReassessmentSignal` (`risk_authority/domain/authority_signal.py:79`),
the `RUNTIME_RISK_ESCALATED` category (`:51`), an authenticated intake
(`integrations/authority_lifecycle.py:207`), a reference reassessor
(`…status-runtime/reassessor.py:110`), and a sole authenticated writer performing
targeted revoke / tenant-epoch advance (`…status-runtime/writer.py:112`) with
bounded-stale pre-effect enforcement.

**But the seam has no producer.** Every signal construction and every `.submit()`
call in the repo is in tests; `agent-runtime/src` imports nothing from
`risk_authority` (verified grep-clean at `e6aa6edf`). The loop
`runtime behavior → signal → reassess → revoke/epoch → enforce` is open at the
first hop only.

Meanwhile: `trajectory_policy_id` is a *signed* envelope condition
(`domain/envelope.py:32`) and `trajectory_version` is threaded through ActionGate
(`domain/actions.py:56`, `integrations/actiongate.py:56,77,178`) but **no evaluator
consumes them**; Agent Runtime owns a cumulative `PortfolioBudget`/`BudgetCoordinator`
ledger (`orchestration/budgets.py:48,149`) that "decides nothing about governance";
and Decision Authority already models `ExecutionRecord` / `ReconciliationResult` /
`ReconciliationService` (`decision-authority/execution/*`) — the RA-8 concept —
**unwired** from the runtime. ACP remains spec-only.

The discovery left seven authority-critical decisions (D1–D7) open. This ADR
ratifies them.

## Decision

**RA-7 is a runtime / trajectory assurance *observer + risk evaluator* that emits
neutral signals into the existing RA-6 intake. RA-7 OBSERVES AND ASSESSES; RA-6
OWNS AUTHORITY CONSEQUENCES.** RA-7 is the missing producer, not a second authority.

Ratified answers to the open decisions (full detail in the spec):

- **D1 — RA-7/RA-8 boundary.** RA-7 = pre-completion trajectory observation,
  stopping at execution-completion events; consumes runtime *events* only, never
  execution receipts. RA-8 = post-effect reconciliation, wiring Decision
  Authority's existing primitives to the runtime effect. RA-7 does **not** absorb
  reconciliation despite the code existing.
- **D2 — Trajectory-policy ownership/integrity.** WorkflowIR owns policy *content*;
  `trajectory_policy_id`/`trajectory_version` already provide authority-bound
  identity and versioning; add a **non-breaking, additive `trajectory_policy_digest`**
  (deferred) to pin content integrity like `workflow_ir_digest`. RA leaf stays free
  of telemetry-specific policy.
- **D3 — Sequence-risk source.** RA-7 **observes** the existing Agent Runtime
  portfolio ledger and **risk-types** it externally; it does not duplicate
  authoritative accounting. Agent Runtime owns the numbers; RA-7 owns the risk
  interpretation.
- **D4 — Assurance-required policy.** RA-7 is additive and event-driven **by
  default** — never a global synchronous hot-path dependency. An **opt-in, signed
  `assurance_required` envelope condition** (the same mechanism as
  `context_minimization`) may make specific consequential actions fail-closed
  (`ERROR_NON_EXECUTABLE` / `DENY_IF_ASSURANCE_REQUIRED`) when current assurance is
  absent/stale.
- **D5 — Consequence granularity.** Default = targeted `revoke_envelope`
  (`target_type = ENVELOPE`); RA-6 decides any broader consequence (subject / model
  / tenant epoch) on reassessment. **No new workflow epoch.**
- **D6 — Signal categories.** Reuse the single existing `RUNTIME_RISK_ESCALATED`
  with **structured reason codes**; add categories only on demonstrated
  reassessment-policy divergence (additive, later). RA-8's effect-mismatch category
  is excluded from RA-7.
- **D7 — Telemetry producer trust.** Producer authentication delegated to an
  **authenticated deployment ingress seam** (mirroring RA-5 evidence ingress /
  RA-6 write authz), with explicit minimum bindings (tenant / workflow / envelope /
  event_id / observed_at / source). **No cryptographic per-event telemetry-signing
  overclaim.**

**Trajectory** is canonically the ordered per-workflow-instance sequence of
runtime events and authority-relevant state transitions, derived from the existing
`RuntimeEvent` stream — **not** a new execution ledger, and **excluding**
post-effect reconciliation (RA-8).

**Package:** a new sibling integration package
`packages/integration/risk-authority-runtime-assurance/`, depending on the RA leaf
+ RA-6 status-runtime intake, observing Agent Runtime through the **existing
neutral `event_sink` seam** — no agent-runtime change for the core loop.

## Rejected alternatives

- **RA-7 as trajectory-policy enforcer / action-blocker.** Rejected — would make
  RA-7 a second enforcer/authority. Enforcement stays with ActionGate / RA-6.
- **RA-7 as a runtime control loop that directly stops actions.** Rejected —
  violates observer/authority separation; that is ACP's job for physical systems.
- **RA-7 mutating revocation/epoch directly.** Rejected — only RA-6's authenticated
  writer mutates lifecycle state.
- **A new RA-7 risk-budget ledger (D3 Option B).** Rejected — duplicates the
  authoritative Agent Runtime portfolio ledger. RA-7 reads and risk-types instead.
- **Cryptographic per-event telemetry signing for the reference milestone (D7
  Option A).** Rejected as an overclaim; delegated ingress seam (Option B) instead.
- **Severity tiers `ELEVATED`/`CRITICAL` (§13).** Rejected — no real policy
  difference; RA-6's consequence is identical for any material escalation.
- **New signal taxonomy for its own sake (D6).** Rejected — one category +
  structured reasons suffices.
- **Absorbing RA-8 reconciliation into RA-7 (D1).** Rejected — reconciliation is
  post-effect; RA-7 is pre-completion.
- **A new per-workflow epoch (D5).** Rejected as unnecessary — targeted
  `revoke_envelope` already isolates a single drifting trajectory.

## Consequences

- The RA-6 feedback loop becomes *closable*: observed runtime behavior can cause
  previously-valid signed machine authority to be reassessed and invalidated —
  event-driven and bounded-latency, **not** zero-window or continuous.
- No new signed authority artifact; `RiskAuthorizationEnvelope` remains the sole
  one. RA-7 cannot mint, widen, or directly mutate authority; it cannot trigger
  emergency stop.
- The RA leaf stays stdlib-only; Agent Runtime stays concrete-free and imports no
  RA; ActionGate, RA-6, Decision Authority, ACP, and RA-8 are untouched.
- One additive, deferred schema evolution is anticipated (`trajectory_policy_digest`,
  and optionally an `assurance_required` condition), both signed via the existing
  `signing_payload()` path and both backward-compatible with existing envelopes.
- Sequence-level risk ($9k×10) becomes detectable by risk-typing existing ledger
  state — a capability neither ActionGate nor logging/SIEM/IAM provides.

## Scope statement

Documentation / architecture only. This ADR changes no production code, starts no
RA-7 implementation, creates no package, adds no port to source, adds no
persistence or telemetry infrastructure, and modifies no envelope / ActionGate /
Agent Runtime / RA-6 / Decision Authority. It implements no ACP and no RA-8. No PR
is opened by this ratification.
