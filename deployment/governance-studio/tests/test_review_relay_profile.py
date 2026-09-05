"""The CR-2 amendment (ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md, step 3).

Row 4 of the ADR's failure matrix: the studio deployed without the review-service URL
reports a typed gap on every review route, never an empty queue. ID-1: the approver
proof travels through this process to the review service verbatim and is never logged
or stored. And the profile's boundary: the variable reaches the studio context and
nothing else; production accepts only an https origin; v1 is served unchanged.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from starlette.testclient import TestClient

from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig
from governance_studio_deployment.logging_utils import log_event

from depaths import CERTS, FRONTEND_DIR, MANIFEST, REPO, SCENARIOS_ROOT, USERNAME, PASSWORD  # noqa: F401
from conftest import basic_auth

PROOF_HEADER = "X-Ugence-Approver-Proof"
PROOF = "opaque.proof.value-that-must-pass-through-untouched"
REVIEW_PATHS = ("/api/v2/review/queue", "/api/v2/review/runs/i1",
                "/api/v2/review/runs/i1/events", "/api/v2/review/approvals/a1")
DECISION = {"approval_id": "a1", "decision": "GRANT", "justification": "reviewed",
            "presented_approver": {"approver_id": "alice", "approver_kind": "HUMAN",
                                   "role": "risk-approver", "authority_reference": "x"}}


def _headers(**extra) -> dict:
    return {"Authorization": basic_auth(), "X-Ugence-Request": "GovernanceStudio",
            "Origin": "http://testserver", **extra}


class _ReviewStandIn:
    """A loopback stand-in for the governed runtime worker's listener. Records every
    request it receives so the relay can be checked byte for byte."""

    def __init__(self) -> None:
        self.requests: list = []
        stand_in = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def _record(self, body: bytes) -> None:
                stand_in.requests.append({
                    "method": self.command, "path": self.path,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": body.decode("utf-8") if body else "",
                })

            def do_GET(self):
                self._record(b"")
                self._send({"entries": [], "maturity": "REFERENCE_GRADE_SHADOW_ONLY",
                            "identity_proof": "PRESENTED_UNPROVEN"} if self.path.startswith("/review/queue")
                           else {"instance": {"status": "PAUSED"}, "events": [], "linkages": []})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                self._record(self.rfile.read(length))
                self._send({"result": "REFUSED_UNAUTHENTICATED", "recorded": False,
                            "reason": "stand-in"}, status=409)

            def _send(self, payload: dict, status: int = 200) -> None:
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._server.shutdown()
        self._server.server_close()


def _config(password_hash: str, tmp_path, **over) -> DeploymentConfig:
    return DeploymentConfig.from_env(
        mode="test", username=USERNAME, password_hash=password_hash,
        tls_cert_file=os.path.join(CERTS, "server.crt"), tls_key_file=os.path.join(CERTS, "server.key"),
        allowed_hosts=["localhost", "127.0.0.1", "testserver"], frontend_dir=FRONTEND_DIR,
        scenarios_root=SCENARIOS_ROOT, manifest_path=MANIFEST, runtime_dir=str(tmp_path), **over,
    )


def _client(config: DeploymentConfig) -> TestClient:
    app = build_app(config, readiness=lambda: True, tracker=FailureTracker(), sleep=lambda _s: None)
    return TestClient(app, base_url="http://testserver", raise_server_exceptions=True)


# --------------------------------------------------------------------------- #
# row 4: unset URL is a typed gap on every review route, never an empty queue
# --------------------------------------------------------------------------- #
def test_row_4_unset_review_url_is_a_typed_gap_on_every_review_route(config):
    assert not config.review_service_configured
    with _client(config) as client:
        for path in REVIEW_PATHS:
            r = client.get(path, headers=_headers())
            assert r.status_code == 200, (path, r.text)
            body = r.json()["result"]  # the v2 envelope; the gap is its result
            assert body["available"] is False and body["capability"] == "review_service"
            assert body["result"] is None and "no governed review service" in body["reason"]
        r = client.post("/api/v2/review/decisions", headers=_headers(**{"Content-Type": "application/json"}),
                        json=DECISION)
        assert r.status_code == 200
        gap = r.json()["result"]
        assert gap["available"] is False and gap["capability"] == "review_service"


def test_the_review_routes_sit_behind_the_same_gate_as_v1(config):
    with _client(config) as client:
        assert client.get("/api/v2/review/queue").status_code == 401
        assert client.get("/api/v2/review/queue", headers={"Authorization": basic_auth(pw="wrong")}).status_code == 401
        assert client.get("/api/v1/scenarios", headers=_headers()).status_code == 200
        assert client.get("/openapi.json", headers=_headers()).status_code == 404


# --------------------------------------------------------------------------- #
# ID-1: the proof passes through verbatim and is never logged or stored
# --------------------------------------------------------------------------- #
def test_id_1_the_proof_header_reaches_the_review_service_verbatim_and_only_on_decisions(
        password_hash, tmp_path, capsys):
    with _ReviewStandIn() as review:
        cfg = _config(password_hash, tmp_path, review_service_url=review.url)
        assert cfg.review_service_configured and cfg.validate() == []
        with _client(cfg) as client:
            queue = client.get("/api/v2/review/queue", headers=_headers(**{PROOF_HEADER: PROOF}))
            assert queue.status_code == 200 and queue.json()["result"]["available"] is True
            assert queue.json()["result"]["result"]["entries"] == []
            decided = client.post("/api/v2/review/decisions",
                                  headers=_headers(**{PROOF_HEADER: PROOF, "Content-Type": "application/json"}),
                                  json=DECISION)
            assert decided.status_code == 200
            relayed = decided.json()["result"]
            assert relayed["available"] is True
            assert relayed["result"]["result"] == "REFUSED_UNAUTHENTICATED"

    listed, posted = review.requests
    assert listed["method"] == "GET" and listed["path"] == "/review/queue"
    assert PROOF_HEADER.lower() not in listed["headers"], "reads never carry the proof"
    assert posted["method"] == "POST" and posted["path"] == "/review/decisions"
    assert posted["headers"][PROOF_HEADER.lower()] == PROOF
    assert json.loads(posted["body"])["approval_id"] == "a1"
    assert "authorization" not in posted["headers"], "the studio credential never leaves the studio"

    captured = capsys.readouterr()
    assert PROOF not in captured.out + captured.err
    assert PROOF not in decided.text and PROOF not in queue.text
    assert not [p for p in os.listdir(tmp_path) if PROOF in open(os.path.join(tmp_path, p), errors="ignore").read()
                if os.path.isfile(os.path.join(tmp_path, p))]


def test_the_log_writer_drops_a_proof_or_the_review_url_even_if_handed_one(capsys):
    log_event("request", method="POST", path="/api/v2/review/decisions", proof=PROOF,
              **{"x-ugence-approver-proof": PROOF, "review_service_url": "https://worker.internal:8444"})
    line = capsys.readouterr().out
    assert PROOF not in line and "worker.internal" not in line


# --------------------------------------------------------------------------- #
# the variable: one reader, one shape
# --------------------------------------------------------------------------- #
def test_the_variable_is_read_by_the_config_and_handed_to_the_studio_context_only():
    src = os.path.join(REPO, "deployment", "governance-studio", "src", "governance_studio_deployment")
    readers = []
    for name in sorted(os.listdir(src)):
        if name.endswith(".py"):
            text = open(os.path.join(src, name), encoding="utf-8").read()
            if '"UGENCE_STUDIO_REVIEW_SERVICE_URL"' in text:  # the literal a reader needs
                readers.append(name)
    assert readers == ["config.py"]
    app_src = open(os.path.join(src, "app.py"), encoding="utf-8").read()
    assert app_src.count("review_service_url") == 1
    assert "build_studio_context(review_service_base_url=config.review_service_url" in app_src


@pytest.mark.parametrize("url,production,ok", [
    ("https://worker.internal:8444", True, True),
    ("https://10.0.0.7:8444/", True, True),
    ("http://worker.internal:8444", True, False),
    ("http://127.0.0.1:8444", True, False),
    ("http://127.0.0.1:8444", False, True),
    ("http://worker.internal:8444", False, False),
    ("https://user:pw@worker.internal:8444", True, False),
    ("https://worker.internal:8444/?x=1", True, False),
    ("worker.internal:8444", True, False),
    ("ftp://worker.internal", True, False),
])
def test_review_url_is_an_https_origin_without_credential_query_or_fragment(
        password_hash, tmp_path, url, production, ok):
    cfg = _config(password_hash, tmp_path, review_service_url=url)
    cfg = DeploymentConfig(**{**cfg.__dict__, "mode": "production" if production else "test",
                              "allowed_hosts": ["worker.internal"]})
    errors = [e for e in cfg.validate() if "REVIEW_SERVICE_URL" in e]
    assert (errors == []) is ok, errors
    assert cfg.review_service_url == url.strip().rstrip("/") or not ok


def test_from_env_reads_the_variable_and_strips_a_trailing_slash(monkeypatch, password_hash, tmp_path):
    monkeypatch.setenv("UGENCE_STUDIO_REVIEW_SERVICE_URL", "https://worker.internal:8444/")
    cfg = _config(password_hash, tmp_path)
    assert cfg.review_service_url == "https://worker.internal:8444"
    monkeypatch.delenv("UGENCE_STUDIO_REVIEW_SERVICE_URL")
    assert _config(password_hash, tmp_path).review_service_url == ""


# --------------------------------------------------------------------------- #
# the image carries what the served backend imports, and nothing else new
# --------------------------------------------------------------------------- #
def test_the_dockerfile_installs_every_distribution_the_served_backend_imports(config):
    with _client(config) as client:
        client.get("/api/v2/review/queue", headers=_headers())
    distributions = set()
    for name, module in list(sys.modules.items()):
        location = getattr(module, "__file__", None) or ""
        if name.startswith("ugence_") and "/src/" in location:
            distributions.add(os.path.relpath(location.split("/src/")[0], REPO))
    dockerfile = open(os.path.join(REPO, "deployment", "governance-studio", "Dockerfile"), encoding="utf-8").read()
    for distribution in sorted(distributions):
        assert f"COPY {distribution} /build/" in dockerfile, distribution
    assert distributions == {"apps/ugence-governance-studio/backend",
                             "packages/capabilities/agent-workforce-composer",
                             "packages/runtime/agent-runtime",
                             "packages/tooling/policy-workflow-compiler"}
