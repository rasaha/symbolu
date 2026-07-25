"""Deterministic lifecycle transition rules for a decision case.

The transition table is the single source of truth for *which* status changes are
structurally legal. Whether a legal transition is also *permitted right now*
(authority present, required reviews complete, no blocking assessment) is decided
by ``CaseValidationService`` — this module only encodes shape.

A key invariant: ``DECIDED`` is a terminal decision state, not an execution state.
There is no transition to any "executed" status because Phase 4A does not execute.
"""

from __future__ import annotations

from .status import CaseStatus

#: Legal successor states for each case status.
ALLOWED_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.CREATED: frozenset({
        CaseStatus.EVIDENCE_ASSEMBLY, CaseStatus.ASSESSMENT_IN_PROGRESS,
        CaseStatus.CANCELLED}),
    CaseStatus.EVIDENCE_ASSEMBLY: frozenset({
        CaseStatus.ASSESSMENT_IN_PROGRESS, CaseStatus.READY_FOR_RECOMMENDATION,
        CaseStatus.CANCELLED}),
    CaseStatus.ASSESSMENT_IN_PROGRESS: frozenset({
        CaseStatus.READY_FOR_RECOMMENDATION, CaseStatus.READY_FOR_DECISION,
        CaseStatus.CANCELLED}),
    CaseStatus.READY_FOR_RECOMMENDATION: frozenset({
        CaseStatus.RECOMMENDATION_AVAILABLE, CaseStatus.UNDER_REVIEW,
        CaseStatus.READY_FOR_DECISION, CaseStatus.CANCELLED}),
    CaseStatus.RECOMMENDATION_AVAILABLE: frozenset({
        CaseStatus.RECOMMENDATION_AVAILABLE, CaseStatus.UNDER_REVIEW,
        CaseStatus.READY_FOR_DECISION, CaseStatus.CANCELLED}),
    CaseStatus.UNDER_REVIEW: frozenset({
        CaseStatus.UNDER_REVIEW, CaseStatus.RECOMMENDATION_AVAILABLE,
        CaseStatus.READY_FOR_DECISION, CaseStatus.CANCELLED}),
    CaseStatus.READY_FOR_DECISION: frozenset({
        CaseStatus.UNDER_REVIEW, CaseStatus.DECIDED, CaseStatus.CANCELLED}),
    CaseStatus.DECIDED: frozenset({
        CaseStatus.SUPERSEDED, CaseStatus.CLOSED}),
    CaseStatus.SUPERSEDED: frozenset({
        CaseStatus.READY_FOR_DECISION, CaseStatus.CLOSED}),
    CaseStatus.CANCELLED: frozenset({CaseStatus.CLOSED}),
    CaseStatus.CLOSED: frozenset(),
}


def is_legal_transition(current: CaseStatus, target: CaseStatus) -> bool:
    """True if moving ``current`` → ``target`` is structurally allowed."""
    if current == target:
        # Idempotent re-entry is allowed only where explicitly listed above
        # (e.g. RECOMMENDATION_AVAILABLE, UNDER_REVIEW accumulate records).
        return target in ALLOWED_TRANSITIONS.get(current, frozenset())
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())
