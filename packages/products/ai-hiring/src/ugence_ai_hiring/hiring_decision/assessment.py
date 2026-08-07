"""DimensionAssessment — advisory, per-dimension evidence-backed assessment.

There are no bare scores: every scored dimension carries confidence, the
evidence it consumed, an assessment version, and rationale/provenance. Produced
by an assessment engine (AI-assisted); this record is advisory and never a
decision.

Invariants enforced here:

- No culture-fit / resilience constructs: a forbidden legacy dimension is
  rejected (``CULTURE_FIT`` → Operating Environment Compatibility, ``RESILIENCE``
  → Role Sustainability & Adaptation).
- Role Sustainability & Adaptation stays post-hire-oriented: it may be SCORED
  pre-hire only when explicit job-relevant evidence supports a *bounded* pre-hire
  assessment (``pre_hire_justified=True`` with non-empty evidence).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..hiring_policy.enums import DIM_ROLE_SUSTAINABILITY, FORBIDDEN_DIMENSIONS
from .enums import AssessmentOutcome


class AssessmentProvenance(DomainModel):
    """Where a dimension assessment came from (engine/model identity + time)."""

    engine: str
    model_id: str = ""
    model_version: str = ""
    produced_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "AssessmentProvenance":
        if not self.engine.strip():
            raise DomainValidationError("assessment provenance.engine is required")
        return self


class DimensionAssessment(DomainModel):
    """Advisory assessment of one role-scoped compatibility dimension."""

    dimension: str
    outcome: AssessmentOutcome
    score: Optional[float] = None  # 0..100; present iff outcome == SCORED
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = ()
    assessment_version: int = 1
    rationale: tuple[str, ...] = ()
    provenance: AssessmentProvenance
    # Justifies a bounded pre-hire ROLE_SUSTAINABILITY score with job-relevant evidence.
    pre_hire_justified: bool = False
    advisory_only: Literal[True] = True

    @model_validator(mode="after")
    def _validate(self) -> "DimensionAssessment":
        dim = self.dimension.strip().upper()
        if not dim:
            raise DomainValidationError("dimension is required")
        if dim in FORBIDDEN_DIMENSIONS:
            raise DomainValidationError(
                f"dimension {self.dimension!r} is removed from the model; "
                f"use OPERATING_ENVIRONMENT_COMPATIBILITY or "
                f"ROLE_SUSTAINABILITY_AND_ADAPTATION instead"
            )
        if self.assessment_version < 1:
            raise DomainValidationError("assessment_version must be >= 1")
        if self.outcome is AssessmentOutcome.SCORED:
            if self.score is None:
                raise DomainValidationError("a SCORED assessment must carry a score")
            if not (0.0 <= self.score <= 100.0):
                raise DomainValidationError("score must be in [0, 100]")
            if not self.evidence_refs:
                raise DomainValidationError("a SCORED assessment must cite evidence")
            # Role Sustainability stays post-hire unless explicitly justified.
            if dim == DIM_ROLE_SUSTAINABILITY and not self.pre_hire_justified:
                raise DomainValidationError(
                    "ROLE_SUSTAINABILITY_AND_ADAPTATION is post-hire-oriented; a pre-hire "
                    "score requires pre_hire_justified=True backed by job-relevant evidence"
                )
        else:  # INSUFFICIENT_EVIDENCE
            if self.score is not None:
                raise DomainValidationError(
                    "an INSUFFICIENT_EVIDENCE assessment must not carry a score"
                )
        return self
