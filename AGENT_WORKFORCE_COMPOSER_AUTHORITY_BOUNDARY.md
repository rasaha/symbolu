# Agent Workforce Composer — Authority Boundary

> ## Implementation-Status Correction & Reconciliation Note (2026-08-03)
>
> *Added by AWC Phase 0 (H16 reconciliation). Changes documentation only; no production code.*
> See the ADR: [`docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`](docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md)
> and the audit set [`docs/audits/agent_workforce_composer_phase0/`](docs/audits/agent_workforce_composer_phase0/).
>
> - **Original assumption:** the Policy Workflow Compiler was *spec-only / not yet implemented*, with no typed
>   `WorkflowIR`, to be integrated "when it ships"; AWC would consume an invented `WorkflowGraphSource`.
> - **Current verified state:** the compiler is **implemented** as the independently packaged
>   `ugence-policy-workflow-compiler` tooling distribution (PR #1303, merge `96afb58a…`). It emits a deterministic
>   **`WorkflowIR`** (`workflow_ir.v1`), capability metadata, assurance artifacts, and content-addressed compiled
>   packages. Document extraction, NLP interpretation, and runtime deployment remain outside its implemented
>   Phase 1 scope.
> - **Architectural consequence:** AWC Phase 1 consumes the **canonical compiler contract** via a thin, versioned,
>   data-only `CompilerWorkflowAdapter` (formerly `WorkflowGraphSource`) — **not** a second workflow
>   representation. The former "spec-only upstream" risk is replaced by
>   **`UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT`**.
> - **Documents changed:** all seven `AGENT_WORKFORCE_COMPOSER_*.md`, plus the new ADR and
>   `docs/architecture/agent_workforce_composer_boundaries.json`.
>
> **Reconciled positions all seven documents now agree on:** (1) the Policy Workflow Compiler is implemented;
> (2) AWC consumes the canonical compiler `WorkflowIR`; (3) H16 canonicalization is the accepted ADR decision
> (Option A); (4) AWC is a deterministic, offline, side-effect-free *planning* capability; (5) H16 retains runtime
> coordination and recovery; (6) Model Selection remains separate (models, not agents); (7) Agent Runtime remains
> the executor; (8) H22 remains the scheduler; (9) binding authority (Decision Authority / ActionGate / Action
> Clearance) remains outside AWC; (10) P1 implementation cannot start until the ADR's exit gates pass.


**Status:** `[SPEC]` design / pre-implementation. Companion to `AGENT_WORKFORCE_COMPOSER_DESIGN_SPEC.md`.
Claim labels per design spec §1. This document is the load-bearing boundary artifact: it states, per existing
component, exactly what AWC must never do, grounded in each component's verified authority
(`[EXISTING]` `UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md` §5 + five subsystem audits).

---

## 1. First principle

`[EXISTING]` *Coordination does not transfer authority. Each component owns exactly one function.* AWC **coordinates
selection** and **emits a plan**. Producing a plan that references a permission, a decision point, an action, a
clearance, a model, or a schedule confers **none** of those authorities. AWC holds no credentials, opens no
connection, executes nothing, and decides nothing binding.

## 2. What AWC may own

Role-requirement extraction · hard-constraint agent eligibility · evidence-backed assessment and ranking · team
composition · **proposed** least-privilege permission grants and authority ceilings · fallback selection · the
immutable `AgentTeamPlan` · the elimination/explanation ledger · snapshot pinning, replay, and offline
counterfactuals of its own outputs.

## 3. Boundary table — what AWC must NOT own

| Function | Owner (`[EXISTING]`) | Owner's authority (verbatim scope) | AWC's permitted interaction | The exact line AWC must not cross |
|---|---|---|---|---|
| Binding business decision | **Decision Authority** `ugence_decision_authority` | Decides *when an AI recommendation may become a binding, authority-attributed business decision*; `AuthorityType` = HUMAN_REVIEWER/HUMAN_APPROVER/DELEGATED_POLICY/COMMITTEE/EXTERNAL_AUTHORITY — **no AI member**; owns SoD, evidence completeness, overrides, immutable `DecisionRecord`, reconstruction. | Mark a step `HUMAN_AUTHORITY_REQUIRED`; reference `decision_refs` by id/hash. | AWC produces **no `DecisionRecord`**, attributes no authority, and never decides a go/no-go. A binding decision point is a `NonAgentDisposition`, never an AI role. |
| Exact-action authorization | **ActionGate** `ugence_actiongate_provider` | Answers *"is this exact action, by this principal, authorized right now?"* → `ALLOW/DENY/ALLOW_WITH_CONSTRAINTS/UNKNOWN` with constraints, obligations, expiry, authority basis, trace id. Does not execute. | Bound an action-executing assignment's permissions; reference the action point. | AWC never emits an authorization, never adds/broadens/bypasses an ActionGate outcome; every action a staffed agent takes still passes ActionGate at runtime. |
| Commit-time operational clearance | **Action Clearance** `ugence_action_clearance` | Given an existing authorization + trusted current-state signals, decides if the action is *clear to execute now* → `CLEAR/HOLD/BLOCK/ESCALATE` (no `DENY` — ActionGate owns denial). Invariant: `Clearance ⊆ ActionGate-authorized`. | None at plan time; the plan's actions will be cleared at runtime. | AWC cannot upgrade a HOLD/BLOCK/ESCALATE into an executable result; it grants no clearance. |
| Sequence-risk verdict | **StoryGraph** `ugence_storygraph` | **Advisory only**; output alphabet exactly `{OBSERVE, ESCALATE, UNAVAILABLE}`; never ALLOW/DENY/BLOCK. Emits advisory sequence-risk findings. | *Consume* an advisory signal as an input to a role's risk facet. | AWC must not treat `ESCALATE` as a binding block, and must never be given selection/authorization authority over StoryGraph. Advisory in, advisory only. |
| Model / provider selection | **Model Selection** `ugence_model_selection` | Picks an approved *model/provider* for a request via `ExecutionGate`+`ModelPolicy`; owns no routing/execution/authorization. Inputs are **model candidates**, not agents. | Record a neutral `model_policy_ref` per assignment for later resolution. | AWC selects **agents**, never models; it never ranks or picks a model, and never imports Model Selection. |
| Workflow execution / coordination | **Agent Runtime** `ugence_agent_runtime` (+ H16 `Coordinator`) | Executes a `WorkflowDefinition` of `TaskDefinition`s; selects **providers**; enforces a fail-closed `GovernanceHook` per consequential task; never self-authorizes. H16 `Coordinator` selects+executes+recovers at runtime. | Hand off an `AgentTeamPlan` as neutral data (maps to a `WorkflowDefinition`). | AWC never executes, routes, supervises, or recovers at runtime; it computes a plan and stops. |
| Multi-workflow scheduling / budget / resource contention | **H22** `agentic.agentic_framework.multi_workflow_orchestration` | Deterministic in-process scheduling **across** workflows: priority/fairness ordering, dependencies, budgets, resource locks. Treats `PortfolioWorkflowEntry.assigned_agent` + `authority_scope` as **fixed inputs**. | **Produce** `assigned_agent` + `authority_scope` for H22 to consume. | AWC never schedules, orders, budgets, or arbitrates resource contention; it does not choose *when/in-what-order* work runs. |

## 4. The complementary seam with H22 (why there is no overlap)

`[EXISTING]` H22's `PortfolioWorkflowEntry` carries `assigned_agent` and `authority_scope` and **treats them as
given** — H22 does not choose or substitute agents; it runs already-staffed workflows fairly and safely. `[SPEC]`
AWC produces exactly those two fields (via `AgentAssignment` + `AuthorityBoundary`). The pipeline is:

```
AWC:  who staffs each role, with what bounded authority   →   H22:  when/in-what-order/under-what-budget it runs
```

These are disjoint. Merging them would recreate the "one orchestrator owns requirements + selection + scheduling +
authority + execution" anti-pattern the platform explicitly avoids (`[EXISTING]` terminology audit §5, design
brief).

