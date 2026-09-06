"""Front-door seam 9 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md FD-1, FD-3, FD-4, FD-13).

The P3E profile hands the Vendor screen a tenant-bound sqlite declarations file under
the runtime volume. The failure matrix of ADR §14.4 as tests, row by row: the unset gap,
the missing tenant, blank and malformed input, a caller-supplied tenant, an inadmissible
supersession, the cross-tenant refusal and the foreign file, the vendor that cannot be
reached, the absent mutating route, restart, and the posture nothing ranks. The
contract-byte amendment is recorded and the composition record supersedes the seam-8 one.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

import pytest
from starlette.testclient import TestClient

from ugence_vendor_dependency import CrossTenantRefused, SqliteVendorDeclarations

from governance_studio_deployment import DEPLOYMENT_NAME, DEPLOYMENT_VERSION, app as deployment_app
from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig, DeploymentConfigError
from governance_studio_deployment.vendor import VENDOR_RECORDED_BY, open_vendor_declarations
from governance_studio_deployment.startup_integrity import IntegrityInputs, run_startup_integrity

from conftest import basic_auth
from depaths import APPROVED_OPS, CERTS, FRONTEND_DIR, MANIFEST, OPENAPI, SCENARIOS_ROOT, USERNAME  # noqa: F401

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(HERE))
TENANT = "tenant-1"
OTHER = "tenant-2"
D = "f" * 64
ROUTE = "/api/v2/vendor/declarations"


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


def _declaration(**over):
    declared = {"binding": {"binding_id": "bind-1", "subject_id": "subject-1", "context_id": "ctx-1",
                            "context_digest": D, "system_id": "hiring-screener",
                            "system_version": "1.0.0", "configuration_id": "cfg-1",
                            "configuration_digest": D},
                "vendor_ref": "vendor://acme-llm",
                "risk_posture_label": "elevated",
                "policy_ref": "policy://vendor-standard/v3",
                "validity": {"issued_at": "2026-09-01T00:00:00+00:00",
                             "expires_at": "2027-09-01T00:00:00+00:00"},
                "declared_by": "directory://people/declarer-1"}
    declared.update(over)
    return declared


@pytest.fixture()
def runtime_dir(tmp_path):
    d = tmp_path / "runtime"
    d.mkdir()
    return d


@pytest.fixture()
def declarations_path(runtime_dir):
    return str(runtime_dir / "vendor-declarations.sqlite3")


@pytest.fixture()
def enabled(password_hash, runtime_dir, declarations_path) -> DeploymentConfig:
    return _config(password_hash, runtime_dir, tenant_id=TENANT,
                   vendor_declarations_path=declarations_path)


def _count(path: str) -> int:
    store = SqliteVendorDeclarations(path, tenant_id=TENANT)
    try:
        return store.count()
    finally:
        store.close()


# --------------------------------------------------------------------------- #
# §14.4 rows 1 and 2 — the typed gap, the path rules, the tenant rule
# --------------------------------------------------------------------------- #
def test_unset_is_the_typed_gap_on_both_routes(config):
    assert config.vendor_declarations_configured is False
    with _client(config) as client:
        for response in (client.post(ROUTE, headers=_headers(), json=_declaration()),
                         client.get(ROUTE, headers=_headers())):
            r = _result(response)
            assert r["available"] is False and r["capability"] == "vendor_declarations"
            assert r["result"] is None


def test_missing_tenant_fails_validation_and_startup_integrity_with_the_seam_code(
        password_hash, runtime_dir, declarations_path, tmp_path):
    cfg = _config(password_hash, runtime_dir, vendor_declarations_path=declarations_path)
    errors = cfg.validate()
    assert any("requires UGENCE_STUDIO_TENANT_ID" in e for e in errors)
    result = _integrity(cfg, tmp_path)
    assert result.ok is False and result.code == "GOVERNANCE_STUDIO_P3E_VENDOR_SEAM_FAILED"
    good = _config(password_hash, runtime_dir, tenant_id=TENANT,
                   vendor_declarations_path=declarations_path)
    assert good.validate() == []
    report = _integrity(good, tmp_path).report
    assert report["vendor_declarations"] == "configured" and report["system_registry"] == "unset"


@pytest.mark.parametrize("path", [":memory:", "file::memory:?cache=shared", "relative.sqlite3",
                                  "/elsewhere/v.sqlite3"])
def test_a_path_outside_the_volume_or_in_memory_is_refused(password_hash, runtime_dir, path):
    cfg = _config(password_hash, runtime_dir, tenant_id=TENANT, vendor_declarations_path=path)
    assert any("UGENCE_STUDIO_VENDOR_DECLARATIONS_PATH" in e for e in cfg.validate())


def test_an_unwritable_directory_fails_startup_integrity_before_bind(password_hash, runtime_dir,
                                                                     tmp_path):
    cfg = _config(password_hash, runtime_dir, tenant_id=TENANT,
                  vendor_declarations_path=str(runtime_dir / "missing" / "v.sqlite3"))
    assert cfg.validate() == []
    result = _integrity(cfg, tmp_path)
    assert result.ok is False and result.checks["vendor_declarations_writable"] is False
    assert result.code == "GOVERNANCE_STUDIO_P3E_VENDOR_SEAM_FAILED"


# --------------------------------------------------------------------------- #
# §14.4 rows 3, 4, 5 and 7 — the write, its refusals, and what never crosses
# --------------------------------------------------------------------------- #
def test_declare_records_with_the_deployment_as_recorder_and_the_declarer_unproven(
        enabled, declarations_path):
    with _client(enabled) as client:
        r = _result(client.post(ROUTE, headers=_headers(), json=_declaration()))
    assert r["declared"] is True and r["tenant_id"] == TENANT
    assert r["recorded_by"] == VENDOR_RECORDED_BY == f"{DEPLOYMENT_NAME}/{DEPLOYMENT_VERSION}"
    assert r["declared_by_status"] == "PRESENTED_UNPROVEN" and r["confers"].startswith("nothing")
    assert r["store_kind"] == "SqliteVendorDeclarations"
    assert r["record"]["declaration"]["declared_by"] == "directory://people/declarer-1"
    assert _count(declarations_path) == 1


@pytest.mark.parametrize("over,code", [
    ({"vendor_ref": ""}, "vendor_declaration_refused"),
    ({"risk_posture_label": " "}, "vendor_declaration_refused"),
    ({"policy_ref": ""}, "vendor_declaration_refused"),
    ({"validity": {"issued_at": "2026-09-01T00:00:00"}}, "vendor_declaration_refused"),
    ({"supersedes": "vdd_" + "0" * 32}, "supersession_refused"),
])
def test_blank_malformed_input_and_an_inadmissible_supersession_are_typed_refusals(
        enabled, declarations_path, over, code):
    with _client(enabled) as client:
        r = _result(client.post(ROUTE, headers=_headers(), json=_declaration(**over)))
    assert r["refused"] is True and r["code"] == code
    assert _count(declarations_path) == 0


def test_a_caller_supplied_tenant_or_id_is_a_contract_refusal_and_no_field_carries_data(enabled):
    with _client(enabled) as client:
        for extra in ({"tenant_id": OTHER}, {"declaration_id": "dud_x"}, {"recorded_by": "me"},
                      {"payload": "the data itself"}, {"rows": [1, 2]}):
            response = client.post(ROUTE, headers=_headers(), json=_declaration(**extra))
            assert response.status_code == 422, (extra, response.text)


# --------------------------------------------------------------------------- #
# §14.4 rows 6 and 9 — the tenant boundary and restart
# --------------------------------------------------------------------------- #
def test_a_cross_tenant_read_is_refused_and_a_foreign_file_is_refused_before_bind(
        password_hash, runtime_dir, declarations_path, enabled):
    with _client(enabled) as client:
        _result(client.post(ROUTE, headers=_headers(), json=_declaration()))
        listed = _result(client.get(ROUTE, headers=_headers(),
                                    params={"as_of": "2026-10-01T00:00:00+00:00"}))
        assert listed["tenant_id"] == TENANT and listed["count"] == 1
        assert all(rec["binding"]["tenant_id"] == TENANT for rec in listed["result"])
    store = open_vendor_declarations(declarations_path, tenant_id=TENANT, production_mode=False)
    try:
        with pytest.raises(CrossTenantRefused):
            store.declarations_for_tenant(
                tenant_id=OTHER, as_of=dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc))
    finally:
        store.close()
    foreign = _config(password_hash, runtime_dir, tenant_id=OTHER,
                      vendor_declarations_path=declarations_path)
    with pytest.raises(DeploymentConfigError, match="another tenant"):
        deployment_app._build_backend(foreign)


def test_records_survive_a_restart_of_the_profile(enabled):
    with _client(enabled) as client:
        first = _result(client.post(ROUTE, headers=_headers(), json=_declaration()))
    with _client(enabled) as client:  # a second process over the same file
        listed = _result(client.get(ROUTE, headers=_headers(),
                                    params={"as_of": "2026-10-01T00:00:00+00:00"}))
        assert [rec["declaration"]["declaration_id"] for rec in listed["result"]] == [
            first["declaration_id"]]
        dup = _result(client.post(ROUTE, headers=_headers(), json=_declaration()))
        assert dup["refused"] is True and dup["code"] == "vendor_declaration_duplicate"


# --------------------------------------------------------------------------- #
# §14.4 — declare is the only write; nothing ranks the posture
# --------------------------------------------------------------------------- #
def test_no_mutating_or_admitting_route_exists_on_the_composed_profile(enabled):
    with _client(enabled) as client:
        for method, path in (("PUT", ROUTE + "/dud_x"), ("PATCH", ROUTE + "/dud_x"),
                             ("DELETE", ROUTE + "/dud_x"), ("POST", ROUTE + "/dud_x/revoke"),
                             ("POST", "/api/v2/data-use/admit"),
                             ("POST", "/api/v2/data-use/authorize"),
                             ("POST", "/api/v2/data-use/enforce")):
            response = client.request(method, path, headers=_headers(), json={})
            assert response.status_code in (404, 405), (method, path, response.status_code)


def test_the_answers_state_that_the_posture_is_recorded_and_never_assessed(enabled):
    with _client(enabled) as client:
        declared = _result(client.post(ROUTE, headers=_headers(), json=_declaration()))
        listed = _result(client.get(ROUTE, headers=_headers()))
    for answer in (declared, listed):
        assert answer["risk_posture"].startswith("uninterpreted")
        assert "ranked and scored nowhere" in answer["risk_posture"]
        assert "no package computes one" in answer["risk_posture"]


def test_no_vendor_approval_or_onboarding_status_is_expressible_through_the_profile(enabled):
    """§14.4: the posture is the only judgement-shaped field, and it is a record. A
    caller cannot smuggle a verdict in beside it."""

    with _client(enabled) as client:
        for extra in ({"approved": True}, {"onboarding_status": "complete"},
                      {"risk_score": 7}, {"tier": "critical"},
                      {"certification": "iso-27001"},
                      {"vendor_endpoint": "https://acme.example"},
                      {"contract_terms": "net-30"}):
            response = client.post(ROUTE, headers=_headers(), json=_declaration(**extra))
            assert response.status_code == 422, (extra, response.text)
        declared = _result(client.post(ROUTE, headers=_headers(), json=_declaration()))
    text = json.dumps(declared["record"])
    for forbidden in ("approved", "onboarding", "risk_score", "tier", "certification",
                      "endpoint", "credential", "pricing"):
        assert forbidden not in text, forbidden


# --------------------------------------------------------------------------- #
# the approved profile: the configuration value, the freeze, the composition record
# --------------------------------------------------------------------------- #
def test_the_approved_runtime_config_records_the_seam_and_the_fifth_amendment():
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    assert cfg["deployment_version"] == DEPLOYMENT_VERSION == "0.10.0"
    added = cfg["configuration_added"]["UGENCE_STUDIO_VENDOR_DECLARATIONS_PATH"]
    assert "requires UGENCE_STUDIO_TENANT_ID" in added and "front-door seam 9" in added
    seam = cfg["vendor_declarations"]
    assert "FD-13.4 RISK_POSTURE_UNINTERPRETED" in seam["ruling"]
    assert "no server, no driver, no DSN" in seam["store"]
    assert seam["risk_posture"].startswith("uninterpreted")
    assert "no package computes one" in seam["risk_posture"]
    assert "packages/integration/vendor-dependency" in cfg["first_party_packages_in_image"]
    assert any(h.startswith("vendor_declarations (seam 9")
               for h in cfg["front_door_seams"]["handed_to_build_studio_context"])
    # the frozen v2 bytes and the amendment chain
    contract = os.path.join(REPO, "apps", "ugence-governance-studio", "contracts")
    with open(os.path.join(contract, "openapi_v2.json"), "rb") as fh:
        committed = hashlib.sha256(fh.read()).hexdigest()
    assert cfg["frozen"]["openapi_v2_sha256"] == committed
    record = json.load(open(os.path.join(contract, "openapi_v2.amendments.json"), encoding="utf-8"))
    latest = record["amendments"][-1]
    assert latest["amendment_id"] == "v2-A5" and latest["sha256"] == committed
    assert set(latest["operations_added"]) == {"v2_vendor_declare", "v2_vendor_list"}
    assert cfg["frozen"]["openapi_v2_amendment"].startswith("v2-A5 (FD-13.3")
    # FD-1: the ratified v1 bytes and the shadow-only ceiling are untouched
    assert cfg["frozen"]["api_contract"] == "governance_studio.api.v1"
    assert cfg["frozen"]["openapi_sha256"] == \
        "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"
