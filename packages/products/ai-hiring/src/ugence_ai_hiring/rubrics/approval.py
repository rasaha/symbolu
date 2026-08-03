"""Rubric approval workflow and lifecycle state machine.

Author → Reviewer → Approver → Publisher. Only a PUBLISHED rubric may later be
used for evaluation. Transitions are validated here (data + pure functions), not
scattered through the service.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError, InvalidLifecycleTransitionError


class RubricStatus(str, Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class ApprovalRole(str, Enum):
    AUTHOR = "AUTHOR"
    REVIEWER = "REVIEWER"
    APPROVER = "APPROVER"
    PUBLISHER = "PUBLISHER"


class ApprovalAction(str, Enum):
    CREATE = "CREATE"
    SUBMIT = "SUBMIT"
    REVIEW = "REVIEW"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    PUBLISH = "PUBLISH"
    DEPRECATE = "DEPRECATE"
    RETIRE = "RETIRE"


class ApprovalRecord(DomainModel):
    """An immutable record of one lifecycle action."""

    actor_id: str
    role: ApprovalRole
    action: ApprovalAction
    timestamp: datetime = Field(default_factory=utc_now)
    note: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ApprovalRecord":
        if not self.actor_id.strip():
            raise DomainValidationError("actor_id is required")
        return self


S = RubricStatus
ALLOWED_TRANSITIONS: dict[RubricStatus, frozenset[RubricStatus]] = {
    S.DRAFT: frozenset({S.UNDER_REVIEW}),
    S.UNDER_REVIEW: frozenset({S.APPROVED, S.DRAFT}),  # approve or send back
    S.APPROVED: frozenset({S.PUBLISHED, S.DRAFT}),
    S.PUBLISHED: frozenset({S.DEPRECATED}),
    S.DEPRECATED: frozenset({S.RETIRED}),
    S.RETIRED: frozenset(),
}

# The role permitted to drive each target transition.
TRANSITION_ROLE: dict[RubricStatus, ApprovalRole] = {
    S.UNDER_REVIEW: ApprovalRole.AUTHOR,
    S.APPROVED: ApprovalRole.APPROVER,
    S.PUBLISHED: ApprovalRole.PUBLISHER,
    S.DEPRECATED: ApprovalRole.PUBLISHER,
    S.RETIRED: ApprovalRole.PUBLISHER,
    S.DRAFT: ApprovalRole.REVIEWER,  # send-back during review
}


def validate_transition(current: RubricStatus, target: RubricStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidLifecycleTransitionError(
            f"illegal rubric transition {current.value} -> {target.value}")


def role_for_target(target: RubricStatus) -> ApprovalRole:
    return TRANSITION_ROLE[target]
