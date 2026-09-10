"""MA-2 as amended in the P3E profile (ADR_UGENCE_MODULE_ADMINISTRATION_SCOPING.md §15,
rulings MS-1 to MS-5): the Status panel's one read through the deployed studio.

What only this suite can assert, because it is about the deployment's side of the
seam: the gate's own report is what reaches the studio (MS-2), handed once, and the
file under the runtime volume is read by nothing; the seam states the panel shows are
the states the gate computed for THIS configuration; the certificate facts stay
behind (MS-4); the route sits behind the access gate, is a read, and has no write
beside it; and the freeze records the seventh amendment, the version moved, the
composition record names the new seam, and nothing else moved: no configuration
value, no image package, no SD-1 entry, no console route.
"""
from __future__ import annotations

import hashlib
import json
import os

from starlette.testclient import TestClient

from governance_studio_deployment import DEPLOYMENT_NAME, DEPLOYMENT_VERSION
from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig
from governance_studio_deployment.startup_integrity import (
    IntegrityInputs,
    run_startup_integrity,
    write_report,
)

from depaths import APPROVED_OPS, CERTS, FRONTEND_DIR, MANIFEST, OPENAPI, REPO, SCENARIOS_ROOT, USERNAME
from conftest import basic_auth

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACTS = os.path.join(REPO, "apps", "ugence-governance-studio", "contracts")
ROUTE = "/api/v2/observe/deployment"
SEAMS = ("constitution_registry", "authority_reads", "simulation_provider",
         "system_registry", "data_use_declarations", "vendor_declarations",
         # Bring Your Workflow phase 3A (authority-plane ADR §24): the seventh seam state.
         "workflow_drafts")


def _headers(**extra) -> dict:
    return {"Authorization": basic_auth(), "X-Ugence-Request": "GovernanceStudio",
            "Origin": "http://testserver", **extra}


def _config(password_hash: str, tmp_path, **over) -> DeploymentConfig:
    return DeploymentConfig.from_env(
        mode="test", username=USERNAME, password_hash=password_hash,
        tls_cert_file=os.path.join(CERTS, "server.crt"), tls_key_file=os.path.join(CERTS, "server.key"),
        allowed_hosts=["localhost", "127.0.0.1", "testserver"], frontend_dir=FRONTEND_DIR,
        scenarios_root=SCENARIOS_ROOT, manifest_path=MANIFEST, runtime_dir=str(tmp_path), **over,
    )


def _gate(config: DeploymentConfig) -> dict:
    """The real gate, over the real inputs: its report is what the panel shows."""
    marker = os.path.join(os.path.dirname(os.path.abspath(config.frontend_dir)), "frontend-build.json")
    result = run_startup_integrity(IntegrityInputs(
        config=config, openapi_path=OPENAPI, approved_ops_path=APPROVED_OPS, frontend_build_marker=marker))
    return result.report


def _client(config: DeploymentConfig, report: dict | None) -> TestClient:
    app = build_app(config, readiness=lambda: True, tracker=FailureTracker(), sleep=lambda _s: None,
                    deployment_report=report)
    return TestClient(app, base_url="http://testserver", raise_server_exceptions=True)


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


def _cfg() -> dict:
    return json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))


# -- the seam ---------------------------------------------------------------- #

def test_without_a_report_the_route_reports_the_typed_gap_behind_the_gate(config):
    with _client(config, None) as client:
        assert client.get(ROUTE).status_code == 401
        assert client.get(ROUTE, headers={"Authorization": basic_auth(pw="wrong")}).status_code == 401
        gap = _result(client.get(ROUTE, headers=_headers()))
        assert gap["available"] is False and gap["capability"] == "deployment_report"
        assert gap["result"] is None and "integrity gate" in gap["reason"]


def test_the_gates_own_report_reaches_the_panel_and_a_bare_config_reads_all_six_seams_unset(config):
    report = _gate(config)
    with _client(config, report) as client:
        status = _result(client.get(ROUTE, headers=_headers()))
    assert status["available"] is True
    assert status["result"]["seams"] == {name: "unset" for name in SEAMS}
    assert status["result"]["checks"] == report["checks"]
    assert status["result"]["result"] == report["result"]
    assert status["result"]["failure_code"] == report["failure_code"]
    pins = status["result"]["pins"]
    assert pins["deployment"] == DEPLOYMENT_NAME and pins["deployment_version"] == DEPLOYMENT_VERSION
    assert pins["api_contract"] == "governance_studio.api.v1"
    assert "not a reachable engine" in status["ceiling"]


