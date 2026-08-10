# Agent Workforce Composer — Design Specification

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


**Working name:** Ugence Agent Workforce Composer (AWC)
**Proposed distribution:** `ugence-agent-workforce-composer` · **namespace:** `ugence_agent_workforce_composer`
**Status:** `[SPEC]` — design / pre-implementation. Version 0.1 (design spec). Date: 2026-08-03.
**Discipline:** falsification-first. No implementation, validation, production-readiness, competitive-superiority,
or customer-demand claim is made in this document. Every reference to existing code is grounded in a repository
path and classified (`REUSE` / `COMPOSE` / `ADAPT` / `REFERENCE_ONLY` / `OUT_OF_SCOPE` / `OVERLAPPING` /
`DUPLICATE_RISK`) in §5.

**Companion documents (this deliverable set):**
- `AGENT_WORKFORCE_COMPOSER_ARCHITECTURE.md` — component decomposition, data flow, dependency direction.
- `AGENT_WORKFORCE_COMPOSER_OBJECT_MODEL.md` — canonical objects, fields, AI-Hiring mapping table, reused primitives.
- `AGENT_WORKFORCE_COMPOSER_AUTHORITY_BOUNDARY.md` — what AWC must never own; boundary table vs each component.
- `AGENT_WORKFORCE_COMPOSER_SELECTION_POLICY.md` — the deterministic selection/composition procedure.
- `AGENT_WORKFORCE_COMPOSER_ASSURANCE_PLAN.md` — synthetic tests, counterfactuals, replay, failure modes.
- `AGENT_WORKFORCE_COMPOSER_IMPLEMENTATION_ROADMAP.md` — MVP scope, deferred capabilities, phases, risks.

### Claim labels used throughout
`[EXISTING]` verifiable in the repository today · `[SPEC]` proposed design in this document ·
`[INFERENCE]` reasoned from repository evidence, not directly asserted by it · `[PROPOSED]` a recommendation ·
`[DEFERRED]` intentionally out of the first implementation · `[UNVALIDATED]` no empirical support exists.

---

## 1. Executive summary

`[SPEC]` The **Agent Workforce Composer (AWC)** is a proposed **deterministic, offline, leaf capability** that,
given a compiled business-process workflow, (a) extracts the AI-agent **role requirements** for each eligible
workflow step, (b) evaluates registered AI agents against those requirements using **evidence-backed** capability
data, (c) eliminates agents that violate **hard constraints** before any scoring, (d) ranks eligible agents,
(e) composes a **team** whose members' interfaces, permissions, cost, latency and failure-correlation are jointly
acceptable, (f) attaches **bounded permission grants and an authority ceiling** to each assignment, (g) selects
**fallback** agents, and (h) emits a single immutable, replayable **`AgentTeamPlan`** together with a complete
**elimination/explanation ledger**.

`[SPEC]` AWC is the **role-team analogue, one level above, of the existing Model Selection Policy Engine**
`[EXISTING]` (`packages/capabilities/model-selection`, dist `ugence-model-selection`). Model Selection answers
"*which approved model may power this request, and why was every alternative rejected?*" over a frozen candidate
snapshot. AWC answers "*which approved agent(s) should staff this workflow's roles, with what bounded permissions,
and why was every alternative rejected?*" over a frozen agent-registry snapshot. It reuses Model Selection's
**two-stage, constraint-first, fail-closed** shape verbatim in structure:

```
Compiled workflow (governed workflow graph, from the Policy Workflow Compiler)
        ↓  role extraction
WorkflowRoleRequirement[]                         (one per eligible step; some steps → NO agent)
        ↓  pin snapshot
AgentRegistrySnapshot  +  EnterpriseAgentPolicy  +  CompositionPolicy
        ↓  Stage 1: hard-constraint elimination  (fail-closed; never ranks)
Eligible agents per role
        ↓  Stage 2: evidence-backed scoring       (only over eligible)
Ranked agents per role
        ↓  Stage 3: team composition               (interfaces, permissions, cost, latency, correlation)
TeamCandidate(s)
        ↓  Stage 4: permission + authority bounding
Bounded AgentAssignment[]  +  FallbackAssignment[]
        ↓  emit
AgentTeamPlan  +  SelectionExplanation ledger  +  SelectionReplayRecord
        ↓  optional handoff (as neutral data)
Agent Runtime (executes) · H22 (schedules) · Decision Authority / ActionGate / Action Clearance (govern)
```

`[SPEC]` AWC is a **planner, not a runtime**. It computes a plan artifact; it does not execute agents, route
traffic, authorize actions, make binding business decisions, grant execution clearance, or schedule workflows.
Those authorities are owned by named existing components and are enumerated as hard non-goals in §3 and
`AGENT_WORKFORCE_COMPOSER_AUTHORITY_BOUNDARY.md`.

`[SPEC]` AWC must be able to conclude that a step needs **no AI agent at all** — returning
`NO_AI_AGENT_REQUIRED`, `DETERMINISTIC_SERVICE_PREFERRED`, `HUMAN_AUTHORITY_REQUIRED`, `HUMAN_REVIEW_REQUIRED`,
or `NO_ELIGIBLE_AGENT`. It never assumes every step is agent-shaped.

---

## 2. Why this capability may or may not need to exist (falsification-first)

The strongest form of this section is the case **against** building AWC, answered point by point.

### 2.1 The case against
- **F1 — It duplicates the H16 coordination layer.** `[EXISTING]` `agentic/agentic_framework/coordination.py`
  already implements `AgentProfile` (capability + authority manifest per agent), `CapabilityRegistry.candidates_for(goal)`
  (deterministic agent selection filtered by supported goal + required capabilities + availability, ordered
  `(-trust_level, agent_id)`), `Mission`/`CoordinationGoal` (goals with `required_capabilities`, `authority_scope`),
  `DelegationContract`/`AgentAssignment`, `AuthorityModel` (capability/authority/budget/ownership checks with a
  `RejectionReason` vocabulary including `CAPABILITY_MISMATCH`, `AUTHORITY_DENIED`, `NO_QUALIFIED_AGENT`), and
  `Coordinator._coordinate_goal`, which recovers across candidate agents on failure (fallback). `multi_agent.py`
  adds `AgentRegistry`, a `Router` protocol, `KeywordRouter`/`LLMRouter`, and `MultiAgentOrchestrator`. **The
  concepts AWC needs largely already exist.**
- **F2 — It duplicates Model Selection.** Both are constraint-first selectors over a frozen registry snapshot.
- **F3 — It becomes a covert orchestrator.** The ADR record (`ADR_MODEL_SELECTION_POLICY_PLACEMENT.md` §Options,
  `model_selection_experiment/ARCHITECTURE_NOTE.md` Q3) `[EXISTING]` explicitly rejected framing Model Selection as
  an "AI Orchestrator." A "workforce composer" invites the same taxonomy-inflating, authority-accreting failure the
  repo has repeatedly guarded against.
- **F4 — No validated customer demand.** `[UNVALIDATED]` There is no repository evidence of a customer asking for
  automated agent-team composition.

