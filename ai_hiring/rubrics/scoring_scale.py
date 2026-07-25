"""Scoring-scale definitions (no scores).

Defines the *shape* of scales a future evaluator must use — never any candidate
score. A rubric references a scale by ``scale_id``; standard scales are provided,
and a rubric may declare custom scales inline.
"""

from __future__ import annotations

from enum import Enum

from pydantic import model_validator

from ..domain.base import DomainModel
from ..errors import DomainValidationError


class ScaleType(str, Enum):
    ONE_TO_FIVE = "ONE_TO_FIVE"
    ZERO_TO_TEN = "ZERO_TO_TEN"
    PERCENTAGE = "PERCENTAGE"
    BINARY = "BINARY"
    PASS_FAIL = "PASS_FAIL"
    CUSTOM = "CUSTOM"


class ScoringScale(DomainModel):
    """Metadata describing a scale. Carries no score."""

    scale_id: str
    scale_type: ScaleType
    minimum: float
    maximum: float
    labels: tuple[str, ...] = ()
    precision: int = 0
    interpretation: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ScoringScale":
        if not self.scale_id.strip():
            raise DomainValidationError("scale_id is required")
        if self.maximum < self.minimum:
            raise DomainValidationError("maximum must be >= minimum")
        if self.precision < 0:
            raise DomainValidationError("precision must be >= 0")
        if self.scale_type in (ScaleType.BINARY, ScaleType.PASS_FAIL):
            if (self.minimum, self.maximum) != (0.0, 1.0):
                raise DomainValidationError(
                    f"{self.scale_type.value} scale must span [0, 1]")
        if self.scale_type is ScaleType.CUSTOM and not self.labels:
            raise DomainValidationError("a CUSTOM scale must declare labels")
        return self


SCALE_1_5 = ScoringScale(
    scale_id="scale.1_5", scale_type=ScaleType.ONE_TO_FIVE, minimum=1, maximum=5,
    labels=("1", "2", "3", "4", "5"), precision=0,
    interpretation="Higher is stronger evidence of the capability.")
SCALE_0_10 = ScoringScale(
    scale_id="scale.0_10", scale_type=ScaleType.ZERO_TO_TEN, minimum=0, maximum=10,
    precision=0, interpretation="Higher is stronger.")
SCALE_PERCENTAGE = ScoringScale(
    scale_id="scale.percentage", scale_type=ScaleType.PERCENTAGE, minimum=0,
    maximum=100, precision=1, interpretation="Percent of the bar met.")
SCALE_BINARY = ScoringScale(
    scale_id="scale.binary", scale_type=ScaleType.BINARY, minimum=0, maximum=1,
    labels=("0", "1"), interpretation="Absent (0) or present (1).")
SCALE_PASS_FAIL = ScoringScale(
    scale_id="scale.pass_fail", scale_type=ScaleType.PASS_FAIL, minimum=0, maximum=1,
    labels=("FAIL", "PASS"), interpretation="Meets the bar or not.")

STANDARD_SCALES: dict[str, ScoringScale] = {
    s.scale_id: s for s in (SCALE_1_5, SCALE_0_10, SCALE_PERCENTAGE, SCALE_BINARY,
                            SCALE_PASS_FAIL)
}


def is_standard_scale(scale_id: str) -> bool:
    return scale_id in STANDARD_SCALES
