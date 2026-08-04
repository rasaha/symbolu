"""Trusted-host, cross-origin, security-header and request-limit gates (P3E §14-§16)."""
import pytest

REQUIRED_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "cache-control",
]


# -- trusted host ----------------------------------------------------------
def test_approved_host_passes(client, auth_headers):
    r = client.get("/", headers={**auth_headers, "host": "testserver"})
    assert r.status_code == 200


def test_unapproved_host_rejected(client, auth_headers):
    r = client.get("/", headers={**auth_headers, "host": "evil.example.com"})
    assert r.status_code == 400


def test_health_is_host_agnostic(client):
    assert client.get("/healthz", headers={"host": "anything"}).status_code == 200


# -- origin / deployment header (mutating requests) ------------------------
def test_same_origin_mutating_request_allowed(client, auth_headers):
    r = client.post("/api/v1/explanations/eligibility",
                    headers={**auth_headers, "Content-Type": "application/json"},
                    json={"scenario_id": "procurement"})
    assert r.status_code != 403  # origin guard passed; backend handles the rest


def test_cross_origin_mutating_request_rejected(client, auth_headers):
    r = client.post("/api/v1/explanations/eligibility",
                    headers={**auth_headers, "Origin": "https://evil.example.com", "Content-Type": "application/json"},
                    json={"scenario_id": "procurement"})
    assert r.status_code == 403


def test_missing_deployment_header_rejected_for_mutating(client):
    import base64
    from depaths import USERNAME, PASSWORD
    auth = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    r = client.post("/api/v1/explanations/eligibility",
                    headers={"Authorization": auth, "Content-Type": "application/json"},
                    json={"scenario_id": "procurement"})
    assert r.status_code == 403


def test_safe_get_needs_no_deployment_header(client):
    import base64
    from depaths import USERNAME, PASSWORD
    auth = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    assert client.get("/api/v1/scenarios", headers={"Authorization": auth}).status_code == 200


# -- security headers ------------------------------------------------------
@pytest.mark.parametrize("path", ["/", "/api/v1/scenarios"])
def test_security_headers_present(client, auth_headers, path):
    r = client.get(path, headers=auth_headers)
    for h in REQUIRED_HEADERS:
        assert h in r.headers, f"missing {h} on {path}"


def test_headers_present_on_auth_failure(client):
    r = client.get("/")  # 401
    assert r.status_code == 401
    assert "content-security-policy" in r.headers


def test_csp_is_strict(client, auth_headers):
    csp = client.get("/", headers=auth_headers).headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    for weak in ("unsafe-eval", "unsafe-inline", "*"):
        assert weak not in csp


def test_api_responses_are_no_store(client, auth_headers):
    r = client.get("/api/v1/scenarios", headers=auth_headers)
    assert r.headers.get("cache-control") == "no-store"


# -- request size limit ----------------------------------------------------
def test_oversized_body_rejected(client, auth_headers):
    big = b"x" * (1024 * 1024 + 10)  # > 1 MiB
    r = client.post("/api/v1/explanations/eligibility",
                    headers={**auth_headers, "Content-Type": "application/json"},
                    content=big)
    assert r.status_code == 413
