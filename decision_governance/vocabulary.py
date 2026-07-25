"""Domain-neutral governance vocabulary shared by kernel contracts.

``ReasonCode`` is the closed catalog of structured reasons a governance record may
cite (missing/stale/conflicting evidence, low confidence, not applicable, …).
``UncertaintyLevel``/``UncertaintyRule`` fix how uncertainty must be *expressed*
independently of any score. Both are domain-neutral: they name governance
concepts, not any particular subject domain.
"""

from __future__ import annotations

from enum import Enum

from pydantic import model_validator

from .base import DomainModel
from .errors import DomainValidationError


class ReasonCode(str, Enum):
    """Closed catalog of structured governance reason codes."""

    MISSING_REQUIRED_EVIDENCE = "MISSING_REQUIRED_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    PROHIBITED_EVIDENCE = "PROHIBITED_EVIDENCE"
    QUARANTINED_CONTENT = "QUARANTINED_CONTENT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReasonCodeSpec(DomainModel):
    """Documentation record for one reason code."""

    code: ReasonCode
    summary: str
    description: str
    category: str


REASON_CODE_CATALOG: dict[ReasonCode, ReasonCodeSpec] = {
    ReasonCode.MISSING_REQUIRED_EVIDENCE: ReasonCodeSpec(
        code=ReasonCode.MISSING_REQUIRED_EVIDENCE,
        summary="Required evidence was not provided",
        description="A capability's required evidence type is absent for the subject.",
        category="evidence"),
    ReasonCode.STALE_EVIDENCE: ReasonCodeSpec(
        code=ReasonCode.STALE_EVIDENCE,
        summary="Evidence is older than the allowed freshness window",
        description="Provided evidence exceeds the capability's freshness limit.",
        category="evidence"),
    ReasonCode.INSUFFICIENT_SAMPLE: ReasonCodeSpec(
        code=ReasonCode.INSUFFICIENT_SAMPLE,
        summary="Not enough evidence to meet the minimum count",
        description="Fewer admissible evidence items than the required minimum.",
        category="evidence"),
    ReasonCode.CONFLICTING_EVIDENCE: ReasonCodeSpec(
        code=ReasonCode.CONFLICTING_EVIDENCE,
        summary="Evidence sources contradict one another",
        description="Two or more sources make incompatible claims for a capability.",
        category="conflict"),
    ReasonCode.PROHIBITED_EVIDENCE: ReasonCodeSpec(
        code=ReasonCode.PROHIBITED_EVIDENCE,
        summary="A prohibited evidence type was supplied",
        description="Evidence of a type the contract explicitly forbids was present.",
        category="evidence"),
    ReasonCode.QUARANTINED_CONTENT: ReasonCodeSpec(
        code=ReasonCode.QUARANTINED_CONTENT,
        summary="Content was quarantined and withheld",
        description="Evidence content was quarantined (e.g. protected attributes).",
        category="governance"),
    ReasonCode.LOW_CONFIDENCE: ReasonCodeSpec(
        code=ReasonCode.LOW_CONFIDENCE,
        summary="Assessment confidence is low",
        description="A producer expressed low confidence for a capability.",
        category="uncertainty"),
    ReasonCode.NOT_APPLICABLE: ReasonCodeSpec(
        code=ReasonCode.NOT_APPLICABLE,
        summary="Capability is not applicable",
        description="The capability does not apply given the context.",
        category="applicability"),
}


def is_known_reason_code(value: str) -> bool:
    return value in ReasonCode._value2member_map_


def get_reason_code_spec(code: ReasonCode) -> ReasonCodeSpec:
    return REASON_CODE_CATALOG[code]


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
