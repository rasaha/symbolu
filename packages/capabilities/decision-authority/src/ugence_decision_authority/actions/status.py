"""Deterministic vocabularies for governed action requests (Phase 4B).

These enums name states and outcomes only. Crucially, there is **no** ``EXECUTED``
or ``SUCCEEDED`` status: Phase 4B prepares and authorizes a proposed action, it
never executes it. Authorization is not execution.
"""

from __future__ import annotations

from enum import Enum


class ActionRequestStatus(str, Enum):
    """Lifecycle state of a governed action request. None of these means executed."""

    DRAFT = "DRAFT"
    READY_FOR_BINDING = "READY_FOR_BINDING"
    CER_BOUND = "CER_BOUND"
    READY_FOR_AUTHORIZATION = "READY_FOR_AUTHORIZATION"
    AUTHORIZATION_PENDING = "AUTHORIZATION_PENDING"
    AUTHORIZED = "AUTHORIZED"
    AUTHORIZED_WITH_CONSTRAINTS = "AUTHORIZED_WITH_CONSTRAINTS"
    DENIED = "DENIED"
    INDETERMINATE = "INDETERMINATE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


#: States after which a request snapshot is finalized and never mutated in place.
TERMINAL_REQUEST_STATUSES = frozenset({
    ActionRequestStatus.CANCELLED, ActionRequestStatus.SUPERSEDED,
})

#: A successful control-plane authorization did NOT execute anything.
AUTHORIZED_STATUSES = frozenset({
    ActionRequestStatus.AUTHORIZED,
    ActionRequestStatus.AUTHORIZED_WITH_CONSTRAINTS,
})

#: Outcomes that permit a fresh authorization attempt (retry) on the same request.
RETRYABLE_STATUSES = frozenset({
    ActionRequestStatus.INDETERMINATE, ActionRequestStatus.EXPIRED,
})


class AuthorizationOutcome(str, Enum):
    """What the control plane returned. Distinct outcomes are never conflated."""

    AUTHORIZED = "AUTHORIZED"
    AUTHORIZED_WITH_CONSTRAINTS = "AUTHORIZED_WITH_CONSTRAINTS"
    DENIED = "DENIED"
    INDETERMINATE = "INDETERMINATE"
    EXPIRED = "EXPIRED"


#: Deterministic mapping from a control-plane outcome to the resulting status.
OUTCOME_TO_STATUS: dict[AuthorizationOutcome, ActionRequestStatus] = {
    AuthorizationOutcome.AUTHORIZED: ActionRequestStatus.AUTHORIZED,
    AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS:
        ActionRequestStatus.AUTHORIZED_WITH_CONSTRAINTS,
    AuthorizationOutcome.DENIED: ActionRequestStatus.DENIED,
    AuthorizationOutcome.INDETERMINATE: ActionRequestStatus.INDETERMINATE,
    AuthorizationOutcome.EXPIRED: ActionRequestStatus.EXPIRED,
}


class ActionMappingStatus(str, Enum):
    """Publication lifecycle of an action mapping. Only PUBLISHED is usable."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"
