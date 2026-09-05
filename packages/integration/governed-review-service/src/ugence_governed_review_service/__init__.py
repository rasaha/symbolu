"""Ugence Governed Review Service — lists the review queue, renders a run, and records
a human's decision, then re-arms the instance it binds to.

    THIS SERVICE RECORDS A DECISION A HUMAN ALREADY MADE.
    IT NEVER APPROVES, AUTHENTICATES, MINTS AUTHORITY, CLEARS OR EXECUTES.

GAS-7 step HR-C under owner rulings HR-1 to HR-5
(``docs/architecture/ADR_UGENCE_HUMAN_REVIEW_DURABLE_RESUME_SCOPING.md``). It composes
``ugence_governed_review`` (the binding), the approval ledger, the authority directory's
eligibility adapter and the DBOS adapter. Maturity ``REFERENCE_GRADE_SHADOW_ONLY``:
the approver on every decision is a presented reference, not a proven identity.
"""

from __future__ import annotations

from .errors import ClockDisciplineError, ContractViolation, GovernedReviewServiceError
from .http import ROUTES, build_app, decision_view, queue_entry_view
from .reader import DbosRunReader, RunReader, StaticRunReader
from .service import (
    SIGNAL_NAME,
    DecisionOutcome,
    DecisionResult,
    QueueEntry,
    ReviewService,
    instance_of,
)
from .version import (
    CONTRACT_VERSION,
    ENFORCEMENT_ENABLED,
    IDENTITY_PROOF,
    MATURITY,
    __version__,
)

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "IDENTITY_PROOF", "ENFORCEMENT_ENABLED",
    "ReviewService", "DecisionOutcome", "DecisionResult", "QueueEntry", "SIGNAL_NAME",
    "instance_of",
    "RunReader", "DbosRunReader", "StaticRunReader",
    "ROUTES", "build_app", "queue_entry_view", "decision_view",
    "GovernedReviewServiceError", "ContractViolation", "ClockDisciplineError",
]
