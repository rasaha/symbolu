"""Immutable, versioned hiring recommendation contract (H2).

A recommendation is **advisory** — it is grounded in versioned evidence and
provider-evaluated claims, and it is destined for human review. It is never a
binding hiring decision (there is no binding decision status; the outcome is an
advisory proposal). Supersession replaces a recommendation with a newer version;
prior versions are never overwritten.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError, IllegalRecommendationTransitionError
from .status import RecommendationStatus, recommendation_transition_allowed


class RecommendationOutcome(str, Enum):
    """Advisory recommendation outcome — NOT a binding hiring decision."""

    RECOMMEND_ADVANCE = "RECOMMEND_ADVANCE"
    RECOMMEND_HOLD = "RECOMMEND_HOLD"
    RECOMMEND_DECLINE = "RECOMMEND_DECLINE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_RECOMMENDATION = "NO_RECOMMENDATION"


class HiringRecommendation(DomainModel):
    recommendation_id: str
    tenant_id: str
    application_id: str
    candidate_subject_ref: str
    requisition_id: str
    job_definition_id: str
    job_definition_version: int
    rubric_id: str
    rubric_version: int
    assessment_workspace_ref: str = ""
    outcome: RecommendationOutcome = RecommendationOutcome.NO_RECOMMENDATION
    advisory: bool = True  # invariant: recommendations are always advisory
    confidence: float = 0.0
    uncertainty_note: str = ""
    rationale: tuple[str, ...] = ()                 # structured rationale points
    material_claim_ids: tuple[str, ...] = ()
    unsupported_claim_ids: tuple[str, ...] = ()     # unsupported/partially-supported
    evidence_gaps: tuple[str, ...] = ()
    evidence_package_ref: str = ""
    evidence_refs: tuple[str, ...] = ()             # the exact evidence set used
    generator_id: str = ""
    provider_id: str = ""
    provider_contract_version: str = ""
    policy_refs: tuple[str, ...] = ()
    provenance_id: str = ""
    correlation_id: str = ""
    generated_at: datetime = Field(default_factory=utc_now)
    status: RecommendationStatus = RecommendationStatus.DRAFT
    supersedes: str = ""            # prior recommendation_id this replaces
    superseded_by: str = ""         # newer recommendation_id that replaced this
    version: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "HiringRecommendation":
        for req in ("recommendation_id", "tenant_id", "application_id",
                    "candidate_subject_ref", "requisition_id", "job_definition_id", "rubric_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"HiringRecommendation.{req} is required")
        if self.advisory is not True:
            raise DomainValidationError("a recommendation must always be advisory")
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainValidationError("confidence must be within [0, 1]")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def with_status(self, new_status: RecommendationStatus) -> "HiringRecommendation":
        if new_status == self.status:
            raise IllegalRecommendationTransitionError(
                f"recommendation '{self.recommendation_id}' is already {self.status.value}")
        if not recommendation_transition_allowed(self.status, new_status):
            raise IllegalRecommendationTransitionError(
                f"illegal recommendation transition {self.status.value} -> {new_status.value}")
        data = self.model_dump()
        data["status"] = new_status
        data["version"] = self.version + 1
        return type(self)(**data)

    def superseded(self, by_recommendation_id: str) -> "HiringRecommendation":
        """Return a new version in SUPERSEDED status linked to its replacement."""
        if not by_recommendation_id.strip():
            raise DomainValidationError("by_recommendation_id is required")
        data = self.model_dump()
        data["status"] = RecommendationStatus.SUPERSEDED
        data["superseded_by"] = by_recommendation_id
        data["version"] = self.version + 1
        if not recommendation_transition_allowed(self.status, RecommendationStatus.SUPERSEDED):
            raise IllegalRecommendationTransitionError(
                f"cannot supersede a {self.status.value} recommendation")
        return type(self)(**data)
