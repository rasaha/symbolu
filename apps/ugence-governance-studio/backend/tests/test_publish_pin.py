"""FD-8.2, PIN_SHADOW_AND_REFUSE_UNMAPPED (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md §9.5).

The studio names ``shadow`` in every governed-loop body it sends; a compiled release
package without a valid frozen-scenario id is the typed refusal
``publish_payload_unmapped``, decided before any outbound request; only the validated
``scenario_id`` crosses to the console. Proven against a loopback console stub that
records every request, and against a disarmed ``urlopen`` for the refusal paths.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.clients.console import (
    CONSOLE_ALLOWED_ROUTES,
    GOVERNED_LOOP_MODE,
    ConsoleClient,
    ConsoleUnavailable,
)
from ugence_governance_studio_api.services.studio_v2 import (
    PUBLISH_PAYLOAD_UNMAPPED,
    PublishService,
    scenario_id_refusal,
)
from ugence_governance_studio_api.settings import ApiSettings

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
_APP = os.path.join(_REPO, "apps", "ugence-governance-studio")

SCENARIO = "k8s_rollout_restart_clean"
#: A compiled package that tries everything it should not be able to do.
HOSTILE_PACKAGE = {
    "mode": "enforcement",
    "assertion": {"claim": "made up"},
    "action": {"kind": "delete"},
    "operational_signals": {"ok": True},
    "scenario_id": "k8s_delete_during_freeze",
    "manifest": {"name": "release"},
    "workflow_ir": {"tasks": []},
}


class _FakeConsole(BaseHTTPRequestHandler):
    """A stand-in console. Records every request; answers the scenario route only."""

    received: list = []
    status = 200

    def log_message(self, *_args):  # silence
        pass

    def _send(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        type(self).received.append(("POST", self.path, json.loads(body) if body else None))
        if type(self).status != 200:
            return self._send(type(self).status, {"detail": "console failure"})
        if self.path.startswith("/v1/governed-loop/scenario/"):
            return self._send(200, {"correlation_id": "corr-1", "mode": "shadow",
                                    "final_disposition": "OBSERVED (shadow)", "recorded": True})
        return self._send(404, {"detail": "unknown"})

    def do_GET(self):
        type(self).received.append(("GET", self.path, None))
        return self._send(404, {"detail": "unknown"})


@pytest.fixture()
def console_server():
    _FakeConsole.received = []
    _FakeConsole.status = 200
    server = HTTPServer(("127.0.0.1", 0), _FakeConsole)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture()
def client(console_server):
    studio = build_studio_context(console_base_url=console_server)
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


@pytest.fixture()
def no_network(monkeypatch):
    """Every outbound HTTP attempt is an assertion failure."""
    def _boom(*_a, **_k):
        raise AssertionError("an outbound request was attempted")
    monkeypatch.setattr(urllib.request, "urlopen", _boom)


def _post(client, body):
    return client.post("/api/v2/publish/shadow", json=body)


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


# --------------------------------------------------------------------------- #
# the accepted path: exactly one loopback request, mode pinned, only the id crosses
# --------------------------------------------------------------------------- #
def test_a_valid_scenario_id_produces_exactly_one_request_with_mode_shadow(client):
    result = _result(_post(client, {"compiled_package": HOSTILE_PACKAGE, "scenario_id": SCENARIO}))
    assert result["available"] is True and result["mode"] == "SHADOW"
    assert result["scenario_id"] == SCENARIO and result["result"]["recorded"] is True
    assert len(_FakeConsole.received) == 1
    method, path, body = _FakeConsole.received[0]
    assert (method, path) == ("POST", f"/v1/governed-loop/scenario/{SCENARIO}")
    assert body == {"mode": "shadow"} and GOVERNED_LOOP_MODE == "shadow"


def test_no_compiled_package_field_crosses_the_boundary(client):
    _result(_post(client, {"compiled_package": HOSTILE_PACKAGE, "scenario_id": SCENARIO}))
    (_m, path, body) = _FakeConsole.received[0]
    wire = json.dumps(body) + path
    for key, value in HOSTILE_PACKAGE.items():
        if key == "mode":
            continue
        assert key not in json.dumps(body), key
        assert json.dumps(value) not in wire, key
    # the package's own scenario_id is not the one relayed; the request's is
    assert HOSTILE_PACKAGE["scenario_id"] not in path


def test_enforcement_requested_by_caller_or_package_cannot_change_the_emitted_mode(client):
    for body in (
        {"compiled_package": HOSTILE_PACKAGE, "scenario_id": SCENARIO},
        {"compiled_package": {"mode": "ENFORCEMENT", "deployment_mode": "enforcement"}, "scenario_id": SCENARIO},
        {"compiled_package": {}, "scenario_id": SCENARIO},
    ):
        _FakeConsole.received = []
        _result(_post(client, body))
        assert [b for (_m, _p, b) in _FakeConsole.received] == [{"mode": "shadow"}]
    # the client itself pins the mode on both governed-loop routes
    console = ConsoleClient(client.app.state.studio.publish._console._base)
    _FakeConsole.received = []
    console.governed_loop_scenario(SCENARIO)
    with pytest.raises(ConsoleUnavailable):  # the stub answers 404 on the shadow route
        console.governed_loop_shadow({"mode": "enforcement", "assertion": {"x": 1}})
    assert [b["mode"] for (_m, _p, b) in _FakeConsole.received] == ["shadow", "shadow"]


# --------------------------------------------------------------------------- #
# the refused path: typed, before any outbound request
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("scenario_id", [
    None, "", " ", "a b", "../k8s", "k8s/rollout", "k8s\nrollout", "-lead", "é", "x" * 65,
])
def test_missing_empty_or_malformed_scenario_id_refuses_unmapped_with_zero_outbound_calls(
        client, no_network, scenario_id):
    body = {"compiled_package": HOSTILE_PACKAGE}
    if scenario_id is not None:
        body["scenario_id"] = scenario_id
    result = _result(_post(client, body))
    assert result["refused"] is True and result["code"] == PUBLISH_PAYLOAD_UNMAPPED
    assert result["available"] is True and result["result"] is None
    assert _FakeConsole.received == []


@pytest.mark.parametrize("scenario_id", [123, 1.5, True, ["k8s"], {"id": "k8s"}])
def test_a_wrong_type_scenario_id_refuses_unmapped_at_the_service_and_422_at_the_contract(
        client, no_network, scenario_id):
    # the frozen v2 contract types scenario_id as an optional string: a wrong type never
    # reaches the service over HTTP, and the contract's own 422 is the answer
    response = _post(client, {"compiled_package": {}, "scenario_id": scenario_id})
    assert response.status_code == 422, response.text
    assert _FakeConsole.received == []
    # the service refuses it too, for any caller that bypasses the contract
    service = PublishService(ConsoleClient("http://console.invalid"))
    result = service.shadow(compiled_package={}, scenario_id=scenario_id)  # type: ignore[arg-type]
    assert result["refused"] is True and result["code"] == PUBLISH_PAYLOAD_UNMAPPED


def test_the_refusal_is_decided_before_the_console_client_is_consulted(no_network):
    class _NeverCalled:
        def governed_loop_scenario(self, *_a, **_k):
            raise AssertionError("the console client was invoked")

        def governed_loop_shadow(self, *_a, **_k):
            raise AssertionError("the console client was invoked")

    service = PublishService(_NeverCalled())  # type: ignore[arg-type]
    for scenario_id in (None, "", "bad id"):
        result = service.shadow(compiled_package=HOSTILE_PACKAGE, scenario_id=scenario_id)
        assert result["code"] == PUBLISH_PAYLOAD_UNMAPPED
    # and with no console at all the refusal still comes first, not the gap
    assert PublishService(None).shadow(compiled_package={}, scenario_id=None)["code"] == PUBLISH_PAYLOAD_UNMAPPED
    assert PublishService(None).shadow(compiled_package={}, scenario_id=SCENARIO)["capability"] == "console_api"


def test_nothing_is_invented_for_the_console(no_network):
    reason = scenario_id_refusal(None)
    assert "invents none" in reason and "assertion" in reason and "operational signals" in reason
    assert scenario_id_refusal(SCENARIO) is None
    assert scenario_id_refusal("k8s_delete_during_freeze") is None


# --------------------------------------------------------------------------- #
# transport failure keeps the existing typed gap
# --------------------------------------------------------------------------- #
def test_transport_failure_keeps_the_typed_console_gap(client):
    _FakeConsole.status = 503
    result = _result(_post(client, {"compiled_package": {}, "scenario_id": SCENARIO}))
    assert result["available"] is False and result["capability"] == "console_api"
    assert "HTTP 503" in result["reason"] and result["result"] is None
    unreachable = build_studio_context(console_base_url="http://127.0.0.1:9")
    dead = TestClient(create_v2_app(ApiSettings(environment="test"), studio=unreachable))
    result = _result(_post(dead, {"compiled_package": {}, "scenario_id": SCENARIO}))
    assert result["available"] is False and result["capability"] == "console_api"
    assert "unreachable" in result["reason"]


# --------------------------------------------------------------------------- #
# what this step must not have changed
# --------------------------------------------------------------------------- #
def test_the_console_allowlist_is_exactly_the_four_routes():
    assert CONSOLE_ALLOWED_ROUTES == (
        ("POST", "/v1/governed-loop/shadow"),
        ("POST", "/v1/governed-loop/scenario/{scenario_id}"),
        ("GET", "/v1/audit"),
        ("GET", "/v1/audit/{correlation_id}"),
    )


def test_the_frozen_runtime_configuration_still_permits_one_destination_and_no_console():
    path = os.path.join(_REPO, "deployment", "governance-studio", "approved-runtime-config.json")
    cfg = json.load(open(path, encoding="utf-8"))
    (permitted,) = cfg["external_network_egress"]["permitted"]
    assert "UGENCE_STUDIO_REVIEW_SERVICE_URL" in permitted["destination"]
    assert any(s.startswith("console_base_url") for s in cfg["front_door_seams"]["absent_by_ruling"])
    assert "UGENCE_STUDIO_CONSOLE" not in json.dumps(cfg)


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def test_v1_and_v2_contract_bytes_and_the_generated_client_are_unchanged():
    from ugence_governance_studio_api.openapi import canonical_openapi_bytes
    from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes

    v1 = os.path.join(_APP, "contracts", "openapi.json")
    v2 = os.path.join(_APP, "contracts", "openapi_v2.json")
    assert _sha256(v1) == "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"
    assert _sha256(v2) == "dd63180dc91ba7842dc1dc2b6efb3dbc155ea3bd47200f40de7bac85d373f39a"
    assert open(v1, "rb").read() == canonical_openapi_bytes()
    assert open(v2, "rb").read() == canonical_v2_openapi_bytes()
    generated = json.load(open(os.path.join(_APP, "frontend", "src", "generated", "openapi-v2.hash.json")))
    assert _sha256(v2) in json.dumps(generated)
