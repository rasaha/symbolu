"""Screens 7 and 8 — the review relay (GAS-7, HR-D), under owner ruling HR-1.

What these assert is that the studio DISPLAYS and TRANSMITS and does nothing else: the
decision body reaches the review service byte-for-byte as the studio received it, the
studio's review client cannot reach anything but the five audited routes, an
unreachable review service is a gap and never an empty queue, and a HOLD is never
presented as awaiting a human (HR-5). The review service is stood in for by a real
local HTTP server, because the property under test is what goes over the wire.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from starlette.testclient import TestClient

from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.clients.review import (
    REVIEW_ALLOWED_ROUTES,
    ReviewNotFound,
    ReviewServiceClient,
    ReviewServiceUnavailable,
)
from ugence_governance_studio_api.settings import ApiSettings

PROHIBITED = ("issue", "activate", "revoke", "grant", "authorize", "clear", "execute",
              "resume", "release", "continue", "signal", "retry")

ENTRY_ESCALATE = {
    "approval_id": "apr-1", "approval_state": "PENDING", "instance_id": "i1", "task_id": "t1",
    "fingerprint": "f" * 64, "required_role": "risk-approver", "requested_by": "governed-review",
    "requested_at": "2026-09-05T09:00:00+00:00", "expires_at": "2026-09-12T09:00:00+00:00",
    "justification": "parked", "workflow_id": "wf", "workflow_status": "PAUSED",
    "task_status": "WAITING", "provider_id": "p", "operation": "op",
    "governance_disposition": "ESCALATE",
    "eligible_approvers": [{"approver_id": "approver-1", "approver_kind": "HUMAN",
                            "role": "risk-approver", "authority_reference": ""}],
    "instance_known": True,
}
ENTRY_HOLD = dict(ENTRY_ESCALATE, approval_id="apr-h", instance_id="ih",
                  governance_disposition="HOLD", workflow_status="WAITING")


class _FakeReview(BaseHTTPRequestHandler):
    """A stand-in review service. Records every request it receives."""

    received: list = []
    queue_entries: list = []
    decision_status = 200
    decision_body: dict = {"result": "RECORDED", "recorded": True, "identity_proof": "PRESENTED_UNPROVEN"}

    def log_message(self, *_args):  # silence
        pass

    def _send(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        type(self).received.append(("GET", self.path, None))
        if self.path.startswith("/review/queue"):
            return self._send(200, {"entries": list(type(self).queue_entries),
                                    "maturity": "REFERENCE_GRADE_SHADOW_ONLY",
                                    "identity_proof": "PRESENTED_UNPROVEN"})
        if self.path == "/review/runs/i1":
            return self._send(200, {"instance": {"status": "PAUSED"}, "engine": {"known": True},
                                    "open_approvals": [], "identity_proof": "PRESENTED_UNPROVEN"})
        if self.path == "/review/runs/i1/events":
            return self._send(200, {"instance_id": "i1", "events": []})
        if self.path == "/review/approvals/apr-1":
            return self._send(200, {"approval_id": "apr-1", "state_at": "PENDING", "events": []})
        return self._send(404, {"detail": "unknown"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        type(self).received.append(("POST", self.path, body))
        if self.path == "/review/decisions":
            return self._send(type(self).decision_status, dict(type(self).decision_body))
        return self._send(404, {"detail": "unknown"})


@pytest.fixture()
def review_server():
    _FakeReview.received = []
    _FakeReview.queue_entries = [ENTRY_ESCALATE]
    _FakeReview.decision_status = 200
    server = HTTPServer(("127.0.0.1", 0), _FakeReview)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture()
def relay_client(review_server):
    studio = build_studio_context(review_service_base_url=review_server)
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


# --------------------------------------------------------------------------- #
# HR-1 — display and transmit, nothing else
# --------------------------------------------------------------------------- #
def test_the_decision_body_is_relayed_verbatim(relay_client):
    body = {
        "approval_id": "apr-1", "decision": "GRANT",
        "presented_approver": {"approver_id": "approver-1", "approver_kind": "HUMAN",
                               "role": "risk-approver", "authority_reference": "directory://x"},
        "justification": "reviewed the proposal",
    }
    result = _result(relay_client.post("/api/v2/review/decisions", json=body))
    assert result["available"] is True and result["result"]["result"] == "RECORDED"
    posts = [r for r in _FakeReview.received if r[0] == "POST"]
    assert len(posts) == 1 and posts[0][1] == "/review/decisions"
    assert json.loads(posts[0][2]) == body, "forwarded exactly as received: nothing added"


def test_a_refused_decision_is_the_service_answer_not_a_transport_fault(relay_client):
    _FakeReview.decision_status = 409
    _FakeReview.decision_body = {"result": "REFUSED_INELIGIBLE", "recorded": False,
                                 "reason": "approver role 'auditor' is not the required"}
    body = {"approval_id": "apr-1", "decision": "REJECT",
            "presented_approver": {"approver_id": "x", "approver_kind": "HUMAN", "role": "auditor"},
            "justification": "no"}
    result = _result(relay_client.post("/api/v2/review/decisions", json=body))
    assert result["available"] is True
    assert result["result"]["result"] == "REFUSED_INELIGIBLE" and result["result"]["recorded"] is False


@pytest.mark.parametrize("body", [
    {"approval_id": "apr-1", "decision": "APPROVE", "presented_approver": {}, "justification": "x"},
    {"approval_id": "apr-1", "decision": "GRANT", "presented_approver": {}},
    {"approval_id": "apr-1", "decision": "GRANT", "presented_approver": {}, "justification": ""},
    {"approval_id": "apr-1", "decision": "GRANT", "presented_approver": {}, "justification": "x",
     "session": "abc"},
])
def test_a_malformed_or_widened_decision_is_never_relayed(relay_client, body):
    response = relay_client.post("/api/v2/review/decisions", json=body)
    assert response.status_code in (400, 422), response.text
    assert [r for r in _FakeReview.received if r[0] == "POST"] == []


def test_reads_render_what_the_review_service_returned(relay_client):
    queue = _result(relay_client.get("/api/v2/review/queue"))
    assert queue["available"] is True and queue["identity_proof"] == "PRESENTED_UNPROVEN"
    assert [e["approval_id"] for e in queue["result"]["entries"]] == ["apr-1"]
    run = _result(relay_client.get("/api/v2/review/runs/i1"))
    assert run["available"] is True and run["result"]["instance"]["status"] == "PAUSED"
    events = _result(relay_client.get("/api/v2/review/runs/i1/events"))
    assert events["result"]["events"] == []
    approval = _result(relay_client.get("/api/v2/review/approvals/apr-1"))
    assert approval["result"]["state_at"] == "PENDING"
    unknown = _result(relay_client.get("/api/v2/review/runs/nope"))
    assert unknown["available"] is True and unknown["found"] is False and unknown["result"] is None


def test_a_role_filter_is_forwarded_as_a_query(relay_client):
    _result(relay_client.get("/api/v2/review/queue", params={"required_role": "auditor"}))
    assert any(p == "/review/queue?required_role=auditor" for (_m, p, _b) in _FakeReview.received)


# --------------------------------------------------------------------------- #
# HR-5 — a HOLD is never presented as awaiting a human
# --------------------------------------------------------------------------- #
def test_a_hold_entry_is_filtered_and_counted(relay_client):
    _FakeReview.queue_entries = [ENTRY_ESCALATE, ENTRY_HOLD]
    queue = _result(relay_client.get("/api/v2/review/queue"))
    assert [e["instance_id"] for e in queue["result"]["entries"]] == ["i1"]
    assert queue["excluded_hold"] == 1


# --------------------------------------------------------------------------- #
# gap, not empty
# --------------------------------------------------------------------------- #
def test_an_unconfigured_review_service_is_a_gap():
    client = TestClient(create_v2_app(ApiSettings(environment="test")))
    for path in ("/api/v2/review/queue", "/api/v2/review/runs/i1",
                 "/api/v2/review/runs/i1/events", "/api/v2/review/approvals/a"):
        result = _result(client.get(path))
        assert result["available"] is False and result["capability"] == "review_service"
        assert result["result"] is None
    result = _result(client.post("/api/v2/review/decisions", json={
        "approval_id": "a", "decision": "GRANT", "presented_approver": {}, "justification": "x"}))
    assert result["available"] is False and result["capability"] == "review_service"


def test_an_unreachable_review_service_is_a_gap_never_an_empty_queue():
    studio = build_studio_context(review_service_base_url="http://review.invalid:9")
    client = TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))
    result = _result(client.get("/api/v2/review/queue"))
    assert result["available"] is False and result["capability"] == "review_service"
    assert "unreachable" in result["reason"] and result["result"] is None


def test_an_empty_queue_is_reported_as_reachable_and_empty(relay_client):
    _FakeReview.queue_entries = []
    queue = _result(relay_client.get("/api/v2/review/queue"))
    assert queue["available"] is True and queue["result"]["entries"] == []


# --------------------------------------------------------------------------- #
# the outbound edge
# --------------------------------------------------------------------------- #
def test_the_review_client_reaches_exactly_the_five_audited_routes():
    assert len(REVIEW_ALLOWED_ROUTES) == 5
    assert [m for m, _p in REVIEW_ALLOWED_ROUTES].count("POST") == 1
    for _method, path in REVIEW_ALLOWED_ROUTES:
        assert not any(v in path.lower() for v in PROHIBITED), path

    client = ReviewServiceClient("http://review.invalid")
    for method, path in (
        ("POST", "/review/resume"),
        ("POST", "/review/runs/{instance_id}/resume"),
        ("POST", "/review/signals"),
        ("POST", "/review/approvals/{approval_id}/grant"),
        ("POST", "/review/queue"),
        ("DELETE", "/review/approvals/{approval_id}"),
    ):
        with pytest.raises(ReviewServiceUnavailable) as excinfo:
            client._request(method, path)  # noqa: SLF001
        assert "not in the studio's permitted review route set" in str(excinfo.value)


def test_the_client_quotes_ids_so_a_slash_cannot_change_the_route(review_server):
    client = ReviewServiceClient(review_server)
    with pytest.raises(ReviewNotFound):
        client.run("i1/events")
    assert ("GET", "/review/runs/i1%2Fevents", None) in _FakeReview.received


def test_the_review_client_is_not_importable_from_the_studio_package_root():
    """Not part of the public API snapshot; a composition root wires it by module."""
    import ugence_governance_studio_api as pkg

    assert "ReviewServiceClient" not in pkg.__all__
