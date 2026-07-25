"""The immutable CompensationRequirement — a governed proposal, not an auto-rollback.

When reconciliation finds a material mismatch, duplicate effect, or partial
completion, a compensation *requirement* is recorded. Phase 4C never performs
compensation automatically: it is a proposal or obligation. Any compensating action
must pass through the normal governance chain (a new governed action request);
rollback is never assumed possible. Closing a requirement preserves history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .status import CompensationApprovalStatus, CompensationType


class CompensationRequirement(DomainModel):
    """An immutable snapshot of a compensation obligation arising from a mismatch."""

    compensation_id: str
    execution_intent_id: str
    reconciliation_id: str
    tenant_id: str
    reason_codes: tuple[str, ...]
    affected_effects: tuple[str, ...] = ()
    proposed_compensation_type: CompensationType = CompensationType.MANUAL_INTERVENTION
    required_authority: str = ""
    approval_status: CompensationApprovalStatus = CompensationApprovalStatus.PROPOSED
    created_by: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None
    resolution_ref: Optional[str] = None
    resolved_by: Optional[str] = None
    revision: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "CompensationRequirement":
        for req in ("compensation_id", "execution_intent_id", "reconciliation_id",
                    "tenant_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if not self.reason_codes:
            raise DomainValidationError("a compensation requirement needs reason codes")
        if self.revision < 1:
            raise DomainValidationError("revision must be >= 1")
        if (self.approval_status is CompensationApprovalStatus.RESOLVED
                and self.resolved_at is None):
            raise DomainValidationError("a resolved compensation requires resolved_at")
        return self

    def resolved(self, *, by: str, at: datetime, resolution_ref: str,
                 status: CompensationApprovalStatus) -> "CompensationRequirement":
        """Return a new, higher-revision snapshot marking the requirement resolved."""
        data = self.model_dump()
        data.update(approval_status=status, resolved_by=by, resolved_at=at,
                    resolution_ref=resolution_ref, revision=self.revision + 1)
        return CompensationRequirement(**data)