def test_a_configured_seam_reads_configured_and_an_unwritable_one_reads_unwritable(password_hash, tmp_path):
    (tmp_path / "locked").mkdir()
    os.chmod(tmp_path / "locked", 0o500)
    try:
        cfg = _config(password_hash, tmp_path,
                      constitution_registry_path=str(tmp_path / "registry.sqlite"),
                      system_registry_path=str(tmp_path / "locked" / "systems.sqlite"),
                      tenant_id="tenant-a")
        report = _gate(cfg)
        seams = {name: report[name] for name in SEAMS}
        if os.access(tmp_path / "locked", os.W_OK):  # running as root: the lock is not a lock
            assert seams["system_registry"] == "configured"
        else:
            assert seams["system_registry"] == "unwritable"
        assert seams["constitution_registry"] == "configured"
        # the studio is built over an unlocked config so composition itself succeeds;
        # the report handed is the one computed above, and the panel shows it verbatim
        with _client(_config(password_hash, tmp_path), report) as client:
            status = _result(client.get(ROUTE, headers=_headers()))
        assert status["result"]["seams"] == seams
    finally:
        os.chmod(tmp_path / "locked", 0o700)


def test_ms4_the_certificate_facts_stay_behind(config):
    report = _gate(config)
    assert report["cert_subject"] is not None, "the gate does record them; the panel must not show them"
    with _client(config, report) as client:
        response = client.get(ROUTE, headers=_headers())
    body = response.text
    assert report["cert_subject"] not in body
    assert str(report["cert_expiry"]) not in body
    status = response.json()["result"]
    assert status["excluded_fields"] == ["cert_subject", "cert_expiry"]
    assert "cert_subject" not in status["result"]["pins"]


def test_ms2_the_report_is_handed_once_and_the_file_under_the_volume_is_read_by_nothing(config, tmp_path):
    report = _gate(config)
    with _client(config, report) as client:
        first = _result(client.get(ROUTE, headers=_headers()))
        # the operator's copy on the volume: written, then corrupted, then deleted
        path = os.path.join(config.runtime_dir, "startup-integrity.json")
        write_report(type("R", (), {"report": report})(), path)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"constitution_registry": "configured", "result": "PASS"}')
        second = _result(client.get(ROUTE, headers=_headers()))
        os.remove(path)
        third = _result(client.get(ROUTE, headers=_headers()))
        # the object handed in, mutated after composition
        report["constitution_registry"] = "configured"
        report["checks"]["config_valid"] = not report["checks"]["config_valid"]
        fourth = _result(client.get(ROUTE, headers=_headers()))
    assert first == second == third == fourth
    assert first["result"]["seams"]["constitution_registry"] == "unset"


def test_the_route_is_a_read_with_no_write_beside_it(config):
    with _client(config, _gate(config)) as client:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            r = client.request(method, ROUTE, headers=_headers(**{"Content-Type": "application/json"}), json={})
            assert r.status_code in (404, 405), (method, r.status_code)


def test_ms1_no_registry_row_and_no_console_route_appear(config):
    with _client(config, _gate(config)) as client:
        # the payload only: the envelope's own SYNTHETIC_NOTICE block is named "maturity"
        body = json.dumps(_result(client.get(ROUTE, headers=_headers()))).lower()
    for word in ("maturity", "wiring", "hybrid llm", "actiongate", "/v1/modules", "modules"):
        assert word not in body, word


# -- the recorded composition ------------------------------------------------ #

