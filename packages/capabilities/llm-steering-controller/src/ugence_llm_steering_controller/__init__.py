"""Ugence LLM Steering Controller — independent, advisory routing capability.

The Steering Controller is the deterministic **routing-recommendation layer** of the
Ugence platform. Given a request's requirements and a metadata-only candidate registry,
it discovers model/provider candidates, applies hard policy and capability constraints
(fail-closed, before scoring), scores the eligible set on decomposable dimensions, and
returns a ranked, explainable **routing recommendation** — to a separately governed
runtime.

Authority boundary (see ``docs/AUTHORITY_BOUNDARY.md``)::

    authority_class:                       ADVISORY
    execution_capability:                  NONE
    provider_invocation_capability:        NONE
    credential_access:                     NONE
    routing_decision_is_authority:         false
    live_provider_calls_enabled_by_default: false

This package recommends model/provider routing. It does **not** execute model requests,
load provider credentials, perform retries or fallbacks, open sockets, or replace the
Agent Runtime. It contains no Hybrid LLM model internals.

Relationship to sibling capabilities (see ``docs/CANONICAL_SOURCE_DECISION.md``):
``ugence-model-selection`` is the deterministic *selection leaf* (eligibility + policy
scoring over an already-approved candidate set). This controller is the *routing*
layer above it — candidate discovery, constraint filtering, ranking, and fallback /
escalation *recommendations*. The two are complementary; this package does not depend on
model-selection and reimplements no provider execution.

Public API (small and stable):
    LLMSteeringController      — registry -> SteeringResult
    CandidateRegistry          — metadata-only registry
    RoutingPolicy              — soft weighting / preset
    SteeringRequest, TaskRequirements
    ModelCandidate, ProviderCandidate
    RoutingRecommendation, SteeringResult, FallbackRecommendation
    RoutingConstraint, CandidateScore, RoutingExplanation, RoutingEvidence,
    RoutingDecisionTrace
    QualityPreference, PrivacyClass, ExecutionStatus, SteeringStatus, DeprecationState
    SteeringError, ContractError, RegistryError, PolicyViolation, NoEligibleCandidate
    recommend, build_controller   (convenience, from .api)
    __version__, POLICY_VERSION, SCHEMA_VERSION
"""

from __future__ import annotations

from .version import POLICY_VERSION, SCHEMA_VERSION, VERSION, __version__
from .contracts import (
    CandidateScore,
    ContractError,
    DeprecationState,
    ExecutionStatus,
    FallbackRecommendation,
    ModelCandidate,
    NoEligibleCandidate,
    PolicyViolation,
    PrivacyClass,
    ProviderCandidate,
    QualityPreference,
    RegistryError,
    RoutingConstraint,
    RoutingDecisionTrace,
    RoutingEvidence,
    RoutingExplanation,
    RoutingRecommendation,
    SteeringError,
    SteeringRequest,
    SteeringResult,
    SteeringStatus,
    TaskRequirements,
)
from .registry import CandidateRegistry, validate_registry
from .policy import RoutingPolicy
from .controller import LLMSteeringController
from .api import build_controller, recommend

__all__ = [
    "LLMSteeringController",
    "CandidateRegistry",
    "validate_registry",
    "RoutingPolicy",
    "SteeringRequest",
    "TaskRequirements",
    "ModelCandidate",
    "ProviderCandidate",
    "RoutingRecommendation",
    "SteeringResult",
    "FallbackRecommendation",
    "RoutingConstraint",
    "CandidateScore",
    "RoutingExplanation",
    "RoutingEvidence",
    "RoutingDecisionTrace",
    "QualityPreference",
    "PrivacyClass",
    "ExecutionStatus",
    "SteeringStatus",
    "DeprecationState",
    "SteeringError",
    "ContractError",
    "RegistryError",
    "PolicyViolation",
    "NoEligibleCandidate",
    "recommend",
    "build_controller",
    "__version__",
    "VERSION",
    "POLICY_VERSION",
    "SCHEMA_VERSION",
]
