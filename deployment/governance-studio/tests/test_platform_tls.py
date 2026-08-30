"""Platform-terminated TLS: HTTPS relocated, never removed.

The container deployment performs the TLS handshake itself, so a plaintext
request cannot reach the application. On a hosting platform that terminates TLS
in front of the process there is no certificate to check, and the forwarded
protocol becomes the only evidence that the client leg was encrypted.

These tests hold the invariant that this mode weakens nothing silently: the
certificate requirement still applies in the default mode, the platform mode is
refused unless the proxy is trusted, and a request that cannot be shown to have
arrived over HTTPS is refused before the auth gate reads any credential.
"""
from __future__ import annotations

import base64

import pytest
from starlette.testclient import TestClient

from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig

from conftest import FRONTEND_DIR, MANIFEST, PASSWORD, SCENARIOS_ROOT, USERNAME
from governance_studio_deployment.passwords import hash_password

HOST = "studio.example.test"


def _config(**over) -> DeploymentConfig:
    base = dict(
        mode="production", username=USERNAME, password_hash=hash_password(PASSWORD),
        tls_cert_file="", tls_key_file="", tls_termination="platform", trusted_proxy=True,
        allowed_hosts=[HOST], frontend_dir=FRONTEND_DIR,
        scenarios_root=SCENARIOS_ROOT, manifest_path=MANIFEST,
    )
    base.update(over)
    return DeploymentConfig(**base)


def _client(cfg) -> TestClient:
    return TestClient(build_app(cfg), base_url=f"http://{HOST}")


def _auth() -> dict:
    token = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# --- configuration -----------------------------------------------------------

def test_self_termination_still_requires_certificate_files():
    """The default container mode is unchanged."""
    errs = _config(tls_termination="self").validate()
    assert sum("TLS" in e for e in errs) == 2


def test_platform_termination_requires_a_trusted_proxy():
    """Without a trusted proxy the forwarded header is unusable, so fail closed."""
    errs = _config(trusted_proxy=False).validate()
    assert any("TRUSTED_PROXY" in e for e in errs)


def test_platform_termination_rejects_stray_certificate_paths():
    errs = _config(tls_cert_file="/tmp/x.crt").validate()
    assert any("must not be set" in e for e in errs)


def test_unknown_termination_mode_is_rejected():
    assert any("TLS_TERMINATION" in e for e in _config(tls_termination="none").validate())


def test_platform_mode_is_otherwise_a_valid_production_config():
    assert _config().validate() == []


# --- runtime enforcement ------------------------------------------------------

def test_plaintext_request_is_refused(  ):
    c = _client(_config())
    r = c.get("/api/v1/scenarios", headers={**_auth(), "X-Forwarded-Proto": "http"})
    assert r.status_code == 400
    assert "HTTPS required" in r.text


def test_missing_forwarded_proto_is_refused_not_assumed_secure():
    c = _client(_config())
    assert c.get("/api/v1/scenarios", headers=_auth()).status_code == 400


def test_https_request_reaches_the_application():
    c = _client(_config())
    r = c.get("/api/v1/scenarios", headers={**_auth(), "X-Forwarded-Proto": "https"})
    assert r.status_code == 200


def test_proxy_chain_uses_the_client_leg():
    """The first entry is the client's own leg; a TLS hop later does not excuse it."""
    c = _client(_config())
    assert c.get("/api/v1/scenarios",
                 headers={**_auth(), "X-Forwarded-Proto": "http, https"}).status_code == 400
    assert c.get("/api/v1/scenarios",
                 headers={**_auth(), "X-Forwarded-Proto": "https, http"}).status_code == 200


def test_plaintext_is_refused_before_credentials_are_read():
    """A plaintext request must not be a credential oracle."""
    c = _client(_config())
    bad = base64.b64encode(b"ghost:wrong").decode()
    r = c.get("/", headers={"Authorization": f"Basic {bad}", "X-Forwarded-Proto": "http"})
    assert r.status_code == 400          # not 401: the request never reached the gate
    assert "HTTPS required" in r.text


def test_authentication_still_applies_over_https():
    """Relocating TLS must not relax the access gate."""
    c = _client(_config())
    assert c.get("/", headers={"X-Forwarded-Proto": "https"}).status_code == 401
    assert c.get("/api/v1/scenarios",
                 headers={"X-Forwarded-Proto": "https"}).status_code == 401


def test_guard_is_absent_when_this_process_terminates_tls(tmp_path):
    """No forwarded-protocol dependency in the container deployment."""
    cert = tmp_path / "c.crt"; cert.write_text("x")
    key = tmp_path / "c.key"; key.write_text("x")
    cfg = _config(tls_termination="self", trusted_proxy=False,
                  tls_cert_file=str(cert), tls_key_file=str(key))
    c = _client(cfg)
    # no X-Forwarded-Proto at all, yet the request is served (auth still applies)
    assert c.get("/api/v1/scenarios", headers=_auth()).status_code == 200
