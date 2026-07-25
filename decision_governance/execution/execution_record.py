"""The immutable ExecutionRecord — observed external-world state, never inferred.

An execution record represents what the external system *actually did*, observed
from a dispatch acknowledgement's later status, a status query, or an external
callback. Acknowledgement and success are distinct: a record is created only from
an observed business outcome, never from dispatch alone. Partial success preserves
completed and incomplete portions; duplicates are detected without collapsing
history; multiple observations may coexist. Records are immutable and append-only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import canonical_hash, utc_now
from ..base import DomainModel
from ..errors import DomainValidationError
from .status import BusinessOutcome, Finality, OutcomeSource


class ExecutionRecord(DomainModel):
    """An immutable record of one observed external outcome for an intent."""

    execution_record_id: str
    execution_intent_id: str
    execution_attempt_id: str
    tenant_id: str
    external_system: str
    external_request_id: str
    external_result_id: str = ""
    business_outcome: BusinessOutcome
    observed_parameters: dict[str, str] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=utc_now)
    source: OutcomeSource = OutcomeSource.ADAPTER_STATUS_QUERY
    evidence_refs: tuple[str, ...] = ()
    finality: Finality = Finality.UNKNOWN
    reason_codes: tuple[str, ...] = ()
    content_hash: str = ""
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ExecutionRecord":
        for req in ("execution_record_id", "execution_intent_id",
                    "execution_attempt_id", "tenant_id", "external_system",
                    "external_request_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        return self

    def compute_hash(self) -> str:
        return canonical_hash({
            "execution_intent_id": self.execution_intent_id,
            "execution_attempt_id": self.execution_attempt_id,
            "external_request_id": self.external_request_id,
            "external_result_id": self.external_result_id,
            "business_outcome": self.business_outcome.value,
            "observed_parameters": dict(self.observed_parameters),
            "finality": self.finality.value,
            "source": self.source.value,
        })
