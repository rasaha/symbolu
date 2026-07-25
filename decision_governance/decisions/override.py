"""OverrideRecord — preserves dissent when a decision departs from advice/default.

An override is created when a decision differs *materially* from a recommendation
or a policy default. It preserves the original proposal and the final outcome side
by side, with the authorizing actor, structured reasons, and the policy that
permits the override. It never rewrites the recommendation — the original record
stays intact and visible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..base import DomainModel
from ..errors import DomainValidationError
from ..vocabulary import ReasonCode
from .status import DecisionOutcome, ProposedOutcome
from .subject import VersionedRef


class OverrideRecord(DomainModel):
    """An immutable record that a decision departed from advice or a default."""

    override_id: str
    decision_case_id: str
    tenant_id: str
    final_outcome: DecisionOutcome
    authorized_by: str
    reason_codes: tuple[ReasonCode, ...]
    original_recommendation_id: Optional[str] = None
    original_proposed_outcome: Optional[ProposedOutcome] = None
    policy_default_outcome: Optional[DecisionOutcome] = None
    permitting_policy_ref: Optional[VersionedRef] = None
    notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "OverrideRecord":
        for req in ("override_id", "decision_case_id", "tenant_id", "authorized_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if not self.reason_codes:
            raise DomainValidationError("an override must record explicit reason codes")
        if (self.original_recommendation_id is None
                and self.policy_default_outcome is None):
            raise DomainValidationError(
                "an override must reference the original recommendation or a "
                "policy default it departs from")
        return self
