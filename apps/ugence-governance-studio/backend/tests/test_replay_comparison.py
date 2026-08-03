"""Plan replay + comparison tests (§14, §28)."""
from __future__ import annotations

import pytest

from tests.conftest import SCENARIOS, result_of


@pytest.mark.parametrize("sid", SCENARIOS)
def test_replay_matches(client, sid):
    result = result_of(client.post("/api/v1/plans/replay", json={"scenario_id": sid}))
    assert result["match"] is True
    assert result["expected_plan_fingerprint"] == result["replayed_plan_fingerprint"]


def test_replay_mismatched_expected(client):
    result = result_of(client.post("/api/v1/plans/replay",
                                   json={"scenario_id": "procurement",
                                         "expected_plan": {"plan_fingerprint": "sha256:wrong"}}))
    assert result["match"] is False
    assert result["diagnostics"]


def test_cross_process_replay_determinism(client):
    """Replaying twice (fresh pipeline each time) reproduces the fingerprint."""
    a = result_of(client.post("/api/v1/plans/replay", json={"scenario_id": "procurement"}))
    b = result_of(client.post("/api/v1/plans/replay", json={"scenario_id": "procurement"}))
    assert a["replayed_plan_fingerprint"] == b["replayed_plan_fingerprint"]


def test_compare_equal_plans(client):
    result = result_of(client.post("/api/v1/plans/compare",
                                   json={"left": {"scenario_id": "procurement"},
                                         "right": {"scenario_id": "procurement"}}))
    assert result["plan_a_fingerprint"] == result["plan_b_fingerprint"]
    assert result["same_workflow"] is True


def test_compare_policy_change(client):
    result = result_of(client.post("/api/v1/plans/compare", json={
        "left": {"scenario_id": "procurement"},
        "right": {"scenario_id": "procurement",
                  "perturbation": {"operation": "FORBID_PROVIDER", "params": {"provider": "anthropic"}}},
    }))
    assert result["plan_a_fingerprint"] != result["plan_b_fingerprint"]


def test_compare_registry_change(client):
    result = result_of(client.post("/api/v1/plans/compare", json={
        "left": {"scenario_id": "procurement"},
        "right": {"scenario_id": "procurement",
                  "perturbation": {"operation": "REMOVE_CANDIDATE",
                                   "params": {"agent_id": "agent_support_specialist",
                                              "agent_version": "1.3.0"}}},
    }))
    assert result["plan_a_fingerprint"] != result["plan_b_fingerprint"]


def test_compare_different_scenarios_workflow_mismatch(client):
    result = result_of(client.post("/api/v1/plans/compare", json={
        "left": {"scenario_id": "procurement"},
        "right": {"scenario_id": "customer_support"},
    }))
    assert result["same_workflow"] is False
    assert result["workflow_mismatch"] is True
