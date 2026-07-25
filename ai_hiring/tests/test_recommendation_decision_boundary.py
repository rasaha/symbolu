"""The core AI/human boundary: recommendations vs decisions."""

from __future__ import annotations

import pytest

from ai_hiring.domain.enums import ActorType, Disposition, EvaluationStatus, WorkflowState
from ai_hiring.domain.decision import Override
from ai_hiring.domain.evaluation import Limitation
from ai_hiring.errors import (
    BlockedEvaluationError,
    BoundaryViolationError,
    DomainValidationError,
    OverrideRequiredError,
    RecordNotFoundError,
    UnauthenticatedActorError,
)

from .conftest import HUMAN_ID, PANEL, make_evaluation

S = WorkflowState


def _prepare_in_review(platform, *, status=EvaluationStatus.EVALUATED, candidate_id="cand-1"):
    """Store an evaluation and drive the workflow to IN_REVIEW."""
    ev = make_evaluation(candidate_id=candidate_id, status=status)
    platform.evaluation_service.store(ev, actor_id="ai-eval-engine", correlation_id="c")
    ws = platform.workflow_service
    ws.initialize(candidate_id, "role-1", correlation_id="c")
    for state in (S.SOURCED, S.ASSESSING, S.EVALUATED):
        ws.transition(candidate_id, state, actor_type=ActorType.SYSTEM, correlation_id="c")
    if status is EvaluationStatus.EVALUATED:
        ws.request_review(candidate_id, ev, correlation_id="c")
    return ev


# --- recommendations -------------------------------------------------------
def test_ai_can_create_recommendation(platform):
    ev = make_evaluation()
    platform.evaluation_service.store(ev, correlation_id="c")
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        actor_id="ai-eval-engine",
        correlation_id="c",
    )
    assert rec.actor_type is ActorType.AI
    assert rec.suggested_disposition is Disposition.ADVANCE


def test_recommendation_for_missing_evaluation_fails(platform):
    with pytest.raises(RecordNotFoundError):
        platform.recommendation_service.create(
            evaluation_id="does-not-exist",
            suggested_disposition=Disposition.ADVANCE,
            correlation_id="c",
        )


def test_recommendation_does_not_transition_workflow(platform):
    ev = _prepare_in_review(platform)
    before = platform.workflow_service.get("cand-1").state
    platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        correlation_id="c",
    )
    after = platform.workflow_service.get("cand-1").state
    assert before is after is S.IN_REVIEW


def test_recommendation_preserves_caveats(platform):
    ev = make_evaluation()
    platform.evaluation_service.store(ev, correlation_id="c")
    caveats = (Limitation(description="video transcript low quality"),)
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.HOLD,
        caveats=caveats,
        correlation_id="c",
    )
    assert rec.caveats == caveats


# --- decisions -------------------------------------------------------------
def test_authenticated_human_can_create_decision(platform):
    ev = _prepare_in_review(platform)
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        correlation_id="c",
    )
    dec = platform.decision_service.create(
        recommendation_id=rec.recommendation_id,
        human_actor_id=HUMAN_ID,
        disposition=Disposition.ADVANCE,
        panel=PANEL,
        rationale_job_related="strong execution and reasoning evidence",
    )
    assert dec.actor_type is ActorType.HUMAN
    assert platform.workflow_service.get("cand-1").state is S.ADVANCED


def test_ai_principal_cannot_create_decision(platform):
    ev = _prepare_in_review(platform)
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        correlation_id="c",
    )
    with pytest.raises(BoundaryViolationError):
        platform.decision_service.create(
            recommendation_id=rec.recommendation_id,
            human_actor_id="ai-eval-engine",  # an AI principal
            disposition=Disposition.ADVANCE,
            panel=("ai-eval-engine",),
            rationale_job_related="attempting to self-advance",
        )
    # nothing advanced
    assert platform.workflow_service.get("cand-1").state is S.IN_REVIEW


def test_service_principal_cannot_impersonate_human(platform):
    ev = _prepare_in_review(platform)
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        correlation_id="c",
    )
    with pytest.raises(BoundaryViolationError):
        platform.decision_service.create(
            recommendation_id=rec.recommendation_id,
            human_actor_id="svc-ats",  # a service principal
            disposition=Disposition.ADVANCE,
            panel=("svc-ats",),
            rationale_job_related="automated advance",
        )


def test_unknown_principal_is_unauthenticated(platform):
    ev = _prepare_in_review(platform)
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        correlation_id="c",
    )
    with pytest.raises(UnauthenticatedActorError):
        platform.decision_service.create(
            recommendation_id=rec.recommendation_id,
            human_actor_id="ghost",
            disposition=Disposition.ADVANCE,
            panel=("ghost",),
            rationale_job_related="who am I",
        )


def test_missing_rationale_fails(platform):
    ev = _prepare_in_review(platform)
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        correlation_id="c",
    )
    with pytest.raises(DomainValidationError):
        platform.decision_service.create(
            recommendation_id=rec.recommendation_id,
            human_actor_id=HUMAN_ID,
            disposition=Disposition.ADVANCE,
            panel=PANEL,
            rationale_job_related="   ",
        )


def test_disagreement_without_override_fails(platform):
    ev = _prepare_in_review(platform)
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        correlation_id="c",
    )
    with pytest.raises(OverrideRequiredError):
        platform.decision_service.create(
            recommendation_id=rec.recommendation_id,
            human_actor_id=HUMAN_ID,
            disposition=Disposition.REJECT,  # diverges from ADVANCE
            panel=PANEL,
            rationale_job_related="does not meet the bar on execution",
        )


def test_disagreement_with_override_succeeds(platform):
    ev = _prepare_in_review(platform)
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        correlation_id="c",
    )
    dec = platform.decision_service.create(
        recommendation_id=rec.recommendation_id,
        human_actor_id=HUMAN_ID,
        disposition=Disposition.REJECT,
        panel=PANEL,
        rationale_job_related="concurrency gap is disqualifying for this role",
        override=Override(
            reason="AI weighted execution too generously",
            from_disposition=Disposition.ADVANCE,
            to_disposition=Disposition.REJECT,
        ),
    )
    assert dec.disposition is Disposition.REJECT
    assert platform.workflow_service.get("cand-1").state is S.REJECTED


def test_blocked_evaluation_cannot_be_decided(platform):
    ev = _prepare_in_review(platform, status=EvaluationStatus.REVIEW_BLOCKED)
    # Workflow is still EVALUATED (blocked evals never entered review), but we
    # can still attempt a decision against the recommendation and must be denied.
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.HOLD,
        correlation_id="c",
    )
    with pytest.raises(BlockedEvaluationError):
        platform.decision_service.create(
            recommendation_id=rec.recommendation_id,
            human_actor_id=HUMAN_ID,
            disposition=Disposition.HOLD,
            panel=PANEL,
            rationale_job_related="needs more review",
        )


def test_duplicate_decision_for_same_evaluation_is_rejected(platform):
    ev = _prepare_in_review(platform)
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        correlation_id="c",
    )
    platform.decision_service.create(
        recommendation_id=rec.recommendation_id,
        human_actor_id=HUMAN_ID,
        disposition=Disposition.ADVANCE,
        panel=PANEL,
        rationale_job_related="clear advance",
    )
    from ai_hiring.errors import DuplicateDecisionError

    with pytest.raises(DuplicateDecisionError):
        platform.decision_service.create(
            recommendation_id=rec.recommendation_id,
            human_actor_id=HUMAN_ID,
            disposition=Disposition.ADVANCE,
            panel=PANEL,
            rationale_job_related="deciding again",
        )
