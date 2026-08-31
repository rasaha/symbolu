"""Concurrency + determinism tests (§19, §28)."""
from __future__ import annotations

import concurrent.futures

from _support import result_of


def _plan_fingerprint(client, sid="procurement"):
    return result_of(client.get(f"/api/v1/scenarios/{sid}/plan"))["agent_team_plan"]["plan_fingerprint"]


def test_concurrent_identical_requests_identical_output(client):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: _plan_fingerprint(client), range(24)))
    assert len(set(results)) == 1


def test_no_cross_request_state_leak(client):
    """A what-if request must not affect a subsequent baseline request."""
    baseline = _plan_fingerprint(client)
    client.post("/api/v1/scenarios/procurement/what-if",
                json={"operation": "FORBID_PROVIDER", "params": {"provider": "anthropic"}})
    after = _plan_fingerprint(client)
    assert baseline == after


def test_no_scenario_mutation_across_requests(client):
    a = result_of(client.get("/api/v1/scenarios/procurement/eligibility"))
    client.post("/api/v1/scenarios/procurement/what-if",
                json={"operation": "TIGHTEN_COST_CEILING", "params": {"ceiling": 0.0}})
    b = result_of(client.get("/api/v1/scenarios/procurement/eligibility"))
    assert a["workflow_eligibility"]["workflow_fingerprint"] == \
        b["workflow_eligibility"]["workflow_fingerprint"]


def test_request_id_does_not_affect_result(client):
    a = client.get("/api/v1/scenarios/procurement/plan").json()
    b = client.get("/api/v1/scenarios/procurement/plan").json()
    assert a["request_id"] != b["request_id"]  # ids differ
    assert a["result"]["agent_team_plan"]["plan_fingerprint"] == \
        b["result"]["agent_team_plan"]["plan_fingerprint"]  # results identical
