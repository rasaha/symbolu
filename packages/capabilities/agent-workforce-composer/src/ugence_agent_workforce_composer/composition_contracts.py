"""Shared P2 vocabulary (contract ``awc.composition.v1``).

Additive to the P1 ``contracts`` module; P1 enums are untouched so P1 object
fingerprints are unchanged.
"""
from __future__ import annotations

from enum import Enum


class SelectionState(str, Enum):
    """A candidate's role-level selection status in an AgentTeamPlan."""

    INELIGIBLE = "INELIGIBLE"                      # excluded by P1 eligibility (never ranked)
    ELIGIBLE_NOT_SELECTED = "ELIGIBLE_NOT_SELECTED"
    SELECTED_PRIMARY = "SELECTED_PRIMARY"
    SELECTED_FALLBACK = "SELECTED_FALLBACK"


class CompositionState(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NO_FEASIBLE_TEAM = "NO_FEASIBLE_TEAM"
    SEARCH_SPACE_EXCEEDED = "SEARCH_SPACE_EXCEEDED"
    INVALID_INPUT = "INVALID_INPUT"


class OptimalityStatus(str, Enum):
    EXACT_OPTIMUM = "EXACT_OPTIMUM"
    NO_FEASIBLE_TEAM = "NO_FEASIBLE_TEAM"
    SEARCH_SPACE_EXCEEDED = "SEARCH_SPACE_EXCEEDED"
    INVALID_INPUT = "INVALID_INPUT"
    RESOURCE_BLOCKED = "RESOURCE_BLOCKED"


class AgentTeamPlanState(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NO_FEASIBLE_TEAM = "NO_FEASIBLE_TEAM"
    SEARCH_SPACE_EXCEEDED = "SEARCH_SPACE_EXCEEDED"
    INVALID_INPUT = "INVALID_INPUT"


class FallbackState(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NO_FALLBACK_AVAILABLE = "NO_FALLBACK_AVAILABLE"
    NOT_REQUIRED = "NOT_REQUIRED"
    INVALID = "INVALID"


class PermissionCategory(str, Enum):
    REQUIRED = "REQUIRED"
    PROPOSED = "PROPOSED"
    PROHIBITED = "PROHIBITED"
    UNSUPPORTED = "UNSUPPORTED"
    EXCESSIVE_REQUESTED = "EXCESSIVE_REQUESTED"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    GOVERNANCE_OWNED = "GOVERNANCE_OWNED"


class FailureDomainKind(str, Enum):
    PROVIDER = "PROVIDER"
    MODEL_FAMILY_REF = "MODEL_FAMILY_REF"
    DEPLOYMENT_REGION = "DEPLOYMENT_REGION"
    CLOUD_ENVIRONMENT = "CLOUD_ENVIRONMENT"
    RUNTIME_IMPLEMENTATION = "RUNTIME_IMPLEMENTATION"
    DATA_SOURCE_DEPENDENCY = "DATA_SOURCE_DEPENDENCY"
    TOOL_DEPENDENCY = "TOOL_DEPENDENCY"
    ORG_OWNER = "ORG_OWNER"


__all__ = [
    "SelectionState",
    "CompositionState",
    "OptimalityStatus",
    "AgentTeamPlanState",
    "FallbackState",
    "PermissionCategory",
    "FailureDomainKind",
]
