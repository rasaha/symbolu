"""Shared fixtures for the P3E deployment tests.

The deployment application is exercised in-process via httpx's ASGITransport for the
functional gates, and over real TLS via a live uvicorn server for the HTTPS/TLS gates.
"""
from __future__ import annotations

import base64
import os

import pytest
from starlette.testclient import TestClient

from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig
from governance_studio_deployment.packaging import write_frontend_marker
from governance_studio_deployment.passwords import hash_password

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CERTS = os.path.join(os.path.dirname(__file__), "certs")

USERNAME = "operator"
PASSWORD = "demo-password-123"
FRONTEND_DIR = os.path.join(REPO, "apps", "ugence-governance-studio", "frontend", "dist")
SCENARIOS_ROOT = os.path.join(REPO, "apps", "ugence-governance-studio", "demo_data")
MANIFEST = os.path.join(REPO, "deployment", "governance-studio", "synthetic-scenarios-manifest.json")
OPENAPI = os.path.join(REPO, "apps", "ugence-governance-studio", "contracts", "openapi.json")
APPROVED_OPS = os.path.join(REPO, "apps", "ugence-governance-studio", "frontend", "security", "approved-api-operations.json")


def basic_auth(user: str = USERNAME, pw: str = PASSWORD) -> str:
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def _ensure_test_certs() -> None:
    """Generate throwaway loopback test certificates if absent (never committed)."""
    import subprocess
    os.makedirs(CERTS, exist_ok=True)
    crt, key, mismatch = (os.path.join(CERTS, n) for n in ("server.crt", "server.key", "mismatch.key"))
    if not (os.path.isfile(crt) and os.path.isfile(key)):
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", crt,
             "-days", "2", "-subj", "/CN=localhost",
             "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
            check=True, capture_output=True,
        )
    if not os.path.isfile(mismatch):
        subprocess.run(["openssl", "genrsa", "-out", mismatch, "2048"], check=True, capture_output=True)


@pytest.fixture(scope="session", autouse=True)
def _test_certs():
    _ensure_test_certs()
    yield


@pytest.fixture(scope="session")
def password_hash() -> str:
    return hash_password(PASSWORD)


@pytest.fixture(scope="session", autouse=True)
def _frontend_marker():
    if os.path.isdir(FRONTEND_DIR):
        write_frontend_marker(FRONTEND_DIR, os.path.join(os.path.dirname(FRONTEND_DIR), "frontend-build.json"))
    yield


@pytest.fixture
def config(password_hash: str, tmp_path) -> DeploymentConfig:
    return DeploymentConfig.from_env(
        mode="test",
        username=USERNAME,
        password_hash=password_hash,
        tls_cert_file=os.path.join(CERTS, "server.crt"),
        tls_key_file=os.path.join(CERTS, "server.key"),
        allowed_hosts=["localhost", "127.0.0.1", "testserver"],
        frontend_dir=FRONTEND_DIR,
        scenarios_root=SCENARIOS_ROOT,
        manifest_path=MANIFEST,
        runtime_dir=str(tmp_path),
    )


@pytest.fixture
def client(config: DeploymentConfig):
    app = build_app(config, readiness=lambda: True, tracker=FailureTracker(), sleep=lambda _s: None)
    with TestClient(app, base_url="http://testserver", raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def auth_headers() -> dict:
    return {
        "Authorization": basic_auth(),
        "X-Ugence-Request": "GovernanceStudio",
        "Origin": "http://testserver",
    }
