"""Application lifecycle, eligibility, and readiness (H1)."""

from __future__ import annotations

from .application import Application
from .eligibility import EligibilityResult, evaluate_eligibility
from .readiness import ReadinessResult, evaluate_readiness
from .status import (
    APPLICATION_ACTIVE_STATUSES,
    APPLICATION_ALLOWED_TRANSITIONS,
    APPLICATION_TERMINAL_STATUSES,
    ApplicationStatus,
    application_transition_allowed,
)

__all__ = [
    "Application",
    "ApplicationStatus",
    "APPLICATION_ACTIVE_STATUSES",
    "APPLICATION_ALLOWED_TRANSITIONS",
    "APPLICATION_TERMINAL_STATUSES",
    "application_transition_allowed",
    "EligibilityResult",
    "evaluate_eligibility",
    "ReadinessResult",
    "evaluate_readiness",
]
