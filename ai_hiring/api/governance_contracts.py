"""API-facing contracts for H3 governance integration.

Request DTOs for opening a governance case, assigning/completing review, recording
a human decision, rejecting a recommendation, and superseding. Response views reuse
the governance view models. No kernel internals are exposed.
"""

from __future__ import annotations

from ..domain.base import DomainModel
from ..governance.outcomes import HiringDecisionIntent


class OpenGovernanceCaseRequest(DomainModel):
    recommendation_id: str
    correlation_id: str = ""


class AssignReviewRequest(DomainModel):
    recommendation_id: str
    assigned_to: str
    task_type: str = "RECOMMENDATION_REVIEW"
    required_role: str = ""


class CompleteReviewRequest(DomainModel):
    recommendation_id: str
    task_id: str


class RecordDecisionRequest(DomainModel):
    recommendation_id: str
    intent: HiringDecisionIntent
    reason_codes: tuple[str, ...] = ()
    override_notes: str = ""


class RejectRecommendationRequest(DomainModel):
    recommendation_id: str
    reason: str = ""


class GovernanceCaseSummaryView(DomainModel):
    recommendation_id: str
    application_id: str
    decision_case_id: str
    kernel_recommendation_id: str
    binding_status: str
    decision_id: str = ""
    overridden: bool = False
