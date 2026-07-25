"""Immutable review-task records for human-in-the-loop orchestration.

Review tasks make required human steps explicit and auditable (required review,
secondary approval, conflict review, evidence-gap review, recommendation review,
decision review). A task is immutable; completing it appends a new revision with
``COMPLETED`` status rather than mutating the original.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..base import DomainModel
from ..errors import DomainValidationError
from .status import ReviewTaskStatus, ReviewTaskType


class ReviewTask(DomainModel):
    """A single required review step on a case."""

    task_id: str
    decision_case_id: str
    tenant_id: str
    task_type: ReviewTaskType
    assigned_to: Optional[str] = None
    required_role: str = ""
    status: ReviewTaskStatus = ReviewTaskStatus.PENDING
    due_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    revision: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "ReviewTask":
        for req in ("task_id", "decision_case_id", "tenant_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if self.revision < 1:
            raise DomainValidationError("revision must be >= 1")
        if self.status is ReviewTaskStatus.COMPLETED and self.completed_at is None:
            raise DomainValidationError("a completed task requires completed_at")
        return self

    def completed(self, *, by: str, at: datetime) -> "ReviewTask":
        """Return a new, higher-revision snapshot marked COMPLETED."""
        data = self.model_dump()
        data.update(status=ReviewTaskStatus.COMPLETED, completed_by=by,
                    completed_at=at, revision=self.revision + 1)
        return ReviewTask(**data)
