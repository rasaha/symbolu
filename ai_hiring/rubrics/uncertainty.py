"""Uncertainty contracts.

Defines how uncertainty must be *expressed* (independently of any score). A
future evaluator fills these in; this phase only fixes the vocabulary and the
per-capability contract. No values are computed here.
"""

from __future__ import annotations

from enum import Enum

from pydantic import model_validator

from ..domain.base import DomainModel
from ..errors import DomainValidationError


class UncertaintyLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class UncertaintyRule(DomainModel):
    """How uncertainty must be represented for a capability."""

    capability_id: str
    requires_uncertainty: bool = True
    default_level: UncertaintyLevel = UncertaintyLevel.UNKNOWN
    allowed_levels: tuple[UncertaintyLevel, ...] = tuple(UncertaintyLevel)

    @model_validator(mode="after")
    def _validate(self) -> "UncertaintyRule":
        if not self.allowed_levels:
            raise DomainValidationError("allowed_levels must be non-empty")
        if self.default_level not in self.allowed_levels:
            raise DomainValidationError("default_level must be in allowed_levels")
        return self
