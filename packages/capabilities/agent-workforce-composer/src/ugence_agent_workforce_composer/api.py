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

# -- fingerprint + version -----------------------------------------------------
from .fingerprint import fingerprint
from .version import CONTRACT_VERSION, VERSION, VersionInfo, __version__, version_info

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
    "CONTRACT_VERSION", "VERSION", "__version__",
]
