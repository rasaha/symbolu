"""Procurement recommendation & decision vocabulary → kernel outcomes.

Procurement speaks in approve/reject/escalate terms; the kernel speaks in the
neutral ``ProposedOutcome`` / ``DecisionOutcome`` vocabulary. These enums are the
procurement-domain vocabulary, and the maps below translate them onto the
existing kernel outcomes — the kernel ``RecommendationRecord`` and
``DecisionRecord`` remain authoritative. No autonomous approval exists here: a
recommendation is only ever advisory; a decision is always an authorized actor's.
"""

from __future__ import annotations

from enum import Enum

from decision_governance.decisions import DecisionOutcome, ProposedOutcome


class PurchaseRecommendation(str, Enum):
    """Advisory recommendation on a purchase request."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class PurchaseApproval(str, Enum):
    """An authorized actor's binding decision on a purchase request."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"


# Procurement recommendation -> neutral kernel proposed outcome.
RECOMMENDATION_TO_PROPOSED: dict[PurchaseRecommendation, ProposedOutcome] = {
    PurchaseRecommendation.APPROVE: ProposedOutcome.ADVANCE,
    PurchaseRecommendation.REJECT: ProposedOutcome.REJECT,
    PurchaseRecommendation.ESCALATE: ProposedOutcome.HOLD,
    PurchaseRecommendation.NEEDS_REVIEW: ProposedOutcome.REQUEST_ADDITIONAL_EVIDENCE,
}

# Procurement decision -> neutral kernel decision outcome.
APPROVAL_TO_DECISION: dict[PurchaseApproval, DecisionOutcome] = {
    PurchaseApproval.APPROVED: DecisionOutcome.ADVANCE,
    PurchaseApproval.APPROVED_WITH_CONDITIONS: DecisionOutcome.ADVANCE,
    PurchaseApproval.REJECTED: DecisionOutcome.REJECT,
}


def proposed_outcome_for(recommendation: PurchaseRecommendation) -> ProposedOutcome:
    return RECOMMENDATION_TO_PROPOSED[recommendation]


def decision_outcome_for(approval: PurchaseApproval) -> DecisionOutcome:
    return APPROVAL_TO_DECISION[approval]
