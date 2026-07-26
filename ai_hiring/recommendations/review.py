"""Human-review package + reviewer dispositions (H2).

The human-review view assembles everything a human reviewer needs to judge a
recommendation, and the reviewer-disposition record captures the reviewer's action
on the **recommendation record** — never a binding hiring decision. Reviewer
actions are human-only (enforced in the service); AI may not approve its own
recommendation or bypass review.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .claim import HiringClaim
from .recommendation import HiringRecommendation


class ReviewerAction(str, Enum):
    """Actions a human reviewer may take on a recommendation record."""

    ACCEPT_FOR_CONSIDERATION = "ACCEPT_FOR_CONSIDERATION"  # advisory: forward to human decision (H3)
    REJECT_RECOMMENDATION = "REJECT_RECOMMENDATION"
    REQUEST_ADDITIONAL_EVIDENCE = "REQUEST_ADDITIONAL_EVIDENCE"
    RETURN_FOR_REVISION = "RETURN_FOR_REVISION"
    RECORD_COMMENT = "RECORD_COMMENT"


class ReviewerDisposition(DomainModel):
    disposition_id: str
    tenant_id: str
    recommendation_id: str
    recommendation_version: int
    action: ReviewerAction
    reviewer_id: str
    comment: str = ""
    requested_evidence_types: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ReviewerDisposition":
        for req in ("disposition_id", "tenant_id", "recommendation_id", "reviewer_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"ReviewerDisposition.{req} is required")
        return self


class ClaimEvidenceView(DomainModel):
    claim_id: str
    claim_type: str
    proposition: str
    competency_id: str = ""
    criterion_id: str = ""
    material: bool = True
    supporting_evidence_refs: tuple[str, ...] = ()
    contradicting_evidence_refs: tuple[str, ...] = ()
    evidence_sufficiency: str = ""
    assertion_outcome: str = ""
    assertion_evidence_coverage: float = 0.0
    confidence: float = 0.0


class RecommendationReviewPackage(DomainModel):
    """The complete, human-facing review view for a recommendation version."""

    recommendation_id: str
    tenant_id: str
    application_id: str
    candidate_subject_ref: str
    status: str
    outcome: str
    advisory: bool = True
    confidence: float = 0.0
    uncertainty_note: str = ""
    summary_rationale: tuple[str, ...] = ()
    claims: tuple[ClaimEvidenceView, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    contradictory_evidence_refs: tuple[str, ...] = ()
    rubric_id: str = ""
    rubric_version: int = 0
    generator_id: str = ""
    provider_id: str = ""
    provider_contract_version: str = ""
    version_history: tuple[int, ...] = ()
    available_reviewer_actions: tuple[str, ...] = ()

    @classmethod
    def build(
        cls, *, recommendation: HiringRecommendation, claims: tuple[HiringClaim, ...],
        version_history: tuple[int, ...], available_actions: tuple[str, ...],
    ) -> "RecommendationReviewPackage":
        claim_views = tuple(
            ClaimEvidenceView(
                claim_id=c.claim_id, claim_type=c.claim_type.value, proposition=c.proposition,
                competency_id=c.competency_id, criterion_id=c.criterion_id, material=c.material,
                supporting_evidence_refs=c.supporting_evidence_refs,
                contradicting_evidence_refs=c.contradicting_evidence_refs,
                evidence_sufficiency=c.evidence_sufficiency.value,
                assertion_outcome=c.assertion_outcome.value,
                assertion_evidence_coverage=c.assertion_evidence_coverage, confidence=c.confidence)
            for c in claims)
        contradictory = tuple(sorted({r for c in claims for r in c.contradicting_evidence_refs}))
        return cls(
            recommendation_id=recommendation.recommendation_id, tenant_id=recommendation.tenant_id,
            application_id=recommendation.application_id,
            candidate_subject_ref=recommendation.candidate_subject_ref,
            status=recommendation.status.value, outcome=recommendation.outcome.value,
            advisory=recommendation.advisory, confidence=recommendation.confidence,
            uncertainty_note=recommendation.uncertainty_note,
            summary_rationale=recommendation.rationale, claims=claim_views,
            missing_evidence=recommendation.evidence_gaps, contradictory_evidence_refs=contradictory,
            rubric_id=recommendation.rubric_id, rubric_version=recommendation.rubric_version,
            generator_id=recommendation.generator_id, provider_id=recommendation.provider_id,
            provider_contract_version=recommendation.provider_contract_version,
            version_history=version_history, available_reviewer_actions=available_actions)
