"""Outcome mappings between the hiring domain and the frozen DGM kernel (H3).

Maps the advisory H2 recommendation outcome to the kernel's neutral
``ProposedOutcome`` and the human hiring-decision intent to the kernel's neutral
``DecisionOutcome``. Kept in one place so the hiring→governance translation is
explicit and testable. Nothing here decides; it only translates vocabulary.
"""

from __future__ import annotations

from enum import Enum

from decision_governance.api.contracts import DecisionOutcome, ProposedOutcome

from ..recommendations.recommendation import RecommendationOutcome


class HiringDecisionIntent(str, Enum):
    """The human reviewer's decision intent (advisory→governed decision)."""

    ADVANCE = "ADVANCE"
    HOLD = "HOLD"
    REJECT = "REJECT"
    DEFER = "DEFER"


_REC_TO_PROPOSED = {
    RecommendationOutcome.RECOMMEND_ADVANCE: ProposedOutcome.ADVANCE,
    RecommendationOutcome.RECOMMEND_HOLD: ProposedOutcome.HOLD,
    RecommendationOutcome.RECOMMEND_DECLINE: ProposedOutcome.REJECT,
    RecommendationOutcome.INSUFFICIENT_EVIDENCE: ProposedOutcome.REQUEST_ADDITIONAL_EVIDENCE,
    RecommendationOutcome.NO_RECOMMENDATION: ProposedOutcome.NO_RECOMMENDATION,
}

_INTENT_TO_DECISION = {
    HiringDecisionIntent.ADVANCE: DecisionOutcome.ADVANCE,
    HiringDecisionIntent.HOLD: DecisionOutcome.HOLD,
    HiringDecisionIntent.REJECT: DecisionOutcome.REJECT,
    HiringDecisionIntent.DEFER: DecisionOutcome.DEFER,
}

# The kernel DecisionOutcome that a given ProposedOutcome would map to, for
# override detection (a human decision diverging from the AI proposal).
_PROPOSED_TO_DECISION = {
    ProposedOutcome.ADVANCE: DecisionOutcome.ADVANCE,
    ProposedOutcome.HOLD: DecisionOutcome.HOLD,
    ProposedOutcome.REJECT: DecisionOutcome.REJECT,
    ProposedOutcome.REQUEST_ADDITIONAL_EVIDENCE: DecisionOutcome.DEFER,
    ProposedOutcome.NO_RECOMMENDATION: DecisionOutcome.DEFER,
}


def proposed_outcome_for(rec_outcome: RecommendationOutcome) -> ProposedOutcome:
    return _REC_TO_PROPOSED[rec_outcome]


def decision_outcome_for(intent: HiringDecisionIntent) -> DecisionOutcome:
    return _INTENT_TO_DECISION[intent]


def is_override(*, proposed: ProposedOutcome, decision: DecisionOutcome) -> bool:
    """True when the human decision diverges from the AI-proposed outcome."""
    return _PROPOSED_TO_DECISION.get(proposed) != decision
