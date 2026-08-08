"""Vocabulary for the post-hire calibration plane."""

from __future__ import annotations

from enum import Enum


class ProposalStatus(str, Enum):
    """Lifecycle of a calibration proposal. Recompile is allowed only from APPROVED."""

    PROPOSED = "PROPOSED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RECOMPILED = "RECOMPILED"


class CalibrationDirection(str, Enum):
    """Direction of calibration error (observed vs predicted)."""

    ACCURATE = "ACCURATE"
    OVERPREDICTION = "OVERPREDICTION"   # predicted higher than observed
    UNDERPREDICTION = "UNDERPREDICTION"  # predicted lower than observed
    INSUFFICIENT = "INSUFFICIENT"        # not enough predicted/observed to judge


class ConfidenceBand(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


def confidence_band(confidence: float) -> ConfidenceBand:
    if confidence < 0.5:
        return ConfidenceBand.LOW
    if confidence < 0.8:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.HIGH


# A |delta| at or below this is treated as an accurate prediction.
ACCURACY_TOLERANCE = 5.0
