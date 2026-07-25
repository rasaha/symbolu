"""Deterministic lifecycle transition rules for an execution.

The transition table is the single source of truth for structurally legal status
changes. It encodes the phase's central invariant: DISPATCHED and ACKNOWLEDGED are
*not* SUCCEEDED, and a timeout goes to OUTCOME_UNKNOWN rather than FAILED. Business
outcomes are reached only from a dispatched/acknowledged/unknown state, and only
via an *observed* result.
"""

from __future__ import annotations

from .status import ExecutionStatus as S

ALLOWED_TRANSITIONS: dict[S, frozenset[S]] = {
    S.INTENT_CREATED: frozenset({S.READY_FOR_DISPATCH, S.CANCELLED, S.SUPERSEDED}),
    S.READY_FOR_DISPATCH: frozenset({
        S.DISPATCH_PENDING, S.CANCELLED, S.SUPERSEDED}),
    S.DISPATCH_PENDING: frozenset({
        S.DISPATCHED, S.ACKNOWLEDGED, S.OUTCOME_UNKNOWN, S.FAILED}),
    # A dispatched/acknowledged/unknown execution reaches a business outcome ONLY
    # from an observed result — never automatically.
    S.DISPATCHED: frozenset({
        S.SUCCEEDED, S.FAILED, S.PARTIALLY_SUCCEEDED, S.REJECTED, S.OUTCOME_UNKNOWN,
        S.READY_FOR_DISPATCH, S.CANCELLED, S.SUPERSEDED}),
    S.ACKNOWLEDGED: frozenset({
        S.SUCCEEDED, S.FAILED, S.PARTIALLY_SUCCEEDED, S.REJECTED, S.OUTCOME_UNKNOWN,
        S.READY_FOR_DISPATCH, S.CANCELLED, S.SUPERSEDED}),
    S.OUTCOME_UNKNOWN: frozenset({
        S.SUCCEEDED, S.FAILED, S.PARTIALLY_SUCCEEDED, S.REJECTED, S.OUTCOME_UNKNOWN,
        S.READY_FOR_DISPATCH, S.MANUAL_REVIEW_REQUIRED, S.CANCELLED, S.SUPERSEDED}),
    # Business outcomes flow into reconciliation.
    S.SUCCEEDED: frozenset({S.RECONCILIATION_PENDING, S.SUPERSEDED}),
    S.FAILED: frozenset({
        S.RECONCILIATION_PENDING, S.READY_FOR_DISPATCH, S.SUPERSEDED}),
    S.PARTIALLY_SUCCEEDED: frozenset({S.RECONCILIATION_PENDING, S.SUPERSEDED}),
    S.REJECTED: frozenset({S.RECONCILIATION_PENDING, S.SUPERSEDED}),
    S.RECONCILIATION_PENDING: frozenset({
        S.RECONCILED, S.MISMATCHED, S.COMPENSATION_REQUIRED,
        S.MANUAL_REVIEW_REQUIRED}),
    S.MISMATCHED: frozenset({S.COMPENSATION_REQUIRED, S.MANUAL_REVIEW_REQUIRED}),
    S.MANUAL_REVIEW_REQUIRED: frozenset({
        S.RECONCILED, S.MISMATCHED, S.COMPENSATION_REQUIRED}),
    S.COMPENSATION_REQUIRED: frozenset({S.RECONCILED, S.MANUAL_REVIEW_REQUIRED}),
    S.RECONCILED: frozenset(),
    S.CANCELLED: frozenset(),
    S.SUPERSEDED: frozenset(),
}


def is_legal_transition(current: S, target: S) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())
