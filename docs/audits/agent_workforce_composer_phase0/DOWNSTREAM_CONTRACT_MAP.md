# Downstream & Adjacent Contract Map

Verified public contracts of the systems AWC touches. AWC is a **leaf planning
capability**: it consumes the compiler `WorkflowIR` and produces an
`AgentTeamPlan`; every adjacent system is reached through **data-only seams**,
never by importing it.

## Model Selection — `ugence-model-selection` / `ugence_model_selection`

- Location: `packages/capabilities/model-selection/`; public surface `ugence_model_selection.api`.
- Owns two audited stages **over an already-approved model/provider candidate set**:
  - **Eligibility** (`ExecutionGate`) — deterministic, fail-closed "can this candidate execute?"; never ranks.
  - **Selection** (`ModelPolicy` / `select`) — policy-weighted deterministic scoring over the eligible set; abstains (`NO_ELIGIBLE_MODEL`) when none qualify.
- Public entry points: `ExecutionGate`, `ExecutableRegistry`, `ModelRecord`, `Request`, `Candidate`, `Signal`, `GateConfig`, `EligibilityDecision`, `ReasonCode`, `select`, `PolicyWeights`, `Selection`, `fingerprint`, `POLICY_VERSION`.
- Placement ADR (`ADR_MODEL_SELECTION_POLICY_PLACEMENT.md`): **Option 4** — cross-cutting platform policy service (Governance Services Layer), **not** an 11th canonical module; "pre-reasoning analogue of ActionGate".
- **Inputs are model candidates, not agents.** It does **not** own agent selection.

**AWC↔Model Selection:** AWC selects functional **agents** for roles; Model
Selection selects **models/providers** that may power a selected agent
invocation. AWC may emit `model_policy_ref` / `model_requirement_ref` /
`model_constraint_ref`; it must never rank LLMs, call provider registries, choose
endpoints, or duplicate Model Selection policy.

## Agent Runtime — `ugence-agent-runtime` / `ugence_agent_runtime`

- Location: `packages/runtime/agent-runtime/` (root `agent_runtime_migration/` is legacy, superseded).
- Key public contract types (`docs/AGENT_RUNTIME_PUBLIC_API.md`):
  - `WorkflowDefinition` (immutable task graph), `WorkflowInstance`, `WorkflowStatus`
  - `TaskDefinition` (`task_id`, `operation`, `provider_id`, `consequential`, `arguments`, `depends_on`, `timeout`, `max_attempts`, `metadata`), `TaskInstance`, `TaskStatus`
  - `AgentRuntime`, `AgentRuntimeConfig`, `AgentDescriptor`, `RuntimeResult`, `RuntimeFailure`/`FailureCategory`
  - `Provider`/`ProviderRegistry`, `Checkpoint`, `RuntimeRecoveryResult`
  - Governance: `GovernanceHook`, `GovernanceDisposition` (`CLEAR/HOLD/BLOCK/ESCALATE`), `UnconfiguredGovernanceHook` (fail-closed), `validate_clearance`
  - Functions: `create_runtime`, `start_workflow`, `resume_workflow`, `recover_runtime`, `register_provider`, `register_governance_hook`
- Owns: execution state, task/workflow lifecycle, provider/tool invocation, retry/timeout/cancellation, pause/resume, checkpoints, runtime recovery, deterministic transitions, failure classification.
- **No `assigned_agent`/`authority_scope` type** — assignment is expressed via `TaskDefinition.provider_id` + neutral `AgentDescriptor`.

**AWC↔Agent Runtime:** future neutral handoff `AgentTeamPlan → Agent Runtime
adapter → WorkflowDefinition/TaskDefinition/runtime assignment`. AWC fields are
planning metadata; the runtime may **narrow** (never broaden) permission/authority
bounds; unsupported agent versions fail closed; assignment digests + policy
versions are preserved; execution outcomes refer back to the originating plan.
Adapter is **not** implemented in Phase 0.

## H22 Multi-Workflow Orchestration — `agentic.agentic_framework` (v1.22.0)

- Code: `agentic/agentic_framework/multi_workflow_orchestration.py`; doc `agentic/docs/H22_MULTI_WORKFLOW_ORCHESTRATION.md`; runtime-side readiness `packages/runtime/agent-runtime/docs/AGENT_RUNTIME_H22_READINESS.md`.
- `PortfolioWorkflowEntry` carries all five listed fields as **fixed given inputs**:
  - `budget_estimate` (`:852`), `resource_claims` (`:854`), `authority_scope` (`:855`), `assigned_agent` (`:856`), `resource_class` (`:857`).
  - Workflow dependencies via `WorkflowDependency`/`DependencyGraph` (acyclic), kinds `REQUIRES_COMPLETION/SUCCESS/MILESTONE/REVIEW_DECISION/OUTPUT`.
- Per-agent / per-authority-scope / per-resource-class caps enforced at `:1295-1303`.

**AWC↔H22:** AWC **produces** staffing/assignment artifacts (`assigned_agent` +
`authority_scope` per role); H22 **schedules** already-staffed workflows. H22 must
not select agents, change assignments, broaden authority, invent fallbacks, or
override residency/provider constraints. On unavailability H22 may pause/surface —
never perform ungoverned reselection.

## Governance authorities (binding, outside AWC)

From the compiler capability registry (all `AUTHORITATIVE`):

- **Decision Authority** — governs when a recommendation becomes a binding decision.
- **ActionGate** — exact-action authorization (range/digest/once-only).
- **Action Clearance** — commit-time operational clearance of an authorized action.
- **StoryGraph** — sequence-risk advisory analysis (advisory).

AWC proposes permission **bounds**; it never makes the binding business decision,
authorizes exact actions, or clears operations.
