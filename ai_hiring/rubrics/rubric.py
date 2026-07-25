"""The rubric contract — an immutable specification of how a role is assessed.

A rubric binds capabilities (with weights, scales, evidence rules, reason codes,
and uncertainty rules) for a role, plus the conflict severities it recognizes and
any custom scales it declares. It is a *contract*, not an evaluation: it holds no
candidate data and no scores. Immutable after publication; changes create a new
version.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..ontology.taxonomy import ReasonCode
from .approval import ApprovalRecord, RubricStatus
from .capability_mapping import RubricCapability
from .conflicts import ConflictSeverity
from .scoring_scale import ScoringScale


class Rubric(DomainModel):
    """An immutable rubric contract for one role + version."""

    rubric_id: str
    role: str
    version: int
    capabilities: tuple[RubricCapability, ...]
    default_scoring_scale_id: str
    allowed_reason_codes: tuple[ReasonCode, ...] = ()
    recognized_conflict_severities: tuple[ConflictSeverity, ...] = tuple(ConflictSeverity)
    custom_scales: tuple[ScoringScale, ...] = ()
    status: RubricStatus = RubricStatus.DRAFT
    approvals: tuple[ApprovalRecord, ...] = ()
    supersedes: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "Rubric":
        if not self.rubric_id.strip():
            raise DomainValidationError("rubric_id is required")
        if not self.role.strip():
            raise DomainValidationError("role is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        if not self.default_scoring_scale_id.strip():
            raise DomainValidationError("default_scoring_scale_id is required")
        return self

    @property
    def is_published(self) -> bool:
        return self.status is RubricStatus.PUBLISHED

    def with_status(
        self, status: RubricStatus, *, approval: Optional[ApprovalRecord] = None,
        **changes: object,
    ) -> "Rubric":
        """Return a new immutable snapshot in ``status`` (same version)."""
        data = self.model_dump()
        data.update(changes)
        data["status"] = status
        if approval is not None:
            data["approvals"] = tuple(self.approvals) + (approval.model_dump(),)
        return Rubric(**data)

    def as_new_version(self, **changes: object) -> "Rubric":
        """Return a fresh DRAFT at ``version + 1`` (post-publication revision)."""
        data = self.model_dump()
        data.update(changes)
        data["version"] = self.version + 1
        data["status"] = RubricStatus.DRAFT
        data["approvals"] = ()
        data["supersedes"] = self.rubric_id
        return Rubric(**data)
