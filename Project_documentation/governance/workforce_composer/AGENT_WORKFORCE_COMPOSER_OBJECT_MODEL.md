# Agent Workforce Composer — Canonical Object Model

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
Claim labels per design spec §1. All objects are **frozen/immutable**; state changes mint a new `version`
(`ADAPT` from AI Hiring's universal `DomainModel` idiom `[EXISTING]`). All objects carry `tenant_id` and a
content digest via `canonical_hash` (`REUSE`).

---

## 1. Naming discipline

`[SPEC]` Names are **domain-neutral**: no employment/recruiting terminology. The proposed names from the concept
brief are adopted where already neutral and improved where not. Two names collide with existing H16 symbols in
`agentic/agentic_framework/coordination.py` (`[EXISTING]` `AgentProfile`, `AgentAssignment`) and one with AI
Hiring/Model Selection (`Candidate`). These are **resolved** by the Phase 0 ADR
(`docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`, Option A): the selection `AgentProfile`
is canonicalized into the AWC namespace (H16 may re-export where byte-identical, the
`execution_gate`→`ugence_model_selection` facade pattern); the planning `AgentAssignment` lives in the AWC
namespace and is kept **distinct** from H16's mutable runtime `AgentAssignment` (they are not merged).

---

## 2. Object catalog

### 2.1 Requirement side

**`WorkflowRoleRequirement`** — the measurable requirement for one agent-eligible workflow step.
```
role_id, workflow_id, workflow_node_id, tenant_id,
required_capabilities: tuple[CapabilityRef],   optional_capabilities: tuple[CapabilityRef],
required_tools: tuple[ToolRef],
input_contract: SchemaRef,   output_contract: SchemaRef,
domain_requirements: tuple[str],
minimum_quality: QualityThreshold,             # hard when the facet makes it impermissible
maximum_latency: Optional[float_ms],           # hard/soft per facet (§ design spec 11)
maximum_cost: Optional[float],                 # hard/soft per facet
data_classification: DataClassification,       # read from compiled node; default most-restrictive
residency_constraints: frozenset[str],
required_permissions: frozenset[PermissionRef],
prohibited_permissions: frozenset[PermissionRef],
authority_ceiling: AuthorityLevel,             # never exceeded by any grant
stateful_or_stateless: StateModel,
human_review_requirement: HumanReviewRule,
fallback_behavior: FallbackBehavior,           # ESCALATE_TO_HUMAN | HALT_ROLE | PROCEED_WITHOUT_FALLBACK
source_node_ref, policy_refs: tuple[str], requirement_digest, version
```

**`NonAgentDisposition`** — for a step that must NOT be staffed by an AI agent.
```
workflow_node_id, disposition: {NO_AI_AGENT_REQUIRED, DETERMINISTIC_SERVICE_PREFERRED,
                                HUMAN_AUTHORITY_REQUIRED, HUMAN_REVIEW_REQUIRED, NO_ELIGIBLE_AGENT},
reason_codes: tuple[EliminationReason], source_node_ref, policy_refs, version
```

### 2.2 Agent side

**`AgentCapability`** — one capability an agent offers.
```
capability_id, capability_version, declared: bool, category, description
```

**`CapabilityEvidence`** — provenance-tagged evidence for a capability (§ design spec 9–10).
```
evidence_id, capability_id,
source: {VENDOR_DECLARED, BENCHMARK, PRODUCTION_TELEMETRY, PILOT, IMPORTED_APPROVED_RECORD},
metric, value, sample_size, evaluated_at, ttl_seconds, confidence,
evidence_ref,   # opaque locator (REUSE governance-contracts) — never raw content
provenance, raw_signal(audit-only)   # is_stale(now) -> stale degrades to UNKNOWN
```

**`AgentProfile`** (canonicalized into AWC per the Phase 0 ADR; H16 re-exports where byte-identical) — evidence-backed agent manifest.
```
agent_id, agent_version, provider, agent_type, tenant_id,
capability_manifest: tuple[AgentCapability],
tool_contracts: tuple[ToolContract],
input_schemas, output_schemas,
domain_specializations, model_dependencies,
permission_requirements: frozenset[PermissionRef],
authority_requirements: AuthorityLevel,
data_access_requirements, deployment_location, security_classification,
latency_profile, cost_profile, reliability_profile,
benchmark_evidence: tuple[CapabilityEvidence],
observed_failure_modes, audit_support, state_model, concurrency_limit,
version_status: {declared, enumerated, benchmarked, production_observed, disabled},  # never 'benchmarked' from declaration
profile_digest, version
```

**`ToolContract`** — per-tool contract (`ADAPT` from `ToolSpec`/`RegisteredTool` `[EXISTING]`).
```
tool_id, read_only, consequence/risk_class: {LOCAL_READ_ONLY, GOVERNED_CONSEQUENTIAL},  # set by trusted operator, never a model
reversibility, scope_permissions, required_evidence, approver_policy, simulation_required
```

**`AgentRegistrySnapshot`** — frozen, content-addressed selection universe.
```
snapshot_id, tenant_id, profiles: tuple[AgentProfile], captured_at, snapshot_digest, version
```

### 2.3 Policy side

**`EnterpriseAgentPolicy`** — customer-owned **hard** constraints (governance veto plane).
```
policy_id, tenant_id, version,
approved_providers, forbidden_providers, residency_rules, data_classification_rules,
hard_cost_ceilings, hard_latency_ceilings, minimum_provenance_per_capability,
authority_concentration_ceiling, max_provider_share, separation_of_duties_rules,
declared_only_allowed_capabilities   # explicit, audited relaxations
```

**`CompositionPolicy`** — the versioned **policy-as-data** artifact the engine interprets (weights + rules).
```
policy_id, policy_version,
scoring_weights: {quality, domain_fit, reliability, cost, latency, security, integration,
                  observability, historical_outcome, conditional_penalty},
team_objective, composition_bias: [C, B, A],   # hybrid > specialist > generalist default (overridable, UNVALIDATED)
allow_conditional: bool, tie_break_key
```

**`CompositionRequest`** — the frozen input tuple (enables replay).
```
role_requirements, agent_registry_snapshot, enterprise_constraints, composition_policy, now, request_fingerprint
```

### 2.4 Assessment / selection side

**`AgentEligibilityResult`** — per-(agent,role) verdict (never a score).
```
agent_id, role_id,
state: {ELIGIBLE, INELIGIBLE, CONDITIONALLY_ELIGIBLE, INDETERMINATE},
conditions: tuple[ConditionResult],   reasons: tuple[EliminationReason],
policy_version, evaluated_at, ttl_seconds   # .selectable -> ELIGIBLE|CONDITIONALLY_ELIGIBLE
```

**`ConditionResult`** — one hard-constraint check.
```
condition, verdict: {PASS, FAIL, UNKNOWN}, reason: EliminationReason,
criticality: {CRITICAL_GOV, CRITICAL_OP, OPERATIONAL}, evidence_ref, detail
```

**`AgentAssessment`** — evidence-backed assessment (advisory; un-forgeable, `ADAPT` AI Hiring `advisory_only:Literal[True]`).
```
assessment_id, agent_id, role_id, tenant_id,
capability_findings: tuple[CapabilityFinding],   # per required capability: admitted/excluded/missing evidence
completeness: CompletenessResult, advisory_only = True, version
```

**`AgentScore`** — ranked score over the eligible pool only.
```
agent_id, role_id, total, contributions: dict[dimension->value], confidence, conditional: bool
```

**`EliminationReason`** — append-only reason-code taxonomy (`ADAPT` Model Selection `ReasonCode`). Examples:
`MISSING_REQUIRED_CAPABILITY, INSUFFICIENT_CAPABILITY_PROVENANCE, INTERFACE_INCOMPATIBLE, PROVIDER_NOT_APPROVED,
DATA_RESIDENCY_VIOLATION, DATA_CLASSIFICATION_VIOLATION, INSUFFICIENT_PERMISSION_ISOLATION,
AUTHORITY_EXCEEDS_CEILING, UNAPPROVED_TOOL, PROHIBITED_PERMISSION_REQUIRED, COST_LIMIT_EXCEEDED,
LATENCY_LIMIT_EXCEEDED, QUALITY_BELOW_MINIMUM, UNTRUSTED_OR_EXPIRED_VERSION, EVIDENCE_STALE,
SEPARATION_OF_DUTIES_VIOLATION, AUTHORITY_CONCENTRATION_EXCEEDED, PROVIDER_CONCENTRATION_EXCEEDED,
NO_ELIGIBLE_AGENT, POLICY_STATE_UNKNOWN`. Codes are versioned and never repurposed.

**`RoleSelectionDecision`** — the per-role outcome (total accounting).
```
role_id, selected_agent: Optional[agent_id], disposition: Optional[NonAgentDisposition],
ranked: tuple[AgentScore], eliminated: tuple[(agent_id, tuple[EliminationReason])],
abstained: bool
```

### 2.5 Assignment / plan side

**`AgentPermissionGrant`** — least-privilege bounded permission subset.
```
granted_permissions: frozenset[PermissionRef],  # ⊆ role.required_permissions, ∩ agent capabilities, − prohibited
each permission cites: source_role_requirement_ref   # construction fails if it includes a prohibited permission
```

**`AuthorityBoundary`** — the authority ceiling for the assignment.
```
authority_ceiling: AuthorityLevel,   max_reachable_resources,   consequential_tool_ids
# construction fails (BoundaryViolation) if agent.authority_requirements > ceiling
```

**`AgentAssignment`** (AWC-namespace planning object; **distinct** from H16's mutable runtime `AgentAssignment` per the Phase 0 ADR) — role→agent binding.
```
assignment_id, role_id, workflow_node_id, agent_id, agent_version, tenant_id,
permission_grant: AgentPermissionGrant, authority_boundary: AuthorityBoundary,
model_policy_ref: Optional[str],   # neutral ref; Model Selection resolves later (COMPOSE, not import)
assignment_expiry, registry_snapshot_digest, policy_version, version
```

**`FallbackAssignment`** — ordered fallback chain, each re-checked against primary constraints (non-broadening).
```
role_id, ordered_fallback_agent_ids: tuple[agent_id],
each re-passes the primary's hard constraints and authority_ceiling; recorded residual risks
```

**`TeamCandidate`** — a whole-team option evaluated for joint feasibility.
```
candidate_id, per_role_agent: dict[role_id -> agent_id], archetype: {A_generalist, B_specialist, C_hybrid},
interface_checks, sod_checks, authority_concentration, provider_concentration,
cumulative_cost, cumulative_latency, feasible: bool, eliminations: tuple, team_score
```

**`AgentTeamPlan`** — the immutable output. Un-forgeably `plan_only` (`ADAPT` AI Hiring `Literal[True]` pattern).
```
plan_id, workflow_id, tenant_id,
assignments: tuple[AgentAssignment],
non_agent_dispositions: tuple[NonAgentDisposition],
fallbacks: tuple[FallbackAssignment],
selected_team_candidate_id, alternatives_considered: tuple[TeamCandidate],
snapshot_digest, policy_version, request_fingerprint,
rendered_explanation, plan_only = True,
approval: Optional[PlanApproval],   # human/delegated-policy; no AI actor; required before consequential handoff
version
```

**`PlanApproval`** — human sign-off (`REUSE` decision-authority `AuthorityType`; no AI member).
```
approver_id, authority_type: {HUMAN_REVIEWER, HUMAN_APPROVER, DELEGATED_POLICY, COMMITTEE, EXTERNAL_AUTHORITY},
approved: bool, note, approved_at
```

### 2.6 Explanation / replay side

**`SelectionExplanation`** — total, deterministically rendered ledger (§ design spec 24).
```
plan_id, per_role: dict[role_id -> RoleSelectionDecision], team_rationale,
alternatives_comparison, residual_risks, rendered_prose   # prose derived from structured record, never divergent
```

**`SelectionReplayRecord`** — frozen inputs + digests enabling exact replay (§ design spec 25).
```
request_fingerprint, snapshot_digest, policy_version, enterprise_policy_digest, now, input_bundle_ref
```

### 2.7 Deferred (designed, not in MVP) `[DEFERRED]`

**`ReassignmentDecision`**, **`AgentOutcomeObservation`**, **`AgentPerformanceSnapshot`** — runtime-adaptation
objects (§ design spec 21). A `ReassignmentDecision` re-runs the primary's hard-constraint check against the frozen
requirement, requires human approval when consequential, and can never broaden permissions.

---

## 3. AI Hiring → AWC mapping (patterns reused; entities NOT reused)

`[SPEC]` AI Hiring is a **`REFERENCE_ONLY`** pattern donor. The table shows the conceptual mapping so the reader can
see the shared shape; **no `ai_hiring` entity is imported**, and all employment terminology is dropped. The reusable
domain-neutral primitives (right-most column) already live in `ugence-decision-authority`/`ugence-governance-contracts`
(`[EXISTING]`), not in `ai_hiring`.

| AI Hiring concept (`[EXISTING]`) | AWC domain-neutral object (`[SPEC]`) | Neutral primitive to `REUSE` |
|---|---|---|
| `JobRequisition` / `JobDefinition` (`required_capability_ids`, `required_evidence_types`) | `WorkflowRoleRequirement` | — |
| `Candidate` / `CandidateProfile` | `AgentProfile` | opaque `subject_ref` seam → `agent_id` |
| resume/`NormalizedEvidence` (`content_hash`, `evidence_ref`) | `CapabilityEvidence` | `evidence_ref`, `canonical_hash` |
| `Rubric` / `RubricCapability` (`weight`, `scoring_scale_id`, `evidence_rule`) | `CompositionPolicy.scoring_weights` + `AgentCapability` | reason-code catalog |
| `Assessment` / `CapabilityAssessment` (`advisory_only:Literal[True]`) | `AgentAssessment` (`advisory_only=True`) | `DomainModel` immutability |
| `EligibilityResult` / `ReadinessResult` (pure structural gates, machine-token reasons) | `AgentEligibilityResult` | reason codes |
| `LayerScore` evidence-backing invariant (`score>0 ⇒ ≥1 evidence_ref`) | `AgentScore` + provenance rule (§ design spec 9) | — |
| `HiringRecommendation` (`advisory=True`, "NOT a binding decision") | `RoleSelectionDecision` (advisory) | — |
| `Decision` (`actor_type` pinned `HUMAN`, `BoundaryViolationError`) | **NOT reused** — binding decisions route to Decision Authority | `AuthorityType` (no AI) |
| `GovernanceCaseBinding` / `ActionAuthorizationRecord` (immutable per-stage facts) | `AgentAssignment` (immutable, cites requirement) | `correlation_id`/`causation_id` |
| `HiringDomainAuditEvent` (hash chain: `previous_event_hash → event_hash`) | AWC audit event | `AuditEvent` kernel type |
| `GovernanceCaseReconstructionService` (rebuild + verify chain) | `reconstruct(plan_id)` | — |
| `package_fingerprint` / `test_h5_determinism` | `request_fingerprint` + replay tests | `canonical_hash` |
| `Offer` / `Assignment` (employment) — **do not exist as models** | — (no employment analogue) | — |

**Employment terminology explicitly avoided** (`[EXISTING]` list from the AI-Hiring audit): `Candidate*`,
`JobRequisition`, `Application`, `Hiring*`, `employment_type`, `department`, `headcount`, `panel`, `human_actor_id`
(as an employment field), `EvidenceType` values (RESUME/PORTFOLIO/GITHUB/CODING_TEST/INTERVIEW/…), and
`CapabilityLayer` values (QUALIFICATION_AND_IDENTITY/ROLE_PURPOSE/PROFESSIONAL_COHERENCE/…). AWC's evidence
vocabulary is agent-native (benchmark run, tool-call trace, eval transcript, prior-task record).

---

## 4. Reused governance-contracts primitives (`REUSE`, `[EXISTING]`)

From `ugence_governance_contracts`: `evidence_refs`, `decision_refs`, `policy_refs`, `authority_context` /
`authority_basis`, `fingerprint`, `correlation_id`; `ProviderKind` / `ProviderCapabilities` (`features`,
`deterministic`) / `ProviderDescriptor` for the provider-discovery side of an `AgentProfile`; `FailureClass` and the
lifecycle-state vocabulary for version/health status. From `ugence_decision_authority`: `DomainModel`, `ActorType`
(**no AI member** — the reason AWC cannot mint a decision actor), `AuthorityType`, `AuditEvent`, `ReasonCode`
catalog machinery, `canonical_hash`, `Clock`/`IdFactory`. AWC introduces **new** primitives only where none exist:
`WorkflowRoleRequirement`, `AgentProfile`/`AgentCapability`/`CapabilityEvidence`, `AgentRegistrySnapshot`,
`CompositionPolicy`, `TeamCandidate`, `AgentTeamPlan` — because the audit confirmed no capability-manifest,
capability-requirement, or workflow-IR primitive exists in the repo today.
