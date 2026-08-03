"""Security boundary tests (§21, §22, §28)."""
from __future__ import annotations

import socket

import pytest

from starlette.testclient import TestClient

from tests.conftest import result_of
from ugence_governance_studio_api import create_app
from ugence_governance_studio_api.settings import ApiSettings


def test_no_external_network_during_domain_evaluation(client, monkeypatch):
    """Domain evaluation must not open any external socket."""
    real_connect = socket.socket.connect

    def _blocked(self, address):  # noqa: ANN001
        raise AssertionError(f"external network access attempted: {address}")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    try:
        result = result_of(client.get("/api/v1/scenarios/procurement/plan"))
        assert result["verification"]["match"] is True
    finally:
        monkeypatch.setattr(socket.socket, "connect", real_connect)


def test_no_shell_or_subprocess_in_source():
    import ugence_governance_studio_api as pkg
    import os
    root = os.path.dirname(pkg.__file__)
    forbidden = ("import subprocess", "subprocess.", "os.system(", "os.popen(",
                 "pty.spawn", "eval(", "exec(", "pickle.load", "__import__(")
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if not f.endswith(".py"):
                continue
            with open(os.path.join(dirpath, f), "r", encoding="utf-8") as fh:
                text = fh.read()
            for token in forbidden:
                assert token not in text, f"{token} found in {f}"


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers
    assert r.headers.get("Referrer-Policy") == "no-referrer"


def test_cors_configuration():
    app = create_app(ApiSettings(environment="test", cors_allowed_origins=["https://example.test"]))
    client = TestClient(app)
    r = client.get("/health", headers={"Origin": "https://example.test"})
    assert r.headers.get("access-control-allow-origin") == "https://example.test"


def test_cors_default_is_closed(client):
    r = client.get("/health", headers={"Origin": "https://evil.test"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_rate_limit_seam():
    app = create_app(ApiSettings(environment="test", enable_rate_limit=True))
    client = TestClient(app)
    r = client.get("/health")
    assert r.headers.get("X-RateLimit-Seam") == "enabled"


def test_authentication_seam_default_off(client):
    # default local mode: no auth required
    assert client.get("/version").status_code == 200


def test_no_credentials_returned(client):
    body = client.get("/version").text.lower()
    for token in ("password", "secret", "token", "api_key", "apikey"):
        assert token not in body


def test_request_id_present_and_operational(client):
    r = client.get("/api/v1/scenarios")
    assert r.headers.get("X-Request-ID", "").startswith("req_")
    # request_id does not appear inside the domain result
    body = r.json()
    assert body["request_id"] not in str(body["result"])
