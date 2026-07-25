"""AI recommendation contract — advisory only.

A ``Recommendation`` is the AI's suggested disposition for a candidate. It is
*advisory evidence*, never a decision: its ``actor_type`` is pinned to ``AI``,
and nothing about it can drive a binding workflow transition (that is enforced
in the workflow/transition policy, which refuses any AI-actor transition).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from ..common import utc_now
from ..errors import BoundaryViolationError, DomainValidationError
from .base import DomainModel
from .enums import ActorType, CapabilityLayer, Disposition
from .evaluation import Limitation


class Recommendation(DomainModel):
    """An AI-produced, advisory suggested disposition for an evaluation."""

    recommendation_id: str
    evaluation_id: str
    suggested_disposition: Disposition
    supporting_layers: tuple[CapabilityLayer, ...] = ()
    caveats: tuple[Limitation, ...] = ()
    actor_type: ActorType = ActorType.AI
    actor_id: str = ""  # the AI/service principal that produced it (optional)
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "Recommendation":
        # The load-bearing invariant: a recommendation is always AI-authored.
        if self.actor_type is not ActorType.AI:
            raise BoundaryViolationError(
                "a Recommendation must have actor_type=AI; "
                f"got {self.actor_type.value}"
            )
        if not self.recommendation_id.strip():
            raise DomainValidationError("recommendation_id is required")
        if not self.evaluation_id.strip():
            raise DomainValidationError("evaluation_id is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self
