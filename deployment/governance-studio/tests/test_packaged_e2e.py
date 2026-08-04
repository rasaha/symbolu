"""Packaged four-scenario end-to-end through the single-process app (P3E §25 integration).

Exercises the full planning surface for every synthetic scenario through the same
authenticated, security-wrapped app the container serves. (Runs in-process; the live
TLS path is covered by test_https_tls.py.)
"""
import base64

import pytest

from depaths import USERNAME, PASSWORD

AUTH = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
GET = {"Authorization": AUTH}
POST = {"Authorization": AUTH, "X-Ugence-Request": "GovernanceStudio", "Origin": "http://testserver", "Content-Type": "application/json"}

SCENARIOS = ["procurement", "customer_support", "cybersecurity_success", "cybersecurity_no_feasible_team"]


def test_spa_served_at_root(client):
    r = client.get("/", headers=GET)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_spa_fallback_for_frontend_routes(client):
    r = client.get("/scenarios/procurement/ranking", headers=GET)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_unknown_api_path_is_not_spa(client):
    r = client.get("/api/v1/nope", headers=GET)
    assert r.status_code == 404
    assert "text/html" not in r.headers.get("content-type", "")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_full_planning_surface_per_scenario(client, scenario):
    # overview, registry, eligibility, ranking, plan, export — all authenticated GETs
    for suffix in ("", "/registry", "/eligibility", "/ranking", "/plan", "/export"):
        r = client.get(f"/api/v1/scenarios/{scenario}{suffix}", headers=GET)
        assert r.status_code == 200, f"{scenario}{suffix} -> {r.status_code}"

    # explanations + replay + a controlled what-if (POST, deployment-guarded)
    assert client.post("/api/v1/explanations/plan", headers=POST, json={"scenario_id": scenario}).status_code == 200
    assert client.post("/api/v1/plans/replay", headers=POST, json={"scenario_id": scenario}).status_code == 200
    wf = client.post(f"/api/v1/scenarios/{scenario}/what-if", headers=POST,
                     json={"operation": "EXPIRE_EVIDENCE", "params": {}})
    assert wf.status_code == 200


def test_no_feasible_team_is_a_domain_result_not_an_error(client):
    r = client.get("/api/v1/scenarios/cybersecurity_no_feasible_team/plan", headers=GET)
    assert r.status_code == 200  # domain state, HTTP 200
    assert r.json()["result"]["agent_team_plan"]["plan_state"] == "NO_FEASIBLE_TEAM"


def test_version_reports_frozen_identities(client):
    r = client.get("/version", headers=GET)
    assert r.status_code == 200
    v = r.json()
    assert v.get("api_contract_version") == "governance_studio.api.v1"
