"""Audit-log tests: append-only, ordering, hashing, correlation propagation."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.common import canonical_hash
from ugence_ai_hiring.domain.enums import ActorType, AuditEventType, Disposition, WorkflowState
from ugence_ai_hiring.errors import BoundaryViolationError

from .conftest import HUMAN_ID, PANEL, make_evaluation

S = WorkflowState


def _full_chain(platform, candidate_id="cand-1"):
    ev = make_evaluation(candidate_id=candidate_id)
    platform.evaluation_service.store(ev, actor_id="ai-eval-engine", correlation_id="corr-X")
    ws = platform.workflow_service
    ws.initialize(candidate_id, "role-1", correlation_id="corr-X")
    for state in (S.SOURCED, S.ASSESSING, S.EVALUATED):
        ws.transition(candidate_id, state, actor_type=ActorType.SYSTEM, correlation_id="corr-X")
    ws.request_review(candidate_id, ev, correlation_id="corr-X")
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        actor_id="ai-eval-engine",
        correlation_id="corr-X",
    )
    dec = platform.decision_service.create(
        recommendation_id=rec.recommendation_id,
        human_actor_id=HUMAN_ID,
        disposition=Disposition.ADVANCE,
        panel=PANEL,
        rationale_job_related="strong evidence across execution and reasoning",
    )
    return ev, rec, dec


def test_audit_is_append_only(platform):
    """The audit repository exposes no update or delete operation."""
    repo = platform.audit_repo
    assert hasattr(repo, "append")
    for forbidden in ("update", "delete", "remove", "clear", "pop"):
        assert not hasattr(repo, forbidden), f"append-only store must not expose {forbidden}"


def test_denied_actions_are_logged(platform):
    ev = make_evaluation()
    platform.evaluation_service.store(ev, correlation_id="c")
    platform.workflow_service.initialize("cand-1", "role-1", correlation_id="c")
    with pytest.raises(BoundaryViolationError):
        platform.workflow_service.transition(
            "cand-1", S.SOURCED, actor_type=ActorType.AI, correlation_id="c",
        )
    denials = [
        e for e in platform.audit_repo.all()
        if e.event_type in (AuditEventType.POLICY_DENIED, AuditEventType.SECURITY_VIOLATION)
    ]
    assert denials


def test_entity_history_is_ordered(platform):
    _full_chain(platform)
    history = platform.audit_service.history("cand-1")
    timestamps = [e.timestamp for e in history]
    assert timestamps == sorted(timestamps)


def test_payload_hash_is_deterministic():
    payload = {"b": 2, "a": 1, "nested": {"y": 2, "x": 1}}
    reordered = {"a": 1, "nested": {"x": 1, "y": 2}, "b": 2}
    assert canonical_hash(payload) == canonical_hash(reordered)
    assert canonical_hash(payload) != canonical_hash({"a": 1})


def test_correlation_id_propagates_across_the_chain(platform):
    ev, rec, dec = _full_chain(platform)

    rec_events = platform.audit_service.history(rec.recommendation_id)
    dec_events = platform.audit_service.history(dec.decision_id)
    wf_events = platform.audit_service.history("cand-1")

    assert rec_events, "recommendation creation must be audited"
    assert dec_events, "decision creation must be audited"

    # One correlation id ties recommendation -> decision -> transition together.
    rec_event = rec_events[-1]
    dec_event = dec_events[-1]
    transition_events = [
        e for e in wf_events if e.event_type is AuditEventType.WORKFLOW_TRANSITION
    ]
    assert rec_event.correlation_id == dec_event.correlation_id
    assert all(e.correlation_id == rec_event.correlation_id for e in transition_events)

    # Causation threads: decision caused by the recommendation event; the
    # binding transition caused by the decision event.
    assert dec_event.causation_id == rec_event.event_id
    advance_event = [e for e in transition_events if e.new_state == "ADVANCED"][-1]
    assert advance_event.causation_id == dec_event.event_id


def test_correlation_query_returns_whole_chain(platform):
    _full_chain(platform)
    chain = platform.audit_service.by_correlation("corr-X")
    types = {e.event_type for e in chain}
    assert AuditEventType.EVALUATION_CREATED in types
    assert AuditEventType.RECOMMENDATION_CREATED in types
    assert AuditEventType.DECISION_CREATED in types
    assert AuditEventType.WORKFLOW_TRANSITION in types
