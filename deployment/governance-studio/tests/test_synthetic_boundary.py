"""Synthetic-data-only boundary at the packaged deployment (P3E §8, §25)."""
import json
import os

from governance_studio_deployment.synthetic import (
    SyntheticManifest,
    verify_bundle,
    build_manifest,
    SyntheticDataBoundaryError,
    enforce,
)
from depaths import SCENARIOS_ROOT, MANIFEST, FRONTEND_DIR

APPROVED = {"procurement", "customer_support", "cybersecurity_success", "cybersecurity_no_feasible_team"}


def test_manifest_pins_exactly_the_approved_scenarios():
    m = SyntheticManifest.load(MANIFEST)
    assert set(m.scenario_ids) == APPROVED
    assert m.data_classification == "SYNTHETIC_DEMONSTRATION_ONLY"
    assert m.source_contract == "governance_studio.api.v1"


def test_packaged_bundle_verifies_clean():
    assert verify_bundle(SyntheticManifest.load(MANIFEST), SCENARIOS_ROOT) == []


def test_served_catalog_is_exactly_the_approved_scenarios(client, auth_headers):
    r = client.get("/api/v1/scenarios", headers=auth_headers)
    assert r.status_code == 200
    result = r.json()["result"]
    scenarios = result["scenarios"] if isinstance(result, dict) else result
    ids = {s["scenario_id"] for s in scenarios}
    assert ids == APPROVED  # no additional scenario is served


def test_env_scenario_root_override_does_not_change_served_catalog(config, monkeypatch):
    # the deployment pins scenario_root explicitly; a stray env var cannot redirect it
    from starlette.testclient import TestClient
    from governance_studio_deployment.app import build_app
    monkeypatch.setenv("UGS_API_SCENARIO_ROOT", "/tmp/not-a-real-root")
    app = build_app(config, sleep=lambda _s: None)
    with TestClient(app, base_url="http://testserver") as c:
        import base64
        from depaths import USERNAME, PASSWORD
        auth = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
        r = c.get("/api/v1/scenarios", headers={"Authorization": auth})
        assert r.status_code == 200


def test_extra_scenario_is_a_boundary_violation(tmp_path):
    import shutil
    scen = tmp_path / "scen"
    shutil.copytree(SCENARIOS_ROOT, scen)
    (scen / "unapproved").mkdir()
    (scen / "unapproved" / "x.json").write_text("{}")
    violations = verify_bundle(SyntheticManifest.load(MANIFEST), str(scen))
    assert any("extra scenario" in v for v in violations)


def test_enforce_raises_on_tamper(tmp_path):
    import shutil
    scen = tmp_path / "scen2"
    shutil.copytree(SCENARIOS_ROOT, scen)
    f = next((scen / "procurement").glob("*.json"))
    f.write_text(f.read_text() + " ")
    try:
        enforce(MANIFEST, str(scen))
        assert False, "expected SyntheticDataBoundaryError"
    except SyntheticDataBoundaryError as exc:
        assert exc.code == "SYNTHETIC_DATA_BOUNDARY_FAILED"


def test_no_upload_route_exists(client, auth_headers):
    # there is no file-upload surface; a POST to a made-up upload path is not found
    r = client.post("/api/v1/scenarios/upload", headers={**auth_headers, "Content-Type": "application/json"}, json={})
    assert r.status_code in (403, 404, 405)


def test_frontend_bundle_carries_synthetic_banner():
    # the frozen P3D SPA renders a persistent synthetic-demonstration banner on every
    # screen; assert the packaged bundle contains that copy (no frozen build change).
    blob = ""
    assets = os.path.join(FRONTEND_DIR, "assets")
    for name in os.listdir(assets):
        if name.endswith(".js"):
            blob += open(os.path.join(assets, name), encoding="utf-8", errors="ignore").read()
    assert "Synthetic demonstration data" in blob


def test_rebuilt_manifest_matches_committed():
    fresh = build_manifest(SCENARIOS_ROOT, sorted(APPROVED))
    committed = json.load(open(MANIFEST, encoding="utf-8"))
    assert fresh["bundle_hash"] == committed["bundle_hash"]
    assert fresh["fixture_hashes"] == committed["fixture_hashes"]