## 5. Type-enforced boundary (not documentation-enforced)

`[SPEC]` The boundary is enforced in types, mirroring AI Hiring's construction-time `BoundaryViolationError`
(`[EXISTING]`):
- `AgentTeamPlan.plan_only = True` (`Literal[True]`, `extra` fields forbidden) — a decision/authorization field can
  never be smuggled onto a plan.
- `PlanApproval.authority_type` drawn from `ugence_decision_authority.AuthorityType`, which has **no AI member** —
  AWC structurally cannot mint an AI approver.
- `AgentPermissionGrant` construction fails if it includes a `prohibited_permission`; `AuthorityBoundary`
  construction fails if `agent.authority_requirements > authority_ceiling`.
- **Monotonic narrowing:** grants and fallbacks can only subset the role's permissions; there is no code path that
  widens a permission or raises a ceiling.
- **Import-boundary test** (Model Selection / Agent Runtime pattern `[EXISTING]`) forbids importing Agent Runtime,
  H22, Model Selection, Decision Authority, ActionGate, Action Clearance, StoryGraph, concrete providers,
  `ai_hiring`, and the `agentic/` framework.

## 6. The five non-agent outcomes (AWC's humility contract)

`[SPEC]` AWC must be able to conclude a step should **not** be an AI role, and does so via `NonAgentDisposition`:

| Outcome | Meaning | Routes to |
|---|---|---|
| `NO_AI_AGENT_REQUIRED` | The step needs no autonomous agent at all. | (nothing) |
| `DETERMINISTIC_SERVICE_PREFERRED` | A rule engine / deterministic service is sufficient and safer. | Deterministic service (compiler-mapped) |
| `HUMAN_AUTHORITY_REQUIRED` | The step is a binding decision or an authority-attributed act. | Decision Authority / human |
| `HUMAN_REVIEW_REQUIRED` | An agent may prepare, but a human must review before proceeding. | Human reviewer |
| `NO_ELIGIBLE_AGENT` | The step is agent-shaped but no agent satisfies the hard constraints. | Human: procure / relax / re-scope |

`[SPEC]` This is a **feature, not a fallback**: a composer that always returns a full agent team is unsafe. The
assurance corpus asserts each reference workflow produces at least one correct non-agent disposition
(acceptance criterion 6).

## 7. Separation of duties & concentration of authority (plan-time)

`[SPEC]` AWC enforces *plan-time* SoD and authority-concentration limits (§ design spec 17–18) as **hard team-level
constraints**. This is distinct from Decision Authority's *binding* SoD: AWC proposes a team whose structure does
not concentrate authority or collapse duties; Decision Authority remains the binding SoD authority for the decision
itself. AWC's SoD prevents, e.g., the same agent both *recommending* a binding decision and *executing* the
resulting action. If AWC cannot find an SoD-satisfying, concentration-bounded team, it returns a partial plan with
the offending roles flagged — it never relaxes SoD to complete a team.

## 8. Escalation of ambiguity

`[SPEC]` Where a workflow node's classification is ambiguous (is it a binding decision or an advisory
recommendation? is a permission consequential?), AWC **fails toward the more restrictive** interpretation
(`HUMAN_AUTHORITY_REQUIRED` / most-restrictive `data_classification` / narrower grant) and records the ambiguity for
human review — never toward more autonomy or broader authority.
