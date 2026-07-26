"""Job requisition contract (H1).

A ``JobRequisition`` is the immutable, versioned record of a job opening. State
changes are new versions (never overwrites); illegal lifecycle transitions raise
:class:`~ai_hiring.errors.IllegalRequisitionTransitionError`. Nothing here scores
or decides.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError, IllegalRequisitionTransitionError
from .status import RequisitionStatus, requisition_transition_allowed


class JobRequisition(DomainModel):
    requisition_id: str
    tenant_id: str
    title: str
    department: str = ""
    employment_type: str = ""
    location: str = ""
    headcount: int = 1
    description: str = ""
    status: RequisitionStatus = RequisitionStatus.DRAFT
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "JobRequisition":
        for req in ("requisition_id", "tenant_id", "title", "created_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"JobRequisition.{req} is required")
        if self.headcount < 1:
            raise DomainValidationError("headcount must be >= 1")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def with_status(self, new_status: RequisitionStatus) -> "JobRequisition":
        """Return a new, higher-versioned record in ``new_status``.

        Raises if the transition is illegal. Immutable: never mutates in place.
        """
        if new_status == self.status:
            raise IllegalRequisitionTransitionError(
                f"requisition '{self.requisition_id}' is already {self.status.value}"
            )
        if not requisition_transition_allowed(self.status, new_status):
            raise IllegalRequisitionTransitionError(
                f"illegal requisition transition {self.status.value} -> {new_status.value}"
            )
        data = self.model_dump()
        data["status"] = new_status
        data["version"] = self.version + 1
        return type(self)(**data)
