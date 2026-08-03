# Changelog

All notable changes to `ugence-agent-workforce-composer` are documented here.
This project versions the distribution independently of the Ugence platform.

## 0.2.1 — P2.1: Policy Workflow Compiler workflow_ir.v2 compatibility adapter

Additive. Consumes the compiler's enriched `workflow_ir.v2` contract directly while
keeping the v1 path byte-frozen. The `awc.v1` / `awc.composition.v1` planning
contracts are UNCHANGED; a new `awc.compiler_adapter.v2` metadata version covers
adaptation envelopes only.

### Added
- `adapter_v2` (v2 semantic compatibility adapter) + `compatibility` (explicit
  contract-version dispatch, `compare_adaptations`, `compare_workforce_plans`).
- Overlay reduction (`reduce_overlay`) with a monotonic authority/security merge and
  typed conflict diagnostics; the compiler now supplies role name/description, the
  functional base capability, human-review classification, dependency semantics and
  provenance — enterprise policy fields remain external.
- Committed v1/v2 equivalence conformance fixtures for the four Governance Studio P3A
  scenarios (all SEMANTICALLY_EQUIVALENT); CLI `adapt-workflow --contract`,
  `compare-adaptations`, `inspect-overlay-reduction`; extended isolated verifier;
  scoped CI. Public API 93 -> 109.

### Compatibility
Eligibility, ranking, composition, permission and fallback algorithms unchanged; v1
adaptation and plan fingerprints byte-identical; AWC P1/P2 (158) and Governance
Studio P3A (94) green; platform-freeze digest unchanged. Not implemented: Governance
Studio API, runtime handoff/execution, H16/H22/Model Selection, pilot/production.

## [0.2.0] — Agent Workforce Composer P2

Additive composition contract `awc.composition.v1`. P1 (`awc.v1`) contracts,
object fingerprints, public names and CLI behaviour are preserved.

### Added
- **Deterministic ranking** of P1-eligible candidates: `AgentRankingPolicy`,
  `RankingCriterion`, `RankingCriterionResult`, `AgentRankResult`,
  `RoleCandidateRanking`, `rank_eligible_candidates`, `rank_workflow_candidates`.
  Integer basis-point scores (Decimal ROUND_FLOOR normalization), exactly
  reconstructable from criterion contributions; frozen total-order tie-break.
- **Role dependency/interface graph**: `RoleDependency`, `RoleDependencyGraph`,
  `build_role_dependency_graph` (derived from typed I/O contracts; cycle-checked).
- **Bounded exact team composition**: `TeamCompositionPolicy`, `RoleAssignment`,
  `TeamConstraintResult`, `TeamObjectiveResult`, `SearchStatistics`,
  `TeamCompositionResult`, `compose_agent_team` — deterministic branch-and-bound,
  proven exact against a brute-force oracle; typed `NO_FEASIBLE_TEAM` /
  `SEARCH_SPACE_EXCEEDED`.
- **Least-privilege permission-bound proposals**: `PermissionBoundingPolicy`,
  `ProposedPermission`, `PermissionBoundProposal`, `propose_permission_bound`.
  Proposal-only; grants nothing.
- **Fallback planning**: `AgentFallbackPolicy`, `FallbackCandidate`,
  `RoleFallbackPlan`, `TeamFallbackPlan`, `build_fallback_plan`.
- **Failure domains**: `FailureDomain`, `FailureDomainSet`.
- **AgentTeamPlan** + selection explanation, replay, and diff: `AgentTeamPlan`,
  `AgentTeamPlanState`, `CompositionReplayRecord`, `AgentTeamPlanDiff`,
  `build_agent_team_plan`, `replay_agent_team_plan`, `compare_agent_team_plans`.
- P2 CLI: `rank`, `compose`, `explain-plan`, `replay-plan`, `compare-plans`,
  `demo <name> --compose`.

### Changed (documented compatibility migrations)
- Distribution/product version `0.1.0 → 0.2.0`.
- Maturity: `agent_ranking_implemented` / `team_composition_implemented` now `true`;
  added `deterministic_ranking_implemented`, `permission_bound_proposal_implemented`,
  `fallback_planning_implemented`, `agent_team_plan_implemented` (`true`) and
  `permission_granting_implemented`, `runtime_execution_implemented`,
  `live_availability_implemented`, `model_selection_integration_implemented`,
  `h22_integration_implemented` (`false`). The P1 maturity/version/no-ranking
  assertions were updated to reflect this (see docs/audits IMPLEMENTATION_DECISIONS).

### Not implemented (by design)
permission granting, runtime execution/handoff, live availability, H16 migration,
Agent Runtime / H22 adapters, Model Selection invocation, scheduling, large-scale
approximate solving. `pilot_validated=false`, `production_certified=false`.

## [0.1.0] — Agent Workforce Composer P1

First canonical distribution. Contract version `awc.v1`.

### Added
- **Canonical planning object model** (frozen, `extra='forbid'`, content-addressed):
  `WorkflowRoleRequirement`, `NonAgentDisposition`, `WorkflowNodeDisposition`,
  `AgentProfile`, `AgentCapability`, `AgentCapabilityEvidence`,
  `CapabilityEvidenceSet`, `AgentRegistrySnapshot`, `EnterpriseAgentPolicy`,
  `EligibilityPolicy`, `AgentEligibilityResult`, `RoleEligibilityReport`,
  `EligibilityExplanation`, `EligibilityReplayRecord`.
- **`CompilerWorkflowAdapter`** — read-only, data-only adapter over a serialized
  Policy Workflow Compiler `WorkflowIR` (`workflow_ir.v1`). Total node accounting;
  fail-closed on unknown version / missing digest / malformed graph; authority
  preservation for governance and human nodes.
- **Hard-constraint eligibility engine** — deterministic, fail-closed, complete
  elimination accounting; evidence discipline (DECLARED / MEASURED / OBSERVED with
  `OBSERVED > MEASURED > DECLARED` precedence); append-only `EliminationReason`
  taxonomy.
- **Deterministic explanation & replay**; content fingerprints on every object.
- **Frozen synthetic fixtures** — procurement / support / security workflows and a
  ~17-agent registry exercising every important elimination reason.
- **Offline CLI**, **frozen public-API artifact + drift verifier**, **isolated
  distribution verifier**, **tests**, **docs**, and **path-scoped CI**.

### Not implemented (by design; see `docs/NEXT_PHASES.md`)
Ranking, scoring, winner selection, team composition, permission assignment,
fallback selection, runtime handoff, H16 migration, Agent Runtime / H22 adapters,
Model Selection invocation, live registration, agent execution.
`pilot_validated=false`, `production_certified=false`.
