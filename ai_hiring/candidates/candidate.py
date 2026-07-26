"""Candidate identity and profile contracts (H1).

A ``Candidate`` is the tenant-scoped identity of a person under consideration. It
carries a ``subject_id`` that maps to the governance kernel's neutral subject
reference (used by decision cases in later phases) — the candidate entity is
hiring-owned; the governance kernel only ever sees the opaque subject id.

``CandidateProfile`` holds candidate-supplied descriptive attributes. Profiles are
immutable revisions; PII minimization is a caller concern (store references where
possible). Nothing here scores or decides.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError, IllegalCandidateTransitionError


class CandidateStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"


CANDIDATE_TERMINAL_STATUSES = frozenset({CandidateStatus.WITHDRAWN})


class CandidateProfile(DomainModel):
    """Immutable candidate-supplied descriptive attributes."""

    display_name: str = ""
    headline: str = ""
    location: str = ""
    contact_ref: str = ""  # a reference/handle, not raw PII where avoidable
    attributes: tuple[tuple[str, str], ...] = ()  # ordered key/value pairs

    @model_validator(mode="after")
    def _validate(self) -> "CandidateProfile":
        keys = [k for k, _ in self.attributes]
        if len(set(keys)) != len(keys):
            raise DomainValidationError("duplicate profile attribute key")
        return self


class Candidate(DomainModel):
    candidate_id: str
    tenant_id: str
    subject_id: str
    profile: CandidateProfile = Field(default_factory=CandidateProfile)
    status: CandidateStatus = CandidateStatus.ACTIVE
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "Candidate":
        for req in ("candidate_id", "tenant_id", "subject_id", "created_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"Candidate.{req} is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def with_profile(self, profile: CandidateProfile) -> "Candidate":
        """Return a new, higher-versioned candidate with a revised profile."""
        if self.status != CandidateStatus.ACTIVE:
            raise IllegalCandidateTransitionError(
                f"cannot revise a {self.status.value} candidate '{self.candidate_id}'"
            )
        data = self.model_dump()
        data["profile"] = profile.model_dump()
        data["version"] = self.version + 1
        return type(self)(**data)

    def withdrawn(self) -> "Candidate":
        """Return a new, higher-versioned candidate in WITHDRAWN status."""
        if self.status == CandidateStatus.WITHDRAWN:
            raise IllegalCandidateTransitionError(
                f"candidate '{self.candidate_id}' is already WITHDRAWN"
            )
        data = self.model_dump()
        data["status"] = CandidateStatus.WITHDRAWN
        data["version"] = self.version + 1
        return type(self)(**data)
