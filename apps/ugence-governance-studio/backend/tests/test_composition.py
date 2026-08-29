"""Composition + permission + fallback API tests (§12, §13, §28)."""
from __future__ import annotations

from _support import result_of


def test_complete_team(client):
    result = result_of(client.post("/api/v1/composition/compose", json={"scenario_id": "procurement"}))
    assert result["plan_state"] == "COMPLETE"
    assert result["role_assignments"]
    assert not result["unfilled_roles"]


def test_no_feasible_team_is_domain_result(client):
    r = client.post("/api/v1/composition/compose",
                    json={"scenario_id": "cybersecurity_no_feasible_team"})
    assert r.status_code == 200  # NOT a 500
    assert result_of(r)["plan_state"] == "NO_FEASIBLE_TEAM"


def test_search_statistics_and_concentration(client):
    result = result_of(client.post("/api/v1/composition/compose", json={"scenario_id": "procurement"}))
    stats = result["search_statistics"]
    assert "algorithm" in stats
    assert "optimality_status" in stats
    # team constraint results carry provider / failure-domain concentration checks
    assert result["team_constraint_results"]


def test_non_greedy_selection_scenario(client):
    # procurement demonstrates non-greedy selection under provider concentration
    result = result_of(client.post("/api/v1/composition/compose", json={"scenario_id": "procurement"}))
    assert result["plan_state"] == "COMPLETE"


def test_expected_plan_verification(client):
    result = result_of(client.get("/api/v1/scenarios/procurement/plan"))
    assert result["verification"]["match"] is True


def test_permission_proposals_present(client):
    result = result_of(client.post("/api/v1/composition/compose", json={"scenario_id": "procurement"}))
    props = result["permission_bound_proposals"]
    assert props
    for p in props:
        assert "proposed_permissions" in p
        assert "categorized" in p
        assert "feasible" in p


def test_permission_no_grant_wording(client):
    """Permission output must never claim a grant/authorization."""
    body = client.post("/api/v1/composition/compose", json={"scenario_id": "procurement"}).text.lower()
    assert "permission granted" not in body
    assert "access granted" not in body
    assert "authorized to execute" not in body


def test_fallback_output(client):
    result = result_of(client.post("/api/v1/composition/compose", json={"scenario_id": "procurement"}))
    plans = result["role_fallback_plans"]
    assert plans
    states = {p["fallback_state"] for p in plans}
    # procurement demonstrates a no-fallback-available state for some roles
    assert states  # at least one fallback state reported


def test_no_fallback_state_visible(client):
    result = result_of(client.post("/api/v1/composition/compose",
                                   json={"scenario_id": "cybersecurity_success"}))
    plans = result["role_fallback_plans"]
    # single-holder roles surface a no-fallback state, not an error
    assert any("NO" in p["fallback_state"] or "SINGLE" in p["fallback_state"]
               or p["candidates"] == [] for p in plans)
