"""Bring Your Workflow phase 3A in the P3E profile (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md
§24, owner ruling BW-3A).

The profile hands the Bring Your Workflow screen a tenant-bound sqlite drafts file under
the runtime volume. As tests: the typed gap when unset, the tenant that is server
configuration and never a request value, the path rules, the write that keeps the
validated canonical document and confers nothing, its typed refusals, the lineage,
restart, the absence of any advancing route, and the freeze that recorded the
amendment.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest
from starlette.testclient import TestClient

from ugence_workflow_drafts import CrossTenantRefused, SqliteWorkflowDrafts, workflow_digest

from governance_studio_deployment import DEPLOYMENT_NAME, DEPLOYMENT_VERSION, app as deployment_app
from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig, DeploymentConfigError
from governance_studio_deployment.drafts import DRAFTS_RECORDED_BY, open_workflow_drafts
from governance_studio_deployment.startup_integrity import IntegrityInputs, run_startup_integrity

from conftest import basic_auth
from depaths import APPROVED_OPS, CERTS, FRONTEND_DIR, MANIFEST, OPENAPI, REPO, SCENARIOS_ROOT, USERNAME  # noqa: F401

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TENANT = "tenant-1"
OTHER = "tenant-2"
ROUTE = "/api/v2/workflow-drafts"
EXAMPLE = os.path.join(REPO, "apps", "ugence-governance-studio", "frontend", "src", "features", "bring",
                       "example-workflow-ir.v1.json")


def _headers(**extra) -> dict:
    return {"Authorization": basic_auth(), "X-Ugence-Request": "GovernanceStudio",
            "Origin": "http://testserver", **extra}


def _config(password_hash: str, runtime_dir, **over) -> DeploymentConfig:
    return DeploymentConfig.from_env(
        mode="test", username=USERNAME, password_hash=password_hash,
        tls_cert_file=os.path.join(CERTS, "server.crt"), tls_key_file=os.path.join(CERTS, "server.key"),
        allowed_hosts=["localhost", "127.0.0.1", "testserver"], frontend_dir=FRONTEND_DIR,
        scenarios_root=SCENARIOS_ROOT, manifest_path=MANIFEST, runtime_dir=str(runtime_dir), **over,
    )


def _client(config: DeploymentConfig) -> TestClient:
    app = build_app(config, readiness=lambda: True, tracker=FailureTracker(), sleep=lambda _s: None)
    return TestClient(app, base_url="http://testserver", raise_server_exceptions=True)


def _integrity(config: DeploymentConfig, tmp_path):
    marker = tmp_path / "frontend-build.json"
    marker.write_text(json.dumps({"version": "0.2.0", "build_hash": "x"}))
    return run_startup_integrity(IntegrityInputs(config=config, openapi_path=OPENAPI,
                                                 approved_ops_path=APPROVED_OPS,
                                                 frontend_build_marker=str(marker)))


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


@pytest.fixture(scope="module")
def example():
    with open(EXAMPLE, encoding="utf-8") as fh:
        return json.load(fh)


def _body(example, **over):
    body = {"workflow": example, "contract_version": "workflow_ir.v1", "title": "Procurement intake",
            "claimed_owner_ref": "directory://people/owner-1"}
    body.update(over)
    return body


@pytest.fixture()
def runtime_dir(tmp_path):
    d = tmp_path / "runtime"
    d.mkdir()
    return d


@pytest.fixture()
def drafts_path(runtime_dir):
    return str(runtime_dir / "workflow-drafts.sqlite3")


@pytest.fixture()
def enabled(password_hash, runtime_dir, drafts_path) -> DeploymentConfig:
    return _config(password_hash, runtime_dir, tenant_id=TENANT, workflow_drafts_path=drafts_path)


def _count(path: str) -> int:
    store = SqliteWorkflowDrafts(path, tenant_id=TENANT)
    try:
        return store.count()
    finally:
        store.close()


# --------------------------------------------------------------------------- #
# the typed gap, the path rules, the tenant rule (BW-3A.2)
# --------------------------------------------------------------------------- #
def test_unset_is_the_typed_gap_on_every_route(config, example):
    assert config.workflow_drafts_configured is False
    with _client(config) as client:
        for response in (client.post(ROUTE, headers=_headers(), json=_body(example)),
                         client.get(ROUTE, headers=_headers()),
                         client.get(ROUTE + "/wfd_" + "0" * 32, headers=_headers())):
            r = _result(response)
            assert r["available"] is False and r["capability"] == "workflow_drafts"
            assert r["result"] is None


def test_missing_tenant_fails_validation_and_startup_integrity_with_the_seam_code(
        password_hash, runtime_dir, drafts_path, tmp_path):
    cfg = _config(password_hash, runtime_dir, workflow_drafts_path=drafts_path)
    errors = cfg.validate()
    assert any("requires UGENCE_STUDIO_TENANT_ID" in e for e in errors)
    result = _integrity(cfg, tmp_path)
    assert result.ok is False and result.code == "GOVERNANCE_STUDIO_P3E_WORKFLOW_DRAFTS_SEAM_FAILED"
    good = _config(password_hash, runtime_dir, tenant_id=TENANT, workflow_drafts_path=drafts_path)
    assert good.validate() == []
    report = _integrity(good, tmp_path).report
    assert report["workflow_drafts"] == "configured" and report["vendor_declarations"] == "unset"


@pytest.mark.parametrize("path", [":memory:", "file::memory:?cache=shared", "relative.sqlite3",
                                  "/elsewhere/d.sqlite3"])
def test_a_path_outside_the_volume_or_in_memory_is_refused(password_hash, runtime_dir, path):
    cfg = _config(password_hash, runtime_dir, tenant_id=TENANT, workflow_drafts_path=path)
    assert any("UGENCE_STUDIO_WORKFLOW_DRAFTS_PATH" in e for e in cfg.validate())


def test_an_unwritable_directory_fails_startup_integrity_before_bind(password_hash, runtime_dir, tmp_path):
    cfg = _config(password_hash, runtime_dir, tenant_id=TENANT,
                  workflow_drafts_path=str(runtime_dir / "missing" / "d.sqlite3"))
    assert cfg.validate() == []
    result = _integrity(cfg, tmp_path)
    assert result.ok is False and result.checks["workflow_drafts_writable"] is False
    assert result.code == "GOVERNANCE_STUDIO_P3E_WORKFLOW_DRAFTS_SEAM_FAILED"


# --------------------------------------------------------------------------- #
# the write: the validated canonical document, the deployment as recorder, the
# claimed owner unproven, and what never crosses (BW-3A.1, BW-3A.5)
# --------------------------------------------------------------------------- #
def test_save_keeps_the_canonical_document_with_the_deployment_as_recorder(enabled, drafts_path, example):
    with _client(enabled) as client:
        r = _result(client.post(ROUTE, headers=_headers(), json=_body(example)))
    assert r["saved"] is True and r["tenant_id"] == TENANT
    assert r["recorded_by"] == DRAFTS_RECORDED_BY == f"{DEPLOYMENT_NAME}/{DEPLOYMENT_VERSION}"
    assert r["lifecycle"] == "DRAFT" and r["claimed_owner_status"] == "PRESENTED_UNPROVEN"
    assert r["confers"].startswith("nothing") and r["store_kind"] == "SqliteWorkflowDrafts"
    assert r["workflow_digest"] == workflow_digest(example)
    assert r["record"]["draft"]["claimed_owner_ref"] == "directory://people/owner-1"
    assert r["record"]["draft"]["tenant_id"] == TENANT
    assert _count(drafts_path) == 1


def test_a_caller_supplied_tenant_id_or_lifecycle_is_a_contract_refusal(enabled, example):
    with _client(enabled) as client:
        for extra in ({"tenant_id": OTHER}, {"draft_id": "wfd_x"}, {"recorded_by": "me"},
                      {"lifecycle": "APPROVED"}, {"claimed_owner_assurance": "IDP_AUTHENTICATED"},
                      {"approved": True}, {"status": "COMPILED"}):
            response = client.post(ROUTE, headers=_headers(), json=_body(example, **extra))
            assert response.status_code == 422, (extra, response.text)


@pytest.mark.parametrize("over,code", [
    ({"contract_version": "workflow_ir.v9"}, "draft_refused"),
    ({"workflow": {"ir_version": "workflow_ir.v2", "nodes": [], "edges": []}, "contract_version": "workflow_ir.v2"}, "draft_refused"),
    ({"supersedes": "wfd_" + "0" * 32}, "supersession_refused"),
    ({"registration_ref": "reg_" + "0" * 32, "registration_digest": "a" * 64}, "registration_link_refused"),
])
def test_invalid_unsupported_unlinked_and_unrecorded_inputs_are_typed_refusals(
        enabled, drafts_path, example, over, code):
    with _client(enabled) as client:
        r = _result(client.post(ROUTE, headers=_headers(), json=_body(example, **over)))
    assert r["refused"] is True and r["code"] == code, r
    assert _count(drafts_path) == 0


def test_the_bw2_limits_apply_and_nothing_is_kept_past_them(enabled, drafts_path):
    too_many = {"ir_version": "workflow_ir.v2", "nodes": [{"node_id": f"n{i}"} for i in range(201)], "edges": []}
    with _client(enabled) as client:
        response = client.post(ROUTE, headers=_headers(), json=_body(too_many, contract_version="workflow_ir.v2"))
    assert response.status_code == 422 and response.json()["error"]["code"] == "workflow_too_complex"
    assert _count(drafts_path) == 0


# --------------------------------------------------------------------------- #
# lineage (BW-3A.3), the tenant boundary, restart
# --------------------------------------------------------------------------- #
def test_revisions_supersede_and_are_never_edited(enabled, drafts_path, example):
    with _client(enabled) as client:
        first = _result(client.post(ROUTE, headers=_headers(), json=_body(example)))
        dup = _result(client.post(ROUTE, headers=_headers(), json=_body(example)))
        assert dup["code"] == "draft_duplicate"
        second = _result(client.post(ROUTE, headers=_headers(),
                                     json=_body(example, title="Revised", supersedes=first["draft_id"])))
        assert second["saved"] is True
        third = _result(client.post(ROUTE, headers=_headers(),
                                    json=_body(example, title="Third", supersedes=first["draft_id"])))
        assert third["code"] == "supersession_refused" and "already superseded" in third["reason"]
        heads = _result(client.get(ROUTE, headers=_headers()))
        assert [row["draft_id"] for row in heads["result"]] == [second["draft_id"]]
        everything = _result(client.get(ROUTE, headers=_headers(), params={"include_superseded": "true"}))
        assert everything["count"] == 2 and everything["result"][0]["superseded_by"] == second["draft_id"]
        read = _result(client.get(f"{ROUTE}/{second['draft_id']}", headers=_headers()))
        assert read["lineage"] == [first["draft_id"], second["draft_id"]]
        assert read["record"]["workflow"] == example
    assert _count(drafts_path) == 2


def test_a_cross_tenant_read_is_refused_and_a_foreign_file_is_refused_before_bind(
        password_hash, runtime_dir, drafts_path, enabled, example):
    with _client(enabled) as client:
        _result(client.post(ROUTE, headers=_headers(), json=_body(example)))
        listed = _result(client.get(ROUTE, headers=_headers()))
        assert listed["tenant_id"] == TENANT and all(row["tenant_id"] == TENANT for row in listed["result"])
    store = open_workflow_drafts(drafts_path, tenant_id=TENANT, production_mode=False)
    try:
        with pytest.raises(CrossTenantRefused):
            store.drafts_for_tenant(tenant_id=OTHER)
    finally:
        store.close()
    foreign = _config(password_hash, runtime_dir, tenant_id=OTHER, workflow_drafts_path=drafts_path)
    with pytest.raises(DeploymentConfigError, match="another tenant"):
        deployment_app._build_backend(foreign)


def test_records_survive_a_restart_of_the_profile(enabled, example):
    with _client(enabled) as client:
        first = _result(client.post(ROUTE, headers=_headers(), json=_body(example)))
    with _client(enabled) as client:  # a second process over the same file
        listed = _result(client.get(ROUTE, headers=_headers()))
        assert [row["draft_id"] for row in listed["result"]] == [first["draft_id"]]
        read = _result(client.get(f"{ROUTE}/{first['draft_id']}", headers=_headers()))
        assert read["found"] is True and read["record_digest"] == first["record_digest"]


# --------------------------------------------------------------------------- #
# save is the only write; nothing approves, compiles, publishes or exports
# --------------------------------------------------------------------------- #
def test_no_advancing_or_mutating_route_exists_on_the_composed_profile(enabled):
    with _client(enabled) as client:
        for method, path in (("PUT", ROUTE + "/wfd_x"), ("PATCH", ROUTE + "/wfd_x"), ("DELETE", ROUTE + "/wfd_x"),
                             ("POST", ROUTE + "/wfd_x/approve"), ("POST", ROUTE + "/wfd_x/compile"),
                             ("POST", ROUTE + "/wfd_x/publish"), ("POST", ROUTE + "/wfd_x/export"),
                             ("POST", ROUTE + "/wfd_x/submit"), ("POST", ROUTE + "/wfd_x/activate")):
            response = client.request(method, path, headers=_headers(), json={})
            assert response.status_code in (404, 405), (method, path, response.status_code)


def test_the_v1_bring_your_workflow_operations_are_unchanged(enabled, example):
    with _client(enabled) as client:
        r = _result(client.post("/api/v1/workflows/validate", headers=_headers(),
                                json={"contract_version": "workflow_ir.v1", "workflow": example}))
    assert r["validation_state"] == "VALID"


# --------------------------------------------------------------------------- #
# the approved profile: the configuration value, the freeze, the composition record
# --------------------------------------------------------------------------- #
def test_the_approved_runtime_config_records_the_seam_and_the_eighth_amendment():
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    assert cfg["deployment_version"] == DEPLOYMENT_VERSION
    added = cfg["configuration_added"]["UGENCE_STUDIO_WORKFLOW_DRAFTS_PATH"]
    assert "requires UGENCE_STUDIO_TENANT_ID" in added and "never taken from a request" in added
    seam = cfg["workflow_drafts"]
    assert "BW-3A DRAFTS_AUTHORIZED_NOW" in seam["ruling"] and "blocked on AP-3" in seam["ruling"]
    assert "no server, no driver, no DSN" in seam["store"]
    assert "never accepted from the client" in seam["tenant_binding"]
    assert "never the uploaded n8n or BPMN file" in seam["what_is_recorded"]
    assert "PRESENTED_UNPROVEN" in seam["claimed_owner"]
    assert seam["lifecycle"].startswith("DRAFT") and "refusal to compile a DRAFT stands" in seam["lifecycle"]
    assert seam["reachable_acts"].startswith("save (the only write")
    assert "no edit, deletion, approval, compilation, publication, export" in seam["reachable_acts"]
    assert seam["maturity"].startswith("REFERENCE_GRADE")
    assert "packages/integration/workflow-drafts" in cfg["first_party_packages_in_image"]
    assert any(h.startswith("workflow_drafts (seam 12") for h in cfg["front_door_seams"]["handed_to_build_studio_context"])
    assert "workflow_drafts" in cfg["deployment_status"]["field_set"]["seam_states"]
    contract = os.path.join(REPO, "apps", "ugence-governance-studio", "contracts")
    with open(os.path.join(contract, "openapi_v2.json"), "rb") as fh:
        committed = hashlib.sha256(fh.read()).hexdigest()
    assert cfg["frozen"]["openapi_v2_sha256"] == committed
    record = json.load(open(os.path.join(contract, "openapi_v2.amendments.json"), encoding="utf-8"))
    (mine,) = [a for a in record["amendments"] if a["amendment_id"] == "v2-A8"]
    assert set(mine["operations_added"]) == {"v2_workflow_drafts_save", "v2_workflow_drafts_list",
                                             "v2_workflow_drafts_read"}
    assert record["amendments"][-1]["sha256"] == committed == mine["sha256"]
    assert cfg["frozen"]["openapi_v2_amendment"].startswith("v2-A8 (BW-3A")
    # the ratified v1 bytes are untouched
    assert cfg["frozen"]["api_contract"] == "governance_studio.api.v1"
    assert cfg["frozen"]["openapi_sha256"] == "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"
    head = json.load(open(os.path.join(HERE, "composition-record.json"), encoding="utf-8"))
    assert head["seams_handed_to_build_studio_context"][-1] == "workflow_drafts"
    assert head["supersedes_record"] == "composition-record.seam-11.json"
    assert head["binding"]["binding_id"].endswith("front-door/seam-12")
    assert head["binding"]["system_version"] == DEPLOYMENT_VERSION
    assert "BW-3A" in head["registration"]["notes"] and "never edited" in head["registration"]["notes"]
