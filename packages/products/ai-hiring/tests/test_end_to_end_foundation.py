"""End-to-end foundation scenario.

Walks the full Phase-1 path and proves the boundary end to end:

    AI recommends ADVANCE -> human overrides to REJECT -> workflow REJECTED,
    with the whole chain reconstructable from the audit history.
"""

from __future__ import annotations

from ugence_ai_hiring.api.schemas import (
    CreateDecisionRequest,
    CreateEvaluationRequest,
    CreateRecommendationRequest,
)
from ugence_ai_hiring.domain.decision import Override
from ugence_ai_hiring.domain.enums import ActorType, AuditEventType, Disposition, WorkflowState
from ugence_ai_hiring.domain.evaluation import Limitation

from .conftest import AI_ID, HUMAN_ID, PANEL, SERVICE_ID, make_evaluation

S = WorkflowState


def test_ai_recommends_advance_human_overrides_to_reject(platform):
    ws = platform.workflow_service
    candidate_id = "cand-42"

    # 1. Candidate workflow reaches EVALUATED.
    ws.initialize(candidate_id, "role-backend", correlation_id="corr-e2e")
    for state in (S.SOURCED, S.ASSESSING, S.EVALUATED):
        ws.transition(candidate_id, state, actor_type=ActorType.SYSTEM, correlation_id="corr-e2e")
    assert ws.get(candidate_id).state is S.EVALUATED

    # 2. Store a complete CandidateEvaluation.
    ev = make_evaluation(evaluation_id="eval-42", candidate_id=candidate_id, role_id="role-backend")
    platform.evaluation_service.store(ev, actor_id=AI_ID, correlation_id="corr-e2e")

    # 3. AI creates Recommendation(ADVANCE).
    rec = platform.recommendation_service.create(
        evaluation_id=ev.evaluation_id,
        suggested_disposition=Disposition.ADVANCE,
        caveats=(Limitation(description="concurrency untested in the work sample"),),
        actor_id=AI_ID,
        correlation_id="corr-e2e",
    )
    assert rec.actor_type is ActorType.AI

    # 4. The recommendation did NOT advance the candidate; move to review.
    assert ws.get(candidate_id).state is S.EVALUATED
    ws.request_review(candidate_id, ev, correlation_id="corr-e2e")
    assert ws.get(candidate_id).state is S.IN_REVIEW

    # 5-6. Human reviewer decides REJECT against the AI, with an override.
    decision = platform.decision_service.create(
        recommendation_id=rec.recommendation_id,
        human_actor_id=HUMAN_ID,
        disposition=Disposition.REJECT,
        panel=PANEL,
        rationale_job_related=(
            "Execution evidence is adequate but the concurrency gap is "
            "disqualifying for a backend role handling live traffic."
        ),
        override=Override(
            reason="AI over-weighted a passing happy-path work sample",
            from_disposition=Disposition.ADVANCE,
            to_disposition=Disposition.REJECT,
        ),
    )
    assert decision.actor_type is ActorType.HUMAN

    # 7. Workflow moves to REJECTED.
    final = ws.get(candidate_id)
    assert final.state is S.REJECTED
    assert final.last_decision_id == decision.decision_id

    # 8. Reconstruct the chain from audit history:
    #    evaluation -> recommendation -> human override/decision -> transition.
    chain = platform.audit_service.by_correlation("corr-e2e")
    ordered_types = [e.event_type for e in chain]

    assert ordered_types.index(AuditEventType.EVALUATION_CREATED) < \
        ordered_types.index(AuditEventType.RECOMMENDATION_CREATED)
    assert ordered_types.index(AuditEventType.RECOMMENDATION_CREATED) < \
        ordered_types.index(AuditEventType.DECISION_CREATED)

    rec_event = platform.audit_service.history(rec.recommendation_id)[-1]
    dec_event = platform.audit_service.history(decision.decision_id)[-1]
    reject_event = [
        e for e in platform.audit_service.history(candidate_id)
        if e.event_type is AuditEventType.WORKFLOW_TRANSITION and e.new_state == "REJECTED"
    ][-1]

    # Causation links form an unbroken chain.
    assert dec_event.causation_id == rec_event.event_id
    assert reject_event.causation_id == dec_event.event_id
    assert dec_event.actor_type is ActorType.HUMAN
    assert reject_event.previous_state == "IN_REVIEW"


def test_end_to_end_through_the_api_facade(platform):
    """The same boundary holds through the callable API surface, with auth hooks."""
    api = platform.build_api()
    candidate_id = "cand-api"

    # Move to EVALUATED via the service (process transitions).
    ws = platform.workflow_service
    ws.initialize(candidate_id, "role-1", correlation_id="corr-api")
    for state in (S.SOURCED, S.ASSESSING, S.EVALUATED):
        ws.transition(candidate_id, state, actor_type=ActorType.SYSTEM, correlation_id="corr-api")

    ev = make_evaluation(evaluation_id="eval-api", candidate_id=candidate_id)

    # AI/service principal stores the evaluation and recommendation.
    api.create_evaluation(CreateEvaluationRequest(principal_id=SERVICE_ID, evaluation=ev))
    ws.request_review(candidate_id, ev, correlation_id="corr-api")
    rec = api.create_recommendation(
        CreateRecommendationRequest(
            principal_id=AI_ID,
            evaluation_id=ev.evaluation_id,
            suggested_disposition=Disposition.ADVANCE,
        )
    )

    # An AI principal cannot create a decision through the API.
    import pytest
    from ugence_ai_hiring.errors import BoundaryViolationError

    with pytest.raises(BoundaryViolationError):
        api.create_decision(
            CreateDecisionRequest(
                principal_id=AI_ID,
                recommendation_id=rec.recommendation_id,
                disposition=Disposition.ADVANCE,
                panel=(AI_ID,),
                rationale_job_related="self-advance attempt",
            )
        )

    # The human decides through the API.
    decision = api.create_decision(
        CreateDecisionRequest(
            principal_id=HUMAN_ID,
            recommendation_id=rec.recommendation_id,
            disposition=Disposition.ADVANCE,
            panel=PANEL,
            rationale_job_related="meets the bar across all ten layers",
        )
    )
    assert decision.actor_type is ActorType.HUMAN
    assert ws.get(candidate_id).state is S.ADVANCED

    # Audit is queryable through the API facade.
    audit = api.get_candidate_audit(candidate_id, principal_id=HUMAN_ID)
    assert any(e.event_type is AuditEventType.WORKFLOW_TRANSITION for e in audit)
