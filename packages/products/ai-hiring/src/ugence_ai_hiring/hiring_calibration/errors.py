"""Typed errors for the post-hire calibration plane."""

from __future__ import annotations

from ..errors import HiringError


class CalibrationError(HiringError):
    """Base for calibration-plane failures."""


class ReviewTimingError(CalibrationError):
    """A review was recorded outside its checkpoint window, or out of sequence."""


class DuplicateReviewError(CalibrationError):
    """A checkpoint review already exists for this case."""


class NotHiredError(CalibrationError):
    """Post-hire reviews require a case with a binding ADVANCE decision (an actual hire)."""


class CohortMismatchError(CalibrationError):
    """A cohort mixed cases from different role/policy/contract versions."""


class NoCalibrationSignalError(CalibrationError):
    """The report shows no systematic signal warranting a policy change."""


class CalibrationApprovalError(CalibrationError):
    """A recompile was attempted without an approved proposal, or versioning was invalid."""
