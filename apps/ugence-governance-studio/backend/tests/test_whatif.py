"""Controlled what-if tests (§15, §28)."""
from __future__ import annotations

import pytest

from _support import result_of
from ugence_governance_studio_api.scenarios.catalog import ScenarioCatalog

PERTURBATIONS = [
    ("FORBID_PROVIDER", {"provider": "anthropic"}),
    ("REQUIRE_RESIDENCY", {"residency": "IN"}),
    ("TIGHTEN_COST_CEILING", {"ceiling": 0.0}),
    ("TIGHTEN_LATENCY_CEILING", {"ceiling": 1.0}),
    ("REVOKE_AGENT_VERSION", {"agent_version": "agent_procurement_specialist@2.1.0"}),
    ("EXPIRE_EVIDENCE", {}),
    ("TIGHTEN_PERMISSION_POLICY", {"permission": "read_context"}),
    ("TIGHTEN_PROVIDER_CONCENTRATION", {"limit_pct": 30}),
    ("REMOVE_CANDIDATE", {"agent_id": "agent_support_specialist", "agent_version": "1.3.0"}),
]


@pytest.mark.parametrize("op,params", PERTURBATIONS)
def test_every_supported_perturbation(client, op, params):
    result = result_of(client.post("/api/v1/scenarios/procurement/what-if",
                                   json={"operation": op, "params": params}))
    assert result["baseline_state"] == "COMPLETE"
    assert "modified_plan" in result
    assert "plan_diff" in result
    assert result["perturbation_applied"]["operation"] == op
    # baseline and modified fingerprints differ (each perturbation is material)
    assert result["baseline_plan"]["plan_fingerprint"] != result["modified_plan"]["plan_fingerprint"]


def test_immutable_baseline_fixtures():
    """A perturbation never mutates committed fixtures."""
    cat = ScenarioCatalog()
    before = cat.inputs("procurement")["enterprise_policy"].policy_digest
    from ugence_governance_studio_api.services.orchestration import AwcOrchestrationService
    svc = AwcOrchestrationService()
    s = cat.inputs("procurement")
    svc.apply_perturbation(s, "FORBID_PROVIDER", {"provider": "anthropic"}, 1_000_000.0)
    after = cat.inputs("procurement")["enterprise_policy"].policy_digest
    assert before == after  # committed fixture digest unchanged


def test_deterministic_modified_plan(client):
    body = {"operation": "TIGHTEN_COST_CEILING", "params": {"ceiling": 0.0}}
    a = result_of(client.post("/api/v1/scenarios/procurement/what-if", json=body))
    b = result_of(client.post("/api/v1/scenarios/procurement/what-if", json=body))
    assert a["modified_plan"]["plan_fingerprint"] == b["modified_plan"]["plan_fingerprint"]


def test_exact_plan_diff(client):
    result = result_of(client.post("/api/v1/scenarios/procurement/what-if",
                                   json={"operation": "TIGHTEN_COST_CEILING", "params": {"ceiling": 0.0}}))
    diff = result["plan_diff"]
    assert diff["plan_a_fingerprint"] == result["baseline_plan"]["plan_fingerprint"]
    assert diff["plan_b_fingerprint"] == result["modified_plan"]["plan_fingerprint"]


def test_unsupported_perturbation_rejected(client):
    r = client.post("/api/v1/scenarios/procurement/what-if",
                    json={"operation": "DELETE_EVERYTHING", "params": {}})
    assert r.status_code == 422


def test_what_if_changed_input_digests(client):
    result = result_of(client.post("/api/v1/scenarios/procurement/what-if",
                                   json={"operation": "FORBID_PROVIDER", "params": {"provider": "anthropic"}}))
    assert "enterprise_policy" in result["changed_input_digests"]
