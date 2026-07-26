"""Structured hiring claims (H2).

Recommendation reasoning is represented as structured, evidence-linked claims —
not only free-form text. Each material claim carries its supporting/contradicting
evidence, an evidence-sufficiency result, and an assertion-governance outcome
(from the Assertion Governance Provider). Immutable and versioned with its parent
recommendation.

Prohibited: personality, demographic, medical, emotional, or protected-class
inference. Claim types are competency/requirement/evidence-structural only.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError


class ClaimType(str, Enum):
    DEMONSTRATED_CAPABILITY = "DEMONSTRATED_CAPABILITY"
    INSUFFICIENT_EVIDENCE_FOR_CAPABILITY = "INSUFFICIENT_EVIDENCE_FOR_CAPABILITY"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    REQUIREMENT_SATISFIED = "REQUIREMENT_SATISFIED"
    REQUIREMENT_NOT_DEMONSTRATED = "REQUIREMENT_NOT_DEMONSTRATED"
    ASSESSMENT_INCOMPLETE = "ASSESSMENT_INCOMPLETE"
    RECOMMENDATION_CANNOT_BE_FORMED = "RECOMMENDATION_CANNOT_BE_FORMED"


class EvidenceSufficiency(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTING = "CONFLICTING"
    ABSENT = "ABSENT"


class AssertionOutcome(str, Enum):
    """H2 view of the provider's assertion-governance result for a claim."""

    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICTING = "CONFLICTING"
    UNEVALUABLE = "UNEVALUABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


# Outcomes that satisfy a required-claim assertion policy.
ASSERTION_POLICY_PASS = frozenset({AssertionOutcome.SUPPORTED, AssertionOutcome.PARTIALLY_SUPPORTED})


class ClaimReviewStatus(str, Enum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"


class HiringClaim(DomainModel):
    claim_id: str
    tenant_id: str
    recommendation_id: str
    recommendation_version: int
    application_id: str
    candidate_subject_ref: str
    claim_type: ClaimType
    proposition: str  # normalized proposition / claim text
    competency_id: str = ""      # rubric capability id, where applicable
    criterion_id: str = ""       # rubric criterion id, where applicable
    material: bool = True        # material claims gate readiness
    supporting_evidence_refs: tuple[str, ...] = ()
    contradicting_evidence_refs: tuple[str, ...] = ()
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.ABSENT
    assertion_outcome: AssertionOutcome = AssertionOutcome.NOT_EVALUATED
    assertion_trace_id: str = ""
    assertion_evidence_coverage: float = 0.0
    assertion_explanation_refs: tuple[str, ...] = ()
    confidence: float = 0.0      # 0..1 advisory confidence
    uncertainty_note: str = ""
    generator_id: str = ""
    review_status: ClaimReviewStatus = ClaimReviewStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "HiringClaim":
        for req in ("claim_id", "tenant_id", "recommendation_id", "application_id",
                    "candidate_subject_ref", "proposition"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"HiringClaim.{req} is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainValidationError("confidence must be within [0, 1]")
        if not 0.0 <= self.assertion_evidence_coverage <= 1.0:
            raise DomainValidationError("assertion_evidence_coverage must be within [0, 1]")
        return self

    @property
    def passes_assertion_policy(self) -> bool:
        return self.assertion_outcome in ASSERTION_POLICY_PASS
