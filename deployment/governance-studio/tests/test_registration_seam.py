"""Front-door seam 5 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md FD-1, FD-3, FD-4, FD-9).

The P3E profile hands the Registration screen a tenant-bound sqlite system registry
under the runtime volume. The failure matrix of ADR §10.4 as tests: missing tenant,
blank owner or label, inadmissible supersession, cross-tenant read, restart, and the
contract-byte amendment recorded.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest
from starlette.testclient import TestClient

from ugence_ai_system_registry import CrossTenantRefused, SqliteSystemRegistry

from governance_studio_deployment import DEPLOYMENT_NAME, DEPLOYMENT_VERSION, app as deployment_app
from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig, DeploymentConfigError
from governance_studio_deployment.registration import REGISTERED_BY, open_system_registry
from governance_studio_deployment.startup_integrity import IntegrityInputs, run_startup_integrity

from conftest import basic_auth
from depaths import APPROVED_OPS, CERTS, FRONTEND_DIR, MANIFEST, OPENAPI, SCENARIOS_ROOT, USERNAME  # noqa: F401

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(HERE))
TENANT = "tenant-1"
OTHER = "tenant-2"
D = "c" * 64


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


def _body(**over):
    body = {"binding": {"binding_id": "bind-1", "subject_id": "subject-1", "context_id": "ctx-1",
                        "context_digest": D, "system_id": "hiring-screener", "system_version": "1.0.0",
                        "configuration_id": "cfg-1", "configuration_digest": D},
            "owner_ref": "directory://people/owner-1", "classification_label": "high-risk",
            "validity": {"issued_at": "2026-09-01T00:00:00+00:00", "expires_at": "2027-09-01T00:00:00+00:00"}}
    body.update(over)
    return body


@pytest.fixture()
def runtime_dir(tmp_path):
    d = tmp_path / "runtime"
    d.mkdir()
    return d


@pytest.fixture()
def registry_path(runtime_dir):
    return str(runtime_dir / "system-registry.sqlite3")


@pytest.fixture()
def enabled(password_hash, runtime_dir, registry_path) -> DeploymentConfig:
    return _config(password_hash, runtime_dir, tenant_id=TENANT, system_registry_path=registry_path)


# --------------------------------------------------------------------------- #
# unset: the typed gap; the path rules; the tenant rule
# --------------------------------------------------------------------------- #
def test_unset_is_the_typed_gap_on_both_routes(config):
    assert config.system_registry_configured is False
    with _client(config) as client:
        for response in (client.post("/api/v2/registry/registrations", headers=_headers(), json=_body()),
                         client.get("/api/v2/registry/registrations", headers=_headers())):
            r = _result(response)
            assert r["available"] is False and r["capability"] == "system_registry" and r["result"] is None


def test_missing_tenant_fails_validation_and_startup_integrity_with_the_seam_code(
        password_hash, runtime_dir, registry_path, tmp_path):
    cfg = _config(password_hash, runtime_dir, system_registry_path=registry_path)
    errors = cfg.validate()
    assert any("requires UGENCE_STUDIO_TENANT_ID" in e for e in errors)
    result = _integrity(cfg, tmp_path)
    assert result.ok is False and result.code == "GOVERNANCE_STUDIO_P3E_REGISTRATION_SEAM_FAILED"
    # the tenant may stand alone for the system registry (no policy identities needed)
    good = _config(password_hash, runtime_dir, tenant_id=TENANT, system_registry_path=registry_path)
    assert good.validate() == []
    report = _integrity(good, tmp_path).report
    assert report["system_registry"] == "configured" and report["authority_reads"] == "unset"


@pytest.mark.parametrize("path", [":memory:", "file::memory:?cache=shared", "relative.sqlite3", "/elsewhere/r.sqlite3"])
def test_a_path_outside_the_volume_or_in_memory_is_refused(password_hash, runtime_dir, path):
    cfg = _config(password_hash, runtime_dir, tenant_id=TENANT, system_registry_path=path)
    assert any("UGENCE_STUDIO_SYSTEM_REGISTRY_PATH" in e for e in cfg.validate())


def test_an_unwritable_directory_fails_startup_integrity_before_bind(password_hash, runtime_dir, tmp_path):
    cfg = _config(password_hash, runtime_dir, tenant_id=TENANT,
                  system_registry_path=str(runtime_dir / "missing" / "registry.sqlite3"))
    assert cfg.validate() == []
    result = _integrity(cfg, tmp_path)
    assert result.ok is False and result.checks["system_registry_writable"] is False
    assert result.code == "GOVERNANCE_STUDIO_P3E_REGISTRATION_SEAM_FAILED"


# --------------------------------------------------------------------------- #
# the write and its refusals, through the composed profile
# --------------------------------------------------------------------------- #
def test_register_records_with_the_deployment_as_registrant_and_the_owner_unproven(enabled, registry_path):
    with _client(enabled) as client:
        r = _result(client.post("/api/v2/registry/registrations", headers=_headers(), json=_body()))
    assert r["registered"] is True and r["tenant_id"] == TENANT
    assert r["registered_by"] == REGISTERED_BY == f"{DEPLOYMENT_NAME}/{DEPLOYMENT_VERSION}"
    assert r["owner_ref_status"] == "PRESENTED_UNPROVEN" and r["confers"].startswith("nothing")
    assert r["record"]["registration"]["registered_by"] == REGISTERED_BY
    store = SqliteSystemRegistry(registry_path, tenant_id=TENANT)
    try:
        assert store.count() == 1
    finally:
        store.close()


@pytest.mark.parametrize("over,code", [
    ({"owner_ref": ""}, "registration_refused"),
    ({"classification_label": " "}, "registration_refused"),
    ({"supersedes": "reg_" + "0" * 32}, "supersession_refused"),
])
def test_blank_owner_or_label_and_an_inadmissible_supersession_are_typed_refusals(enabled, registry_path, over, code):
    with _client(enabled) as client:
        r = _result(client.post("/api/v2/registry/registrations", headers=_headers(), json=_body(**over)))
    assert r["refused"] is True and r["code"] == code
    store = SqliteSystemRegistry(registry_path, tenant_id=TENANT)
    try:
        assert store.count() == 0
    finally:
        store.close()


# --------------------------------------------------------------------------- #
# cross-tenant, restart
# --------------------------------------------------------------------------- #
def test_a_cross_tenant_read_is_refused_and_a_foreign_file_is_refused_before_bind(
        password_hash, runtime_dir, registry_path, enabled):
    with _client(enabled) as client:
        _result(client.post("/api/v2/registry/registrations", headers=_headers(), json=_body()))
        listed = _result(client.get("/api/v2/registry/registrations", headers=_headers(),
                                    params={"as_of": "2026-10-01T00:00:00+00:00"}))
        assert listed["tenant_id"] == TENANT and listed["count"] == 1
        assert all(rec["binding"]["tenant_id"] == TENANT for rec in listed["result"])
    store = open_system_registry(registry_path, tenant_id=TENANT, production_mode=False)
    try:
        with pytest.raises(CrossTenantRefused):
            store.registrations_for_tenant(tenant_id=OTHER, as_of=__import__("datetime").datetime(
                2026, 10, 1, tzinfo=__import__("datetime").timezone.utc))
    finally:
        store.close()
    # the same file opened for another tenant is a deployment refusal before anything binds
    foreign = _config(password_hash, runtime_dir, tenant_id=OTHER, system_registry_path=registry_path)
    with pytest.raises(DeploymentConfigError, match="another tenant"):
        deployment_app._build_backend(foreign)


def test_records_survive_a_restart_of_the_profile(enabled):
    with _client(enabled) as client:
        first = _result(client.post("/api/v2/registry/registrations", headers=_headers(), json=_body()))
    with _client(enabled) as client:  # a second process over the same file
        listed = _result(client.get("/api/v2/registry/registrations", headers=_headers(),
                                    params={"as_of": "2026-10-01T00:00:00+00:00"}))
        assert [rec["registration"]["registration_id"] for rec in listed["result"]] == [first["registration_id"]]
        dup = _result(client.post("/api/v2/registry/registrations", headers=_headers(), json=_body()))
        assert dup["refused"] is True and dup["code"] == "registration_duplicate"


# --------------------------------------------------------------------------- #
# FD-9.5, the contract amendment, the other screens
# --------------------------------------------------------------------------- #
def test_register_is_the_only_write(enabled):
    with _client(enabled) as client:
        for method, path in (("PUT", "/api/v2/registry/registrations/reg_x"),
                             ("DELETE", "/api/v2/registry/registrations/reg_x"),
                             ("POST", "/api/v2/registry/registrations/reg_x/revoke"),
                             ("POST", "/api/v2/registry/admit"), ("POST", "/api/v2/registry/approve")):
            assert client.request(method, path, headers=_headers(), json={}).status_code in (404, 405), path
        assert client.post("/api/v2/registry/registrations", json=_body()).status_code == 401


def test_the_contract_amendment_is_recorded_in_the_p3e_freeze():
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    record = json.load(open(os.path.join(REPO, "apps", "ugence-governance-studio", "contracts",
                                         "openapi_v2.amendments.json"), encoding="utf-8"))
    with open(os.path.join(REPO, "apps", "ugence-governance-studio", "contracts", "openapi_v2.json"), "rb") as fh:
        current = hashlib.sha256(fh.read()).hexdigest()
    last = record["amendments"][-1]
    assert cfg["frozen"]["openapi_v2_sha256"] == current == last["sha256"]
    assert last["amendment_id"] in cfg["frozen"]["openapi_v2_amendment"]
    assert record["original_sha256"] in cfg["frozen"]["openapi_v2_amendment"]
    # v2-A1 is this seam's amendment; a later seam (6, FD-10.4) amended once more
    (a1,) = [a for a in record["amendments"] if a["amendment_id"] == "v2-A1"]
    assert set(a1["operations_added"]) == {"v2_registry_register", "v2_registry_list"}
    assert "v2-A1" in cfg["frozen"]["openapi_v2_amendment"]
    # v1 stays frozen
    assert cfg["frozen"]["openapi_sha256"] == "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"


def test_v1_and_the_other_v2_screens_behave_as_before(enabled):
    with _client(enabled) as client:
        assert client.get("/api/v1/scenarios", headers=_headers()).status_code == 200
        review = _result(client.get("/api/v2/review/queue", headers=_headers()))
        assert review["available"] is False and review["capability"] == "review_service"
        authority = _result(client.get("/api/v2/authority/policies", headers=_headers()))
        assert authority["available"] is False and authority["capability"] == "authority_registry"
        simulate = _result(client.post("/api/v2/simulate/run", headers=_headers(), json={
            "workflow": {"workflow_id": "w", "tasks": [{"task_id": "t1", "operation": "prepare", "provider_id": "fixture"}]}}))
        assert simulate["available"] is False and simulate["capability"] == "simulation_providers"
        assert client.get("/openapi.json", headers=_headers()).status_code == 404
