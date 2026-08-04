"""Runtime network-egress boundary (P3E §22, G13).

Proves the running application makes no non-loopback outbound connection while serving
the full planning surface, and imports no external model/agent SDK.
"""
import base64
import ipaddress
import socket
import sys

import pytest

from depaths import USERNAME, PASSWORD

AUTH = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
POST = {"Authorization": AUTH, "X-Ugence-Request": "GovernanceStudio", "Origin": "http://testserver", "Content-Type": "application/json"}

BANNED_SDKS = ["openai", "anthropic", "google.generativeai", "cohere", "boto3", "litellm", "mistralai", "vertexai"]


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in ("localhost", "testserver", "")


@pytest.fixture
def egress_recorder(monkeypatch):
    attempts = []
    real_connect = socket.socket.connect

    def guarded_connect(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else str(address)
        if not _is_loopback(host):
            attempts.append(host)
        return real_connect(self, address, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection",
                        lambda address, *a, **k: attempts.append(address[0]) if not _is_loopback(address[0]) else None)
    return attempts


def test_no_non_loopback_egress_during_full_surface(client, egress_recorder):
    for suffix in ("", "/registry", "/eligibility", "/ranking", "/plan", "/export"):
        client.get(f"/api/v1/scenarios/procurement{suffix}", headers={"Authorization": AUTH})
    client.post("/api/v1/plans/replay", headers=POST, json={"scenario_id": "procurement"})
    client.post("/api/v1/scenarios/procurement/what-if", headers=POST,
                json={"operation": "FORBID_PROVIDER", "params": {"provider": "openai"}})
    assert egress_recorder == [], f"unexpected outbound hosts: {egress_recorder}"


def test_no_external_model_or_agent_sdk_imported(client):
    # touch the API so the backend + AWC are fully imported, then check sys.modules
    client.get("/api/v1/scenarios/procurement/plan", headers={"Authorization": AUTH})
    imported = [m for m in BANNED_SDKS if m in sys.modules]
    assert imported == [], f"external SDKs imported at runtime: {imported}"
