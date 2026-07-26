"""Governance-case binding (H3).

The hiring-owned, immutable, versioned link between an H2 hiring recommendation and
the DGM governance case it is bound to (and, once decided, the DGM decision). It is
the durable cross-reference that ties the hiring domain to the frozen kernel's
case → recommendation → decision chain without duplicating kernel state.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError


class GovernanceBindingStatus(str, Enum):
    OPEN = "OPEN"                 # case created, recommendation submitted, awaiting decision
    DECIDED = "DECIDED"          # a human decision has been recorded
    REJECTED = "REJECTED"        # the kernel recommendation was rejected by a human
    SUPERSEDED = "SUPERSEDED"    # the recommendation/case was superseded
    CLOSED = "CLOSED"


class GovernanceCaseBinding(DomainModel):
    binding_id: str
    tenant_id: str
    application_id: str
    hiring_recommendation_id: str
    candidate_subject_ref: str
    decision_case_id: str
    kernel_recommendation_id: str
    decision_id: str = ""
    override_id: str = ""
    status: GovernanceBindingStatus = GovernanceBindingStatus.OPEN
    correlation_id: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "GovernanceCaseBinding":
        for req in ("binding_id", "tenant_id", "application_id", "hiring_recommendation_id",
                    "decision_case_id", "kernel_recommendation_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"GovernanceCaseBinding.{req} is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def with_updates(self, **changes) -> "GovernanceCaseBinding":
        data = self.model_dump()
        data.update(changes)
        data["version"] = self.version + 1
        return type(self)(**data)
