"""Capability contract — an immutable node in the capability ontology.

A capability defines *what* can be assessed and *what evidence* is admissible for
it. It carries no scores and no evaluation logic — it is a definition. Immutable;
a change creates a new version (never an overwrite).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError, UnknownEvidenceTypeError
from .taxonomy import EvidenceType, is_known_evidence_type


class CapabilityStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"
    SUPERSEDED = "SUPERSEDED"


class Capability(DomainModel):
    """An immutable capability definition."""

    capability_id: str
    name: str
    description: str = ""
    category: str = ""
    parent_id: Optional[str] = None
    child_ids: tuple[str, ...] = ()
    required_evidence_types: tuple[EvidenceType, ...] = ()
    allowed_evidence_types: tuple[EvidenceType, ...] = ()
    minimum_evidence_count: int = 0
    status: CapabilityStatus = CapabilityStatus.DRAFT
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    supersedes: Optional[str] = None
    deprecated: bool = False

    @model_validator(mode="after")
    def _validate(self) -> "Capability":
        if not self.capability_id.strip():
            raise DomainValidationError("capability_id is required")
        if not self.name.strip():
            raise DomainValidationError("capability name is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        if self.minimum_evidence_count < 0:
            raise DomainValidationError("minimum_evidence_count must be >= 0")
        if self.parent_id is not None and self.parent_id == self.capability_id:
            raise DomainValidationError("a capability cannot be its own parent")
        # every declared type must be a known evidence type (enum guarantees it,
        # but this guards against future string coercion paths)
        for et in tuple(self.required_evidence_types) + tuple(self.allowed_evidence_types):
            if not is_known_evidence_type(et.value):
                raise UnknownEvidenceTypeError(f"unknown evidence type {et!r}")
        # required must be a subset of allowed (when an allow-list is given)
        if self.allowed_evidence_types:
            allowed = set(self.allowed_evidence_types)
            missing = [t for t in self.required_evidence_types if t not in allowed]
            if missing:
                raise DomainValidationError(
                    f"required evidence types not in allowed list: {missing}")
        return self

    def as_status(self, status: CapabilityStatus, **changes: object) -> "Capability":
        """Return a new, higher-versioned capability with a changed status."""
        data = self.model_dump()
        data.update(changes)
        data["status"] = status
        data["version"] = self.version + 1
        return Capability(**data)
