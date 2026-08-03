"""Scenario catalog + execution tests (§8, §20, §28)."""
from __future__ import annotations

import pytest

from tests.conftest import SCENARIOS, result_of


def test_four_required_scenarios(client):
    r = client.get("/api/v1/scenarios")
    assert r.status_code == 200
    ids = {s["scenario_id"] for s in result_of(r)["scenarios"]}
    assert ids == set(SCENARIOS)


def test_scenario_metadata_labels_synthetic(client):
    for s in result_of(client.get("/api/v1/scenarios"))["scenarios"]:
        assert s["synthetic_data"] is True
        assert s["workflow_contract_version"] == "workflow_ir.v1"
        assert s["supported_operations"]


def test_unknown_scenario_404(client):
    r = client.get("/api/v1/scenarios/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "scenario_not_found"


@pytest.mark.parametrize("sid", SCENARIOS)
def test_scenario_detail(client, sid):
    r = client.get(f"/api/v1/scenarios/{sid}")
    assert r.status_code == 200
    result = result_of(r)
    assert result["metadata"]["scenario_id"] == sid
    assert result["manifest"]["synthetic"] is True
    assert "planning only" in result["synthetic_data_notice"].lower()


@pytest.mark.parametrize("sid", SCENARIOS)
def test_scenario_workflow_projection(client, sid):
    result = result_of(client.get(f"/api/v1/scenarios/{sid}/workflow"))
    assert result["contract_version"] == "workflow_ir.v1"
    assert result["nodes"]
    assert result["node_dispositions"]
    # total node accounting: every classified node is either an agent role or a
    # non-agent disposition; every disposition carries a node id.
    for disp in result["node_dispositions"]:
        assert disp["node_id"]
    agent_roles = [d for d in result["node_dispositions"] if d["is_agent_role"]]
    assert len(agent_roles) == len(result["role_requirements"])


def test_scenario_registry(client):
    result = result_of(client.get("/api/v1/scenarios/procurement/registry"))
    assert "registry_snapshot" in result
    assert result["registry_snapshot"]["agent_profiles"]


def test_manifest_hash_validation(catalog):
    ok, mismatches = catalog.verify_fixture_hashes()
    assert ok, mismatches


@pytest.mark.parametrize("sid", SCENARIOS)
def test_scenario_execution_real_pipeline(client, sid):
    """Scenario endpoints EXECUTE the real pipeline and verify the oracle."""
    result = result_of(client.get(f"/api/v1/scenarios/{sid}/plan"))
    assert result["verification"]["match"] is True
    assert result["verification"]["observed_fingerprint"] == \
        result["verification"]["expected_fingerprint"]


def test_no_feasible_team_is_200(client):
    r = client.get("/api/v1/scenarios/cybersecurity_no_feasible_team/plan")
    assert r.status_code == 200
    assert result_of(r)["plan_state"] == "NO_FEASIBLE_TEAM"


def test_immutable_catalog(catalog):
    """Two independent input loads never share a mutable object."""
    a = catalog.inputs("procurement")
    b = catalog.inputs("procurement")
    assert a["registry"] is not b["registry"]
    # mutating one dict must not affect the other
    a["workflow"]["_scratch"] = 1
    assert "_scratch" not in b["workflow"]
