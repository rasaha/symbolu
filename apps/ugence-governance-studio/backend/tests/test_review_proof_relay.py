"""Row 14 of the approver-identity failure matrix (AI-B, owner ruling ID-1).

The studio may forward ONE opaque, review-service-bound approver proof, in
``X-Ugence-Approver-Proof``, on the decision relay only. These tests hold, over a real
local HTTP stand-in for the review service and with the root logger captured at DEBUG:

- no decode: the header value reaches the review service byte-for-byte, whatever it
  contains, and the studio's source never decodes, parses or inspects it;
- no log line: the value appears in no log record emitted while it is relayed;
- no store: the value appears in no attribute of the studio context, the relay service
  or the client after the request, and no source under the package persists it;
- no reuse: a second decision without the header is relayed without it, and a proof
  presented on a read is not forwarded, even when the client is asked to;
- absent from every other route: the four reads never carry the header;
- no schema: the header is declared in no OpenAPI operation, so the generated client
  type and the v2 boundary manifest are unchanged.
"""
from __future__ import annotations

import ast
import gc
import json
import logging
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from starlette.testclient import TestClient

import ugence_governance_studio_api as pkg
from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.clients.review import (
    PROOF_HEADER,
    PROOF_ROUTE,
    REVIEW_ALLOWED_ROUTES,
    ReviewServiceClient,
    ReviewServiceUnavailable,
)
from ugence_governance_studio_api.settings import ApiSettings

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent

#: Deliberately not base64, not JSON, not a JWT shape: whatever it is, it is bytes.
PROOF = "opaque-proof-7f3e|not/for=the:studio;to,read"
BODY = {
    "approval_id": "apr-1", "decision": "GRANT",
    "presented_approver": {"approver_id": "issuer.example|alice", "approver_kind": "HUMAN",
                           "role": "risk-approver", "authority_reference": "directory://x"},
    "justification": "reviewed the proposal",
}


class _FakeReview(BaseHTTPRequestHandler):
    """Records method, path, body and the proof header (or None) of every request."""

    received: list = []

    def log_message(self, *_args):
        pass

    def _send(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _record(self, method, body=None):
        type(self).received.append((method, self.path, body, self.headers.get(PROOF_HEADER)))

    def do_GET(self):
        self._record("GET")
        if self.path.startswith("/review/queue"):
            return self._send(200, {"entries": [], "identity_proof": "PRESENTED_UNPROVEN"})
        if self.path == "/review/runs/i1":
            return self._send(200, {"instance": {}, "engine": {}, "open_approvals": []})
        if self.path == "/review/runs/i1/events":
            return self._send(200, {"instance_id": "i1", "events": []})
        if self.path == "/review/approvals/apr-1":
            return self._send(200, {"approval_id": "apr-1", "events": []})
        return self._send(404, {"detail": "unknown"})

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self._record("POST", body)
        return self._send(200, {"result": "RECORDED", "recorded": True,
                                "identity_proof": "PRESENTED_UNPROVEN",
                                "authentication_reference": "authn:sha256:" + "0" * 64})


@pytest.fixture()
def review_server():
    _FakeReview.received = []
    server = HTTPServer(("127.0.0.1", 0), _FakeReview)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture()
def world(review_server):
    studio = build_studio_context(review_service_base_url=review_server)
    client = TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))
    return client, studio


def _posts():
    return [r for r in _FakeReview.received if r[0] == "POST"]


def _walk(obj, seen=None, depth=0):
    """Every string reachable from ``obj`` through attributes, mappings and sequences."""
    seen = seen if seen is not None else set()
    if id(obj) in seen or depth > 6:
        return
    seen.add(id(obj))
    if isinstance(obj, str):
        yield obj
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(k, seen, depth + 1)
            yield from _walk(v, seen, depth + 1)
        return
    if isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            yield from _walk(v, seen, depth + 1)
        return
    for v in vars(obj).values() if hasattr(obj, "__dict__") else ():
        yield from _walk(v, seen, depth + 1)


