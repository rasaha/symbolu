"""Operational endpoint tests (§7, §28)."""
from __future__ import annotations

from ugence_governance_studio_api import create_app
from ugence_governance_studio_api.settings import ApiSettings
from starlette.testclient import TestClient


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["ready"] is True
    assert body["checks"]["fixture_hashes_match"] is True
    assert body["checks"]["supported_contracts_present"] is True


def test_not_ready_condition():
    # Point the catalog at an empty root → manifests fail to load → 503.
    app = create_app(ApiSettings(environment="test", scenario_root="/nonexistent",
                                 expected_output_root="/nonexistent"))
    client = TestClient(app)
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["ready"] is False


def test_version(client):
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert body["api_contract_version"] == "governance_studio.api.v1"
    assert body["awc_distribution_version"] == "0.2.1"
    assert "workflow_ir.v1" in body["supported_workflow_contracts"]
    assert "workflow_ir.v2" in body["supported_workflow_contracts"]


def test_build_metadata():
    app = create_app(ApiSettings(environment="test", build_commit="abc123", build_id="ci-42"))
    client = TestClient(app)
    body = client.get("/version").json()
    assert body["build_commit"] == "abc123"
    assert body["build_id"] == "ci-42"


def test_maturity_flags(client):
    m = client.get("/version").json()["maturity"]
    assert m["deterministic_demo_api_implemented"] is True
    assert m["workflow_ir_v1_supported"] is True
    assert m["workflow_ir_v2_supported"] is True
    assert m["frontend_implemented"] is False
    # GAS-4 shipped the six studio screens; GAS-5 (Langflow import) is deferred by
    # owner ruling and must not drift to True without a new ruling.
    assert m["studio_screens_implemented"] is True
    assert m["langflow_import_implemented"] is False
    # GAS-7 HR-D: the Review Queue and Run Detail screens relay to the governed review
    # service. The approver stays a presented reference; no identity provider exists.
    assert m["human_review_implemented"] is True
    assert m["authentication_implemented"] is False
    assert m["agent_execution_implemented"] is False
    assert m["permission_granting_implemented"] is False
    assert m["pilot_validated"] is False
    assert m["production_certified"] is False
