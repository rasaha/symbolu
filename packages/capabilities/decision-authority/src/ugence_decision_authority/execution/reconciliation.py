"""The immutable ReconciliationResult — authorized intent vs observed effect.

Reconciliation compares what was authorized (action type, target, subject,
parameters, constraints, quantity/amount) against what was observed (business
outcome, observed parameters, finality, duplicates). It produces an immutable
result and **never mutates the source records**. Unknown finality is
``INDETERMINATE``, not success; duplicates or material mismatches escalate.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import canonical_hash, utc_now
from ..base import DomainModel
from ..errors import DomainValidationError
from .status import BusinessOutcome, ReconciliationStatus


class ReconciliationResult(DomainModel):
    """An immutable comparison of authorized intent against observed execution."""

    reconciliation_id: str
    execution_intent_id: str
    tenant_id: str
    execution_record_ids: tuple[str, ...]
    expected_action_type: str
    expected_target_system: str
    expected_parameters: dict[str, str] = Field(default_factory=dict)
    observed_outcome: BusinessOutcome
    observed_parameters: dict[str, str] = Field(default_factory=dict)
    status: ReconciliationStatus
    mismatch_codes: tuple[str, ...] = ()
    missing_observations: tuple[str, ...] = ()
    excess_observations: tuple[str, ...] = ()
    compensation_required: bool = False
    reconciled_by: str = ""
    reconciled_at: datetime = Field(default_factory=utc_now)
    notes: str = ""
    content_hash: str = ""
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ReconciliationResult":
        for req in ("reconciliation_id", "execution_intent_id", "tenant_id",
                    "expected_action_type"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        return self

    def compute_hash(self) -> str:
        return canonical_hash({
            "execution_intent_id": self.execution_intent_id,
            "execution_record_ids": sorted(self.execution_record_ids),
            "expected_action_type": self.expected_action_type,
            "expected_target_system": self.expected_target_system,
            "expected_parameters": dict(self.expected_parameters),
            "observed_outcome": self.observed_outcome.value,
            "observed_parameters": dict(self.observed_parameters),
            "status": self.status.value,
            "mismatch_codes": sorted(self.mismatch_codes),
        })
