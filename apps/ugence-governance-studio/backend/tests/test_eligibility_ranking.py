"""Eligibility + ranking API tests (§10, §11, §28)."""
from __future__ import annotations

import pytest

from tests.conftest import SCENARIOS, result_of


@pytest.mark.parametrize("sid", SCENARIOS)
def test_eligibility_complete_accounting(client, sid):
    result = result_of(client.post("/api/v1/eligibility/evaluate", json={"scenario_id": sid}))
    for report in result["role_reports"]:
        n = len(report["results"])
        counted = (len(report["eligible_agent_ids"]) + len(report["eliminated_agent_ids"])
                   + len(report["indeterminate_agent_ids"]))
        assert n == counted  # every role-agent pair accounted exactly once


def test_eligibility_states_present(client):
    result = result_of(client.post("/api/v1/eligibility/evaluate", json={"scenario_id": "procurement"}))
    states = {res["state"] for rep in result["role_reports"] for res in rep["results"]}
    assert "ELIGIBLE" in states
    assert "ELIMINATED" in states or "INELIGIBLE" in states


def test_eligibility_elimination_reasons_and_evidence(client):
    result = result_of(client.post("/api/v1/eligibility/evaluate", json={"scenario_id": "procurement"}))
    saw_reason = False
    for rep in result["role_reports"]:
        for res in rep["results"]:
            if res["elimination_reasons"]:
                saw_reason = True
    assert saw_reason


def test_eligibility_expected_fingerprint(client):
    a = result_of(client.post("/api/v1/eligibility/evaluate", json={"scenario_id": "procurement"}))
    b = result_of(client.get("/api/v1/scenarios/procurement/eligibility"))
    assert a["workflow_eligibility_fingerprint"] == \
        b["workflow_eligibility"]["workflow_fingerprint"]


@pytest.mark.parametrize("sid", SCENARIOS)
def test_ranking_every_eligible_ranked_once(client, sid):
    elig = result_of(client.post("/api/v1/eligibility/evaluate", json={"scenario_id": sid}))
    rank = result_of(client.post("/api/v1/ranking/evaluate", json={"scenario_id": sid}))
    elig_by_role = {r["role_id"]: set(r["eligible_agent_ids"]) for r in elig["role_reports"]}
    for ranking in rank["rankings"]:
        ranked = [f"{c['agent_id']}@{c['agent_version']}" for c in ranking["ranked_candidates"]]
        assert len(ranked) == len(set(ranked))  # no duplicates
        # no ineligible candidate is ranked
        assert set(ranked) <= elig_by_role.get(ranking["role_id"], set())


def test_ranking_score_contributions_and_tiebreaks(client):
    rank = result_of(client.post("/api/v1/ranking/evaluate", json={"scenario_id": "procurement"}))
    for ranking in rank["rankings"]:
        for cand in ranking["ranked_candidates"]:
            assert "total_score" in cand
            assert "criterion_results" in cand
            assert "tie_break_values" in cand


def test_ranking_deterministic_order(client):
    a = result_of(client.post("/api/v1/ranking/evaluate", json={"scenario_id": "procurement"}))
    b = result_of(client.post("/api/v1/ranking/evaluate", json={"scenario_id": "procurement"}))
    assert [r["ranking_fingerprint"] for r in a["rankings"]] == \
        [r["ranking_fingerprint"] for r in b["rankings"]]