def test_the_seventh_amendment_is_recorded_in_the_p3e_freeze():
    cfg = _cfg()
    record = json.load(open(os.path.join(CONTRACTS, "openapi_v2.amendments.json"), encoding="utf-8"))
    with open(os.path.join(CONTRACTS, "openapi_v2.json"), "rb") as fh:
        committed = hashlib.sha256(fh.read()).hexdigest()
    # Found by id, not by position: seam 12 (workflow drafts, BW-3A) appended v2-A8
    # after this seam's v2-A7, and the committed bytes are the chain's last entry.
    (a6,) = [a for a in record["amendments"] if a["amendment_id"] == "v2-A6"]
    (a7,) = [a for a in record["amendments"] if a["amendment_id"] == "v2-A7"]
    assert a7["previous_sha256"] == a6["sha256"]
    assert a7["operations_added"] == ["v2_observe_deployment"] and a7["operations_removed"] == []
    assert a7["paths_added"] == ["/api/v2/observe/deployment"]
    assert "MS-3 OBSERVE_DEPLOYMENT_ONE_READ" in a7["ruling"]
    assert a7["sha256"] == "c6785b267dafe9e2593b58744890606727b26d450ffd1a32f9b544f95a2d0f3e"
    assert cfg["frozen"]["openapi_v2_sha256"] == committed == record["amendments"][-1]["sha256"]
    # The freeze note is prepended by each new amendment: v2-A8 (BW-3A, Bring Your
    # Workflow phase 3A) now leads and this seam's v2-A7 entry sits behind it.
    assert cfg["frozen"]["openapi_v2_amendment"].startswith("v2-A8 (BW-3A")
    for tag in ("v2-A7 (MS-3", "v2-A6", "v2-A5", "v2-A4", "v2-A3", "v2-A2", "v2-A1"):
        assert tag in cfg["frozen"]["openapi_v2_amendment"]
    assert cfg["frozen"]["openapi_sha256"] == "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"
    # Against the constant: seam 12 (workflow drafts) moved the version past 0.12.0.
    assert cfg["deployment_version"] == DEPLOYMENT_VERSION


def test_the_runtime_config_records_the_seam_and_nothing_else_moved():
    cfg = _cfg()
    seam = cfg["deployment_status"]
    assert seam["operations"] == ["v2_observe_deployment"]
    assert seam["sd1_entries_added"] == []
    assert seam["field_set"]["seam_states"] == list(SEAMS)
    assert seam["excluded_fields"] == ["cert_subject", "cert_expiry"]
    assert seam["registry_rows"].startswith("refused (MS-1)")
    assert seam["live_probe"].startswith("none")
    assert seam["screen"].startswith("/studio/status")
    assert "once" in seam["source"] and "read by no route" in seam["source"]
    # nothing else moved by this seam; the one value, package and seam beyond MS-3's
    # count are seam 12's (workflow drafts, BW-3A), named here so a further addition
    # still fails
    assert len(cfg["configuration_added"]) == 9, "no configuration value was added"
    assert "UGENCE_STUDIO_WORKFLOW_DRAFTS_PATH" in cfg["configuration_added"]
    assert "console" not in " ".join(cfg["first_party_packages_in_image"])
    assert len(cfg["first_party_packages_in_image"]) == 18, "no image package was added"
    assert "packages/integration/workflow-drafts" in cfg["first_party_packages_in_image"]
    assert len(cfg["front_door_seams"]["handed_to_build_studio_context"]) == 9
    assert any(s.startswith("console_base_url") for s in cfg["front_door_seams"]["absent_by_ruling"])
    (permitted,) = cfg["external_network_egress"]["permitted"]
    assert len(permitted["routes"]) == 7, "no egress route was added"
    assert "UGENCE_STUDIO_CONSOLE" not in json.dumps(cfg)


def test_the_composition_record_names_the_new_seam_and_the_prior_record_is_kept():
    # This seam's record was the head at 0.12.0; seam 12 (workflow drafts, BW-3A)
    # superseded it and kept it byte-for-byte as composition-record.seam-11.json.
    mine = json.load(open(os.path.join(HERE, "composition-record.seam-11.json"), encoding="utf-8"))
    assert mine["seams_handed_to_build_studio_context"][-1] == "deployment_report"
    assert mine["supersedes_record"] == "composition-record.seam-10.json"
    assert mine["binding"]["binding_id"].endswith("front-door/seam-11")
    assert mine["binding"]["system_version"] == "0.12.0"
    notes = mine["registration"]["notes"]
    assert "MS-1 to MS-5" in notes and "never edited" in notes
    prior = json.load(open(os.path.join(HERE, "composition-record.seam-10.json"), encoding="utf-8"))
    assert prior["seams_handed_to_build_studio_context"][-1] == "received_clearances"
    assert prior["supersedes_record"] == "composition-record.seam-9.json"
    assert mine["registration"]["supersedes"] == prior["registration"]["registration_id"]
    head = json.load(open(os.path.join(HERE, "composition-record.json"), encoding="utf-8"))
    assert head["supersedes_record"] == "composition-record.seam-11.json"
    assert head["registration"]["supersedes"] == mine["registration"]["registration_id"]
    assert head["binding"]["system_version"] == DEPLOYMENT_VERSION
