"""Workflow transition policy.

All legal-transition knowledge lives here as data plus a few pure functions —
never as inline conditionals scattered through services. Services ask this
module whether a transition is allowed, who may perform it, and whether it
requires a human decision.
"""

from __future__ import annotations

from ..domain.enums import ActorType, Disposition, WorkflowState
from ..errors import (
    BoundaryViolationError,
    InvalidTransitionError,
)

S = WorkflowState

# Canonical legal transitions: current -> allowed next states.
ALLOWED_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    S.PLANNED: frozenset({S.SOURCED}),
    S.SOURCED: frozenset({S.ASSESSING}),
    S.ASSESSING: frozenset({S.EVALUATED}),
    S.EVALUATED: frozenset({S.IN_REVIEW}),
    S.IN_REVIEW: frozenset({S.ADVANCED, S.HOLD, S.REJECTED}),
    S.HOLD: frozenset({S.IN_REVIEW}),  # a hold may return to review
    S.ADVANCED: frozenset({S.OFFERED}),
    S.OFFERED: frozenset({S.ONBOARDED}),
    S.REJECTED: frozenset(),  # terminal
    S.ONBOARDED: frozenset(),  # terminal
}

# Targets that require a valid, recorded human Decision to enter.
HUMAN_DECISION_STATES: frozenset[WorkflowState] = frozenset(
    {S.ADVANCED, S.HOLD, S.REJECTED}
)

# Targets that require an authorized human action (but not a Decision record).
AUTHORIZED_HUMAN_STATES: frozenset[WorkflowState] = frozenset({S.OFFERED, S.ONBOARDED})

# Process targets a SYSTEM/integration principal may drive.
#   - EVALUATED -> IN_REVIEW is explicitly system-triggerable.
#   - OFFERED  -> ONBOARDED may be completed by an approved integration.
SYSTEM_ALLOWED_STATES: frozenset[WorkflowState] = frozenset(
    {S.SOURCED, S.ASSESSING, S.EVALUATED, S.IN_REVIEW, S.ONBOARDED}
)

_DISPOSITION_TO_STATE: dict[Disposition, WorkflowState] = {
    Disposition.ADVANCE: S.ADVANCED,
    Disposition.HOLD: S.HOLD,
    Disposition.REJECT: S.REJECTED,
}


def disposition_to_state(disposition: Disposition) -> WorkflowState:
    """Map a human disposition to its terminal review state."""
    return _DISPOSITION_TO_STATE[disposition]


def requires_human_decision(target: WorkflowState) -> bool:
    return target in HUMAN_DECISION_STATES


def is_binding_state(target: WorkflowState) -> bool:
    """Binding = requires a human decision or an authorized human action."""
    return target in HUMAN_DECISION_STATES or target in AUTHORIZED_HUMAN_STATES


def validate_transition(current: WorkflowState, target: WorkflowState) -> None:
    """Raise :class:`InvalidTransitionError` if ``current -> target`` is illegal."""
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            f"illegal transition {current.value} -> {target.value}; "
            f"allowed: {sorted(s.value for s in allowed) or 'none (terminal)'}"
        )


def authorize_actor_for_target(actor_type: ActorType, target: WorkflowState) -> None:
    """Raise :class:`BoundaryViolationError` if ``actor_type`` may not drive ``target``.

    * AI actors may never drive any transition.
    * SYSTEM actors may drive only process transitions in ``SYSTEM_ALLOWED_STATES``.
    * HUMAN actors may drive any otherwise-legal transition (a Decision is still
      required separately for ``HUMAN_DECISION_STATES``).
    """
    if actor_type is ActorType.AI:
        raise BoundaryViolationError(
            "an AI actor may not drive workflow transitions; AI output is advisory"
        )
    if actor_type is ActorType.SYSTEM and target not in SYSTEM_ALLOWED_STATES:
        raise BoundaryViolationError(
            f"a SYSTEM actor may not drive a transition to {target.value}; "
            "an authorized human action is required"
        )
