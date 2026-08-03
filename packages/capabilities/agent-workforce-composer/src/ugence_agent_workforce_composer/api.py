"""Ugence Agent Workforce Composer — curated public API (contract ``awc.v1``).

The single supported import surface::

    import ugence_agent_workforce_composer.api as api

It re-exports the canonical planning object model, the data-only compiler
adapter, the frozen registry/evidence model, the hard-constraint eligibility
engine, deterministic explanation and replay, and the offline fixtures. Internal
helpers are not exposed. The name set is frozen against ``artifacts/public_api.json``.

Scope discipline (P1): there is **no** ranking, scoring, winner selection, team
composition, permission assignment, runtime handoff, H16 migration, Model
Selection invocation, or agent execution anywhere in this surface.
"""
from __future__ import annotations

# -- contract vocabulary -------------------------------------------------------
from .contracts import (
    AuthorityDisposition,
    CapabilityOwner,
    Criticality,
    EdgeKind,
    EligibilityState,
    EvidenceClass,
    NodeDisposition,
    NodeKind,
    Verdict,
)

# -- compiler adapter + canonical workflow objects -----------------------------
from .adapter import CompilerWorkflowAdapter, adapt_compiled_workflow, classify_node
from .workflow import (
    AuthorityContext,
    CompilerAdaptationResult,
    NonAgentDisposition,
    Provenance,
    WorkflowNodeDisposition,
    WorkflowRoleRequirement,
)

# -- agent / evidence / registry model -----------------------------------------
from .agents import (
    AgentCapability,
    AgentCapabilityEvidence,
    AgentProfile,
    AgentRegistrySnapshot,
    AgentStatus,
    CapabilityEvidenceSet,
    build_registry_snapshot,
)

# -- policy --------------------------------------------------------------------
from .policy import (
    EligibilityPolicy,
    EnterpriseAgentPolicy,
    finalize_eligibility_policy,
    finalize_enterprise_policy,
)

# -- elimination taxonomy ------------------------------------------------------
from .reasons import EliminationReason, normalize_reason

# -- eligibility engine + results ----------------------------------------------
from .eligibility import (
    AgentEligibilityResult,
    ConditionResult,
    EligibilityExplanation,
    EligibilityReplayRecord,
    RoleEligibilityReport,
    WorkflowEligibilityResult,
    build_replay_record,
    evaluate_agent_eligibility,
    evaluate_registry_for_role,
    evaluate_workflow_eligibility,
    explain_role_report,
)

# -- P2: ranking ---------------------------------------------------------------
from .ranking import (
    AgentRankingPolicy,
    AgentRankResult,
    RankingCriterion,
    RankingCriterionResult,
    RoleCandidateRanking,
    rank_eligible_candidates,
    rank_workflow_candidates,
)

# -- P2: role dependency graph -------------------------------------------------
from .dependency import (
    RoleDependency,
    RoleDependencyGraph,
    RoleInterfaceRequirement,
    build_role_dependency_graph,
)

# -- P2: failure domains -------------------------------------------------------
from .failure_domains import FailureDomain, FailureDomainSet, build_failure_domain_set

# -- P2: team composition ------------------------------------------------------
from .composition import (
    RoleAssignment,
    SearchStatistics,
    TeamCompositionPolicy,
    TeamCompositionResult,
    TeamConstraintResult,
    TeamObjectiveResult,
    compose_agent_team,
)

# -- P2: permission bounding ---------------------------------------------------
from .permissions import (
    PermissionBoundProposal,
    PermissionBoundingPolicy,
    ProposedPermission,
    propose_permission_bound,
)

# -- P2: fallback planning -----------------------------------------------------
from .fallback import (
    AgentFallbackPolicy,
    FallbackCandidate,
    RoleFallbackPlan,
    TeamFallbackPlan,
    build_fallback_plan,
)

# -- P2: plan + replay + diff --------------------------------------------------
from .composition_contracts import (
    AgentTeamPlanState,
    CompositionState,
    FallbackState,
    OptimalityStatus,
    PermissionCategory,
    SelectionState,
)
from .plan import (
    AgentTeamPlan,
    AgentTeamPlanDiff,
    CompositionReplayRecord,
    TeamSelectionExplanation,
    build_agent_team_plan,
    build_replay_record,
    compare_agent_team_plans,
    replay_agent_team_plan,
)

