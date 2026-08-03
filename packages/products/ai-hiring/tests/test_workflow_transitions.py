"""Workflow state-machine tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.domain.enums import ActorType, AuditEventType, WorkflowState
from ugence_ai_hiring.errors import (
    BindingTransitionRequiresDecisionError,
    BlockedEvaluationError,
    BoundaryViolationError,
    InvalidTransitionError,
)
from ugence_ai_hiring.policies import transition_policy as tp

from .conftest import make_evaluation

S = WorkflowState


def _init(platform, candidate_id="cand-1", role_id="role-1", corr="corr-1"):
    return platform.workflow_service.initialize(
        candidate_id, role_id, correlation_id=corr
    )


def _advance_to(platform, candidate_id, target_state, corr="corr-1"):
    """Drive the workflow up to (but not into binding states) a given state."""
    ws = platform.workflow_service
    path = {
        S.PLANNED: [],
        S.SOURCED: [S.SOURCED],
        S.ASSESSING: [S.SOURCED, S.ASSESSING],
        S.EVALUATED: [S.SOURCED, S.ASSESSING, S.EVALUATED],
        S.IN_REVIEW: [S.SOURCED, S.ASSESSING, S.EVALUATED, S.IN_REVIEW],
    }[target_state]
    ev = make_evaluation(candidate_id=candidate_id)
    for state in path:
        ws.transition(
            candidate_id, state, actor_type=ActorType.SYSTEM,
            evaluation=ev if state is S.IN_REVIEW else None,
            correlation_id=corr,
        )
    return ws.get(candidate_id)


# --- valid / invalid transitions ------------------------------------------
def test_valid_process_transitions_succeed(platform):
    _init(platform)
    wf = _advance_to(platform, "cand-1", S.EVALUATED)
    assert wf.state is S.EVALUATED
    assert wf.version == 4  # PLANNED -> SOURCED -> ASSESSING -> EVALUATED


def test_invalid_transition_is_rejected(platform):
    _init(platform)
    with pytest.raises(InvalidTransitionError):
        platform.workflow_service.transition(
            "cand-1", S.OFFERED, actor_type=ActorType.SYSTEM, correlation_id="c",
        )


def test_evaluated_to_in_review_is_system_triggerable(platform):
    _init(platform)
    _advance_to(platform, "cand-1", S.EVALUATED)
    ev = make_evaluation(candidate_id="cand-1")
    wf = platform.workflow_service.request_review(
        "cand-1", ev, correlation_id="c"
    )
    assert wf.state is S.IN_REVIEW


# --- binding transitions require a human decision -------------------------
def test_binding_transition_without_decision_is_rejected(platform):
    _init(platform)
    _advance_to(platform, "cand-1", S.IN_REVIEW)
    with pytest.raises(BindingTransitionRequiresDecisionError):
        platform.workflow_service.transition(
            "cand-1", S.REJECTED, actor_type=ActorType.HUMAN,
            actor_id="hm", correlation_id="c",
        )


def test_ai_cannot_drive_any_transition(platform):
    _init(platform)
    _advance_to(platform, "cand-1", S.IN_REVIEW)
    with pytest.raises(BoundaryViolationError):
        platform.workflow_service.transition(
            "cand-1", S.ADVANCED, actor_type=ActorType.AI,
            actor_id="ai-eval-engine", correlation_id="c",
        )


def test_system_cannot_drive_binding_state(platform):
    _init(platform)
    _advance_to(platform, "cand-1", S.IN_REVIEW)
    with pytest.raises(BoundaryViolationError):
        platform.workflow_service.transition(
            "cand-1", S.ADVANCED, actor_type=ActorType.SYSTEM, correlation_id="c",
        )


def test_blocked_evaluation_cannot_enter_review(platform):
    _init(platform)
    _advance_to(platform, "cand-1", S.EVALUATED)
    from ugence_ai_hiring.domain.enums import EvaluationStatus

    blocked = make_evaluation(candidate_id="cand-1", status=EvaluationStatus.REVIEW_BLOCKED)
    with pytest.raises(BlockedEvaluationError):
        platform.workflow_service.request_review("cand-1", blocked, correlation_id="c")


# --- audit on transitions --------------------------------------------------
def test_every_transition_emits_audit(platform):
    _init(platform)
    _advance_to(platform, "cand-1", S.EVALUATED)
    events = platform.audit_service.history("cand-1")
    types = [e.event_type for e in events]
    assert AuditEventType.WORKFLOW_INITIALIZED in types
    assert types.count(AuditEventType.WORKFLOW_TRANSITION) == 3


def test_denied_transition_is_audited(platform):
    _init(platform)
    _advance_to(platform, "cand-1", S.IN_REVIEW)
    with pytest.raises(BoundaryViolationError):
        platform.workflow_service.transition(
            "cand-1", S.ADVANCED, actor_type=ActorType.AI, correlation_id="c",
        )
    denials = [
        e for e in platform.audit_service.history("cand-1")
        if e.event_type is AuditEventType.SECURITY_VIOLATION
    ]
    assert denials, "an AI attempt at a binding transition must be audited"


# --- policy-level unit checks ---------------------------------------------
def test_disposition_to_state_mapping():
    from ugence_ai_hiring.domain.enums import Disposition

    assert tp.disposition_to_state(Disposition.ADVANCE) is S.ADVANCED
    assert tp.disposition_to_state(Disposition.HOLD) is S.HOLD
    assert tp.disposition_to_state(Disposition.REJECT) is S.REJECTED
