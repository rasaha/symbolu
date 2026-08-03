"""Typed validation results and deterministic scale-value validation.

Validation confirms an observation *conforms to the published contract*; it never
computes or interprets the observation value. Value validation is pure membership
checking against the immutable scale definition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..rubrics.scoring_scale import ScaleType, ScoringScale


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    field: str = ""
    criterion_id: str = ""
    capability_id: str = ""
    evidence_id: str = ""
    blocking: bool = True


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    warnings: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    blocking_conditions: tuple[str, ...] = field(default_factory=tuple)
    referenced_contract_versions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def error_codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.errors)


def _is_int_token(value: str) -> Optional[int]:
    try:
        # reject floats and non-canonical forms deterministically
        if value.strip() != value or "." in value or "e" in value.lower():
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def _is_number_token(value: str) -> Optional[float]:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def validate_value_against_scale(value: str, scale: ScoringScale) -> Optional[str]:
    """Return an issue code if ``value`` is not a member of ``scale``, else None.

    Deterministic membership only — no computation of the value.
    """
    st = scale.scale_type

    if st in (ScaleType.ONE_TO_FIVE, ScaleType.ZERO_TO_TEN):
        n = _is_int_token(value)
        if n is None:
            return "OBSERVATION_VALUE_NOT_INTEGER"
        if not (int(scale.minimum) <= n <= int(scale.maximum)):
            return "OBSERVATION_VALUE_OUT_OF_RANGE"
        return None

    if st is ScaleType.PERCENTAGE:
        n = _is_number_token(value)
        if n is None:
            return "OBSERVATION_VALUE_NOT_NUMERIC"
        if not (scale.minimum <= n <= scale.maximum):
            return "OBSERVATION_VALUE_OUT_OF_RANGE"
        return None

    if st is ScaleType.BINARY:
        if value.lower() in {"0", "1", "true", "false"}:
            return None
        return "OBSERVATION_VALUE_NOT_BINARY"

    if st is ScaleType.PASS_FAIL:
        if value.upper() in {"PASS", "FAIL"}:
            return None
        return "OBSERVATION_VALUE_NOT_PASS_FAIL"

    if st is ScaleType.CUSTOM:
        # membership against the immutable custom labels only
        if value in scale.labels:
            return None
        return "OBSERVATION_VALUE_NOT_IN_CUSTOM_SCALE"

    return "OBSERVATION_SCALE_UNKNOWN"