# -- P2.1: compiler workflow_ir.v2 compatibility adapter -----------------------
from .adapter_v2 import (
    COMPILER_ADAPTER_CONTRACT_VERSION,
    SUPPORTED_COMPILER_CONTRACTS,
    AdaptationResultV2,
    AdapterDiagnostic,
    AdapterDiagnosticCode,
    CompilerAdapterMode,
    CompilerContractVersion,
    adapt_compiled_workflow_v2,
    declared_contract_version,
    reduce_overlay,
)
from .compatibility import (
    AdaptationEquivalenceReport,
    AdaptationEquivalenceState,
    EquivalenceDifference,
    adapt_workflow,
    compare_adaptations,
    compare_workforce_plans,
)

# -- fingerprint + version -----------------------------------------------------
from .fingerprint import fingerprint
from .version import (
    COMPOSITION_CONTRACT_VERSION,
    CONTRACT_VERSION,
    VERSION,
    VersionInfo,
    __version__,
    version_info,
)

__all__ = [
    # contract vocabulary
    "NodeKind", "EdgeKind", "AuthorityDisposition", "CapabilityOwner",
    "NodeDisposition", "EvidenceClass", "EligibilityState", "Verdict", "Criticality",
    # adapter + workflow objects
    "CompilerWorkflowAdapter", "adapt_compiled_workflow", "classify_node",
    "Provenance", "AuthorityContext", "WorkflowRoleRequirement", "NonAgentDisposition",
    "WorkflowNodeDisposition", "CompilerAdaptationResult",
    # agent / evidence / registry
    "AgentStatus", "AgentCapability", "AgentCapabilityEvidence", "CapabilityEvidenceSet",
    "AgentProfile", "AgentRegistrySnapshot", "build_registry_snapshot",
    # policy
    "EnterpriseAgentPolicy", "EligibilityPolicy",
    "finalize_enterprise_policy", "finalize_eligibility_policy",
    # elimination taxonomy
    "EliminationReason", "normalize_reason",
    # eligibility engine + results
    "ConditionResult", "AgentEligibilityResult", "RoleEligibilityReport",
    "EligibilityExplanation", "EligibilityReplayRecord", "WorkflowEligibilityResult",
    "evaluate_agent_eligibility", "evaluate_registry_for_role",
    "evaluate_workflow_eligibility", "explain_role_report", "build_replay_record",
    # fingerprint + version
    "fingerprint", "version_info", "VersionInfo",
    # -- P2.1: compiler workflow_ir.v2 compatibility adapter --
    "adapt_compiled_workflow_v2", "adapt_workflow", "declared_contract_version",
    "reduce_overlay", "compare_adaptations", "compare_workforce_plans",
    "AdaptationResultV2", "AdapterDiagnostic", "AdapterDiagnosticCode",
    "CompilerContractVersion", "CompilerAdapterMode",
    "AdaptationEquivalenceState", "AdaptationEquivalenceReport", "EquivalenceDifference",
    "SUPPORTED_COMPILER_CONTRACTS", "COMPILER_ADAPTER_CONTRACT_VERSION",
    "CONTRACT_VERSION", "VERSION", "__version__",
    # -- P2 (contract awc.composition.v1) --
    "COMPOSITION_CONTRACT_VERSION",
    # ranking
    "RankingCriterion", "AgentRankingPolicy", "RankingCriterionResult",
    "AgentRankResult", "RoleCandidateRanking",
    "rank_eligible_candidates", "rank_workflow_candidates",
    # dependency graph
    "RoleInterfaceRequirement", "RoleDependency", "RoleDependencyGraph",
    "build_role_dependency_graph",
    # failure domains
    "FailureDomain", "FailureDomainSet", "build_failure_domain_set",
    # composition
    "TeamCompositionPolicy", "RoleAssignment", "TeamConstraintResult",
    "TeamObjectiveResult", "SearchStatistics", "TeamCompositionResult",
    "compose_agent_team",
    # permission bounding
    "PermissionBoundingPolicy", "ProposedPermission", "PermissionBoundProposal",
    "propose_permission_bound",
    # fallback
    "AgentFallbackPolicy", "FallbackCandidate", "RoleFallbackPlan", "TeamFallbackPlan",
    "build_fallback_plan",
    # plan + replay + diff
    "AgentTeamPlan", "AgentTeamPlanState", "TeamSelectionExplanation",
    "CompositionReplayRecord", "AgentTeamPlanDiff",
    "build_agent_team_plan", "replay_agent_team_plan", "compare_agent_team_plans",
    "build_replay_record",
    # P2 enums
    "SelectionState", "CompositionState", "OptimalityStatus", "FallbackState",
    "PermissionCategory",
]
