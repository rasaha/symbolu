"""Job-definition contract (H1).

A ``JobDefinition`` binds a requisition to a published rubric version and the
required capabilities / evidence types that later assessment and readiness checks
depend on. It is the durable job → rubric binding the roadmap flagged as the H1
gap. Immutable and versioned; publish/retire are lifecycle transitions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError, IllegalJobDefinitionTransitionError
from .status import JobDefinitionStatus, job_definition_transition_allowed


class JobDefinition(DomainModel):
    job_definition_id: str
    requisition_id: str
    tenant_id: str
    rubric_id: str
    rubric_version: int
    required_capability_ids: tuple[str, ...] = ()
    required_evidence_types: tuple[str, ...] = ()
    status: JobDefinitionStatus = JobDefinitionStatus.DRAFT
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "JobDefinition":
        for req in ("job_definition_id", "requisition_id", "tenant_id",
                    "rubric_id", "created_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"JobDefinition.{req} is required")
        if self.rubric_version < 1:
            raise DomainValidationError("rubric_version must be >= 1")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        if len(set(self.required_capability_ids)) != len(self.required_capability_ids):
            raise DomainValidationError("duplicate required_capability_id")
        if len(set(self.required_evidence_types)) != len(self.required_evidence_types):
            raise DomainValidationError("duplicate required_evidence_type")
        return self

    @property
    def is_published(self) -> bool:
        return self.status == JobDefinitionStatus.PUBLISHED

    def with_status(self, new_status: JobDefinitionStatus) -> "JobDefinition":
        if new_status == self.status:
            raise IllegalJobDefinitionTransitionError(
                f"job definition '{self.job_definition_id}' is already {self.status.value}"
            )
        if not job_definition_transition_allowed(self.status, new_status):
            raise IllegalJobDefinitionTransitionError(
                f"illegal job-definition transition {self.status.value} -> {new_status.value}"
            )
        data = self.model_dump()
        data["status"] = new_status
        data["version"] = self.version + 1
        return type(self)(**data)
