"""Hiring calibration plane — the 1/3/6/12-month closed-loop policy-improvement path.

Records structured, job-related post-hire reviews; compares at-hire *predicted*
compatibility against *observed* outcomes to compute *calibration error*;
aggregates cohorts into a :class:`HiringCalibrationReport`; and emits a governed
:class:`CalibrationProposal`. An approved proposal is routed back through the
Step-1 Hiring Policy Compiler, producing a NEW versioned HiringWorkflowIR and
Hiring Decision Contract — the active contract is never mutated.

Invariants: post-hire outcomes never change the historical decision; calibration
proposes future policy changes only; no hidden-weight retraining; no automatic
policy mutation; every change is explicitly versioned and approved; the Overall
Fit Index stays descriptive/analytics-only; shared services stay behind ports.
"""

from __future__ import annotations

from .enums import (
    ACCURACY_TOLERANCE,
    CalibrationDirection,
    ConfidenceBand,
    ProposalStatus,
    confidence_band,
)
from .errors import (
    CalibrationApprovalError,
    CalibrationError,
    CohortMismatchError,
    DuplicateReviewError,
    NoCalibrationSignalError,
    NotHiredError,
    ReviewTimingError,
)
from .ports import CalibrationSinkOutcome, CalibrationSinkPort
from .proposal import (
    CalibrationApprovalService,
    CalibrationProvenance,
    RecompileResult,
    build_provenance,
    generate_calibration_proposal,
)
from .report import (
    CalibrationDelta,
    CohortKey,
    DimensionReliability,
    HiringCalibrationReport,
    build_calibration_report,
)
from .review_service import CHECKPOINT_WINDOW_DAYS, PostHireReviewService

__all__ = [
    # review service
    "PostHireReviewService",
    "CHECKPOINT_WINDOW_DAYS",
    # report
    "HiringCalibrationReport",
    "build_calibration_report",
    "CohortKey",
    "CalibrationDelta",
    "DimensionReliability",
    # proposal + recompile
    "generate_calibration_proposal",
    "CalibrationApprovalService",
    "RecompileResult",
    "CalibrationProvenance",
    "build_provenance",
    # enums
    "ProposalStatus",
    "CalibrationDirection",
    "ConfidenceBand",
    "confidence_band",
    "ACCURACY_TOLERANCE",
    # ports
    "CalibrationSinkPort",
    "CalibrationSinkOutcome",
    # errors
    "CalibrationError",
    "ReviewTimingError",
    "DuplicateReviewError",
    "NotHiredError",
    "CohortMismatchError",
    "NoCalibrationSignalError",
    "CalibrationApprovalError",
]
