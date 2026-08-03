"""Explanation endpoint tests (§13, §28)."""
from __future__ import annotations

from tests.conftest import result_of


def test_eligibility_explanation(client):
    result = result_of(client.post("/api/v1/explanations/eligibility",
                                   json={"scenario_id": "procurement"}))
    assert result["roles"]
    for role in result["roles"]:
        for agent in role["agents"]:
            assert "passed_conditions" in agent
            assert "failed_conditions" in agent
            assert "unknown_conditions" in agent


def test_ranking_reconstruction(client):
    result = result_of(client.post("/api/v1/explanations/ranking",
                                   json={"scenario_id": "procurement"}))
    for ranking in result["rankings"]:
        for cand in ranking["ranked_candidates"]:
            for cr in cand["criterion_results"]:
                assert "raw_value" in cr
                assert "normalized_bp" in cr
                assert "weight_bp" in cr
                assert "weighted_contribution_bp" in cr


def test_plan_selection_states_distinct(client):
    result = result_of(client.post("/api/v1/explanations/plan", json={"scenario_id": "procurement"}))
    all_states = set()
    for states in result["selection_states"].values():
        all_states.update(states.values())
    assert "SELECTED_PRIMARY" in all_states
    # each state is one of the four distinct values
    assert all_states <= {"INELIGIBLE", "ELIGIBLE_NOT_SELECTED",
                          "SELECTED_PRIMARY", "SELECTED_FALLBACK"}


def test_plan_explanation_fields(client):
    result = result_of(client.post("/api/v1/explanations/plan", json={"scenario_id": "procurement"}))
    assert "team_constraint_results" in result
    assert "team_objective_results" in result
    assert "permission_bound_proposals" in result
    assert "role_fallback_plans" in result
    assert "unfilled_roles" in result


def test_eligible_not_selected_present(client):
    result = result_of(client.post("/api/v1/explanations/plan", json={"scenario_id": "procurement"}))
    values = [v for states in result["selection_states"].values() for v in states.values()]
    # procurement has more eligible candidates than selected primaries
    assert "ELIGIBLE_NOT_SELECTED" in values or "SELECTED_FALLBACK" in values


def test_no_invented_reasons(client):
    """Explanation reasons come only from AWC — cross-check against raw eligibility."""
    exp = result_of(client.post("/api/v1/explanations/eligibility",
                                json={"scenario_id": "procurement"}))
    raw = result_of(client.post("/api/v1/eligibility/evaluate", json={"scenario_id": "procurement"}))
    raw_reasons = set()
    for rep in raw["role_reports"]:
        for res in rep["results"]:
            for reason in res["elimination_reasons"]:
                raw_reasons.add(str(reason))
    for role in exp["roles"]:
        for agent in role["agents"]:
            for reason in agent["elimination_reasons"]:
                assert str(reason) in raw_reasons
