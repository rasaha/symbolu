"""Evidence contracts.

``NormalizedEvidence`` is the immutable, versioned unit of candidate evidence
produced by the (later-phase) ingestion engine. This phase defines and
validates the contract only — nothing here extracts, parses, or scores
evidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..errors import DomainValidationError
from .base import DomainModel


class EvidenceRef(DomainModel):
    """A pointer to a span of evidence that justifies a score or reason code."""

    evidence_id: str
    locator: str = ""  # optional intra-evidence pointer (line range, timestamp, ...)

    @model_validator(mode="after")
    def _require_evidence_id(self) -> "EvidenceRef":
        if not self.evidence_id.strip():
            raise DomainValidationError("EvidenceRef.evidence_id must be non-empty")
        return self


class NormalizedEvidence(DomainModel):
    """A single, format-normalized unit of candidate evidence.

    Immutable. A revision is a *new version* (see :meth:`revise`) with an
    incremented ``version`` — prior records are never overwritten.
    """

    evidence_id: str
    candidate_id: str
    role_id: str
    assessment_item_id: Optional[str] = None
    content_hash: str
    source_ref: str = ""
    index_ref: str = ""
    job_relevant: bool  # must be explicit — no default
    format: str = ""
    provenance: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "NormalizedEvidence":
        if not self.evidence_id.strip():
            raise DomainValidationError("evidence_id is required")
        if not self.candidate_id.strip():
            raise DomainValidationError("candidate_id is required")
        if not self.role_id.strip():
            raise DomainValidationError("role_id is required")
        if not self.content_hash.strip():
            raise DomainValidationError("content_hash is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def revise(self, **changes: object) -> "NormalizedEvidence":
        """Return a new, higher-versioned revision of this evidence record.

        The logical ``evidence_id`` is preserved; ``version`` is incremented.
        Because the model is frozen, this never mutates the current record.
        """
        data = self.model_dump()
        data.update(changes)
        data["version"] = self.version + 1
        return NormalizedEvidence(**data)
