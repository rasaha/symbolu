"""Front-door seam 6 in the studio backend (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md
§11, rulings FD-10.1 to FD-10.4): the worker shadow-run relay.

What these assert is that the studio RELAYS and nothing else. The §11.3 failure matrix
at this edge: row 1 (review URL unset: typed gap), row 2 (worker unreachable or an
older worker without the route: typed gap, never an empty run), row 3 (a workflow,
provider, mode or digest is not expressible: the contract refuses the key and nothing
goes out), row 4 (a replay is the worker's typed answer), row 7 (a tenant is not
expressible), row 8 (LIVE is not expressible; the mode word is pinned), row 9 (no
credential and no proof crosses on the start), row 10 (the in-process Simulate route
is unchanged). The worker is stood in for by a real local HTTP server because the
property under test is what goes over the wire.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from starlette.testclient import TestClient

from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.clients.review import (
    PROOF_HEADER,
    REVIEW_ALLOWED_ROUTES,
    SHADOW_RUN_MODE,
    START_ROUTE,
    ReviewServiceClient,
)
from ugence_governance_studio_api.services.studio_v2 import WORKER_RELAY_PATH, StartRunService
from ugence_governance_studio_api.settings import ApiSettings

STARTED = {
    "result": "STARTED", "started": True, "mode": "shadow", "instance_id": "shadow-abc",
    "workflow_id": "wf-shadow", "correlation_id": "c-1", "definition_digest": "shadow-v1",
    "advanced": True, "awaiting_external": True, "stop_reason": "ESCALATE", "reason": "",
    "workload_maturity": "FIXTURE_ONLY", "maturity": "REFERENCE_GRADE_SHADOW_ONLY",
    "identity_proof": "PRESENTED_UNPROVEN",
}


class _FakeWorker(BaseHTTPRequestHandler):
    received: list = []
    status = 200
    body: dict = dict(STARTED)
    has_route = True

    def log_message(self, *_args):
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
        raw = self.rfile.read(length)
        type(self).received.append({"path": self.path, "body": json.loads(raw) if raw else None,
                                    "headers": {k.lower(): v for k, v in self.headers.items()}})
        if self.path == "/review/runs" and type(self).has_route:
            return self._send(type(self).status, dict(type(self).body))
        return self._send(404, {"detail": "Not Found"})


@pytest.fixture()
def worker():
    _FakeWorker.received = []
    _FakeWorker.status = 200
    _FakeWorker.body = dict(STARTED)
    _FakeWorker.has_route = True
    server = HTTPServer(("127.0.0.1", 0), _FakeWorker)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture()
def client(worker):
    studio = build_studio_context(review_service_base_url=worker)
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


# --------------------------------------------------------------------------- #
# the relay
# --------------------------------------------------------------------------- #
def test_the_start_is_relayed_with_the_pinned_mode_and_the_answer_returned_unchanged(client):
    result = _result(client.post("/api/v2/review/runs", json={"correlation_id": "c-1"}))
    assert result["available"] is True and result["result"] == STARTED
    assert result["path"] == WORKER_RELAY_PATH and result["path"]["path"] == "worker_shadow_run"
    assert result["path"]["maturity"] == "REFERENCE_GRADE_SHADOW_ONLY"
    (sent,) = _FakeWorker.received
    assert sent["path"] == "/review/runs"
    assert sent["body"] == {"mode": SHADOW_RUN_MODE, "correlation_id": "c-1"}
    assert set(sent["body"]) <= {"mode", "correlation_id"}, "nothing else crosses (FD-10.3)"
    assert "authorization" not in sent["headers"] and PROOF_HEADER.lower() not in sent["headers"]


def test_without_a_correlation_id_only_the_mode_word_is_sent(client):
    _result(client.post("/api/v2/review/runs", json={}))
    assert _FakeWorker.received[-1]["body"] == {"mode": SHADOW_RUN_MODE}


def test_row_4_and_the_workers_refusals_are_the_answer_not_a_transport_fault(client):
    _FakeWorker.body = dict(STARTED, result="REPLAYED", advanced=False)
    replay = _result(client.post("/api/v2/review/runs", json={"correlation_id": "c-1"}))
    assert replay["available"] is True and replay["result"]["result"] == "REPLAYED"
    for refusal in ("REFUSED_MODE", "REFUSED_DEFINITION", "REFUSED_CONFLICT", "REFUSED_UNCONFIGURED"):
        _FakeWorker.status = 409
        _FakeWorker.body = dict(STARTED, result=refusal, started=False, reason="the worker said so")
        answer = _result(client.post("/api/v2/review/runs", json={"correlation_id": "c-1"}))
        assert answer["available"] is True
        assert answer["result"]["result"] == refusal and answer["result"]["started"] is False
        assert answer["result"]["reason"] == "the worker said so"


# --------------------------------------------------------------------------- #
# rows 3, 7, 8: not expressible
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("body", [
    {"workflow": {"workflow_id": "wf-mine", "tasks": []}},
    {"workflow_id": "wf-mine"},
    {"tasks": [{"task_id": "t1"}]},
    {"provider_id": "openai"},
    {"definition_digest": "other"},
    {"mode": "live"},
    {"mode": "shadow"},
    {"execution_mode": "LIVE"},
    {"tenant_id": "tenant-b"},
    {"instance_id": "chosen"},
    {"inputs": {"x": 1}},
    {"correlation_id": ""},
    {"correlation_id": "has space"},
    {"correlation_id": "a" * 65},
    {"correlation_id": 7},
])
def test_rows_3_7_8_nothing_but_a_typed_correlation_id_is_expressible(client, body):
    response = client.post("/api/v2/review/runs", json=body)
    assert response.status_code == 422, response.text
    assert _FakeWorker.received == [], "refused at the contract; nothing went out"


def test_row_8_the_client_has_no_way_to_send_another_mode(worker):
    import inspect

    params = inspect.signature(ReviewServiceClient.start_shadow_run).parameters
    assert set(params) == {"self", "correlation_id"}
    assert START_ROUTE == ("POST", "/review/runs") and START_ROUTE in REVIEW_ALLOWED_ROUTES
    ReviewServiceClient(worker).start_shadow_run("c-2")
    assert _FakeWorker.received[-1]["body"]["mode"] == "shadow"


# --------------------------------------------------------------------------- #
# rows 1 and 2: gaps, never an empty run
# --------------------------------------------------------------------------- #
def test_row_1_an_unconfigured_review_service_is_a_typed_gap():
    unconfigured = TestClient(create_v2_app(ApiSettings(environment="test")))
    result = _result(unconfigured.post("/api/v2/review/runs", json={"correlation_id": "c"}))
    assert result["available"] is False and result["capability"] == "review_service"
    assert result["result"] is None and "no governed review service" in result["reason"]
    assert StartRunService(review=None).start(correlation_id=None)["available"] is False


def test_row_2_an_older_worker_without_the_route_or_an_unreachable_one_is_a_gap(client, worker):
    _FakeWorker.has_route = False
    older = _result(client.post("/api/v2/review/runs", json={"correlation_id": "c"}))
    assert older["available"] is False and older["capability"] == "review_service"
    assert "no start route" in older["reason"] and older["result"] is None
    unreachable = build_studio_context(review_service_base_url="http://127.0.0.1:9")
    gone = TestClient(create_v2_app(ApiSettings(environment="test"), studio=unreachable))
    result = _result(gone.post("/api/v2/review/runs", json={"correlation_id": "c"}))
    assert result["available"] is False and "unreachable" in result["reason"]


# --------------------------------------------------------------------------- #
# row 9: no credential on the start; row 10: the in-process Simulate is unchanged
# --------------------------------------------------------------------------- #
def test_row_9_a_proof_presented_on_the_start_is_never_forwarded(client):
    _result(client.post("/api/v2/review/runs", json={"correlation_id": "c"},
                        headers={PROOF_HEADER: "opaque-proof-value"}))
    (sent,) = _FakeWorker.received
    assert PROOF_HEADER.lower() not in sent["headers"]
    assert "opaque-proof-value" not in json.dumps(sent)


def test_row_10_the_in_process_simulate_route_is_a_separate_path(client):
    result = _result(client.post("/api/v2/simulate/run", json={
        "workflow": {"workflow_id": "w", "tasks": [{"task_id": "t1", "operation": "prepare",
                                                     "provider_id": "fixture"}]},
        "execution_mode": "DRY_RUN"}))
    assert result["available"] is False and result["capability"] == "simulation_providers"
    assert _FakeWorker.received == [], "the in-process path never reaches the worker"


def test_the_relay_service_holds_no_definition_provider_mode_or_digest():
    import inspect

    assert set(inspect.signature(StartRunService.start).parameters) == {"self", "correlation_id"}
    assert WORKER_RELAY_PATH["providers"] == "FIXTURE_ONLY"
    assert "sends no workflow, task, provider, mode or digest" in WORKER_RELAY_PATH["definition"]
