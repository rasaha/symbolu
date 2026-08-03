"""Conflict representation — contradictory evidence is *recorded, never resolved*.

This phase defines the contract for representing conflicting evidence sources. It
provides no resolution logic; a future process (with human oversight) decides.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError


class ConflictSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConflictStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ESCALATED = "ESCALATED"
    # deliberately no "RESOLVED": this phase represents, it does not resolve


class ConflictSource(DomainModel):
    """One side of a conflict — a source and the claim it makes."""

    source_ref: str
    claim: str

    @model_validator(mode="after")
    def _validate(self) -> "ConflictSource":
        if not self.source_ref.strip():
            raise DomainValidationError("source_ref is required")
        return self


class Conflict(DomainModel):
    """A recorded contradiction between evidence sources for a capability."""

    conflict_id: str
    capability_id: str
    sources: tuple[ConflictSource, ...]
    severity: ConflictSeverity
    reason: str
    status: ConflictStatus = ConflictStatus.OPEN
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "Conflict":
        if not self.conflict_id.strip():
            raise DomainValidationError("conflict_id is required")
        if not self.capability_id.strip():
            raise DomainValidationError("capability_id is required")
        if len(self.sources) < 2:
            raise DomainValidationError("a conflict needs at least two sources")
        if not self.reason.strip():
            raise DomainValidationError("conflict reason is required")
        return self
