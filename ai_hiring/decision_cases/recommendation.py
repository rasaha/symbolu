"""The advisory RecommendationRecord — a *proposed course of action*, never binding.

A recommendation is one of the four separate records. It proposes; it does not
decide. It cannot bind the case, multiple recommendations may coexist (including
conflicting ones), and rejection never deletes it — new facts create new records.
AI-assisted recommendations are permitted **as advice** and must retain model
provenance, but an AI can never be the binding decision authority (see
``decision.py``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..ontology.taxonomy import ReasonCode
from ..rubrics.uncertainty import UncertaintyLevel
from .status import GeneratorType, ProposedOutcome, RecommendationStatus
from .subject import VersionedRef


class RecommendationRecord(DomainModel):
    """An immutable, advisory-only recommendation attached to a case."""

    recommendation_id: str
    decision_case_id: str
    tenant_id: str
    recommendation_type: str
    proposed_outcome: ProposedOutcome
    assessment_refs: tuple[VersionedRef, ...] = ()
    policy_refs: tuple[VersionedRef, ...] = ()
    reason_codes: tuple[ReasonCode, ...] = ()
    uncertainty: Optional[UncertaintyLevel] = None
    generated_by: str
    generator_type: GeneratorType
    model_provenance: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    status: RecommendationStatus = RecommendationStatus.PROPOSED
    supersedes_recommendation_id: Optional[str] = None
    #: Pinned True at the type level: a recommendation is never a decision.
    advisory_only: Literal[True] = True

    @model_validator(mode="after")
    def _validate(self) -> "RecommendationRecord":
        for req in ("recommendation_id", "decision_case_id", "tenant_id",
                    "generated_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if self.advisory_only is not True:
            raise DomainValidationError("advisory_only must be True in Phase 4A")
        # AI-assisted advice must carry model provenance for auditability.
        if (self.generator_type is GeneratorType.AI_ASSISTED
                and not (self.model_provenance or "").strip()):
            raise DomainValidationError(
                "AI_ASSISTED recommendations must retain model_provenance")
        return self
