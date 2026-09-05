"""``create_combined_app`` serves both contracts at the paths they are spelled with.

v2 is mounted at the root behind v1 (CR-2): ``/api/v2/...`` answers, ``/api/v1/...``
still answers first, and neither canonical OpenAPI document is generated from the
combined application, so mounting perturbs neither freeze.
"""
from __future__ import annotations

import json

from starlette.testclient import TestClient

from ugence_governance_studio_api.app_v2 import create_combined_app
from ugence_governance_studio_api.openapi import canonical_openapi_bytes
from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes
from ugence_governance_studio_api.settings import ApiSettings


def _client() -> TestClient:
    return TestClient(create_combined_app(ApiSettings(environment="test", enable_docs=False)))


def test_v2_routes_are_served_at_their_contract_paths_behind_v1():
    client = _client()
    assert client.get("/api/v1/scenarios").status_code == 200
    assert client.get("/health").status_code == 200
    queue = client.get("/api/v2/review/queue")
    assert queue.status_code == 200
    body = queue.json()["result"]
    assert body["available"] is False and body["capability"] == "review_service"
    # the old prefixed spelling is served nowhere
    assert client.get("/v2/api/v2/review/queue").status_code == 404


def test_every_v2_operation_path_resolves_on_the_combined_app():
    client = _client()
    document = json.loads(canonical_v2_openapi_bytes())
    for path, methods in document["paths"].items():
        concrete = path.replace("{instance_id}", "i1").replace("{approval_id}", "a1") \
            .replace("{record_id}", "r1").replace("{decision_id}", "d1").replace("{correlation_id}", "c1")
        for method in methods:
            response = client.request(method.upper(), concrete, json={} if method == "post" else None)
            assert response.status_code != 404, (method, path, response.status_code)


def test_mounting_changes_neither_canonical_document():
    before_v1, before_v2 = canonical_openapi_bytes(), canonical_v2_openapi_bytes()
    _client()
    assert canonical_openapi_bytes() == before_v1
    assert canonical_v2_openapi_bytes() == before_v2
