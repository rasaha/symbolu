"""Workflow validation & adaptation tests (§9, §28)."""
from __future__ import annotations

import pytest

from tests.conftest import SCENARIOS, result_of
from ugence_governance_studio_api.scenarios.catalog import ScenarioCatalog


@pytest.fixture()
def cat() -> ScenarioCatalog:
    return ScenarioCatalog()


def test_validate_valid_v1(client, cat):
    wf = cat.raw_workflow("procurement")
    result = result_of(client.post("/api/v1/workflows/validate",
                                   json={"contract_version": "workflow_ir.v1", "workflow": wf}))
    assert result["validation_state"] == "VALID"
    assert result["supported_version"] is True


def test_validate_v2(client, cat):
    v2s = cat.v2_inputs("procurement")
    result = result_of(client.post("/api/v1/workflows/validate",
                                   json={"contract_version": "workflow_ir.v2",
                                         "workflow": v2s["v2_workflow"]}))
    assert result["declared_contract_version"] == "workflow_ir.v2"
    assert result["supported_version"] is True


def test_validate_unknown_contract(client):
    result = result_of(client.post("/api/v1/workflows/validate",
                                   json={"contract_version": "workflow_ir.v9", "workflow": {}}))
    assert result["validation_state"] == "INVALID"
    assert result["supported_version"] is False


def test_adapt_valid_v1(client, cat):
    wf, ov = cat.raw_workflow("procurement"), cat.raw_overlay("procurement")
    result = result_of(client.post("/api/v1/workflows/adapt", json={"workflow": wf, "overlay": ov}))
    assert result["ok"] is True
    assert result["adapter_mode"] == "V1_FROZEN"
    assert result["role_requirements"]
    # provenance is present on each role requirement
    for role in result["role_requirements"]:
        assert role["provenance"]


def test_adapt_valid_v2(client, cat):
    v2s = cat.v2_inputs("procurement")
    result = result_of(client.post("/api/v1/workflows/adapt",
                                   json={"workflow": v2s["v2_workflow"],
                                         "contract_version": "workflow_ir.v2",
                                         "overlay": v2s["v2_overlay"]}))
    assert result["ok"] is True
    assert result["role_requirements"]


def test_adapt_unknown_contract_fails_closed(client):
    r = client.post("/api/v1/workflows/adapt",
                    json={"workflow": {"contract_version": "workflow_ir.v9"}})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unsupported_contract_version"


def test_adapt_malformed_workflow(client):
    r = client.post("/api/v1/workflows/adapt",
                    json={"workflow": {"contract_version": "workflow_ir.v1", "garbage": True}})
    # known contract but malformed content → typed envelope with ok False (200)
    assert r.status_code == 200
    assert result_of(r)["ok"] is False


def test_adapt_determinism(client, cat):
    wf, ov = cat.raw_workflow("procurement"), cat.raw_overlay("procurement")
    body = {"workflow": wf, "overlay": ov}
    a = result_of(client.post("/api/v1/workflows/adapt", json=body))
    b = result_of(client.post("/api/v1/workflows/adapt", json=body))
    assert a["adaptation_fingerprint"] == b["adaptation_fingerprint"]


def test_node_accounting(client, cat):
    wf, ov = cat.raw_workflow("procurement"), cat.raw_overlay("procurement")
    result = result_of(client.post("/api/v1/workflows/adapt", json={"workflow": wf, "overlay": ov}))
    agent = [d for d in result["node_dispositions"] if d["is_agent_role"]]
    non_agent = [d for d in result["node_dispositions"] if not d["is_agent_role"]]
    assert len(agent) == len(result["role_requirements"])
    assert len(non_agent) >= len(result["non_agent_dispositions"])


@pytest.mark.parametrize("sid", SCENARIOS)
def test_v1_v2_comparison(client, sid):
    result = result_of(client.post("/api/v1/workflows/compare-adaptations",
                                   json={"scenario_id": sid}))
    assert result["equivalence_state"] in ("BYTE_IDENTICAL", "SEMANTICALLY_EQUIVALENT")
