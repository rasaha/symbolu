# AWC Public API Inventory (as consumed by Governance Studio)

The Governance Studio demo layer consumes AWC **only** through its single curated
public surface, `import ugence_agent_workforce_composer.api as awc` (93 names,
frozen in `packages/capabilities/agent-workforce-composer/artifacts/public_api.json`).
The top-level `ugence_agent_workforce_composer` package exports only version
constants; all schema classes and pipeline functions come from `.api`.

Everything below is **called, never re-implemented**. P3A produces inputs in these
schemas and freezes the outputs these functions return.

## Pipeline entry points

| Function | Signature (abbreviated) | Purpose |
|---|---|---|
| `adapt_compiled_workflow` | `(document, *, source_package_digest=None, role_overlay=None) -> CompilerAdaptationResult` | Data-only adaptation of a serialized `workflow_ir.v1` document → role requirements + non-agent dispositions (total node accounting). |
| `classify_node` | `(kind, owner, disposition, authority_type) -> (NodeDisposition, reasons)` | Pure per-node disposition (used internally by the adapter; consulted for documentation only). |
| `evaluate_workflow_eligibility` | `(adaptation, snapshot, enterprise_policy, eligibility_policy, logical_time) -> WorkflowEligibilityResult` | Hard-constraint eligibility for every role × agent, with explanations + replay records. |
| `evaluate_registry_for_role` | `(role, snapshot, enterprise_policy, eligibility_policy, logical_time) -> RoleEligibilityReport` | Per-role eligibility report. |
| `evaluate_agent_eligibility` | `(role, profile, snapshot, enterprise_policy, eligibility_policy, logical_time) -> AgentEligibilityResult` | Single pair. |
| `rank_eligible_candidates` | `(role, report, snapshot, ranking_policy, logical_time) -> RoleCandidateRanking` | Deterministic ranking of the eligible set. |
| `rank_workflow_candidates` | `(adaptation, snapshot, enterprise_policy, eligibility_policy, ranking_policy, logical_time) -> tuple[RoleCandidateRanking, …]` | Ranking across all roles. |
| `build_role_dependency_graph` | `(roles, overlay=None) -> RoleDependencyGraph` | Interface dependency edges between roles. |
| `build_failure_domain_set` | `(profile) -> FailureDomainSet` | Failure-domain projection of an agent. |
| `compose_agent_team` | `(roles, rankings, snapshot, enterprise_policy, composition_policy, permission_policy, dep_graph, *, …digests) -> TeamCompositionResult` | Bounded exact team composition. |
| `propose_permission_bound` | `(role, profile, enterprise_policy, permission_policy) -> PermissionBoundProposal` | Least-privilege permission-bound proposal (never a grant). |
| `build_fallback_plan` | `(role, ranking, primary_id, primary_version, snapshot, enterprise_policy, permission_policy, fallback_policy) -> RoleFallbackPlan` | Per-role fallback plan. |
| `build_agent_team_plan` | `(adaptation, snapshot, enterprise_policy, eligibility_policy, ranking_policy, composition_policy, permission_policy, fallback_policy, logical_time) -> AgentTeamPlan` | Full P1→P2 pipeline in one call. |
| `build_replay_record` | `(plan, adaptation, logical_time, contract_versions) -> CompositionReplayRecord` | Pinned replay record (shadows the eligibility-module `build_replay_record` in `api`). |
| `replay_agent_team_plan` | `(…same as build_agent_team_plan…, expected=None) -> AgentTeamPlan` | Rebuild; raises if `expected` fingerprint differs. |
| `compare_agent_team_plans` | `(a, b) -> AgentTeamPlanDiff` | Structured plan diff. |
| `fingerprint` | `(payload) -> "sha256:<hex>"` | Canonical fingerprint over a mapping. |

## Input schema classes (pydantic v2, `frozen=True, extra='forbid'`)

