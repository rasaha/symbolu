"""Explicit extraction-outcome contract.

Success is never inferred merely because a parser returned a string. Every
extraction produces an immutable :class:`ExtractionResult` whose ``status`` and
``evaluation_eligible`` flag are set deliberately.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError


class ExtractionStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    SUCCEEDED_WITH_WARNINGS = "SUCCEEDED_WITH_WARNINGS"
    EMPTY = "EMPTY"
    UNSUPPORTED = "UNSUPPORTED"
    MALFORMED = "MALFORMED"
    ENCRYPTED = "ENCRYPTED"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


# The only statuses under which extracted content may become evaluation-eligible.
ELIGIBLE_STATUSES = frozenset(
    {ExtractionStatus.SUCCEEDED, ExtractionStatus.SUCCEEDED_WITH_WARNINGS}
)


class ExtractionResult(DomainModel):
    """An immutable record of one extraction attempt's outcome."""

    status: ExtractionStatus
    format: str
    extractor_name: str
    extractor_version: str = "0.1.0"
    characters_extracted: int = 0
    bytes_received: int = 0
    warnings: tuple[str, ...] = ()
    failure_code: Optional[str] = None
    failure_detail: str = ""
    evaluation_eligible: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "ExtractionResult":
        if self.characters_extracted < 0 or self.bytes_received < 0:
            raise DomainValidationError("byte/character counts must be >= 0")
        # eligibility can only be true for an eligible status with content
        if self.evaluation_eligible:
            if self.status not in ELIGIBLE_STATUSES:
                raise DomainValidationError(
                    "evaluation_eligible cannot be true for a non-success status"
                )
            if self.characters_extracted <= 0:
                raise DomainValidationError(
                    "evaluation_eligible cannot be true with no extracted content"
                )
        # a failure status must carry a failure code
        if self.status not in ELIGIBLE_STATUSES and self.failure_code is None:
            raise DomainValidationError(
                f"status {self.status.value} requires a failure_code"
            )
        return self
