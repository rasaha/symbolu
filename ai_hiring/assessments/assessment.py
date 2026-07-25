"""The immutable, advisory assessment snapshot.

An assessment records, per criterion, what admitted evidence supports under the
pinned rubric — with observations, missing-evidence records, uncertainty,
conflicts, and reason codes. It is **advisory only**. It carries no recommendation,
no hiring outcome, no rank, no candidate comparison, no action authorization, and
no execution. Finalization is append-only; a revision supersedes rather than
overwrites.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..ontology.taxonomy import ReasonCode
from ..rubrics.conflicts import Conflict
from ..rubrics.uncertainty import UncertaintyLevel
from .completeness import CompletenessResult
from .evidence_binding import ExcludedEvidenceRecord
from .missing_evidence import MissingEvidenceRecord
from .observation import Observation
from .status import AssessmentStatus, CompletenessStatus, ObservationValidationStatus


class CapabilityAssessment(DomainModel):
    """A structured, per-capability result. No score is computed by the runtime."""

    capability_id: str
    capability_version: int
    criterion_id: str
    admitted_evidence_ids: tuple[str, ...] = ()
    excluded_evidence_records: tuple[ExcludedEvidenceRecord, ...] = ()
    observation: Optional[Observation] = None
    missing_evidence_records: tuple[MissingEvidenceRecord, ...] = ()
    uncertainty: Optional[UncertaintyLevel] = None
    conflicts: tuple[Conflict, ...] = ()
    reason_codes: tuple[ReasonCode, ...] = ()
    validation_status: ObservationValidationStatus = ObservationValidationStatus.VALID

    @model_validator(mode="after")
    def _validate(self) -> "CapabilityAssessment":
        if not self.criterion_id.strip():
            raise DomainValidationError("criterion_id is required")
        if self.capability_version < 1:
            raise DomainValidationError("capability_version must be >= 1")
        return self


class Assessment(DomainModel):
    """An immutable, advisory-only assessment snapshot.

    ``advisory_only`` is pinned True at the type level. The model forbids extra
    fields, which structurally prevents a recommendation/rank/decision/action/
    execution field from ever being attached.
    """

    assessment_id: str
    workspace_id: str
    tenant_id: str
    subject_id: str
    rubric_id: str
    rubric_version: int
    reason_code_catalog_version: str = "1.0"
    admissibility_policy_version: str = "1.0"
    capability_assessments: tuple[CapabilityAssessment, ...]
    completeness: CompletenessResult
    status: AssessmentStatus = AssessmentStatus.FINALIZED_ADVISORY
    advisory_only: Literal[True] = True
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    supersedes_assessment_id: Optional[str] = None
    version: int = 1
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "Assessment":
        for req in ("assessment_id", "workspace_id", "tenant_id", "subject_id",
                    "rubric_id", "created_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if not self.capability_assessments:
            raise DomainValidationError("assessment requires capability assessments")
        if self.advisory_only is not True:
            raise DomainValidationError("advisory_only must be True in Phase 3B")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    @property
    def is_finalized(self) -> bool:
        return self.status is AssessmentStatus.FINALIZED_ADVISORY

    @property
    def completeness_status(self) -> CompletenessStatus:
        return self.completeness.status