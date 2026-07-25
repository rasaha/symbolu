"""The immutable ExecutionIntent — an authorized attempt-to-execute, not a result.

An intent references one exact authorized ``ActionRequest`` version and one valid
authorization response whose outcome is executable. Its parameters are a subset of
what was authorized — no new business parameters, target, or action type may be
introduced. It stores no external result. Its ``content_hash`` covers only the
authorized content, so it is stable across lifecycle transitions; a correction is
a new intent, not a mutation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import canonical_hash, utc_now
from ..base import DomainModel
from ..errors import DomainValidationError
from .status import ExecutionStatus


class ExecutionIntent(DomainModel):
    """An immutable snapshot of an authorized intent to execute an action."""

    execution_intent_id: str
    tenant_id: str
    action_request_id: str
    action_request_version: int
    authorization_id: str
    cer_id: str
    action_type: str
    target_system: str
    authorized_parameters: dict[str, str] = Field(default_factory=dict)
    authorization_constraints: tuple[str, ...] = ()
    authorization_obligations: tuple[str, ...] = ()
    authority_ref: Optional[str] = None
    policy_refs: tuple[str, ...] = ()
    correlation_id: str = ""
    execution_idempotency_key: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: Optional[datetime] = None
    content_hash: str = ""
    # Lifecycle projection (append-only via ``evolve``); never changes the
    # authorized content and therefore never changes ``content_hash``.
    status: ExecutionStatus = ExecutionStatus.INTENT_CREATED
    version: int = 1
    intent_version_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ExecutionIntent":
        for req in ("execution_intent_id", "tenant_id", "action_request_id",
                    "authorization_id", "cer_id", "action_type", "target_system",
                    "created_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if self.action_request_version < 1:
            raise DomainValidationError("action_request_version must be >= 1")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def compute_hash(self) -> str:
        """Deterministic hash over the *authorized content* (not the lifecycle)."""
        return canonical_hash({
            "tenant_id": self.tenant_id,
            "action_request_id": self.action_request_id,
            "action_request_version": self.action_request_version,
            "authorization_id": self.authorization_id, "cer_id": self.cer_id,
            "action_type": self.action_type, "target_system": self.target_system,
            "authorized_parameters": dict(self.authorized_parameters),
            "authorization_constraints": sorted(self.authorization_constraints),
            "authorization_obligations": sorted(self.authorization_obligations),
        })

    def is_expired(self, at: datetime) -> bool:
        return self.expires_at is not None and at > self.expires_at

    def evolve(self, *, intent_version_id: str, **changes: object) -> "ExecutionIntent":
        """Return a new, higher-version snapshot; the prior one is never mutated."""
        data = self.model_dump()
        data.update(changes)
        data.update(version=self.version + 1, intent_version_id=intent_version_id)
        return ExecutionIntent(**data)
