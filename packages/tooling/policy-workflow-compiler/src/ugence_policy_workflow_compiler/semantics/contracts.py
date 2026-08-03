"""Vocabulary for the additive ``workflow_ir.v2`` semantic-enrichment contract.

P2 enriches a compiled ``workflow_ir.v1`` graph with role-relevant semantics the
compiler legitimately owns — node meaning, capability requirements, typed data
contracts, dependency semantics, and authority / human-review classification —
each carried with deterministic provenance. It absorbs no enterprise deployment
policy, no agent-selection logic, no runtime state, and no governance execution
authority.

``workflow_ir.v1`` is unchanged and its fingerprints stay byte-stable; v2 is a
strict superset that embeds the v1 graph and adds enrichment beside it.
"""

from __future__ import annotations

from enum import Enum

#: The frozen v1 contract (unchanged by P2).
WORKFLOW_IR_V1 = "workflow_ir.v1"
#: The additive P2 enrichment contract.
WORKFLOW_IR_V2 = "workflow_ir.v2"
#: Every workflow-IR contract this build can emit / validate.
SUPPORTED_WORKFLOW_IR_VERSIONS = (WORKFLOW_IR_V1, WORKFLOW_IR_V2)


class RoleRelevance(str, Enum):
    """Deterministic, compiler-owned classification of what a node *is* for a
    downstream workforce planner. This is the compiler's upstream statement of
    node meaning — it never selects, ranks, or authorizes an agent."""

    #: Advisory cognitive work an AI agent may be considered for.
    ADVISORY_AGENT_ELIGIBLE = "ADVISORY_AGENT_ELIGIBLE"
    #: Deterministic/structural service work (audit emission, terminal outcome).
    DETERMINISTIC_SERVICE = "DETERMINISTIC_SERVICE"
    #: A human-review step (e.g. segregation of duties).
    HUMAN_REVIEW = "HUMAN_REVIEW"
    #: A human-authority / approval / override step.
    HUMAN_AUTHORITY = "HUMAN_AUTHORITY"
    #: An existing governance capability owns the step.
    GOVERNANCE_OWNED = "GOVERNANCE_OWNED"
    #: Not classifiable for agent assignment (fail closed).
    UNSUPPORTED = "UNSUPPORTED"


class RequirementLevel(str, Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


class CapabilityRequirementSource(str, Enum):
    """Where a capability requirement was derived from — always explicit."""

    EXPLICIT_POLICY = "EXPLICIT_POLICY"
    NODE_KIND_MAPPING = "NODE_KIND_MAPPING"
    CAPABILITY_OWNER_MAPPING = "CAPABILITY_OWNER_MAPPING"
    CONTRACT_DERIVATION = "CONTRACT_DERIVATION"
    UNRESOLVED = "UNRESOLVED"


class DependencyKind(str, Enum):
    """Role-relevant dependency semantics between two nodes."""

    DATA_DEPENDENCY = "DATA_DEPENDENCY"
    CONTROL_DEPENDENCY = "CONTROL_DEPENDENCY"
    ORDERING_DEPENDENCY = "ORDERING_DEPENDENCY"
    REVIEW_DEPENDENCY = "REVIEW_DEPENDENCY"
    AUTHORITY_DEPENDENCY = "AUTHORITY_DEPENDENCY"
    GOVERNANCE_DEPENDENCY = "GOVERNANCE_DEPENDENCY"
    CONDITIONAL_DEPENDENCY = "CONDITIONAL_DEPENDENCY"


class ResolutionStatus(str, Enum):
    """How a semantic field was resolved. Unknown is never fabricated."""

    EXPLICITLY_DECLARED = "EXPLICITLY_DECLARED"
    DETERMINISTICALLY_INFERRED = "DETERMINISTICALLY_INFERRED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED = "UNSUPPORTED"


class DerivationClass(str, Enum):
    """Provenance derivation class for an enriched semantic value."""

    EXPLICIT = "EXPLICIT"
    DETERMINISTIC_MAPPING = "DETERMINISTIC_MAPPING"
    DERIVED_FROM_CONTRACT = "DERIVED_FROM_CONTRACT"
    DERIVED_FROM_EDGE = "DERIVED_FROM_EDGE"
    DEFAULTED_SAFE = "DEFAULTED_SAFE"
    UNRESOLVED = "UNRESOLVED"


class SemanticFeatureName(str, Enum):
    """Contract-capability flags a v2 artifact may declare."""

    ROLE_SEMANTICS = "role_semantics"
    TYPED_CONTRACT_REFS = "typed_contract_refs"
    DEPENDENCY_SEMANTICS = "dependency_semantics"
    AUTHORITY_SEMANTICS = "authority_semantics"
    HUMAN_REVIEW_SEMANTICS = "human_review_semantics"
    POLICY_PROVENANCE = "policy_provenance"


__all__ = [
    "WORKFLOW_IR_V1",
    "WORKFLOW_IR_V2",
    "SUPPORTED_WORKFLOW_IR_VERSIONS",
    "RoleRelevance",
    "RequirementLevel",
    "CapabilityRequirementSource",
    "DependencyKind",
    "ResolutionStatus",
    "DerivationClass",
    "SemanticFeatureName",
]
