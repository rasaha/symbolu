"""Hiring-action proposal lifecycle (H4).

Structural lifecycle from proposal through authorization, execution, and
reconciliation, with explicit compensation and terminal states. Authorization,
execution, and reconciliation are distinct stages — a proposal cannot skip from
DRAFT to EXECUTED.
"""

from __future__ import annotations

from enum import Enum


class ActionProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    READY_FOR_AUTHORIZATION = "READY_FOR_AUTHORIZATION"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTION_PENDING = "EXECUTION_PENDING"
    EXECUTED = "EXECUTED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    RECONCILED = "RECONCILED"
    COMPENSATION_REQUIRED = "COMPENSATION_REQUIRED"
    COMPENSATED = "COMPENSATED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


ACTION_TERMINAL_STATUSES = frozenset({
    ActionProposalStatus.RECONCILED, ActionProposalStatus.COMPENSATED,
    ActionProposalStatus.SUPERSEDED, ActionProposalStatus.CANCELLED,
    ActionProposalStatus.AUTHORIZATION_DENIED})

_T = ActionProposalStatus
ACTION_ALLOWED_TRANSITIONS: dict[ActionProposalStatus, frozenset[ActionProposalStatus]] = {
    _T.DRAFT: frozenset({_T.READY_FOR_AUTHORIZATION, _T.CANCELLED, _T.SUPERSEDED}),
    _T.READY_FOR_AUTHORIZATION: frozenset({_T.AUTHORIZED, _T.AUTHORIZATION_DENIED, _T.CANCELLED, _T.SUPERSEDED}),
    _T.AUTHORIZATION_DENIED: frozenset(),
    _T.AUTHORIZED: frozenset({_T.EXECUTION_PENDING, _T.CANCELLED, _T.SUPERSEDED}),
    _T.EXECUTION_PENDING: frozenset({_T.EXECUTED, _T.EXECUTION_FAILED}),
    _T.EXECUTED: frozenset({_T.RECONCILIATION_REQUIRED}),
    _T.EXECUTION_FAILED: frozenset({_T.EXECUTION_PENDING, _T.RECONCILIATION_REQUIRED, _T.CANCELLED}),
    _T.RECONCILIATION_REQUIRED: frozenset({_T.RECONCILED, _T.COMPENSATION_REQUIRED}),
    _T.RECONCILED: frozenset(),
    _T.COMPENSATION_REQUIRED: frozenset({_T.COMPENSATED}),
    _T.COMPENSATED: frozenset(),
    _T.SUPERSEDED: frozenset(),
    _T.CANCELLED: frozenset(),
}


def action_transition_allowed(src: ActionProposalStatus, dst: ActionProposalStatus) -> bool:
    return dst in ACTION_ALLOWED_TRANSITIONS.get(src, frozenset())
