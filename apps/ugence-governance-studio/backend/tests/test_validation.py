"""Request validation + error mapping tests (§18, §21, §28)."""
from __future__ import annotations

from tests.conftest import result_of


def test_malformed_json(client):
    r = client.post("/api/v1/eligibility/evaluate", content=b"{not json",
                    headers={"content-type": "application/json"})
    assert r.status_code in (400, 422)


def test_unknown_fields_rejected(client):
    r = client.post("/api/v1/eligibility/evaluate",
                    json={"scenario_id": "procurement", "unexpected": 1})
    assert r.status_code == 422


def test_oversized_request(client):
    huge = {"operation": "FORBID_PROVIDER", "params": {"provider": "A" * 3_000_000}}
    r = client.post("/api/v1/scenarios/procurement/what-if", json=huge)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "request_too_large"


def test_missing_required_field(client):
    r = client.post("/api/v1/workflows/validate", json={"workflow": {}})  # missing contract_version
    assert r.status_code == 422


def test_invalid_enum(client):
    r = client.post("/api/v1/scenarios/procurement/what-if", json={"operation": "NOPE", "params": {}})
    assert r.status_code == 422


def test_unsupported_media_type(client):
    r = client.post("/api/v1/eligibility/evaluate", content=b"scenario_id=procurement",
                    headers={"content-type": "text/plain"})
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_media_type"


def test_unknown_scenario_reference(client):
    r = client.post("/api/v1/eligibility/evaluate", json={"scenario_id": "does_not_exist"})
    assert r.status_code == 404


def test_sanitized_internal_error_shape(client):
    # An error envelope never leaks a stack trace; production hides the exc type.
    r = client.get("/api/v1/scenarios/does_not_exist")
    body = r.json()
    assert "error" in body
    assert "traceback" not in str(body).lower()


def test_no_unsafe_path_field():
    """Request models expose no filesystem-path field (§14, §21)."""
    from ugence_governance_studio_api.contracts import requests as req

    for name in dir(req):
        obj = getattr(req, name)
        fields = getattr(obj, "model_fields", None)
        if not fields:
            continue
        for fname in fields:
            assert "path" not in fname.lower()
            assert "file" not in fname.lower()
