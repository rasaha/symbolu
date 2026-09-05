"""The canonical approval state machine.

::

    REQUESTED -> PENDING -> GRANTED | REJECTED | CHANGES_REQUIRED | EXPIRED | WITHDRAWN
                                |
                             CONSUMED                         (exactly once)

    PENDING -> EXCEPTION_REQUESTED -> EXCEPTION_GRANTED | EXCEPTION_DENIED
                                            |
                                        CONSUMED             (exactly once)

``REQUESTED`` is the raised request before an eligible approver set is resolved;
``PENDING`` is awaiting decision. Every transition is **forward-only** — each one
strictly increases :data:`STATE_RANK` — so any arrival order converges and a
decision is never walked back.

``CHANGES_REQUIRED`` is terminal for *this* request. Re-review is a **new** request
bound to the new subject digest, recorded with ``supersedes``; a changed subject
never reuses a standing decision. ``EXPIRED`` is **derived at read time** from the
record's :class:`~ugence_governance_contracts.contracts.validity.Validity` and is
never written by a sweeper, so no clock has to run for a request to lapse.
"""

from __future__ import annotations

from enum import Enum

from .errors import IllegalTransitionError

__all__ = [
    "ApprovalState", "ReviewDecision", "LEGAL_TRANSITIONS", "STATE_RANK",
    "TERMINAL_STATES", "EXPIRABLE_STATES", "CONSUMABLE_STATES", "OPEN_STATES",
    "is_legal_transition", "require_transition", "state_for_decision",
]


class ApprovalState(str, Enum):
    """Where one approval request stands. Exactly one applies at one instant."""

    REQUESTED = "REQUESTED"
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    REJECTED = "REJECTED"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"
    EXCEPTION_REQUESTED = "EXCEPTION_REQUESTED"
    EXCEPTION_GRANTED = "EXCEPTION_GRANTED"
    EXCEPTION_DENIED = "EXCEPTION_DENIED"
    CONSUMED = "CONSUMED"


class ReviewDecision(str, Enum):
    """What an eligible approver may decide on a ``PENDING`` request."""

    GRANT = "GRANT"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


#: Forward-only ordering. Every legal transition strictly increases this rank.
STATE_RANK: dict[ApprovalState, int] = {
    ApprovalState.REQUESTED: 0,
    ApprovalState.PENDING: 1,
    ApprovalState.EXCEPTION_REQUESTED: 2,
    ApprovalState.GRANTED: 3,
    ApprovalState.EXCEPTION_GRANTED: 3,
    ApprovalState.REJECTED: 4,
    ApprovalState.CHANGES_REQUIRED: 4,
    ApprovalState.EXPIRED: 4,
    ApprovalState.WITHDRAWN: 4,
    ApprovalState.EXCEPTION_DENIED: 4,
    ApprovalState.CONSUMED: 5,
}

LEGAL_TRANSITIONS: dict[ApprovalState, frozenset[ApprovalState]] = {
    ApprovalState.REQUESTED: frozenset({
        ApprovalState.PENDING, ApprovalState.WITHDRAWN, ApprovalState.EXPIRED}),
    ApprovalState.PENDING: frozenset({
        ApprovalState.GRANTED, ApprovalState.REJECTED, ApprovalState.CHANGES_REQUIRED,
        ApprovalState.WITHDRAWN, ApprovalState.EXPIRED, ApprovalState.EXCEPTION_REQUESTED}),
    ApprovalState.EXCEPTION_REQUESTED: frozenset({
        ApprovalState.EXCEPTION_GRANTED, ApprovalState.EXCEPTION_DENIED,
        ApprovalState.WITHDRAWN, ApprovalState.EXPIRED}),
    ApprovalState.GRANTED: frozenset({ApprovalState.CONSUMED, ApprovalState.EXPIRED}),
    ApprovalState.EXCEPTION_GRANTED: frozenset({ApprovalState.CONSUMED, ApprovalState.EXPIRED}),
    ApprovalState.REJECTED: frozenset(),
    ApprovalState.CHANGES_REQUIRED: frozenset(),
    ApprovalState.EXPIRED: frozenset(),
    ApprovalState.WITHDRAWN: frozenset(),
    ApprovalState.EXCEPTION_DENIED: frozenset(),
    ApprovalState.CONSUMED: frozenset(),
}

#: Nothing follows these.
TERMINAL_STATES = frozenset(s for s, nxt in LEGAL_TRANSITIONS.items() if not nxt)

#: States whose ``Validity`` can lapse, so that ``EXPIRED`` is derived on read.
EXPIRABLE_STATES = frozenset({
    ApprovalState.REQUESTED, ApprovalState.PENDING, ApprovalState.EXCEPTION_REQUESTED,
    ApprovalState.GRANTED, ApprovalState.EXCEPTION_GRANTED})

#: The only states a consumer may consume from, and then exactly once.
CONSUMABLE_STATES = frozenset({ApprovalState.GRANTED, ApprovalState.EXCEPTION_GRANTED})

#: Still awaiting a decision.
OPEN_STATES = frozenset({
    ApprovalState.REQUESTED, ApprovalState.PENDING, ApprovalState.EXCEPTION_REQUESTED})

#: What each review decision writes.
_DECISION_STATE = {
    ReviewDecision.GRANT: ApprovalState.GRANTED,
    ReviewDecision.REJECT: ApprovalState.REJECTED,
    ReviewDecision.REQUEST_CHANGES: ApprovalState.CHANGES_REQUIRED,
}


def state_for_decision(decision: ReviewDecision) -> ApprovalState:
    if not isinstance(decision, ReviewDecision):
        raise IllegalTransitionError(f"{decision!r} is not a ReviewDecision")
    return _DECISION_STATE[decision]


def is_legal_transition(current: ApprovalState, target: ApprovalState) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, frozenset())


def require_transition(current: ApprovalState, target: ApprovalState) -> None:
    """Refuse an illegal or backward transition; never coerce one."""

    if not is_legal_transition(current, target):
        raise IllegalTransitionError(
            f"{current.value} -> {target.value} is not a legal approval transition")
    if STATE_RANK[target] <= STATE_RANK[current]:
        raise IllegalTransitionError(
            f"{current.value} -> {target.value} is not forward-only")