### 2.2 The answers (why it may still be justified)
- **A1 (answers F1).** `[INFERENCE]` The H16 layer conflates three concerns that the rest of the platform keeps
  separate: *selection*, *live runtime coordination/recovery*, and (via `LLMRouter`) *non-deterministic routing*.
  `coordination.py`'s `Coordinator` selects **and executes and recovers at runtime**; `multi_agent.py` routes with
  a supervisor **LLM**. Neither produces a **frozen, snapshot-pinned, replayable, offline plan artifact** with a
  complete elimination ledger and counterfactual support. AWC's distinct contribution is exactly the separation
  the platform already performed for models: lift *deterministic team composition* out of the runtime into a
  leaf capability that emits an immutable `AgentTeamPlan`, the same way `ugence-model-selection` was lifted out of
  the Agent Runtime and `ugence-decision-authority` was extracted from AI Hiring. **This is a canonicalization +
  determinism/explainability play, not a green-field one.** AWC must therefore **`ADAPT`** the H16 concepts, not
  fork them (see §5, §33, and the roadmap's Phase 0 reconciliation task).
- **A2 (answers F2).** `[SPEC]` AWC operates one level up and is explicitly *composed with* Model Selection, not a
  replacement: AWC selects **functional agents for roles**; Model Selection selects the **model that powers each
  selected agent**. AWC never picks a model; it may record a *model-policy reference* per assignment for the
  runtime/Model-Selection to resolve. The two are peers with a hard import boundary (mirroring the existing
  agent-runtime ↔ model-selection boundary, enforced by `packages/runtime/agent-runtime/tests/test_import_boundaries.py`).
- **A3 (answers F3).** `[SPEC]` AWC is fenced by the same discipline that kept Model Selection a policy capability:
  it emits **plans, not decisions/authorizations/schedules**; the authority boundary (§3, boundary doc) is
  type-enforced (a plan is un-forgeably advisory, mirroring AI Hiring's `advisory_only: Literal[True]`).
- **A4 (answers F4).** `[UNVALIDATED]` Demand is unproven and this document does **not** assert it. The MVP is a
  deterministic offline demonstrator (§33) whose only claim is internal-consistency and replay — not market fit.

### 2.3 Verdict
`[INFERENCE]` The capability is **architecturally justifiable as a canonicalization-and-determinism layer** —
*conditional* on (i) reconciling with, and adapting rather than duplicating, the H16 coordination concepts, and
(ii) never crossing into runtime coordination, decision authority, action authorization, clearance, model routing,
or scheduling. Absent condition (i), AWC is `DUPLICATE_RISK` and should not be built as new parallel architecture.
The firm recommendation and the exact overlap test are in §31 and the concluding section.

---

## 3. Product and authority boundary

`[SPEC]` AWC owns exactly one function: **deterministic, explainable composition of a bounded AI-agent team plan
for a compiled workflow, over a frozen registry snapshot.** Coordination does not transfer authority
(`UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md` §5, `[EXISTING]`): producing a plan confers none of the
authorities the plan references.

**AWC may own:** role-requirement extraction from a compiled workflow; hard-constraint eligibility filtering of
agents; evidence-backed agent assessment and ranking; team composition; permission-grant and authority-ceiling
*proposals* per assignment; fallback selection; the immutable `AgentTeamPlan`; the elimination/explanation ledger;
snapshot pinning, replay, and counterfactual analysis of its own outputs.

**AWC must never become / must never own** (each maps to an existing owner; full table in the boundary doc):

| AWC must NOT be / own | Owner today | Evidence |
|---|---|---|
| A workflow **runtime / executor** | Agent Runtime (`ugence-agent-runtime`) | `packages/runtime/agent-runtime` `[EXISTING]` |
| A **binding business decision** authority | Decision Authority (`ugence-decision-authority`) | `AuthorityType` has no AI member `[EXISTING]` |
| An **exact-action authorization** engine | ActionGate (`ugence-actiongate-provider`) | `ActionGateEngine.evaluate` `[EXISTING]` |
| An **operational-clearance** engine | Action Clearance (`ugence-action-clearance`) | `ActionClearanceEvaluator.evaluate` `[EXISTING]` |
| A **binding sequence-risk** verdict | StoryGraph (advisory only: `OBSERVE/ESCALATE/UNAVAILABLE`) | `packages/capabilities/storygraph` `[EXISTING]` |
| A **model router / selector** | Model Selection (`ugence-model-selection`) | `ExecutionGate`+`ModelPolicy` `[EXISTING]` |
| A **multi-workflow scheduler / budgeter** | H22 (`agentic.agentic_framework.multi_workflow_orchestration`) | `PortfolioScheduler` `[EXISTING]` |
| An **agent marketplace** | — | out of scope `[SPEC]` |
| An **autonomous enterprise-control plane** | — (optional AI Control Plane is bypassable) | terminology audit §6 `[EXISTING]` |

`[SPEC]` The permission grants and authority ceilings AWC emits are **proposals bounded from below**: an
assignment's proposed permissions are a *subset request*; the actual permissions an agent receives at runtime are
whatever the runtime + ActionGate + Action Clearance independently allow. AWC can only **narrow**; it can never
add, broaden, or bypass any downstream authority (monotonicity, mirroring Action Clearance's
`Clearance permissions ⊆ ActionGate-authorized permissions` invariant `[EXISTING]`).

---

## 4. Use cases and non-use cases

### 4.1 In-scope use cases `[SPEC]`
1. **Team compilation** — turn a compiled workflow into a role-separated, permission-bounded agent team plan.
2. **Constraint what-if** — recompose after a constraint change (e.g. "customer data must remain in India") and
   show which agents were eliminated, which replaced them, and the cost/latency delta (the demo in §33/§35).
3. **Gap detection** — identify roles for which **no eligible agent** exists (`NO_ELIGIBLE_AGENT`) so a human can
   procure/relax/re-scope, instead of silently under-staffing.
4. **De-agenting** — conclude a step should be a deterministic service, a human authority, or a human review —
   `DETERMINISTIC_SERVICE_PREFERRED` / `HUMAN_AUTHORITY_REQUIRED` / `HUMAN_REVIEW_REQUIRED`.
5. **Separation-of-duties planning** — refuse compositions in which one agent concentrates excessive end-to-end
   authority; propose splits.
6. **Fallback planning** — attach a fallback chain per role, each fallback re-checked against the *same* hard
   constraints as the primary.

### 4.2 Explicit non-use cases `[SPEC]`
- Executing, dispatching, routing, or supervising agents at runtime (Agent Runtime; H16 `Coordinator`).
- Making or recording any binding go/no-go business decision (Decision Authority).
- Authorizing, clearing, or dispatching any action (ActionGate / Action Clearance / execution provider).
- Choosing the LLM/model for an agent (Model Selection).
- Scheduling, budgeting, or arbitrating resource contention across workflows (H22).
- Human recruiting / hiring of people (AI Hiring is a *pattern donor only*, never a dependency; §9, object doc).
- Live agent discovery, registration, benchmarking, or marketplace listing (registry is an **input snapshot**).

---

## 5. Relationship to the existing Ugence architecture (repository audit)

`[EXISTING]` Classification of every materially related component. Method: read-only inspection (five subsystem
audits). Classes: `REUSE` (import its public contract), `COMPOSE` (consume/emit its artifact without importing),
`ADAPT` (canonicalize its concepts into AWC's model), `REFERENCE_ONLY` (design precedent), `OUT_OF_SCOPE`,
`OVERLAPPING`, `DUPLICATE_RISK`.

| Component | Where | Classification | Rationale |
|---|---|---|---|
| **Model Selection** | `packages/capabilities/model-selection` (`ugence_model_selection`) | `REFERENCE_ONLY` (pattern) + `COMPOSE` (per-assignment model-policy ref) | AWC copies its two-stage constraint-first shape and invariants; does **not** import it; records only a neutral `model_policy_ref`. |
| **AI Hiring** | `packages/products/ai-hiring` (`ugence_ai_hiring`) + `ai_hiring/` | `REFERENCE_ONLY` | Donates rubric/evidence/eligibility/authority-separation/immutable-record/replay **patterns**. **No dependency; no candidate/employment entity reuse.** |
| **`ugence-decision-authority` kernel** | `packages/capabilities/decision-authority` (`ugence_decision_authority`) | `REUSE` (domain-neutral primitives) | `DomainModel`, `ActorType`, `AuditEvent`, `ReasonCode`/catalog, `canonical_hash`, `Clock`/`IdFactory`, decision-case/CER contracts are already domain-neutral and extracted from hiring. AWC binds to the opaque-`subject_ref` seam. |
| **Governance Contracts** | `packages/governance-contracts` (`ugence_governance_contracts`) | `REUSE` | Neutral provenance vocabulary: `evidence_refs`, `decision_refs`, `policy_refs`, `authority_context`/`authority_basis`, `fingerprint`, `correlation_id`; `ProviderKind`/`ProviderCapabilities`/`ProviderDescriptor` for the provider side. Leaf, stdlib-only. |
| **Policy Workflow Compiler** | `packages/tooling/policy-workflow-compiler` (`ugence_policy_workflow_compiler`) — **implemented** (PR #1303) | `COMPOSE` (upstream input) | `[EXISTING]` Emits a typed, deterministic **`WorkflowIR`** (`workflow_ir.v1`: 14 node kinds, 9 edge kinds, content-addressed node ids) that AWC consumes. AWC defines a versioned data-only adapter (`CompilerWorkflowAdapter`) over `WorkflowIR` — **not** a second IR (§7). Document extraction / NLP / runtime deployment remain outside the compiler's implemented Phase 1 scope. |
| **StoryGraph policy-pack compiler** | `packages/capabilities/storygraph/.../policypack/compiler.py` | `REFERENCE_ONLY` | Real deterministic-compile-with-digest-lineage + human-approval publish gate — the template for AWC's compile+freeze+publish discipline (`CompiledPolicyBundle`: `source_pack_digest`, `bundle_digest`, `lineage`, `publishable`). |
| **Tool contracts** | `cyber_security/action_gateway_mcp/.../registry.py` (`ToolSpec`); `agent_runtime_migration/tools/registry.py` (`RegisteredTool`, `RiskClass`) | `ADAPT` | Model the per-tool contract shape (`required_evidence`, `approver_policy`, `scope_permissions`, `consequence`, `reversibility`, `simulation_required`) and the risk-class-from-trusted-registry-never-model discipline. |
| **H16 multi-agent coordination** | `agentic/agentic_framework/coordination.py`, `multi_agent.py` | **`OVERLAPPING` / `DUPLICATE_RISK`** → `ADAPT` | Already implements agent profiles, deterministic candidate selection, delegation/assignment, authority model, fallback-across-candidates. AWC must **adapt/canonicalize** these into a leaf capability, not fork them. The *runtime coordination/recovery* and `LLMRouter` parts stay in H16 and are `OUT_OF_SCOPE` for AWC. |
| **Agent Runtime** | `packages/runtime/agent-runtime` (`ugence_agent_runtime`) | `COMPOSE` (downstream) | Executes a `WorkflowDefinition` of `TaskDefinition`s, selects **providers** (not agents), enforces a fail-closed governance boundary. Has **no** agent-selection/team/permission model (only an unused `AgentDescriptor`). AWC's handoff artifact maps to a `WorkflowDefinition`; AWC does not import it. |
| **Decision Authority / ActionGate / Action Clearance / StoryGraph (as authorities)** | see §3 | `OUT_OF_SCOPE` (boundary) | AWC must not own any of their functions; may reference their records by id/hash only. |
| **H22 multi-workflow orchestration** | `agentic/.../multi_workflow_orchestration.py` | `OUT_OF_SCOPE` (boundary) | H22 consumes `PortfolioWorkflowEntry.assigned_agent` + `authority_scope` as **fixed inputs**; AWC **produces** exactly those. Clean, complementary seam; AWC never schedules/budgets. |

**Net:** the single load-bearing risk is the H16 overlap. The design is only defensible if AWC treats
`coordination.py`/`multi_agent.py` as the canonicalization source and does not stand up a second, divergent
agent-profile/selection model. See §31 and the roadmap.

---

## 6. Canonical object model (overview)

`[SPEC]` Full field-level definitions and the AI-Hiring mapping table live in
`AGENT_WORKFORCE_COMPOSER_OBJECT_MODEL.md`. Summary of the canonical objects (names improved for domain neutrality;
where a name collides with an existing H16 symbol it is flagged for reconciliation):

- **`WorkflowRoleRequirement`** — the measurable requirement for one eligible workflow step.
- **`AgentCapability`** / **`CapabilityEvidence`** — a declared/measured/observed capability and its provenance.
- **`AgentProfile`** — an agent's evidence-backed manifest. **Resolved** by the Phase 0 ADR (`docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`): the selection `AgentProfile` is canonicalized into the AWC namespace; H16 retains its runtime coordination and may re-export the canonical profile only where fields are byte-identical.
- **`AgentRegistrySnapshot`** — the frozen, content-addressed set of profiles AWC selects over.
- **`EnterpriseAgentPolicy`** — customer-owned hard constraints and prohibitions (governance plane).
- **`CompositionPolicy`** — the versioned policy-as-data artifact (weights, team rules) the AWC engine interprets.
- **`CompositionRequest`** — the frozen tuple of all inputs (role requirements + snapshot + policies + `now`).
- **`AgentEligibilityResult`** — per-(agent,role) eligibility verdict + reasons (never a score).
- **`AgentAssessment`** / **`AgentScore`** — evidence-backed assessment and the ranked score over eligible agents.
- **`EliminationReason`** — an append-only reason-code taxonomy (mirrors Model Selection `ReasonCode`).
- **`RoleSelectionDecision`** — per-role: selected agent, ranked eligibles, eliminated agents + reasons.
- **`AgentAssignment`** — a role → agent binding with a bounded `AgentPermissionGrant` and `AuthorityBoundary`.
- **`AgentPermissionGrant`** / **`AuthorityBoundary`** — the narrowed permission subset + authority ceiling.
- **`NonAgentDisposition`** — `NO_AI_AGENT_REQUIRED` / `DETERMINISTIC_SERVICE_PREFERRED` / `HUMAN_AUTHORITY_REQUIRED`
  / `HUMAN_REVIEW_REQUIRED` for steps that should not be staffed by an AI agent.
- **`TeamCandidate`** — a whole-team option evaluated for joint feasibility (interfaces, SoD, cost, correlation).
- **`AgentTeamPlan`** — the immutable output: assignments, non-agent dispositions, fallbacks, snapshot digest,
  policy version, and the rendered explanation. Un-forgeably `plan_only`.
- **`FallbackAssignment`** — a fallback agent per role, re-checked against the primary's hard constraints.
- **`SelectionExplanation`** / **`SelectionReplayRecord`** — the ledger and the frozen replay bundle.
- **`ReassignmentDecision`** / **`AgentOutcomeObservation`** / **`AgentPerformanceSnapshot`** — `[DEFERRED]`
  runtime-adaptation objects (design present; not in MVP).

---

## 7. Workflow-role extraction contract

`[SPEC]` **Input.** AWC consumes the canonical **`WorkflowIR`** emitted by the **implemented** Policy Workflow
Compiler (`[EXISTING]` `ugence_policy_workflow_compiler.api.WorkflowIR`, `workflow_ir.v1` — nodes carry
`kind`, `owning_capability`, `disposition` (ADVISORY/AUTHORITATIVE), `input_object_ids`, `failure_behavior`,
`audit_requirements`; edges carry a deterministic `order`). AWC defines a stable, versioned, data-only adapter
interface `CompilerWorkflowAdapter` (formerly named `WorkflowGraphSource`) over `WorkflowIR` — a thin classifier,
**not** a second workflow representation. For offline assurance the MVP may additionally accept a hand-authored
`WorkflowIR` fixture of the same type. AWC never re-derives controls; it reads them.

`[SPEC]` **Extraction is deterministic and per-node.** For each workflow node, the extractor classifies the node
into exactly one of:
- **agent-eligible role** → emit a `WorkflowRoleRequirement`;
- **deterministic control** (the compiler mapped it to a rule engine / evidence collector) → `NonAgentDisposition
  = DETERMINISTIC_SERVICE_PREFERRED`;
- **binding decision gate** (mapped to Decision Authority) → `HUMAN_AUTHORITY_REQUIRED` (no AI agent staffs it);
- **exact-action authorization** (mapped to ActionGate) → not a role; the action-executing role downstream gets a
  narrowly bounded permission and must pass ActionGate at runtime;
- **required human review** → `HUMAN_REVIEW_REQUIRED`.

`[SPEC]` **`WorkflowRoleRequirement` fields** (measurable; wrong-side value on any *hard* field eliminates an
agent): `role_id`, `workflow_id`, `workflow_node_id`, `required_capabilities`, `optional_capabilities`,
`required_tools`, `input_contract`, `output_contract`, `domain_requirements`, `minimum_quality`, `maximum_latency`,
`maximum_cost`, `data_classification`, `residency_constraints`, `required_permissions`, `prohibited_permissions`,
`authority_ceiling`, `stateful_or_stateless`, `human_review_requirement`, `fallback_behavior`, plus provenance
(`source_node_ref`, `policy_refs`) and a `requirement_digest`.

`[SPEC]` **Provenance invariant** (mirrors the compiler's "every object cites its source"): every
`WorkflowRoleRequirement` cites the node it derived from; a requirement with no source node fails extraction
(fail-closed). `data_classification` and `authority_ceiling` are **not invented by AWC** — they are read from the
compiled node (the compiler's "authoritative-field designations" and "authority requirement" objects) or, if
absent, default to the most restrictive value and are flagged for human review.

---

## 8. Agent registry schema

`[SPEC]` The **`AgentRegistrySnapshot`** is a frozen, content-addressed set of `AgentProfile`s plus a
`snapshot_digest` and the `captured_at` timestamp (passed in — never read from a clock). AWC treats the registry
as **input data**; it does not discover, register, benchmark, or health-check agents (those are upstream/`DEFERRED`).

`[SPEC]` **`AgentProfile` fields** (evidence-backed; see §9/§10 for the declared/measured/observed split):
`agent_id`, `agent_version`, `provider`, `agent_type`, `capability_manifest: AgentCapability[]`, `tool_contracts`,
`input_schemas`, `output_schemas`, `domain_specializations`, `model_dependencies`, `permission_requirements`,
`authority_requirements`, `data_access_requirements`, `deployment_location`, `security_classification`,
`latency_profile`, `cost_profile`, `reliability_profile`, `benchmark_evidence: CapabilityEvidence[]`,
`observed_failure_modes`, `audit_support`, `state_model`, `concurrency_limit`, `version_status`
(`declared`/`enumerated`/`benchmarked`/`production_observed`/`disabled`, mirroring Model Selection's `ExecStatus`
discipline — never "benchmarked" from declaration alone), and `profile_digest`.

`[SPEC]` **Tool contract shape** (`ADAPT` from `ToolSpec`/`RegisteredTool`): each entry in `tool_contracts` carries
`tool_id`, `read_only`, `consequence`/`risk_class` (`LOCAL_READ_ONLY` vs `GOVERNED_CONSEQUENTIAL`, set by a trusted
operator — **never by the agent or a model**), `reversibility`, `scope_permissions`, `required_evidence`,
`approver_policy`, `simulation_required`. AWC uses these only to *check* interface/permission compatibility, never
to grant or execute.

---

## 9. Declared vs measured vs observed capabilities

`[SPEC]` AWC enforces the same three-provenance discipline Model Selection's spec mandates (`[EXISTING]`
`MODEL_SELECTION_POLICY_ENGINE_SPEC.md` §5) and AI Hiring implements (`[EXISTING]` `BindingProvenance`,
`SupplierType`):

- **Declared** — vendor/provider assertion (`AgentCapability.declared = True`). **Never sufficient for selection.**
  An agent claiming "financial reconciliation" is not an agent that has *passed* a controlled reconciliation
  benchmark.
- **Measured** — result of a controlled AWC/enterprise benchmark (`CapabilityEvidence.source = BENCHMARK`).
- **Observed** — production/pilot telemetry (`CapabilityEvidence.source = PRODUCTION_TELEMETRY`).

`[SPEC]` **Trust precedence** (structural, mirrors Model Selection §5): `observed > measured > declared`. A hard
constraint that requires a capability is satisfiable **only** by measured or observed evidence unless the
`CompositionPolicy` explicitly permits declared-only for that capability (a policy-visible, audited relaxation,
never a silent one). Unknown/absent evidence is `UNKNOWN`, never a silent pass (mirrors Model Selection's
`Signal.value is None ⇒ UNKNOWN`).

---

## 10. Evidence and provenance model

`[SPEC]` **`CapabilityEvidence` fields**: `evidence_id`, `capability_id`, `source`
(`VENDOR_DECLARED`/`BENCHMARK`/`PRODUCTION_TELEMETRY`/`PILOT`/`IMPORTED_APPROVED_RECORD`), `metric`, `value`,
`sample_size`, `evaluated_at`, `ttl_seconds`, `confidence`, `evidence_ref` (opaque locator, not raw content),
`provenance` (who/what supplied it, from the trusted set), `raw_signal` (audit only). Method `is_stale(now)`
(mirrors Model Selection `Evidence.is_stale`). Stale evidence deterministically degrades to `UNKNOWN`.

`[SPEC]` **First-class negatives** (mirrors AI Hiring `MissingEvidenceRecord`/`ExcludedEvidenceRecord`):
missing evidence for a required capability and excluded (untrusted/expired) evidence are **recorded**, never
silently dropped and never auto-converted into an adverse capability rating. A `NO_ELIGIBLE_AGENT` for a role
must be traceable to specific missing/excluded evidence records.

`[SPEC]` **Reuse:** `evidence_ref`, `policy_refs`, `correlation_id`, and `fingerprint` come from
`ugence_governance_contracts` `[EXISTING]`. AWC defines no new hashing primitive; it uses `canonical_hash`
(`REUSE` from the decision-authority kernel) for all digests.

---

## 11. Hard constraints vs optimization preferences

`[SPEC]` The separation rule is Model Selection's (`[EXISTING]` §3.2), lifted verbatim: **a dimension is a hard
constraint if any wrong-side value makes an agent *impermissible* for the role; a preference if all survivors are
acceptable but some are better. Constraints eliminate; preferences rank.** Crucially, the split is a **function of
the role's facets**, resolved per requirement — e.g. latency is a hard bound for an interactive support role, a
preference for a batch reconciliation role.

`[SPEC]` **Hard constraints** (any failure ⇒ `INELIGIBLE`, evaluated *before* any scoring):
missing required capability (with insufficient provenance); incompatible input/output contract; forbidden provider;
wrong data residency / data-classification violation; insufficient permission isolation; required authority exceeds
the role's `authority_ceiling`; unapproved tool; cost above hard ceiling; latency beyond SLA; benchmark/quality
below `minimum_quality`; untrusted, expired, or disabled agent version; prohibited permission required by the agent.

`[SPEC]` **Governance precedence** (three-plane strict order, mirrors Model Selection §11.3): **EnterpriseAgentPolicy
vetoes > capability/role constraints > optimization scores.** Governance is a **separate higher-precedence veto
plane**, not "more weights"; a large enough preference score can never overwhelm a compliance veto (Model Selection
§11.4's latent-illegal-selection argument applies identically).

`[SPEC]` **Preferences** (rank only the eligible set): task quality, domain fit, reliability, latency, cost,
security posture, integration compatibility, observability, historical outcomes, fallback availability.

**Invariant (constraint supremacy):** *no preference score may promote an agent that fails any hard constraint;
elimination is absolute and precedes scoring.* (Model Selection §2.3 invariant 1, restated for agents.)

---

## 12. Agent eligibility procedure

`[SPEC]` For each `(AgentProfile, WorkflowRoleRequirement)` pair the **eligibility gate** produces an
`AgentEligibilityResult` with a per-condition `ConditionResult[]` and an aggregate state
`ELIGIBLE / INELIGIBLE / CONDITIONALLY_ELIGIBLE / INDETERMINATE` (mirrors Model Selection `EligibilityState`).
Aggregation algebra (fixed precedence, mirrors `ExecutionGate._aggregate`):
- any governance-critical condition not PASS, or any operational-critical FAIL, or a fail-closed UNKNOWN ⇒ `INELIGIBLE`;
- else operational-critical UNKNOWN in the fail-closed set ⇒ `INDETERMINATE`;
- else operational UNKNOWN ⇒ `CONDITIONALLY_ELIGIBLE` (only if the policy allows conditional) else `INELIGIBLE`;
- else `ELIGIBLE`.

`[SPEC]` The gate **never ranks or picks** (Model Selection's `ExecutionGate` discipline). Every agent exits
classified (no silent drops — "explainability totality"); reasons are `EliminationReason` codes drawn from the
append-only taxonomy. Only `ELIGIBLE`/`CONDITIONALLY_ELIGIBLE` agents enter scoring.

---

## 13. Individual-agent scoring procedure

`[SPEC]` The scorer ranks **only the eligible pool** using `CompositionPolicy` weights (policy-as-data; the engine
is a generic interpreter — Model Selection §2.1 "the policy is the product; the engine is the interpreter").
Utility per agent = weighted sum over normalized preference dimensions (quality, domain fit, reliability,
−cost/cref, −latency/lref, security posture, integration compatibility, observability, historical outcome), minus a
`conditional_penalty` for `CONDITIONALLY_ELIGIBLE` agents. Scores are rounded (deterministic) and ties broken by a
stable secondary key (`agent_id`), exactly as `ModelPolicy.select` does (`scored.sort(key=(-utility, agent_id))`).

`[SPEC]` **No empty success:** an empty eligible pool for a role yields `NO_ELIGIBLE_AGENT` with the recorded
reasons — never an invented pick (Model Selection §2.3 invariant 5). Quality is supplied as evidence-backed input
(`quality_of(agent, role)` derived from measured/observed evidence), never computed by an LLM inside AWC — AWC's
core contains **no inference** (mirrors AI Hiring's deterministic runtime).

Full pseudocode is in `AGENT_WORKFORCE_COMPOSER_SELECTION_POLICY.md`.

---

## 14. Multi-agent team-composition procedure

`[SPEC]` Selecting the best individual agent per role need not yield the best *team*. The composer evaluates one or
more `TeamCandidate`s (e.g. the greedy per-role best; a specialist-split option; a hybrid deterministic-services +
agents option — §19/§35) and, for each, checks joint feasibility:
- **interface compatibility** — each producer's `output_contract` satisfies the consumer's `input_contract` (§15);
- **duplicated capability** — flag redundant agents that add cost/authority without quality;
- **permission conflicts** — no two assignments require mutually exclusive permissions on the same resource;
- **data-transfer boundaries** — a data-classification-lowering handoff across a residency/classification boundary
  is a hard reject;
- **cumulative cost** and **cumulative latency** against workflow-level ceilings;
- **correlated failure / provider concentration** (§20);
- **concentration of authority** — no single agent holds excessive end-to-end authority (§18).

`[SPEC]` A `TeamCandidate` that fails any *hard* team-level check is eliminated (recorded); survivors are ranked by
the policy's team objective. The chosen team's rationale — including *why this composition over the alternatives*
(the general-purpose-vs-specialist-vs-hybrid trade — §19) — is written to the explanation ledger. If **no**
`TeamCandidate` is feasible, AWC returns a partial plan marking the offending roles `NO_ELIGIBLE_AGENT` /
`HUMAN_REVIEW_REQUIRED` and does not fabricate a team.

---

## 15. Interface-compatibility checks

`[SPEC]` For every producer→consumer edge in the workflow graph, AWC checks that the upstream assignment's declared
`output_schema`/`output_contract` structurally satisfies the downstream `input_contract` (required fields present,
types compatible, data-classification non-increasing across a lowering boundary, units/encoding declared). A
mismatch is a **hard** team-level elimination with an `INTERFACE_INCOMPATIBLE` reason and the specific field(s)
recorded. AWC performs **structural** checking only — it does not execute agents to test compatibility (that would
be runtime behavior). Where a schema is absent, the edge is `INDETERMINATE` and fails closed unless the policy
permits conditional composition with a recorded obligation.

---

## 16. Permission and authority assignment

`[SPEC]` Each `AgentAssignment` carries an **`AgentPermissionGrant`** (the *minimal* permission subset the role
requires, intersected with the agent's `permission_requirements` and the role's `prohibited_permissions` removed)
and an **`AuthorityBoundary`** (the role's `authority_ceiling`, never exceeded). Construction is **least-privilege
by default**: the grant starts empty and only adds permissions each with a cited `WorkflowRoleRequirement`. A grant
that would include a `prohibited_permission`, or an authority above the ceiling, is a construction-time failure
(type-enforced, mirroring AI Hiring's `BoundaryViolationError`-at-construction).

`[SPEC]` **Monotonicity / non-broadening:** the grant is a *request for at most* these permissions; runtime +
ActionGate + Action Clearance may only narrow it. AWC records the grant as a bound, never as an entitlement. Example
bounded contracts (§35 procurement): a document-extraction agent may *read documents / produce extracted fields*
and may **not** approve or write to an ERP; a policy-validation agent may *recommend HOLD/PASS* and may **not** make
the binding decision (that routes to Decision Authority); an ERP-action agent may *execute the approved ERP update
only after ActionGate authorization and Action Clearance*.

---

## 17. Separation-of-duties rules

`[SPEC]` AWC enforces role-level SoD in the plan (proposal-time; the binding SoD authority remains Decision
Authority): (a) the agent that *recommends* a binding decision must not be the agent that *executes* the resulting
action; (b) the agent that *prepares* an action must not be the sole agent that *validates* it; (c) no agent may
hold both "produce recommendation" and "authorize action" permissions for the same decision. Violations are hard
team-level eliminations (`SEPARATION_OF_DUTIES_VIOLATION`). SoD rules are policy-as-data in `CompositionPolicy`, so
enterprises can add domain-specific incompatibilities.

---

## 18. Concentration-of-authority risk

`[SPEC]` For each `TeamCandidate`, AWC computes an **authority-concentration measure**: the fraction of the
workflow's total consequential authority (weighted by tool consequence/risk-class and reachable resources) that any
single agent holds end-to-end. If a single agent's share exceeds the policy's `authority_concentration_ceiling`, the
candidate is rejected (`AUTHORITY_CONCENTRATION_EXCEEDED`) with a recorded suggestion to split the role. This is the
mechanism that lets AWC prefer a specialist split (Option B, §19) over a single general-purpose agent that would
concentrate authority (Option A) when governance so requires. The measure and ceiling are `[UNVALIDATED]` heuristics
in the MVP — deterministic and explainable, but not empirically calibrated; the roadmap flags calibration.

---

## 19. Cost, latency and quality trade-offs (composition alternatives)

`[SPEC]` AWC evaluates and *compares* at least three archetypal compositions and records the trade in the ledger:

| Option | Shape | Cost | Latency | Quality (measured) | Observability | SoD | Authority concentration | Correlated failure | Handoff complexity |
|---|---|---|---|---|---|---|---|---|---|
| **A** general-purpose | one agent, many steps | lower | lower (no handoffs) | often lower per-step | coarse | weak | **high** | single point | minimal |
| **B** specialist team | one agent per step | higher | higher (handoffs) | often higher per-step | fine | strong | low | diversified | high |
| **C** hybrid | deterministic services + a few agents | lowest where rules suffice | low | high where deterministic | fine | strong | low | low | medium |

`[SPEC]` The policy's objective decides which trade wins for a given workflow; the engine only *reports and applies*
it. AWC's default `[PROPOSED]` bias, where governance constraints bind, is **C then B then A** — prefer a
deterministic service or a specialist with bounded authority over a single high-authority generalist — but this is a
policy default, overridable, and `[UNVALIDATED]`.

---

## 20. Correlated failure and provider concentration

`[SPEC]` AWC computes provider/model/infrastructure concentration across a `TeamCandidate` and its fallbacks. A team
in which all critical roles depend on the same provider, the same underlying model family, or the same deployment
region has **correlated failure risk**: one provider outage disables the whole workflow. Policy sets a
`max_provider_share` and requires that a role's **fallback must not share the primary's provider/model/region**
unless no alternative exists (recorded as a residual risk). Exceeding concentration limits is a soft penalty by
default and a hard reject when the policy marks the workflow business-critical.

---

## 21. Fallback and reassignment policy

`[SPEC]` **Fallback (in MVP).** For each assigned role AWC selects an ordered `FallbackAssignment` chain. Every
fallback is re-evaluated against the **same hard constraints and the same `authority_ceiling`** as the primary — a
fallback can never be more permissive than what it replaces (Model Selection §9.7 "no recovery path may violate a
hard constraint"; Action Clearance non-broadening). A fallback that would broaden permissions is rejected. If no
constraint-satisfying fallback exists, the role's `fallback_behavior` (from the requirement) decides:
`ESCALATE_TO_HUMAN` / `HALT_ROLE` / `PROCEED_WITHOUT_FALLBACK` (recorded).

`[SPEC]` **Reassignment (`[DEFERRED]` — designed, not in MVP).** Triggers: agent unavailable, quality below
threshold, latency breach, cost change, permission revoked, agent-version change, benchmark expiry, repeated
failure, workflow-requirement change. Governance: a `ReassignmentDecision` re-runs the primary's hard-constraint
check against the frozen requirement; a consequential reassignment requires human approval; the runtime resumes from
a durable checkpoint. **A restricted agent is never silently replaced by a more permissive one.** AWC itself never
performs the reassignment at runtime (that is Agent Runtime / H16 territory); it only *plans* the fallback and,
if invoked again with new inputs, *re-computes* a plan.

---

## 22. Human-approval requirements

`[SPEC]` Mirroring StoryGraph's compiler publish gate (`publish()` refuses without human approvals `[EXISTING]`) and
AI Hiring's human-authority separation: an `AgentTeamPlan` is **advisory until approved**. AWC emits the plan as a
proposal; a `plan_approval` (human or delegated-policy actor, from the decision-authority `AuthorityType` set — no
AI actor) is required before the plan may be handed to the runtime for any workflow that contains a consequential
role. AWC records but never *grants* the approval. Roles marked `HUMAN_REVIEW_REQUIRED` / `HUMAN_AUTHORITY_REQUIRED`
carry the requirement into the plan so the runtime cannot execute past them without the human step.

---

## 23. Determinism and snapshot pinning

`[SPEC]` AWC's core is a **pure function** over frozen inputs (Model Selection §2.1):
`compose_agents(role_requirements, agent_registry_snapshot, enterprise_constraints, composition_policy, now) → AgentTeamPlan`.
- No I/O, no clock, no randomness inside the core; `now` is passed in.
- Every non-determinism is frozen into the snapshot; the `AgentTeamPlan` records the `snapshot_digest`, the
  `CompositionPolicy` version, and a `request_fingerprint` (`canonical_hash`, `REUSE`).
- Stable sorting and explicit tie-breaks everywhere (§13, §14).
- Same frozen inputs ⇒ byte-identical plan and digest (tested contract; AI Hiring `test_h5_determinism` is the
  template).

---

## 24. Explanation and elimination ledger

`[SPEC]` The **`SelectionExplanation`** is a total account: **every** agent, for **every** role, exits either in
`eliminated[]` (with `{reason_code, constraint, required, actual, evidence_ref}`) or in `scored[]` (with per-dimension
contributions, total, selected flag, confidence) — no silent drops (Model Selection §7 total-accounting;
"explainability totality"). Every team-level rejection (interface, SoD, concentration, correlation) is recorded with
the specific offending pair/field. Prose is rendered **deterministically from the structured record** so the
narrative can never disagree with the data (Model Selection §7 deterministic template rendering). The ledger also
records the composition-alternatives comparison (§19) and the residual risks accepted.

---

## 25. Audit and replay contract

`[SPEC]` The **`SelectionReplayRecord`** freezes the exact inputs (or their digests) + the `CompositionPolicy`
version + `now`, such that replaying yields the identical `AgentTeamPlan`. Audit events are **hash-chained**
(`previous_event_hash → event_hash`, `ADAPT` from AI Hiring `HiringDomainAuditEvent`) and carry
`correlation_id`/`causation_id`. A `reconstruct(plan_id)` service rebuilds the requirement→eligibility→score→
composition→assignment chain and verifies: hash chain valid; every assignment cites a `WorkflowRoleRequirement`;
no permission grant exceeds its ceiling; human approval upheld where required. (Template: AI Hiring
`GovernanceCaseReconstructionService` `[EXISTING]`.)

---

## 26. Counterfactual analysis

`[SPEC]` AWC supports **offline counterfactuals** because its core is a pure function: re-run `compose_agents` with
one input perturbed (drop an agent, tighten residency, lower a cost ceiling, expire an evidence item) and diff the
two `AgentTeamPlan`s. Outputs: which agents newly become ineligible, which assignments change, the cost/latency
delta, and any role that becomes `NO_ELIGIBLE_AGENT`. This is deterministic and exact — unlike Model Selection's
*runtime* counterfactuals (§8.3), which need shadow/off-policy estimation because only the chosen model is observed
in production. AWC's planning-time counterfactual has no such limitation; **runtime** outcome counterfactuals
(did the chosen team actually perform best?) remain `[DEFERRED]` and would require the same estimation machinery.
The constraint-change demo (§33/§35) is the flagship counterfactual.

---

## 27. Assurance and synthetic test generation

`[SPEC]` See `AGENT_WORKFORCE_COMPOSER_ASSURANCE_PLAN.md`. Summary: property-based synthetic generation of
registries and workflows; invariants asserted as executable tests (constraint supremacy, no-empty-success,
non-broadening fallback, total accounting, determinism/replay, monotonic permission narrowing); a frozen golden
corpus of the three reference workflows (§35) with expected plans; mutation tests (perturb an input, assert the
plan changes in the predicted direction).

---

## 28. Failure modes and fail-closed behavior

`[SPEC]` AWC is **fail-closed** everywhere:
- missing/mismatched workflow graph → extraction fails, no plan;
- unknown/stale/expired evidence → `UNKNOWN`, never a pass;
- empty eligible pool → `NO_ELIGIBLE_AGENT`, never an invented pick;
- no feasible team → partial plan with offending roles flagged, never a fabricated team;
- absent `data_classification`/`authority_ceiling` → most-restrictive default + review flag;
- snapshot/policy digest mismatch on replay → hard error, not a re-derivation;
- any construction that would broaden permissions/authority → type error at construction.
A degraded AWC returns *less* staffing (more human-review / no-eligible-agent), never *more* authority.

---

## 29. Security and privacy boundary

`[SPEC]` AWC handles **metadata about agents and roles**, not customer payloads. Evidence is referenced by opaque
`evidence_ref`, not embedded raw content (AI Hiring's `evidence_ref`/`content_hash` seam). The registry snapshot may
contain sensitive provider/security-classification data; AWC treats it as `data_classification`-tagged and never
emits it beyond the plan's audience. Multi-tenancy: every object carries a `tenant_id` (AI Hiring pattern) and AWC
never composes across tenants. AWC holds **no credentials** and issues none (the runtime + providers own
credentials). The plan itself is classified at the max classification of its inputs.

---

## 30. Public API proposal

`[SPEC]` Single supported surface `ugence_agent_workforce_composer.api` (curated re-export, adds no logic — Model
Selection `api.py` pattern). Core:

```python
def compose_agents(
    role_requirements: Sequence[WorkflowRoleRequirement],
    agent_registry_snapshot: AgentRegistrySnapshot,
    enterprise_constraints: EnterpriseAgentPolicy,
    composition_policy: CompositionPolicy,
    *, now: float,
) -> AgentTeamPlan: ...

def extract_roles(workflow_ir: WorkflowIR, *, now: float) -> list[WorkflowRoleRequirement | NonAgentDisposition]: ...  # via CompilerWorkflowAdapter
def evaluate_eligibility(profile: AgentProfile, role: WorkflowRoleRequirement, *, policy, now) -> AgentEligibilityResult: ...
def explain(plan: AgentTeamPlan) -> SelectionExplanation: ...
def replay(record: SelectionReplayRecord) -> AgentTeamPlan: ...
def counterfactual(record: SelectionReplayRecord, mutation: InputMutation) -> PlanDiff: ...
def fingerprint(obj) -> str: ...   # via canonical_hash (REUSE)
```

Everything is pure and deterministic; no method performs I/O, executes an agent, or contacts a provider.

---

## 31. Package boundary and dependency direction

`[PROPOSED]` **AWC is a capability, not a product, tooling, or part of orchestration.** Reasoning (mirrors the
Model Selection placement ADR):
- It is **cross-cutting**: Procurement, Finance, Security, Customer Support, and AI Hiring can all consume it — the
  terminology audit's definition of a *capability* (internal reusable engine) vs a *product* (customer-facing
  composition). It is not a single vertical.
- It is **not orchestration**: it emits a plan and stops; it does not schedule (H22), execute (Agent Runtime), or
  coordinate at runtime (H16). The repo's own note rejected the "AI Orchestrator" framing for the analogous Model
  Selection engine.
- It is a **policy decision service** (policy-as-data, provider-neutral, deterministic) — exactly the shape the ADR
  accepted for Model Selection.

`[PROPOSED]` **Path** `packages/capabilities/agent-workforce-composer/` · **dist** `ugence-agent-workforce-composer`
· **namespace** `ugence_agent_workforce_composer`. **Dependency policy (leaf-ward):** depend only on the Python
standard library plus, at most, `ugence-governance-contracts` and the domain-neutral `ugence-decision-authority`
kernel primitives (`DomainModel`, `ActorType`, `AuditEvent`, `canonical_hash`, `Clock`/`IdFactory`, reason-code
catalog). **Must NOT depend on** applications, domains, the AI Control Plane, the optional orchestrator, Agent
Runtime, H22, Model Selection, Hybrid LLM, the Governance Provider Framework, concrete providers, `ai_hiring`, or the
`agentic/` framework. Upstream inputs (workflow graph, registry snapshot) arrive as **injected data**, never imports
— preserving the acyclic dependency rule the repo machine-verifies. The H16 reconciliation (§5) is a **content**
task (adapt concepts), explicitly **not** a dependency edge.

**Overlap verdict for the concluding questions:** AWC does **not** overlap materially with Model Selection (peer,
one level up, composable) or H22 (complementary; H22 consumes what AWC produces). It **does** overlap with the H16
coordination layer, and that overlap is the gating design risk — resolved by `ADAPT`, not fork.

---

## 32. Versioning and maturity model

`[SPEC]` Follows the repo's H-phase discipline (`[EXISTING]` AI Hiring H0–H6). Distribution SemVer + a separate
**capability-maturity** label. Contract version `awc.v1` on the public objects. Frozen public-API snapshot +
`verify_agent_workforce_composer_distribution.py` (Model Selection / decision-authority pattern). `CompositionPolicy`
and the `EliminationReason` taxonomy are **append-only, versioned data**; reason codes are never repurposed.
Initial honest label: **research / design-stage; `production_certified = False`**; no benchmark, validation, or
demand claim.

---

## 33. MVP scope

`[SPEC]` **Deterministic and offline.** In:
- three reference workflows (§35): procurement approval, customer-support escalation, cybersecurity incident triage;
- 10–15 **synthetic** agent profiles with declared/measured/observed evidence;
- frozen registry snapshots + `CompositionPolicy` + `EnterpriseAgentPolicy` fixtures;
- role extraction from a real compiler `WorkflowIR` fixture (the Policy Workflow Compiler is implemented; a hand-authored `WorkflowIR` of the same type is an additional offline fixture);
- hard-constraint elimination; individual scoring; team composition; permission-bounded assignments;
- fallback selection; the explanation/elimination ledger; replay; offline counterfactual (the constraint-change
  demo — "customer data must remain in India");
- the five non-agent dispositions;
- assurance corpus + invariant tests.

Out (hard) for MVP: **no execution of any real/arbitrary agent; no production connectors; no autonomous external
action; no live registry/discovery/benchmarking; no runtime reassignment; no model routing; no scheduling.**

## 34. Explicitly deferred capabilities

`[DEFERRED]` Runtime adaptation/reassignment (§21); live agent registry, discovery, and continuous benchmarking;
production telemetry ingestion for `observed` evidence; runtime outcome counterfactuals and off-policy estimation
(§26); learned ranking (a learned model may *rank a proposal* but may **never** be an enforcement node — Policy
Workflow Compiler §7 `[EXISTING]`); marketplace; cross-tenant portfolio optimization; real Policy-Workflow-Compiler
integration (pending its implementation).

---

## 35. Worked examples

Full walkthroughs (roles, requirements, eligibility eliminations, team, bounded grants, fallbacks, the constraint
counterfactual) are in `AGENT_WORKFORCE_COMPOSER_SELECTION_POLICY.md` §Worked-Examples. Summary:

**35.1 Procurement approval.** Steps → roles: request-validation, supplier-risk, budget-analysis, recommendation,
approval-coordination, purchase-action, reconciliation. AWC shows: *human approval* is **not** an AI role
(`HUMAN_AUTHORITY_REQUIRED`); *exact-action authorization* is **ActionGate**, not a role; *request validation* may be
`DETERMINISTIC_SERVICE_PREFERRED`; the purchase-action agent gets a narrowly bounded grant (execute approved ERP
update only, post-ActionGate + Action-Clearance). Then the India-residency counterfactual eliminates non-compliant
agents and recomposes.

**35.2 Customer-support escalation.** Roles: classification, knowledge-retrieval, response-drafting, escalation. The
binding refund/credit **decision** is `HUMAN_AUTHORITY_REQUIRED` (Decision Authority); the reply-sending action is
bounded and passes ActionGate; drafting/retrieval agents get read-only knowledge scopes.

**35.3 Cybersecurity incident triage.** Roles: evidence-collection, threat-analysis. **StoryGraph** provides
*advisory* sequence-risk input the analysis role may consume but must not treat as a binding block; containment
**actions** are `HUMAN_AUTHORITY_REQUIRED` + ActionGate; the plan grants read-only collection scopes and forbids the
analysis agent any containment permission (SoD).

---

## 36. Acceptance criteria

`[SPEC]` (full list in the assurance plan). AWC v0.1 is accepted when, over the frozen MVP corpus:
1. **Determinism** — identical inputs ⇒ byte-identical `AgentTeamPlan` + digest; replay reproduces it exactly.
2. **Constraint supremacy** — no test produces a plan in which a hard-constraint-violating agent is assigned.
3. **Total accounting** — every agent appears in `eliminated[]` or `scored[]` for every role; no silent drops.
4. **No empty success** — empty eligible pool ⇒ `NO_ELIGIBLE_AGENT`, never an invented pick.
5. **Non-broadening** — no fallback and no permission grant ever exceeds the primary/role authority ceiling.
6. **Non-agent dispositions** — the three reference workflows each yield at least one correct non-agent disposition.
7. **Counterfactual** — the India-residency mutation deterministically eliminates the expected agents and recomposes
   (or reports `NO_ELIGIBLE_AGENT`), with a correct cost/latency delta.
8. **Boundary** — AWC emits no decision/authorization/clearance/schedule; import-boundary test forbids Agent Runtime,
   H22, Model Selection, providers, `ai_hiring`, and `agentic/`.

---

## 37. Open questions

1. **H16 reconciliation shape** — should AWC canonicalize `coordination.py`'s `AgentProfile`/`CapabilityRegistry`
   into `ugence_agent_workforce_composer` (and have H16 re-export, mirroring the `execution_gate`→`ugence_model_selection`
   compatibility-facade pattern), or bind to them via a neutral contract? (Recommendation: canonicalize; needs owner
   sign-off.)
2. **Registry ownership** — who owns the live `AgentRegistrySnapshot` upstream (a future Agent Registry service vs an
   AI-Control-Plane capability registry)? AWC consumes it either way, but provenance/trust of the snapshot must be
   owned somewhere.
3. **Authority-concentration metric** — the `[UNVALIDATED]` concentration measure (§18) needs a defensible, calibrated
   definition before any non-advisory use.
4. **Model-policy handoff** — exact neutral shape of the per-assignment `model_policy_ref` that Model Selection later
   resolves (avoid coupling).
5. **Policy Workflow Compiler IR** — the upstream compiler is **implemented** and emits a canonical `WorkflowIR`;
   the `CompilerWorkflowAdapter` consumes it directly (no second IR). The residual risk is
   `UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT` — pinning `workflow_ir.v1` and detecting node/edge/capability
   enum drift rather than inventing a rival representation.
6. **Quality provenance** — minimum evidence bar (sample size, TTL) for a `measured` capability to satisfy a hard
   `minimum_quality`. `[UNVALIDATED]`.

---

## 38. Recommended implementation phases

See `AGENT_WORKFORCE_COMPOSER_IMPLEMENTATION_ROADMAP.md`. Headline: **Phase 0** — H16 reconciliation + boundary ADR
(no code); **Phase 1** — object model + role extraction + eligibility gate over synthetic fixtures; **Phase 2** —
scoring + team composition + permission bounding + non-agent dispositions; **Phase 3** — explanation ledger +
replay + counterfactual + assurance corpus (the demo); later phases (`[DEFERRED]`) — real registry, runtime handoff,
reassignment.

---

## Conclusion (the six required answers)

1. **Architecturally justified?** `[INFERENCE]` **Conditionally yes** — as a deterministic, snapshot-pinned,
   explainable, **offline planning** leaf capability that *canonicalizes* today's scattered agent-selection logic,
   the same move the platform already made for models (`ugence-model-selection`) and decisions
   (`ugence-decision-authority`). It is **not** justified as new parallel architecture that forks the H16 layer.
2. **Overlap with Model Selection or H22?** **No material overlap.** Model Selection is a composable peer one level
   down (AWC picks agents; Model Selection picks each agent's model). H22 is complementary (it *consumes*
   `assigned_agent`/`authority_scope`, which AWC *produces*). The **material overlap is with the H16 coordination
   layer** (`agentic/agentic_framework/coordination.py`, `multi_agent.py`) — the gating risk — resolvable only by
   `ADAPT`/canonicalize, never fork.
3. **Correct package boundary?** A **capability**: `packages/capabilities/agent-workforce-composer/`, dist
   `ugence-agent-workforce-composer`, namespace `ugence_agent_workforce_composer`, leaf (stdlib + at most
   governance-contracts + decision-authority kernel primitives), acyclic, inputs injected as data.
4. **Smallest defensible MVP?** Deterministic + offline: three reference workflows, 10–15 synthetic agents, frozen
   snapshots, hard-constraint filtering, ranking, team composition, permission-bounded assignments, fallback,
   explanation ledger, replay, the constraint-change counterfactual, non-agent dispositions, assurance corpus — and
   **nothing** that executes an agent, routes a model, authorizes an action, or schedules a workflow.
5. **Major technical risks?** (a) H16 duplication if not reconciled first; (b) authority-boundary creep into
   decision/authorization/clearance/scheduling; (c) `[UNVALIDATED]` authority-concentration and quality heuristics;
   (d) `UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT` — consuming the implemented compiler's canonical `WorkflowIR` and detecting contract/semantic drift (this supersedes the earlier assumption that the compiler was unbuilt); (e) trust/provenance of the registry snapshot;
   (f) `[UNVALIDATED]` demand.
6. **Exact next implementation phase?** **Phase 0 (no production code):** a reconciliation ADR that decides the H16
   canonicalization shape and freezes the AWC↔H16, AWC↔Model-Selection, AWC↔Agent-Runtime, and AWC↔H22 boundaries —
   the prerequisite before any object-model code is written.
