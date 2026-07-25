"""Deterministic lifecycle transition rules for a governed action request.

The transition table is the single source of truth for structurally legal status
changes. There is **no transition to any executed/succeeded state** — Phase 4B
stops at an authorization outcome. Authorized does not mean executed.
"""

from __future__ import annotations

from .status import ActionRequestStatus as S

ALLOWED_TRANSITIONS: dict[S, frozenset[S]] = {
    S.DRAFT: frozenset({S.READY_FOR_BINDING, S.CANCELLED, S.SUPERSEDED}),
    S.READY_FOR_BINDING: frozenset({S.CER_BOUND, S.DRAFT, S.CANCELLED, S.SUPERSEDED}),
    S.CER_BOUND: frozenset({S.READY_FOR_AUTHORIZATION, S.CANCELLED, S.SUPERSEDED}),
    S.READY_FOR_AUTHORIZATION: frozenset({
        S.AUTHORIZATION_PENDING, S.CANCELLED, S.SUPERSEDED}),
    S.AUTHORIZATION_PENDING: frozenset({
        S.AUTHORIZED, S.AUTHORIZED_WITH_CONSTRAINTS, S.DENIED, S.INDETERMINATE,
        S.EXPIRED, S.CANCELLED, S.SUPERSEDED}),
    # A granted authorization is terminal for Phase 4B — it never becomes "executed".
    S.AUTHORIZED: frozenset({S.SUPERSEDED, S.CANCELLED}),
    S.AUTHORIZED_WITH_CONSTRAINTS: frozenset({S.SUPERSEDED, S.CANCELLED}),
    S.DENIED: frozenset({S.SUPERSEDED, S.CANCELLED}),
    # Indeterminate / expired permit a fresh authorization attempt on the request.
    S.INDETERMINATE: frozenset({
        S.READY_FOR_AUTHORIZATION, S.SUPERSEDED, S.CANCELLED}),
    S.EXPIRED: frozenset({S.READY_FOR_AUTHORIZATION, S.SUPERSEDED, S.CANCELLED}),
    S.CANCELLED: frozenset(),
    S.SUPERSEDED: frozenset(),
}


def is_legal_transition(current: S, target: S) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())
