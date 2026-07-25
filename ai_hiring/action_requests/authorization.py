"""ActionAuthorizationResponse — what the AI Control Plane returned.

A control-plane response is an **authorization decision, not an execution record**.
``AUTHORIZED`` (with or without constraints), ``DENIED``, ``INDETERMINATE``, and
``EXPIRED`` are strictly distinct: an indeterminate response is never treated as
approval, and a granted authorization never means the action happened. Responses
are immutable and append-only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .status import AuthorizationOutcome


class ActionAuthorizationResponse(DomainModel):
    """An immutable record of one control-plane authorization result."""

    authorization_id: str
    action_request_id: str
    cer_id: str
    outcome: AuthorizationOutcome
    reason_codes: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    authorized_at: datetime = Field(default_factory=utc_now)
    expires_at: Optional[datetime] = None
    control_plane_ref: str = ""
    policy_versions: tuple[str, ...] = ()
    correlation_id: str = ""
    attempt: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "ActionAuthorizationResponse":
        for req in ("authorization_id", "action_request_id", "cer_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if self.attempt < 1:
            raise DomainValidationError("attempt must be >= 1")
        # Constraints only carry meaning for a constrained authorization; requiring
        # them there keeps imposed limits from being silently dropped.
        if (self.outcome is AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS
                and not self.constraints):
            raise DomainValidationError(
                "AUTHORIZED_WITH_CONSTRAINTS must preserve at least one constraint")
        return self
