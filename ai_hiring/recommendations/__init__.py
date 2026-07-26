"""H2 recommendation & structured-claim contracts and integration."""
from __future__ import annotations

from .claim import (
    ASSERTION_POLICY_PASS, AssertionOutcome, ClaimReviewStatus, ClaimType,
    EvidenceSufficiency, HiringClaim)
from .generator import (
    DeterministicRecommendationGenerator, DraftClaim, GenerationContext, GeneratorOutput,
    RecommendationGeneratorPort, validate_generator_output)
from .recommendation import HiringRecommendation, RecommendationOutcome
from .review import (
    ClaimEvidenceView, RecommendationReviewPackage, ReviewerAction, ReviewerDisposition)
from .status import (
    RECOMMENDATION_TERMINAL_STATUSES, RecommendationStatus, recommendation_transition_allowed)
from .tap_integration import ClaimAssertionBinding, ClaimAssertionEvaluator

__all__ = [
    "HiringClaim", "ClaimType", "EvidenceSufficiency", "AssertionOutcome",
    "ClaimReviewStatus", "ASSERTION_POLICY_PASS",
    "HiringRecommendation", "RecommendationOutcome",
    "RecommendationStatus", "RECOMMENDATION_TERMINAL_STATUSES", "recommendation_transition_allowed",
    "DeterministicRecommendationGenerator", "RecommendationGeneratorPort", "GenerationContext",
    "GeneratorOutput", "DraftClaim", "validate_generator_output",
    "ClaimAssertionEvaluator", "ClaimAssertionBinding",
    "RecommendationReviewPackage", "ClaimEvidenceView", "ReviewerAction", "ReviewerDisposition",
]
