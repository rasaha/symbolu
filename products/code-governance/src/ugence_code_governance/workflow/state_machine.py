"""Deterministic Workflow Service state machine (MVP 1A shadow path).

The Workflow Service coordinates stages but owns no governance authority. Every
transition is explicit and fails closed: a stage requested from a state that
does not permit it raises :class:`InvalidWorkflowTransitionError`.

For every state below, the ownership + entry condition + fail behavior is
documented in ``docs/CODE_GOVERNANCE_WORKFLOW_STATE_MACHINE.md`` and the
machine-readable ``docs/workflow_states.json``.
"""
from __future__ import annotations

from typing import Mapping, Tuple

from ..errors import InvalidWorkflowTransitionError
from ..models.enums import WorkflowState as S

#: Legal forward + failure transitions. Terminal states have no successors.
LEGAL_TRANSITIONS: Mapping[S, frozenset] = {
    S.RECEIVED: frozenset({S.IDENTITY_BOUND, S.ERROR}),
    S.IDENTITY_BOUND: frozenset({S.EVIDENCE_PENDING, S.STALE_ARTIFACT, S.ERROR}),
    S.EVIDENCE_PENDING: frozenset({
        S.EVIDENCE_PENDING, S.EVIDENCE_COMPLETE, S.CLAIMS_INCOMPLETE,
        S.STALE_ARTIFACT, S.ERROR}),
    S.EVIDENCE_COMPLETE: frozenset({S.CLAIMS_EVALUATED, S.CLAIMS_INCOMPLETE, S.ERROR}),
    S.CLAIMS_EVALUATED: frozenset({
        S.ASSERTIONS_EVALUATED, S.CLAIMS_INCOMPLETE, S.BLOCKED, S.ERROR}),
    S.ASSERTIONS_EVALUATED: frozenset({S.DECISION_PENDING, S.CHAIN_INCOMPLETE, S.ERROR}),
    S.DECISION_PENDING: frozenset({
        S.DECISION_RECORDED, S.DECISION_REQUIRED, S.BLOCKED, S.ESCALATED, S.ERROR}),
    S.DECISION_RECORDED: frozenset({S.CONTEXT_BOUND, S.ERROR}),
    S.CONTEXT_BOUND: frozenset({S.ACTION_PREPARED, S.ERROR}),
    S.ACTION_PREPARED: frozenset({S.ACTION_EVALUATED, S.ERROR}),
    S.ACTION_EVALUATED: frozenset({S.SHADOW_COMPLETE, S.CHAIN_INCOMPLETE, S.ERROR}),
    # terminal states
    S.SHADOW_COMPLETE: frozenset(),
    S.STALE_ARTIFACT: frozenset(),
    S.CLAIMS_INCOMPLETE: frozenset(),
    S.DECISION_REQUIRED: frozenset(),
    S.CHAIN_INCOMPLETE: frozenset(),
    S.BLOCKED: frozenset(),
    S.ESCALATED: frozenset(),
    S.ERROR: frozenset(),
}


def is_legal_transition(current: S, target: S) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, frozenset())


def assert_transition(current: S, target: S) -> None:
    """Fail closed unless ``current -> target`` is an allowed transition."""
    if not is_legal_transition(current, target):
        raise InvalidWorkflowTransitionError(
            f"illegal workflow transition {current.value} -> {target.value}")


__all__ = ["LEGAL_TRANSITIONS", "is_legal_transition", "assert_transition"]
