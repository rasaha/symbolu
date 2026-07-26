"""H4 — ActionGate authorization outcomes."""

from __future__ import annotations

import pytest

from ai_hiring.actions.action_types import HiringActionType
from ai_hiring.actions.status import ActionProposalStatus
from ai_hiring.tests.h3_helpers import ai_ctx
from ai_hiring.tests.h4_helpers import action_integration, build_h4_env, decided_recommendation


def _ready(env, rec, action_type=HiringActionType.ADVANCE_STAGE):
    prop = env.proposal_service.propose(
        ai_ctx(), recommendation_id=rec.recommendation_id, action_type=action_type,
        target_system="ats", parameters=(("stage", "onsite"),))
    env.proposal_service.mark_ready(ai_ctx(), prop.action_proposal_id)
    return prop


def test_actiongate_approval():
    env = build_h4_env()
    prop = _ready(env, decided_recommendation(env))
    auth = env.authorization_service.authorize(
        ai_ctx(), proposal_id=prop.action_proposal_id, integration=action_integration())
    assert auth.authorized and auth.outcome == "AUTHORIZED"
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.AUTHORIZED


def test_actiongate_denial_blocks_execution():
    env = build_h4_env()
    prop = _ready(env, decided_recommendation(env))
    auth = env.authorization_service.authorize(
        ai_ctx(), proposal_id=prop.action_proposal_id,
        integration=action_integration(denied=frozenset({"ADVANCE_STAGE"})))
    assert not auth.authorized and auth.outcome == "DENIED"
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.AUTHORIZATION_DENIED


def test_constrained_authorization_carries_obligations():
    env = build_h4_env()
    prop = _ready(env, decided_recommendation(env))
    auth = env.authorization_service.authorize(
        ai_ctx(), proposal_id=prop.action_proposal_id,
        integration=action_integration(constrained=frozenset({"ADVANCE_STAGE"})))
    assert auth.authorized and auth.outcome == "AUTHORIZED_WITH_CONSTRAINTS"
    assert auth.constraints and auth.obligations


def test_provider_unavailable_is_fail_safe():
    env = build_h4_env()
    prop = _ready(env, decided_recommendation(env))
    auth = env.authorization_service.authorize(
        ai_ctx(), proposal_id=prop.action_proposal_id, integration=action_integration(unavailable=True))
    assert not auth.authorized
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.AUTHORIZATION_DENIED


def test_authorize_requires_ready_status():
    from ai_hiring.errors import IllegalActionTransitionError
    env = build_h4_env()
    rec = decided_recommendation(env)
    prop = env.proposal_service.propose(
        ai_ctx(), recommendation_id=rec.recommendation_id, action_type=HiringActionType.ADVANCE_STAGE,
        target_system="ats")  # still DRAFT
    with pytest.raises(IllegalActionTransitionError):
        env.authorization_service.authorize(
            ai_ctx(), proposal_id=prop.action_proposal_id, integration=action_integration())
