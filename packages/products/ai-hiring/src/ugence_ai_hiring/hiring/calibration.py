"""Hiring calibration plane — canonical import surface.

Re-exports the 1/3/6/12-month post-hire calibration and policy-improvement loop
so consumers can depend on ``ugence_ai_hiring.hiring.calibration`` alongside the
other canonical hiring-domain surfaces. Implementation lives under
``ugence_ai_hiring.hiring_calibration``; object identity is preserved.

See ``docs/HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md`` §§10–12.
"""

from __future__ import annotations

from ugence_ai_hiring.hiring_calibration import (  # noqa: F401
    CHECKPOINT_WINDOW_DAYS,
    CalibrationApprovalError,
    CalibrationApprovalService,
    CalibrationDelta,
    CalibrationDirection,
    CalibrationError,
    CalibrationProvenance,
    CalibrationSinkOutcome,
    CalibrationSinkPort,
    CohortKey,
    CohortMismatchError,
    ConfidenceBand,
    DimensionReliability,
    DuplicateReviewError,
    HiringCalibrationReport,
    NoCalibrationSignalError,
    NotHiredError,
    PostHireReviewService,
    ProposalStatus,
    RecompileResult,
    ReviewTimingError,
    build_calibration_report,
    build_provenance,
    confidence_band,
    generate_calibration_proposal,
)

__all__ = [
    "PostHireReviewService",
    "CHECKPOINT_WINDOW_DAYS",
    "HiringCalibrationReport",
    "build_calibration_report",
    "CohortKey",
    "CalibrationDelta",
    "DimensionReliability",
    "generate_calibration_proposal",
    "CalibrationApprovalService",
    "RecompileResult",
    "CalibrationProvenance",
    "build_provenance",
    "ProposalStatus",
    "CalibrationDirection",
    "ConfidenceBand",
    "confidence_band",
    "CalibrationSinkPort",
    "CalibrationSinkOutcome",
    "CalibrationError",
    "ReviewTimingError",
    "DuplicateReviewError",
    "NotHiredError",
    "CohortMismatchError",
    "NoCalibrationSignalError",
    "CalibrationApprovalError",
]
