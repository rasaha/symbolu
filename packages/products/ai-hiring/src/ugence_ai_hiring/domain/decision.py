"""Human employment-decision contract — binding.

A ``Decision`` is the recorded, binding human act that accepts, modifies, or
overrides an AI recommendation. Its ``actor_type`` is pinned to ``HUMAN`` and a
``human_actor_id`` is mandatory: a ``Decision`` cannot be *constructed* with
``actor_type=AI``. Authentication that the ``human_actor_id`` is a real,
non-service human is enforced additionally at the policy/service layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..errors import BoundaryViolationError, DomainValidationError
from .base import DomainModel
from .enums import ActorType, Disposition


class Override(DomainModel):
    """A recorded reason for diverging from the AI recommendation."""

    reason: str
    from_disposition: Optional[Disposition] = None
    to_disposition: Optional[Disposition] = None

    @model_validator(mode="after")
    def _require_reason(self) -> "Override":
        if not self.reason.strip():
            raise DomainValidationError("Override.reason must be non-empty")
        return self


class Approval(DomainModel):
    """A second-signature / segregation-of-duties approval marker."""

    approver_id: str
    approved: bool = True
    note: str = ""

    @model_validator(mode="after")
    def _require_approver(self) -> "Approval":
        if not self.approver_id.strip():
            raise DomainValidationError("Approval.approver_id must be non-empty")
        return self


class Decision(DomainModel):
    """A binding, human-authored employment decision."""

    decision_id: str
    recommendation_id: str
    evaluation_id: str
    candidate_id: str
    role_id: str
    disposition: Disposition
    human_actor_id: str
    panel: tuple[str, ...]
    rationale_job_related: str
    override: Optional[Override] = None
    approval: Optional[Approval] = None
    actor_type: ActorType = ActorType.HUMAN
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "Decision":
        # The load-bearing invariant: a decision is always human-authored.
        if self.actor_type is not ActorType.HUMAN:
            raise BoundaryViolationError(
                "a Decision must have actor_type=HUMAN; a non-human actor may "
                f"never author a binding decision (got {self.actor_type.value})"
            )
        if not self.human_actor_id.strip():
            raise DomainValidationError("human_actor_id is mandatory")
        if not self.rationale_job_related.strip():
            raise DomainValidationError("rationale_job_related is mandatory and non-empty")
        if len(self.panel) < 1:
            raise DomainValidationError("panel must contain at least the primary human actor")
        if self.human_actor_id not in self.panel:
            raise DomainValidationError(
                "the primary human_actor_id must be a member of the panel"
            )
        for required in ("decision_id", "recommendation_id", "evaluation_id",
                         "candidate_id", "role_id"):
            if not getattr(self, required).strip():
                raise DomainValidationError(f"{required} is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self
