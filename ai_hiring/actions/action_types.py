"""Hiring action taxonomy + decision→action eligibility (H4).

Explicit, bounded hiring-action types with a consequence classification, and the
mapping from a governed human decision outcome to the action types it may authorize.
Crucially, ``PREPARE_OFFER``/``PREPARE_REJECTION`` are *preparation* actions — they
are never ``issue offer``/``send rejection`` (those require separate authorization).
"""

from __future__ import annotations

from enum import Enum

from decision_governance.api.contracts import DecisionOutcome


class HiringActionType(str, Enum):
    ADVANCE_STAGE = "ADVANCE_STAGE"                       # internal workflow
    REQUEST_ADDITIONAL_ASSESSMENT = "REQUEST_ADDITIONAL_ASSESSMENT"
    SCHEDULE_INTERVIEW = "SCHEDULE_INTERVIEW"             # communication + calendar
    PLACE_ON_HOLD = "PLACE_ON_HOLD"                      # internal workflow
    CLOSE_WITHOUT_SELECTION = "CLOSE_WITHOUT_SELECTION"  # internal workflow
    PREPARE_OFFER = "PREPARE_OFFER"                      # prepares; NOT issue offer
    PREPARE_REJECTION = "PREPARE_REJECTION"             # prepares; NOT send rejection


class ActionConsequence(str, Enum):
    INTERNAL_WORKFLOW = "INTERNAL_WORKFLOW"
    COMMUNICATION = "COMMUNICATION"
    CONTRACTUAL = "CONTRACTUAL"
    IRREVERSIBLE = "IRREVERSIBLE"


ACTION_CONSEQUENCE: dict[HiringActionType, ActionConsequence] = {
    HiringActionType.ADVANCE_STAGE: ActionConsequence.INTERNAL_WORKFLOW,
    HiringActionType.REQUEST_ADDITIONAL_ASSESSMENT: ActionConsequence.INTERNAL_WORKFLOW,
    HiringActionType.SCHEDULE_INTERVIEW: ActionConsequence.COMMUNICATION,
    HiringActionType.PLACE_ON_HOLD: ActionConsequence.INTERNAL_WORKFLOW,
    HiringActionType.CLOSE_WITHOUT_SELECTION: ActionConsequence.INTERNAL_WORKFLOW,
    # Preparation is internal; the *contractual* consequential step (issue offer /
    # send rejection) is a separate, separately-authorized action (deferred).
    HiringActionType.PREPARE_OFFER: ActionConsequence.INTERNAL_WORKFLOW,
    HiringActionType.PREPARE_REJECTION: ActionConsequence.INTERNAL_WORKFLOW,
}

# Which action types a given human decision outcome may authorize.
DECISION_ALLOWED_ACTIONS: dict[DecisionOutcome, frozenset[HiringActionType]] = {
    DecisionOutcome.ADVANCE: frozenset({
        HiringActionType.ADVANCE_STAGE, HiringActionType.SCHEDULE_INTERVIEW,
        HiringActionType.PREPARE_OFFER, HiringActionType.REQUEST_ADDITIONAL_ASSESSMENT}),
    DecisionOutcome.HOLD: frozenset({
        HiringActionType.PLACE_ON_HOLD, HiringActionType.REQUEST_ADDITIONAL_ASSESSMENT}),
    DecisionOutcome.REJECT: frozenset({
        HiringActionType.CLOSE_WITHOUT_SELECTION, HiringActionType.PREPARE_REJECTION}),
    DecisionOutcome.DEFER: frozenset({
        HiringActionType.REQUEST_ADDITIONAL_ASSESSMENT, HiringActionType.PLACE_ON_HOLD}),
}


def action_allowed_for_decision(outcome: DecisionOutcome, action_type: HiringActionType) -> bool:
    return action_type in DECISION_ALLOWED_ACTIONS.get(outcome, frozenset())
