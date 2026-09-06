"""Front-door seam 7 in the studio backend (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md
§12, rulings FD-11.1 to FD-11.5): Observe over the worker's ledger, relay only.

The §12.4 failure matrix at this edge: row 1 (review URL unset: typed gap), row 2
(older worker without the route, or unreachable: typed gap, never an empty chain),
row 3 (unknown correlation id: the worker's typed not-found, distinguished from
unreachable), row 4 (a chain that does not verify: the worker's typed refusal passed
through, entries withheld), row 7 (no tenant is expressible), row 8 (no write is
expressible), row 9 (no credential or proof crosses on the read), row 10 (the console
path unchanged). The worker is stood in for by a real local HTTP server because the
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
    AUDIT_ROUTE,
    PROOF_HEADER,
    REVIEW_ALLOWED_ROUTES,
    ReviewServiceClient,
)
from ugence_governance_studio_api.services.studio_v2 import WORKER_LEDGER_SOURCE, LedgerObserveService
from ugence_governance_studio_api.settings import ApiSettings

READ = {
    "result": "READ", "read": True, "tenant_id": "tenant-a", "correlation_id": "c-1",
    "entries": [{"seq": 1, "entry_ref": "tenant-a/1", "kind": "governed_review.linkage.v2",
                 "recorded_at": "2026-09-06T09:00:00+00:00", "recorded_by": "governed-runtime-worker",
                 "correlation_id": "c-1", "payload": {"instance_id": "shadow-1"},
                 "prev_digest": "0" * 64, "record_digest": "a" * 64}],
    "entry_count": 1, "chain_verified": True, "reason": "",
    "record_type": "control_plane_root audit-ledger rows, raw and uninterpreted",
    "maturity": "REFERENCE_GRADE_SHADOW_ONLY",
}


class _FakeWorker(BaseHTTPRequestHandler):
    received: list = []
    status = 200
    body: dict = dict(READ)
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

    def do_GET(self):
        type(self).received.append({"method": "GET", "path": self.path,
                                    "headers": {k.lower(): v for k, v in self.headers.items()}})
        if self.path.startswith("/review/audit/") and type(self).has_route:
            if self.path.endswith("/c-unknown"):
                return self._send(404, {"detail": "no entry of this tenant carries that correlation id"})
            return self._send(type(self).status, dict(type(self).body))
        return self._send(404, {"detail": "Not Found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        type(self).received.append({"method": "POST", "path": self.path, "headers": {}})
        return self._send(404, {"detail": "Not Found"})


@pytest.fixture()
def worker():
    _FakeWorker.received = []
    _FakeWorker.status = 200
    _FakeWorker.body = dict(READ)
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


def test_the_read_is_relayed_and_the_workers_answer_returned_unchanged_with_the_source_label(client):
    result = _result(client.get("/api/v2/observe/ledger/c-1", headers={PROOF_HEADER: "opaque"}))
    assert result["available"] is True and result["found"] is True and result["result"] == READ
    assert result["source"] == WORKER_LEDGER_SOURCE and result["source"]["source"] == "worker_audit_ledger"
    assert "raw and uninterpreted" in result["source"]["record_type"]
    (sent,) = _FakeWorker.received
    assert sent["method"] == "GET" and sent["path"] == "/review/audit/c-1"
    assert "authorization" not in sent["headers"] and PROOF_HEADER.lower() not in sent["headers"]
    assert "?" not in sent["path"], "no tenant, no filter (row 7)"


def test_row_3_an_unknown_correlation_id_is_the_workers_typed_not_found(client):
    result = _result(client.get("/api/v2/observe/ledger/c-unknown"))
    assert result["available"] is True and result["found"] is False and result["result"] is None
    assert result["source"]["source"] == "worker_audit_ledger"


def test_row_4_the_workers_refusals_pass_through_with_entries_withheld(client):
    for refusal in ("REFUSED_INTEGRITY", "REFUSED_SCHEMA", "REFUSED_UNCONFIGURED"):
        _FakeWorker.status = 409
        _FakeWorker.body = dict(READ, result=refusal, read=False, entries=[], entry_count=0,
                                chain_verified=False, reason="the worker said so")
        answer = _result(client.get("/api/v2/observe/ledger/c-1"))
        assert answer["available"] is True and answer["found"] is True
        assert answer["result"]["result"] == refusal and answer["result"]["entries"] == []
        assert answer["result"]["chain_verified"] is False and answer["result"]["reason"] == "the worker said so"


def test_row_1_an_unconfigured_review_service_is_a_typed_gap():
    unconfigured = TestClient(create_v2_app(ApiSettings(environment="test")))
    result = _result(unconfigured.get("/api/v2/observe/ledger/c-1"))
    assert result["available"] is False and result["capability"] == "review_service"
    assert result["result"] is None and "no governed review service" in result["reason"]
    assert LedgerObserveService(review=None).chain("c-1")["available"] is False


def test_row_2_an_older_worker_or_an_unreachable_one_is_a_gap_never_an_empty_chain(client):
    _FakeWorker.has_route = False
    older = _result(client.get("/api/v2/observe/ledger/c-1"))
    assert older["available"] is True and older["found"] is False, "a 404 from an older worker is not-found"
    gone = TestClient(create_v2_app(ApiSettings(environment="test"),
                                    studio=build_studio_context(review_service_base_url="http://127.0.0.1:9")))
    result = _result(gone.get("/api/v2/observe/ledger/c-1"))
    assert result["available"] is False and "unreachable" in result["reason"]


def test_row_8_no_write_is_expressible_and_row_9_the_client_sends_nothing_but_the_path(client, worker):
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        assert client.request(method, "/api/v2/observe/ledger/c-1", json={}).status_code == 405, method
    assert _FakeWorker.received == []
    import inspect

    assert set(inspect.signature(ReviewServiceClient.read_audit).parameters) == {"self", "correlation_id"}
    assert AUDIT_ROUTE == ("GET", "/review/audit/{correlation_id}") and AUDIT_ROUTE in REVIEW_ALLOWED_ROUTES
    ReviewServiceClient(worker).read_audit("c/with/slash")
    assert _FakeWorker.received[-1]["path"] == "/review/audit/c%2Fwith%2Fslash", "quoted: one route"


def test_row_10_the_console_path_is_unchanged(client):
    result = _result(client.get("/api/v2/observe/audit/c-1"))
    assert result["available"] is False and result["capability"] == "console_api"
    assert _FakeWorker.received == []


def test_the_relay_service_holds_no_tenant_and_interprets_nothing():
    import inspect

    assert set(inspect.signature(LedgerObserveService.chain).parameters) == {"self", "correlation_id"}
    assert WORKER_LEDGER_SOURCE["maturity"] == "REFERENCE_GRADE"
    assert "re-derives nothing" in WORKER_LEDGER_SOURCE["executor"]