# --------------------------------------------------------------------------- #
# no decode, no log line
# --------------------------------------------------------------------------- #
def test_the_proof_is_forwarded_byte_for_byte_on_the_decision_relay_and_never_logged(world, caplog):
    client, _studio = world
    caplog.set_level(logging.DEBUG)
    response = client.post("/api/v2/review/decisions", json=BODY, headers={PROOF_HEADER: PROOF})
    assert response.status_code == 200, response.text
    assert response.json()["result"]["result"]["result"] == "RECORDED"

    posts = _posts()
    assert len(posts) == 1 and posts[0][1] == "/review/decisions"
    assert posts[0][3] == PROOF, "forwarded exactly as presented; nothing decoded or rewritten"
    assert json.loads(posts[0][2]) == BODY, "the body is unchanged: the proof is not merged into it"

    assert PROOF not in response.text and PROOF not in str(response.headers)
    for record in caplog.records:
        assert PROOF not in record.getMessage() and PROOF not in str(record.args)
    assert PROOF not in caplog.text


def test_the_source_never_decodes_parses_or_persists_the_proof():
    """No base64/JSON/JWT decode of the header, no storage of it, anywhere in the package."""
    users = []
    for src in sorted(PKG_DIR.rglob("*.py")):
        text = src.read_text()
        if "PROOF_HEADER" not in text and "proof" not in text.lower():
            continue
        users.append(src.relative_to(PKG_DIR).as_posix())
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                operands = list(node.args) + [k.value for k in node.keywords]
                if isinstance(fn, ast.Attribute):
                    operands.append(fn.value)
                touches_proof = any(isinstance(n, ast.Name) and n.id == "proof"
                                    for a in operands for n in ast.walk(a))
                if touches_proof:
                    # The only calls the proof value may reach: the relay chain. Never
                    # a decoder, parser, logger, formatter or store.
                    assert name in ("submit_decision", "_request", "_guard"), \
                        (src.name, name, node.lineno)
        for root in ("base64", "jwt", "jose", "hashlib", "logging", "shelve", "pickle", "sqlite3"):
            assert f"import {root}" not in text and f"from {root}" not in text, (src.name, root)
        assert "self._proof" not in text and "proof_cache" not in text, src.name
    assert set(users) == {"api/v2/review.py", "clients/review.py", "services/studio_v2.py"}, users


# --------------------------------------------------------------------------- #
# no store, no reuse
# --------------------------------------------------------------------------- #
def test_the_proof_is_held_nowhere_after_the_request_and_not_reused_on_the_next(world):
    client, studio = world
    client.post("/api/v2/review/decisions", json=BODY, headers={PROOF_HEADER: PROOF})
    gc.collect()
    for text in _walk(studio):
        assert PROOF not in text, "the proof survived in the studio context"
    for text in _walk(studio.review):
        assert PROOF not in text, "the proof survived in the relay service"

    client.post("/api/v2/review/decisions", json=dict(BODY, decision="REJECT"))
    posts = _posts()
    assert [p[3] for p in posts] == [PROOF, None], "the second relay carries no proof from the first"


def test_a_proof_presented_on_a_read_is_never_forwarded(world):
    client, _studio = world
    for path in ("/api/v2/review/queue", "/api/v2/review/runs/i1",
                 "/api/v2/review/runs/i1/events", "/api/v2/review/approvals/apr-1"):
        assert client.get(path, headers={PROOF_HEADER: PROOF}).status_code == 200
    reads = [r for r in _FakeReview.received if r[0] == "GET"]
    assert len(reads) == 4 and all(r[3] is None for r in reads)
    assert _posts() == []


def test_the_client_refuses_to_attach_a_proof_to_any_route_but_the_decision_relay(review_server):
    client = ReviewServiceClient(review_server)
    assert PROOF_ROUTE == ("POST", "/review/decisions") and PROOF_ROUTE in REVIEW_ALLOWED_ROUTES
    for method, template in REVIEW_ALLOWED_ROUTES:
        if (method, template) == PROOF_ROUTE:
            continue
        with pytest.raises(ReviewServiceUnavailable, match="may only accompany"):
            client._request(method, template, path_params={"instance_id": "i1",  # noqa: SLF001
                                                            "approval_id": "apr-1"},
                            proof=PROOF)
    assert _FakeReview.received == [], "refused before a connection was opened"
    client.submit_decision(BODY)  # no proof: no header at all, not an empty one
    assert _posts()[-1][3] is None


# --------------------------------------------------------------------------- #
# absent from the schema and the manifest
# --------------------------------------------------------------------------- #
def test_the_header_is_declared_in_no_operation_so_the_contract_is_unchanged(world):
    client, _studio = world
    spec = client.get("/openapi.json").json()
    for path, ops in spec["paths"].items():
        for op in ops.values():
            for param in op.get("parameters", []):
                assert param.get("in") != "header", (path, param)
    text = json.dumps(spec)
    assert PROOF_HEADER not in text and "proof" not in text.lower()
