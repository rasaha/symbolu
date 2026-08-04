import json
import os
import shutil

import pytest

from governance_studio_deployment.startup_integrity import (
    IntegrityInputs,
    run_startup_integrity,
    is_cert_expired,
    cert_not_after_seconds,
)
from depaths import CERTS, OPENAPI, APPROVED_OPS, FRONTEND_DIR


def _marker(tmp_path, version="0.2.0"):
    p = tmp_path / "frontend-build.json"
    p.write_text(json.dumps({"version": version, "build_hash": "sha256:abc"}))
    return str(p)


def _inputs(config, tmp_path, *, openapi=OPENAPI, approved=APPROVED_OPS, marker=None):
    return IntegrityInputs(
        config=config, openapi_path=openapi, approved_ops_path=approved,
        frontend_build_marker=marker or _marker(tmp_path),
    )


def test_valid_startup_passes(config, tmp_path):
    res = run_startup_integrity(_inputs(config, tmp_path))
    assert res.ok, res.failures
    assert res.report["result"] == "PASS"


def test_missing_username_fails(config, tmp_path):
    import dataclasses
    bad = dataclasses.replace(config, username="")
    res = run_startup_integrity(_inputs(bad, tmp_path))
    assert not res.ok and res.code == "GOVERNANCE_STUDIO_P3E_ACCESS_CONTROL_FAILED"


def test_missing_password_hash_fails(config, tmp_path):
    import dataclasses
    res = run_startup_integrity(_inputs(dataclasses.replace(config, password_hash=""), tmp_path))
    assert not res.ok


def test_invalid_password_hash_fails(config, tmp_path):
    import dataclasses
    res = run_startup_integrity(_inputs(dataclasses.replace(config, password_hash="notahash"), tmp_path))
    assert not res.ok


def test_missing_certificate_fails(config, tmp_path):
    import dataclasses
    res = run_startup_integrity(_inputs(dataclasses.replace(config, tls_cert_file="/no/such.crt"), tmp_path))
    assert not res.ok and res.code == "GOVERNANCE_STUDIO_P3E_HTTPS_FAILED"


def test_cert_key_mismatch_fails(config, tmp_path):
    import dataclasses
    bad = dataclasses.replace(config, tls_key_file=os.path.join(CERTS, "mismatch.key"))
    res = run_startup_integrity(_inputs(bad, tmp_path))
    assert not res.ok
    assert not res.checks["tls_certificate_valid"]


def test_missing_allowed_hosts_in_production_fails(config, tmp_path):
    import dataclasses
    bad = dataclasses.replace(config, mode="production", allowed_hosts=[])
    res = run_startup_integrity(_inputs(bad, tmp_path))
    assert not res.ok
    assert not res.checks["allowed_hosts_configured"]


def test_wrong_frontend_version_marker_fails(config, tmp_path):
    res = run_startup_integrity(_inputs(config, tmp_path, marker=_marker(tmp_path, version="0.1.0")))
    assert not res.ok
    assert not res.checks["frontend_version_0_2_0"]


def test_openapi_hash_mismatch_fails(config, tmp_path):
    fake = tmp_path / "openapi.json"
    fake.write_text('{"openapi":"3.1.0","paths":{}}')
    res = run_startup_integrity(_inputs(config, tmp_path, openapi=str(fake)))
    assert not res.ok and res.code == "GOVERNANCE_STUDIO_P3E_OPENAPI_DRIFT"


def test_approved_operation_manifest_mismatch_fails(config, tmp_path):
    fake = tmp_path / "approved.json"
    fake.write_text(json.dumps({"contract": "x", "openapi_sha256": "deadbeef", "approved_operation_ids": []}))
    res = run_startup_integrity(_inputs(config, tmp_path, approved=str(fake)))
    assert not res.ok
    assert not res.checks["approved_operation_manifest_valid"]


def test_extra_fixture_fails(config, tmp_path):
    import dataclasses
    scen = tmp_path / "scenarios"
    shutil.copytree(config.scenarios_root, scen)
    (scen / "rogue_scenario").mkdir()
    (scen / "rogue_scenario" / "x.json").write_text("{}")
    bad = dataclasses.replace(config, scenarios_root=str(scen))
    res = run_startup_integrity(_inputs(bad, tmp_path))
    assert not res.ok and res.code == "SYNTHETIC_DATA_BOUNDARY_FAILED"


def test_missing_fixture_fails(config, tmp_path):
    import dataclasses
    scen = tmp_path / "scenarios2"
    shutil.copytree(config.scenarios_root, scen)
    shutil.rmtree(scen / "procurement")
    bad = dataclasses.replace(config, scenarios_root=str(scen))
    res = run_startup_integrity(_inputs(bad, tmp_path))
    assert not res.ok and res.code == "SYNTHETIC_DATA_BOUNDARY_FAILED"


def test_fixture_hash_tamper_fails(config, tmp_path):
    import dataclasses
    scen = tmp_path / "scenarios3"
    shutil.copytree(config.scenarios_root, scen)
    manifest_file = next((scen / "procurement").glob("*.json"))
    manifest_file.write_text(manifest_file.read_text() + "\n// tampered")
    bad = dataclasses.replace(config, scenarios_root=str(scen))
    res = run_startup_integrity(_inputs(bad, tmp_path))
    assert not res.ok and res.code == "SYNTHETIC_DATA_BOUNDARY_FAILED"


def test_scenario_root_env_override_detected(config, tmp_path, monkeypatch):
    monkeypatch.setenv("UGS_API_SCENARIO_ROOT", "/some/other/root")
    res = run_startup_integrity(_inputs(config, tmp_path))
    assert not res.checks["no_external_fixture_override"]


def test_production_using_test_cert_fails(config, tmp_path):
    # a production deployment reusing the committed test certificate is a dev-in-prod conflict
    import dataclasses
    bad = dataclasses.replace(config, mode="production", bind_host="0.0.0.0",
                              allowed_hosts=["studio.example.internal"])
    res = run_startup_integrity(_inputs(bad, tmp_path))
    assert not res.checks["no_dev_mode_in_production"]
    assert not res.ok


def test_cert_expiry_predicate():
    # valid cert is not expired now; an obviously-past instant would flag any cert
    assert cert_not_after_seconds(os.path.join(CERTS, "server.crt")) is not None
    assert not is_cert_expired(os.path.join(CERTS, "server.crt"), now=0.0)
    assert is_cert_expired(os.path.join(CERTS, "server.crt"), now=4102444800.0)  # year 2100
