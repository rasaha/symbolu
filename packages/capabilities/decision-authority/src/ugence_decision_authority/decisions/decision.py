"""The binding DecisionRecord — what an *authorized actor* decided.

A decision is a separate, immutable record. It may accept, reject, or modify a
recommendation, or be made with no recommendation at all. It records *what was
decided and why*; it never carries execution state, never invokes the ActionGate,
and is never authored by an AI model. A changed decision **supersedes** the prior
record rather than mutating it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..base import DomainModel
from ..errors import DomainValidationError
from ..vocabulary import ReasonCode
from .status import AuthorityType, DecisionOutcome, EffectiveStatus
from .subject import VersionedRef


class DecisionRecord(DomainModel):
    """An immutable, binding decision. Not an execution and not an action request."""

    decision_id: str
    decision_case_id: str
    tenant_id: str
    decision_type: str
    outcome: DecisionOutcome
    authority_type: AuthorityType
    decided_by: str
    decided_at: datetime = Field(default_factory=utc_now)
    recommendation_refs: tuple[VersionedRef, ...] = ()
    assessment_refs: tuple[VersionedRef, ...] = ()
    policy_refs: tuple[VersionedRef, ...] = ()
    reason_codes: tuple[ReasonCode, ...] = ()
    override_record_id: Optional[str] = None
    effective_status: EffectiveStatus = EffectiveStatus.EFFECTIVE
    supersedes_decision_id: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "DecisionRecord":
        for req in ("decision_id", "decision_case_id", "tenant_id", "decided_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        # ``authority_type`` is an ``AuthorityType`` and therefore *structurally*
        # can never be an AI model — the enum has no AI member. Decision reasons
        # must be explicit.
        if not self.reason_codes:
            raise DomainValidationError("a decision must record explicit reason codes")
        return self
