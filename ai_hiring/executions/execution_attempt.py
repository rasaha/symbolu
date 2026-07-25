"""The immutable ExecutionAttempt — one dispatch, its transport outcome only.

Each dispatch creates a new immutable attempt with a monotonic number. It records
the *transport* result (dispatched / acknowledged / failed / timed out / unknown)
and the external request id — never a business outcome. The request payload is
hashed, not indiscriminately logged. A timeout yields ``UNKNOWN`` transport, never
an automatic failure, and no retry happens without an explicit classification.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .status import RetryClassification, TransportStatus


class ExecutionAttempt(DomainModel):
    """An immutable record of one dispatch attempt (transport level only)."""

    execution_attempt_id: str
    execution_intent_id: str
    attempt_number: int
    adapter_id: str
    adapter_version: str
    request_payload_hash: str
    dispatched_at: datetime = Field(default_factory=utc_now)
    transport_status: TransportStatus = TransportStatus.NOT_DISPATCHED
    external_request_id: str = ""
    acknowledgement: str = ""
    completed_at: Optional[datetime] = None
    error_code: str = ""
    error_detail: str = ""
    retry_classification: RetryClassification = RetryClassification.NOT_RETRYABLE
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ExecutionAttempt":
        for req in ("execution_attempt_id", "execution_intent_id", "adapter_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if self.attempt_number < 1:
            raise DomainValidationError("attempt_number must be >= 1")
        return self
