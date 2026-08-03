"""H4 — action proposal eligibility (source-decision gating)."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.actions.action_types import HiringActionType
from ugence_ai_hiring.actions.status import ActionProposalStatus
from ugence_ai_hiring.errors import (
    CrossTenantHiringAccessError,
    DecisionActionMismatchError,
    IneligibleActionSourceError,
)
from ugence_ai_hiring.governance.outcomes import HiringDecisionIntent
from .h3_helpers import ai_ctx, human_ctx, ready_recommendation
from .h4_helpers import build_h4_env, decided_recommendation


def test_valid_decision_to_action_proposal():
    env = build_h4_env()
    rec = decided_recommendation(env, intent=HiringDecisionIntent.ADVANCE)
    prop = env.proposal_service.propose(
        ai_ctx(), recommendation_id=rec.recommendation_id, action_type=HiringActionType.ADVANCE_STAGE,
        target_system="ats", parameters=(("stage", "onsite"),))
    assert prop.status == ActionProposalStatus.DRAFT
    assert prop.human_decision_id and prop.decision_case_id


def test_recommendation_to_action_bypass_is_rejected():
    """A recommendation with no governed human decision can never source an action."""
    env = build_h4_env()
    rec = ready_recommendation(env.h3)  # generated, but NO case opened / NO decision
    with pytest.raises(IneligibleActionSourceError):
        env.proposal_service.propose(
            ai_ctx(), recommendation_id=rec.recommendation_id, action_type=HiringActionType.ADVANCE_STAGE,
            target_system="ats")


def test_missing_human_decision_is_rejected():
    env = build_h4_env()
    rec = ready_recommendation(env.h3)
    env.h3.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)  # bound, not decided
    with pytest.raises(IneligibleActionSourceError):
        env.proposal_service.propose(
            ai_ctx(), recommendation_id=rec.recommendation_id, action_type=HiringActionType.ADVANCE_STAGE,
            target_system="ats")


def test_decision_action_mismatch_rejected():
    env = build_h4_env()
    rec = decided_recommendation(env, intent=HiringDecisionIntent.REJECT)  # REJECT decision
    with pytest.raises(DecisionActionMismatchError):
        # ADVANCE_STAGE is not permitted for a REJECT decision
        env.proposal_service.propose(
            ai_ctx(), recommendation_id=rec.recommendation_id, action_type=HiringActionType.ADVANCE_STAGE,
            target_system="ats")


def test_reject_decision_permits_close_action():
    env = build_h4_env()
    rec = decided_recommendation(env, intent=HiringDecisionIntent.REJECT)
    prop = env.proposal_service.propose(
        ai_ctx(), recommendation_id=rec.recommendation_id,
        action_type=HiringActionType.CLOSE_WITHOUT_SELECTION, target_system="ats")
    assert prop.action_type == HiringActionType.CLOSE_WITHOUT_SELECTION


def test_duplicate_active_proposal_prevented():
    env = build_h4_env()
    rec = decided_recommendation(env)
    env.proposal_service.propose(
        ai_ctx(), recommendation_id=rec.recommendation_id, action_type=HiringActionType.ADVANCE_STAGE,
        target_system="ats")
    with pytest.raises(IneligibleActionSourceError):
        env.proposal_service.propose(
            ai_ctx(), recommendation_id=rec.recommendation_id, action_type=HiringActionType.ADVANCE_STAGE,
            target_system="ats")


def test_proposal_tenant_isolation():
    env = build_h4_env()
    rec = decided_recommendation(env)
    with pytest.raises(CrossTenantHiringAccessError):
        env.proposal_service.propose(
            ai_ctx(tenant="t2", actor="ai-t2"), recommendation_id=rec.recommendation_id,
            action_type=HiringActionType.ADVANCE_STAGE, target_system="ats")
