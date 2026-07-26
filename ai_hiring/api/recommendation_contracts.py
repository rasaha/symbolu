"""API-facing contracts for H2 recommendation & synthesis.

Dependency-light request/response DTOs. Provider implementation details are never
exposed — only neutral outcome/metadata fields. Recommendation detail and review
responses reuse `RecommendationReviewPackage`.
"""

from __future__ import annotations

from typing import Optional

from ..domain.base import DomainModel
from ..recommendations.review import ReviewerAction


class RequestSynthesisRequest(DomainModel):
    application_id: str
    rubric_version: int
    max_items: int = 0
    excluded_fields: tuple[str, ...] = ()
    quarantined_hashes: tuple[str, ...] = ()
    correlation_id: str = ""


class GenerateRecommendationRequest(DomainModel):
    application_id: str
    synthesis_package_id: str
    policy_refs: tuple[str, ...] = ()
    supersede_existing: bool = False
    correlation_id: str = ""


class RecommendationSummaryView(DomainModel):
    recommendation_id: str
    application_id: str
    status: str
    outcome: str
    advisory: bool = True
    confidence: float = 0.0
    version: int = 1
    superseded_by: str = ""


class ClaimEvidenceMappingView(DomainModel):
    claim_id: str
    claim_type: str
    proposition: str
    material: bool
    supporting_evidence_refs: tuple[str, ...] = ()
    contradicting_evidence_refs: tuple[str, ...] = ()
    assertion_outcome: str = ""
    assertion_evidence_coverage: float = 0.0


class SubmitReviewRequest(DomainModel):
    recommendation_id: str
    action: ReviewerAction
    comment: str = ""
    requested_evidence_types: tuple[str, ...] = ()


class RequestAdditionalEvidenceRequest(DomainModel):
    recommendation_id: str
    evidence_types: tuple[str, ...]
    comment: str = ""
