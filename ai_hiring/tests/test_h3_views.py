"""H3 — review workspace, governance dashboard, recommendation history."""

from __future__ import annotations

from ai_hiring.governance.outcomes import HiringDecisionIntent
from ai_hiring.tests.h3_helpers import ai_ctx, build_h3_env, human_ctx, ready_recommendation


def test_review_workspace_combines_hiring_and_governance_state():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    ws = env.views.review_workspace(human_ctx(), rec.recommendation_id,
                                    reviewer_actions=("ADVANCE", "HOLD", "REJECT"))
    assert ws.decision_case_id and ws.kernel_recommendation_id
    assert ws.advisory is True
    assert ws.material_claim_count >= 1
    assert ws.binding_status == "OPEN"
    assert ws.reviewer_actions == ("ADVANCE", "HOLD", "REJECT")


def test_dashboard_counts_open_and_decided():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    dash_open = env.views.dashboard(human_ctx())
    assert dash_open.total == 1 and dash_open.open_count == 1 and dash_open.decided_count == 0
    env.governance.record_human_decision(
        human_ctx(), recommendation_id=rec.recommendation_id, intent=HiringDecisionIntent.ADVANCE)
    dash_decided = env.views.dashboard(human_ctx())
    assert dash_decided.decided_count == 1
    assert dash_decided.cases[0].decision_outcome == "ADVANCE"


def test_recommendation_history_lists_bindings():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    hist = env.views.recommendation_history(human_ctx(), "a1")
    assert hist.entries and hist.entries[0].recommendation_id == rec.recommendation_id
    assert hist.entries[0].decision_case_id


def test_dashboard_is_tenant_scoped():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    # a different tenant sees nothing
    assert env.views.dashboard(human_ctx(tenant="t2", actor="human-t2")).total == 0
