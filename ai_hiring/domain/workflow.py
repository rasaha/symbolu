"""Candidate workflow record.

``CandidateWorkflow`` is the immutable, versioned state of one candidate's
progress through the hiring workflow. Transitions are performed by the
``WorkflowService`` (guarded by the transition policy); each transition produces
a new version rather than mutating the record in place.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from ..common import utc_now
from ..errors import DomainValidationError
from .base import DomainModel
from .enums import WorkflowState


class CandidateWorkflow(DomainModel):
    """Immutable snapshot of a candidate's workflow state at a given version."""

    candidate_id: str
    role_id: str
    state: WorkflowState = WorkflowState.PLANNED
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_decision_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "CandidateWorkflow":
        if not self.candidate_id.strip():
            raise DomainValidationError("candidate_id is required")
        if not self.role_id.strip():
            raise DomainValidationError("role_id is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def transitioned(
        self,
        new_state: WorkflowState,
        *,
        now: datetime | None = None,
        last_decision_id: str | None = None,
    ) -> "CandidateWorkflow":
        """Return a new, higher-versioned workflow snapshot in ``new_state``."""
        return CandidateWorkflow(
            candidate_id=self.candidate_id,
            role_id=self.role_id,
            state=new_state,
            version=self.version + 1,
            created_at=self.created_at,
            updated_at=now or utc_now(),
            last_decision_id=(
                last_decision_id if last_decision_id is not None else self.last_decision_id
            ),
        )