- **Workflow / adaptation**: `Provenance`, `AuthorityContext`, `WorkflowRoleRequirement`, `NonAgentDisposition`, `WorkflowNodeDisposition`, `CompilerAdaptationResult`.
- **Agents / evidence / registry**: `AgentStatus`, `AgentCapability`, `AgentCapabilityEvidence`, `CapabilityEvidenceSet`, `AgentProfile`, `AgentRegistrySnapshot`, `build_registry_snapshot(...)`.
- **Policies**: `EnterpriseAgentPolicy`, `EligibilityPolicy` (+ `finalize_*`), `AgentRankingPolicy`/`RankingCriterion`, `TeamCompositionPolicy`, `PermissionBoundingPolicy`, `AgentFallbackPolicy`.

The **enterprise role overlay** is *not* a class — it is a plain
`Mapping[node_id -> Mapping[field -> value]]` passed to
`adapt_compiled_workflow(role_overlay=...)`. Allowed overlay fields are frozen in
`adapter._OVERLAY_FIELDS`.

## Result / output schema classes

`AgentEligibilityResult`, `ConditionResult`, `RoleEligibilityReport`,
`EligibilityExplanation`, `EligibilityReplayRecord`, `WorkflowEligibilityResult`,
`RankingCriterionResult`, `AgentRankResult`, `RoleCandidateRanking`,
`RoleAssignment`, `TeamConstraintResult`, `TeamObjectiveResult`,
`SearchStatistics`, `TeamCompositionResult`, `ProposedPermission`,
`PermissionBoundProposal`, `FallbackCandidate`, `RoleFallbackPlan`,
`TeamFallbackPlan`, `AgentTeamPlan`, `TeamSelectionExplanation`,
`CompositionReplayRecord`, `AgentTeamPlanDiff`.

## Typed states (the studio must surface these honestly)

| Enum | Members |
|---|---|
| `EligibilityState` | `ELIGIBLE`, `INELIGIBLE`, `INDETERMINATE`, `INVALID_INPUT` |
| `CompositionState` / `AgentTeamPlanState` | `COMPLETE`, `PARTIAL`, `NO_FEASIBLE_TEAM`, `SEARCH_SPACE_EXCEEDED`, `INVALID_INPUT` |
| `OptimalityStatus` | `EXACT_OPTIMUM`, `NO_FEASIBLE_TEAM`, `SEARCH_SPACE_EXCEEDED`, `INVALID_INPUT`, `RESOURCE_BLOCKED` |
| `FallbackState` | `COMPLETE`, `PARTIAL`, `NO_FALLBACK_AVAILABLE`, `NOT_REQUIRED`, `INVALID` |
| `PermissionCategory` | proposed / prohibited / unsupported / excessive-requested / requires-human-review / governance-owned |
| `NodeDisposition` | AI-agent-eligible, deterministic-service, human-authority, human-review, governance-owned, no-agent, unsupported, invalid |
| `RoleEligibilityReport.outcome` | string constant `HAS_ELIGIBLE_AGENT` / `NO_ELIGIBLE_AGENT` |
| `EliminationReason` | 29-member taxonomy (`MISSING_REQUIRED_CAPABILITY`, `RESIDENCY_MISMATCH`, `PROVIDER_FORBIDDEN`, `SECURITY_CLASSIFICATION_INSUFFICIENT`, `AGENT_VERSION_REVOKED`, …) |

## Determinism contract relied upon

- A fixed injected `logical_time` (P3A uses `1_000_000.0`) makes freshness/expiry
  deterministic.
- All models canonicalize (`canonical_dict()` / content digests); serialization
  order is irrelevant. Verified: reversing registry profile/evidence order and
  overlay key order leaves the plan fingerprint unchanged.
- `model_dump(mode="json")` → `model_validate` round-trips reproduce byte-identical
  fingerprints — this is what lets the committed JSON fixtures drive the frozen
  expected outputs.
