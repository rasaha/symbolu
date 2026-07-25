"""The immutable ActionRequest — a *proposed*, governed action. Never an execution.

An action request references exactly one effective ``DecisionRecord`` and pins the
exact mapping and decision versions it was derived from. It carries requested
parameters and a declared target system, but **no execution result and no inferred
evidence**. It is immutable after submission; correction creates a superseding
request with a new CER.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import canonical_hash, utc_now
from ..decisions.subject import SubjectRef, VersionedRef
from ..base import DomainModel
from ..errors import DomainValidationError
from .status import ActionRequestStatus


class ActionRequest(DomainModel):
    """An immutable snapshot of a governed action request."""

    action_request_id: str
    tenant_id: str
    decision_case_id: str
    decision_case_version: int
    decision_id: str
    action_type: str
    target_system: str
    subject_refs: tuple[SubjectRef, ...]
    requested_parameters: dict[str, str] = Field(default_factory=dict)
    policy_refs: tuple[VersionedRef, ...] = ()
    authority_ref: Optional[str] = None
    action_mapping_ref: VersionedRef
    cer_id: Optional[str] = None
    status: ActionRequestStatus = ActionRequestStatus.DRAFT
    version: int = 1
    request_version_id: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    correlation_id: str = ""
    idempotency_key: str = ""
    supersedes_action_request_id: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "ActionRequest":
        for req in ("action_request_id", "tenant_id", "decision_case_id",
                    "decision_id", "action_type", "target_system", "created_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if not self.subject_refs:
            raise DomainValidationError("an action request requires at least one subject")
        if self.decision_case_version < 1:
            raise DomainValidationError("decision_case_version must be >= 1")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def parameters_hash(self) -> str:
        return canonical_hash(dict(self.requested_parameters))

    def content_key(self) -> str:
        """A deterministic content fingerprint used for idempotency conflict checks."""
        return canonical_hash({
            "decision_id": self.decision_id,
            "action_type": self.action_type,
            "target_system": self.target_system,
            "mapping": f"{self.action_mapping_ref.ref_id}:{self.action_mapping_ref.version}",
            "parameters": dict(self.requested_parameters),
        })

    def evolve(self, *, request_version_id: str, **changes: object) -> "ActionRequest":
        """Return a new, higher-version snapshot; the prior one is never mutated."""
        data = self.model_dump()
        data.update(changes)
        data.update(version=self.version + 1, request_version_id=request_version_id)
        return ActionRequest(**data)
