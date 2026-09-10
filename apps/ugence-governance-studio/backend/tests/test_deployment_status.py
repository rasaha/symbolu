"""MA-2 as amended (ADR_UGENCE_MODULE_ADMINISTRATION_SCOPING.md §15, MS-1 to MS-5): the
deployment status read, on the studio side of the seam.

What is asserted here is the shape of the seam rather than the gate's arithmetic,
which the deployment suite owns: a context built without a report reports the gap;
a report handed at composition comes back as seam states, checks and pins and
nothing else (MS-4: the certificate facts are excluded); the copy handed in cannot be
changed afterwards (MS-2: handed once, immutable in the process); and the route is a
read with no write beside it.
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.services.studio_v2 import (
    PIN_FIELDS,
    SEAM_STATE_FIELDS,
    STARTUP_ATTESTATION_CEILING,
    DeploymentStatusService,
)
from ugence_governance_studio_api.settings import ApiSettings

REPORT = {
    "deployment": "governance-studio-private-hosted",
    "deployment_version": "0.12.0",
    "frontend_version": "0.2.0",
    "frontend_build_hash": "f" * 64,
    "backend_api_version": "0.1.0",
    "api_contract": "governance_studio.api.v1",
    "openapi_sha256": "d" * 64,
    "synthetic_bundle_hash": "b" * 64,
    "constitution_registry": "configured",
    "authority_reads": "unset",
    "simulation_provider": "configured",
    "system_registry": "unwritable",
    "data_use_declarations": "unset",
    "vendor_declarations": "unset",
    "workflow_drafts": "unset",
    "checks": {"config_valid": True, "tls_certificate_valid": True, "openapi_hash_unchanged": True},
    "result": "PASS",
    "failure_code": "OK",
    "cert_subject": "CN=localhost",
    "cert_expiry": "Sep  8 00:00:00 2026 GMT",
}


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


@pytest.fixture()
def bare_client():
    return TestClient(create_v2_app(ApiSettings(environment="test")))


@pytest.fixture()
def client():
    studio = build_studio_context(deployment_report=dict(REPORT))
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


def test_a_context_built_without_a_report_reports_the_typed_gap(bare_client):
    gap = _result(bare_client.get("/api/v2/observe/deployment"))
    assert gap["available"] is False and gap["capability"] == "deployment_report"
    assert gap["result"] is None and "integrity gate" in gap["reason"]


def test_the_report_comes_back_as_seam_states_checks_and_pins(client):
    status = _result(client.get("/api/v2/observe/deployment"))
    assert status["available"] is True
    assert status["ceiling"] == STARTUP_ATTESTATION_CEILING
    result = status["result"]
    assert result["seams"] == {name: REPORT[name] for name in SEAM_STATE_FIELDS}
    assert set(result["seams"]) == set(SEAM_STATE_FIELDS) and len(SEAM_STATE_FIELDS) == 7
    assert result["checks"] == REPORT["checks"]
    assert result["result"] == "PASS" and result["failure_code"] == "OK"
    assert result["pins"] == {name: REPORT[name] for name in PIN_FIELDS}


def test_ms4_the_certificate_facts_do_not_travel(client):
    response = client.get("/api/v2/observe/deployment")
    assert "CN=localhost" not in response.text and "2026 GMT" not in response.text
    status = _result(response)
    assert status["excluded_fields"] == ["cert_subject", "cert_expiry"]
    result = status["result"]
    for key in ("cert_subject", "cert_expiry"):
        assert key not in result and key not in result["pins"] and key not in result["seams"]


def test_ms1_no_registry_row_is_present():
    """The nine console rows are struck from MA-2; nothing in the answer resembles one."""
    status = DeploymentStatusService(report=dict(REPORT)).read()
    text = str(status).lower()
    for word in ("maturity", "wiring", "layer", "modules", "question"):
        assert word not in text, word


def test_ms2_the_report_is_copied_at_composition_and_immutable_afterwards():
    handed = dict(REPORT)
    service = DeploymentStatusService(report=handed)
    handed["result"] = "FAIL"
    handed["checks"]["config_valid"] = False
    first = service.read()
    assert first["result"]["result"] == "PASS" and first["result"]["checks"]["config_valid"] is True
    first["result"]["seams"]["constitution_registry"] = "tampered"
    assert service.read()["result"]["seams"]["constitution_registry"] == "configured"


def test_a_missing_seam_field_reads_as_unset_not_as_an_error():
    partial = {k: v for k, v in REPORT.items() if k != "vendor_declarations"}
    status = DeploymentStatusService(report=partial).read()
    assert status["result"]["seams"]["vendor_declarations"] == "unset"


def test_the_route_is_a_read_and_no_write_stands_beside_it(client):
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        r = client.request(method, "/api/v2/observe/deployment", json={})
        assert r.status_code == 405, (method, r.status_code)


def test_the_service_has_no_method_that_could_change_the_report():
    public = [name for name in dir(DeploymentStatusService) if not name.startswith("_")]
    assert public == ["CAPABILITY", "read"], public
