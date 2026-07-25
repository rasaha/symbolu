"""Missing-evidence records (first-class).

Missing evidence is represented explicitly and is *never* automatically converted
into an adverse capability finding. The published rubric decides whether a
criterion is required or optional; the runtime records structural absence only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..ontology.taxonomy import EvidenceType, ReasonCode
from ..rubrics.evidence_rules import MissingEvidenceStatus


class MissingEvidenceRecord(DomainModel):
    """A record that expected evidence is absent, with an explicit status."""

    record_id: str
    workspace_id: str
    criterion_id: str
    capability_id: str
    expected_evidence_type: Optional[EvidenceType] = None
    status: MissingEvidenceStatus
    reason_codes: tuple[ReasonCode, ...] = ()
    detected_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "MissingEvidenceRecord":
        for req in ("record_id", "workspace_id", "criterion_id", "capability_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        return self

    @property
    def blocks_when_required(self) -> bool:
        """Statuses that, for a *required* criterion, prevent finalization.

        NOT_REQUIRED never blocks; the rest indicate the required evidence is not
        usable. This does not make the finding *adverse* — only *incomplete*.
        """
        return self.status is not MissingEvidenceStatus.NOT_REQUIRED