"""Governance adapters — reuse of TAP, Decision Authority, CER, and ActionGate.

Every adapter composes an existing capability through its PUBLIC surface. The
product owns no neutral contract, adds no ProviderKind, and modifies no upstream
policy semantics.
"""
from __future__ import annotations

from .actiongate_adapter import ActionGateShadowAdapter, ShadowActionEvaluation
from .kernel import AuthorizedActor, DecisionCerKernel, DecisionInput
from .prepared_action import PreparedMergeAction
from .recommendation import GovernanceRecommendation, RecommendationDisposition
from .tap_adapter import TapAssertionResult, TapClaimAdapter, TapEvaluation

__all__ = [
    "TapClaimAdapter",
    "TapEvaluation",
    "TapAssertionResult",
    "AuthorizedActor",
    "DecisionInput",
    "DecisionCerKernel",
    "GovernanceRecommendation",
    "RecommendationDisposition",
    "PreparedMergeAction",
    "ActionGateShadowAdapter",
    "ShadowActionEvaluation",
]
