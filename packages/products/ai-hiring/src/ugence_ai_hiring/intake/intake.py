"""Evidence-collection intake contract with provenance binding (H1).

An ``EvidenceIntakeItem`` is the immutable record of a single piece of candidate
evidence *as collected* — bound to an application, candidate, requisition, and
tenant, with an explicit provenance descriptor and a content hash. This is the
intake/collection surface that later phases normalize and evaluate; H1 defines and
governs the intake contract only — nothing here extracts, parses, or scores
content.

Provenance is captured at collection so the evidence's origin is reconstructable
and tamper-evident (the content hash pins the collected bytes; the domain audit
trail chains the intake event).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError


class IntakeSource(str, Enum):
    """How the evidence was collected. No AI-generated source in H1."""

    CANDIDATE_SUBMISSION = "CANDIDATE_SUBMISSION"
    RECRUITER_UPLOAD = "RECRUITER_UPLOAD"
    IMPORTED_APPROVED_RECORD = "IMPORTED_APPROVED_RECORD"
    SYSTEM_COLLECTED = "SYSTEM_COLLECTED"


class EvidenceProvenance(DomainModel):
    """Immutable origin descriptor bound to a collected evidence item."""

    source: IntakeSource
    collected_by: str
    collected_at: datetime = Field(default_factory=utc_now)
    source_ref: str = ""      # external reference/handle for the origin
    source_note: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "EvidenceProvenance":
        if not str(self.collected_by).strip():
            raise DomainValidationError("EvidenceProvenance.collected_by is required")
        return self


class EvidenceIntakeItem(DomainModel):
    intake_id: str
    tenant_id: str
    application_id: str
    candidate_id: str
    requisition_id: str
    evidence_type: str
    content_hash: str
    provenance: EvidenceProvenance
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "EvidenceIntakeItem":
        for req in ("intake_id", "tenant_id", "application_id", "candidate_id",
                    "requisition_id", "evidence_type", "content_hash"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"EvidenceIntakeItem.{req} is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self
