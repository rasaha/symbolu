"""Application contract (H1) — links a candidate to a requisition.

Immutable and versioned. Ties together the tenant, candidate, requisition, and the
job-definition version in force at submission. Lifecycle transitions are
structural (see :mod:`.status`); the binding hiring decision is never made here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError, IllegalApplicationTransitionError
from .status import ApplicationStatus, application_transition_allowed


class Application(DomainModel):
    application_id: str
    tenant_id: str
    candidate_id: str
    requisition_id: str
    job_definition_id: str
    job_definition_version: int
    status: ApplicationStatus = ApplicationStatus.RECEIVED
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "Application":
        for req in ("application_id", "tenant_id", "candidate_id",
                    "requisition_id", "job_definition_id", "created_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"Application.{req} is required")
        if self.job_definition_version < 1:
            raise DomainValidationError("job_definition_version must be >= 1")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def with_status(self, new_status: ApplicationStatus) -> "Application":
        if new_status == self.status:
            raise IllegalApplicationTransitionError(
                f"application '{self.application_id}' is already {self.status.value}"
            )
        if not application_transition_allowed(self.status, new_status):
            raise IllegalApplicationTransitionError(
                f"illegal application transition {self.status.value} -> {new_status.value}"
            )
        data = self.model_dump()
        data["status"] = new_status
        data["version"] = self.version + 1
        return type(self)(**data)
