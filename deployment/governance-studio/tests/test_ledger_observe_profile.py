"""Front-door seam 7 in the P3E profile (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md §12,
rulings FD-11.1 to FD-11.5): Observe over the worker's ledger through the deployed studio.

The §12.4 failure matrix as tests at this edge. Row 1: the review URL unset is the typed
gap on the ledger route. Row 2: a worker without the route or unreachable is typed,
never an empty chain. Row 3: an unknown correlation id is the worker's typed not-found.
Row 4: a chain that does not verify is the worker's typed refusal passed through with
the entries withheld. Row 7: no tenant is expressible. Row 8: no write is expressible.
Row 9: no credential and no proof crosses on the read; the studio's Basic credential
never leaves the studio. Row 10: the console path is unchanged. Plus the freeze: seven
routes over the one destination, the manifest agrees, the third amendment recorded.
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from starlette.testclient import TestClient

from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig

from depaths import CERTS, FRONTEND_DIR, MANIFEST, REPO, SCENARIOS_ROOT, USERNAME  # noqa: F401
from conftest import basic_auth

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROOF_HEADER = "X-Ugence-Approver-Proof"
PROOF = "opaque.proof.value-that-must-never-travel-on-a-read"
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


def _headers(**extra) -> dict:
    return {"Authorization": basic_auth(), "X-Ugence-Request": "GovernanceStudio",
            "Origin": "http://testserver", **extra}


class _WorkerStandIn:
    def __init__(self, *, has_route: bool = True, status: int = 200, body: dict | None = None) -> None:
        self.requests: list = []
        stand_in = self
        answer = dict(body or READ)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def do_GET(self):
                stand_in.requests.append({"method": "GET", "path": self.path,
                                          "headers": {k.lower(): v for k, v in self.headers.items()}})
                if self.path.startswith("/review/audit/") and has_route:
                    if self.path.endswith("/c-unknown"):
                        return self._send({"detail": "unknown"}, 404)
                    return self._send(answer, status)
                self._send({"detail": "Not Found"}, 404)

            def _send(self, payload: dict, code: int) -> None:
                out = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

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


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_row_1_unset_review_url_is_a_typed_gap_on_the_ledger_route(config):
    assert not config.review_service_configured
    with _client(config) as client:
        gap = _result(client.get("/api/v2/observe/ledger/c-1", headers=_headers()))
        assert gap["available"] is False and gap["capability"] == "review_service"
        assert gap["result"] is None and "no governed review service" in gap["reason"]


def test_rows_7_and_9_the_read_is_relayed_with_nothing_of_the_studios_and_the_answer_returned(
        password_hash, tmp_path, capsys):
    with _WorkerStandIn() as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
        with _client(cfg) as client:
            r = client.get("/api/v2/observe/ledger/c-1", headers=_headers(**{PROOF_HEADER: PROOF}))
            assert r.status_code == 200
            relayed = r.json()["result"]
            assert relayed["available"] is True and relayed["found"] is True and relayed["result"] == READ
            assert relayed["source"]["source"] == "worker_audit_ledger"
            assert "raw and uninterpreted" in relayed["source"]["record_type"]
    (sent,) = worker.requests
    assert sent["method"] == "GET" and sent["path"] == "/review/audit/c-1", "no tenant, no filter (row 7)"
    assert "authorization" not in sent["headers"], "the studio credential never leaves the studio"
    assert PROOF_HEADER.lower() not in sent["headers"], "no proof travels on the read (ID-1)"
    captured = capsys.readouterr()
    assert PROOF not in captured.out + captured.err and PROOF not in r.text


def test_rows_3_and_4_not_found_and_the_workers_refusals_pass_through(password_hash, tmp_path):
    with _WorkerStandIn() as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
        with _client(cfg) as client:
            r = _result(client.get("/api/v2/observe/ledger/c-unknown", headers=_headers()))
            assert r["available"] is True and r["found"] is False and r["result"] is None
    for refusal in ("REFUSED_INTEGRITY", "REFUSED_SCHEMA", "REFUSED_UNCONFIGURED"):
        refused = dict(READ, result=refusal, read=False, entries=[], entry_count=0, chain_verified=False,
                       reason="the worker said so")
        with _WorkerStandIn(status=409, body=refused) as worker:
            cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
            with _client(cfg) as client:
                r = _result(client.get("/api/v2/observe/ledger/c-1", headers=_headers()))
                assert r["available"] is True and r["result"]["result"] == refusal
                assert r["result"]["entries"] == [] and r["result"]["chain_verified"] is False


def test_row_2_an_older_worker_without_the_route_or_an_unreachable_one(password_hash, tmp_path):
    with _WorkerStandIn(has_route=False) as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
        with _client(cfg) as client:
            r = _result(client.get("/api/v2/observe/ledger/c-1", headers=_headers()))
            assert r["available"] is True and r["found"] is False, "an older worker's 404 is typed not-found"
    cfg = _config(password_hash, tmp_path, review_service_url="http://127.0.0.1:9")
    with _client(cfg) as client:
        gap = _result(client.get("/api/v2/observe/ledger/c-1", headers=_headers()))
        assert gap["available"] is False and "unreachable" in gap["reason"]


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_row_8_no_write_is_expressible_and_nothing_goes_out(password_hash, tmp_path, method):
    with _WorkerStandIn() as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
        with _client(cfg) as client:
            r = client.request(method, "/api/v2/observe/ledger/c-1",
                               headers=_headers(**{"Content-Type": "application/json"}), json={})
            assert r.status_code in (404, 405), (method, r.text)
    assert worker.requests == []


def test_row_10_the_console_path_is_unchanged_and_the_route_sits_behind_the_gate(password_hash, tmp_path, config):
    with _WorkerStandIn() as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
        with _client(cfg) as client:
            console = _result(client.get("/api/v2/observe/audit/c-1", headers=_headers()))
            assert console["available"] is False and console["capability"] == "console_api"
    assert worker.requests == []
    with _client(config) as client:
        assert client.get("/api/v2/observe/ledger/c-1").status_code == 401
        assert client.get("/api/v2/observe/ledger/c-1",
                          headers={"Authorization": basic_auth(pw="wrong")}).status_code == 401


def test_the_egress_record_names_seven_routes_one_destination_and_the_manifest_agrees():
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    egress = cfg["external_network_egress"]
    (permitted,) = egress["permitted"]
    assert egress["default"] == "none" and permitted["scheme"] == "https"
    assert len(permitted["routes"]) == 7
    assert permitted["routes"][6] == "GET /review/audit/{correlation_id}"
    assert permitted["ledger_read"].startswith("GET /review/audit/{correlation_id}")
    assert "no write route exists" in permitted["ledger_read"]
    manifest = json.load(open(os.path.join(REPO, "apps", "ugence-governance-studio", "frontend", "security",
                                           "approved-v2-api-operations.json"), encoding="utf-8"))
    assert manifest["review_service_routes_reachable_from_the_studio"] == permitted["routes"]
    from ugence_governance_studio_api.clients.review import REVIEW_ALLOWED_ROUTES

    assert [f"{m} {p}" for m, p in REVIEW_ALLOWED_ROUTES] == permitted["routes"]
    seam = cfg["worker_ledger_observe"]
    assert "FD-11.1 OBSERVE_OVER_WORKER_LEDGER" in seam["ruling"] and "FD-11.5" in seam["ruling"]
    assert "no configuration value, image package, credential or second egress destination is added" in seam["route"]
    assert "v2_observe_ledger_chain" in seam["contract"]
    assert seam["mutation_boundary"].startswith("read-only")
    assert seam["composition_record"].endswith("composition-record.seam-6.json")
    assert "FD-11 seam 7" in cfg["front_door_seams"]["ruling"]
    assert list(cfg["configuration_added"])[:6] == ["UGENCE_STUDIO_REVIEW_SERVICE_URL",
                                                   "UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH",
                                                   "UGENCE_STUDIO_TENANT_ID",
                                                   "UGENCE_STUDIO_POLICY_IDENTITIES",
                                                   "UGENCE_STUDIO_SIMULATION_PROVIDER",
                                                   "UGENCE_STUDIO_SYSTEM_REGISTRY_PATH"], "seam 7 added no value (FD-11.5)"
    assert list(cfg["configuration_added"])[6:] == [
        "UGENCE_STUDIO_DATA_USE_DECLARATIONS_PATH",
        "UGENCE_STUDIO_VENDOR_DECLARATIONS_PATH",
            "UGENCE_STUDIO_WORKFLOW_DRAFTS_PATH"], \
        "later values belong to seams 8 and 9 and to phase 3A (workflow drafts, BW-3A)"
    assert cfg["first_party_packages_in_image"][:13][-1] == "packages/integration/ai-system-registry"
    # Membership, not the whole tail: a later seam appends its own packages and
    # the two named here stay in the image either way.
    for later in ("packages/integration/data-use-admission",
                  "packages/integration/vendor-dependency"):
        assert later in cfg["first_party_packages_in_image"], "seams 8 and 9"


def test_the_third_contract_amendment_is_recorded_in_the_p3e_freeze():
    import hashlib

    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    record = json.load(open(os.path.join(REPO, "apps", "ugence-governance-studio", "contracts",
                                         "openapi_v2.amendments.json"), encoding="utf-8"))
    with open(os.path.join(REPO, "apps", "ugence-governance-studio", "contracts", "openapi_v2.json"), "rb") as fh:
        current = hashlib.sha256(fh.read()).hexdigest()
    a2, a3 = record["amendments"][1:3]
    assert a2["amendment_id"] == "v2-A2" and a3["amendment_id"] == "v2-A3"
    assert a3["previous_sha256"] == a2["sha256"]
    # the committed bytes and the freeze carry the latest amendment (v2-A4 since seam 8),
    # which chains from this one
    assert cfg["frozen"]["openapi_v2_sha256"] == current == record["amendments"][-1]["sha256"]
    assert a3["operations_added"] == ["v2_observe_ledger_chain"]
    assert a3["paths_added"] == ["/api/v2/observe/ledger/{correlation_id}"]
    for tag in ("v2-A3", "v2-A2", "v2-A1"):
        assert tag in cfg["frozen"]["openapi_v2_amendment"]
    assert cfg["frozen"]["openapi_sha256"] == "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"
