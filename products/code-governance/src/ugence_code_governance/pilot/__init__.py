"""Bounded shadow-pilot for Code Governance (MVP 1D).

A pilot evaluates real or representative enterprise signals in read-only mode,
explains when human intervention is needed, measures decision quality, survives
source failures safely, and produces an auditable, offline-verifiable report — all
with execution ``DISABLED``. A successful pilot does NOT enable enforcement.
"""
from __future__ import annotations

from .config import (
    PilotStatus,
    PilotThresholds,
    RetentionCategory,
    ShadowPilotConfig,
)
from .metrics import (
    ShadowPilotMetrics,
    calculate_pilot_metrics,
    evaluate_pilot_status,
)
from .records import (
    FeedbackAgreement,
    ObservedResolution,
    PilotReviewerFeedback,
    ShadowPilotEvaluationRecord,
)
from .report import (
    PilotReportVerification,
    REPORT_VERSION,
    export_shadow_pilot_report,
    verify_shadow_pilot_report,
)
from .runner import PilotBoundaryError, ShadowPilotRunner

__all__ = [
    "ShadowPilotConfig", "PilotThresholds", "PilotStatus", "RetentionCategory",
    "ShadowPilotEvaluationRecord", "PilotReviewerFeedback",
    "FeedbackAgreement", "ObservedResolution",
    "ShadowPilotMetrics", "calculate_pilot_metrics", "evaluate_pilot_status",
    "REPORT_VERSION", "PilotReportVerification",
    "export_shadow_pilot_report", "verify_shadow_pilot_report",
    "ShadowPilotRunner", "PilotBoundaryError",
]
