"""Front-door seam 6 in the P3E profile (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md §11,
rulings FD-10.1 to FD-10.5): the worker shadow-run relay through the deployed studio.

The §11.3 failure matrix as tests at this edge. Row 1: the review URL unset is the typed
gap ``review_service`` on the start route. Row 2: a worker without the route (an older
worker) or an unreachable one is a typed gap naming the failure, never an empty run.
Row 3: a workflow, provider, mode or digest is not expressible; the contract refuses the
key and nothing goes out. Row 4: a replay is the worker's typed answer, passed through.
Row 7: a tenant is not expressible. Row 8: LIVE is not expressible; the mode word is
pinned. Row 9: no credential and no proof header crosses on the start; the studio's
own Basic credential never leaves the studio. Row 10: the in-process Simulate path is
unchanged and never reaches the worker. Plus the freeze: the egress record names six
routes, still one destination over https, and the frontend manifest agrees.
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
PROOF = "opaque.proof.value-that-must-never-travel-on-a-start"
STARTED = {
    "result": "STARTED", "started": True, "mode": "shadow", "instance_id": "shadow-0123456789abcdef01234567",
    "workflow_id": "wf-shadow", "correlation_id": "c-1", "definition_digest": "shadow-v1",
    "advanced": True, "awaiting_external": True, "stop_reason": "ESCALATE", "reason": "",
    "workload_maturity": "FIXTURE_ONLY", "maturity": "REFERENCE_GRADE_SHADOW_ONLY",
    "identity_proof": "PRESENTED_UNPROVEN",
}


def _headers(**extra) -> dict:
    return {"Authorization": basic_auth(), "X-Ugence-Request": "GovernanceStudio",
            "Origin": "http://testserver", "Content-Type": "application/json", **extra}


class _WorkerStandIn:
    """A loopback stand-in for the governed runtime worker's listener. Records every
    request so the relay can be checked byte for byte; answers as configured."""

    def __init__(self, *, has_route: bool = True, status: int = 200, body: dict | None = None) -> None:
        self.requests: list = []
        stand_in = self
        answer = dict(body or STARTED)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                stand_in.requests.append({"method": "POST", "path": self.path,
                                          "headers": {k.lower(): v for k, v in self.headers.items()},
                                          "body": json.loads(raw) if raw else None})
                if self.path == "/review/runs" and has_route:
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


# --------------------------------------------------------------------------- #
# row 1
# --------------------------------------------------------------------------- #
def test_row_1_unset_review_url_is_a_typed_gap_on_the_start_route(config):
    assert not config.review_service_configured
    with _client(config) as client:
        gap = _result(client.post("/api/v2/review/runs", headers=_headers(), json={"correlation_id": "c-1"}))
        assert gap["available"] is False and gap["capability"] == "review_service"
        assert gap["result"] is None and "no governed review service" in gap["reason"]


# --------------------------------------------------------------------------- #
# rows 4 and 9: the relay, byte for byte
# --------------------------------------------------------------------------- #
def test_rows_4_and_9_the_start_is_relayed_with_nothing_of_the_studios_and_the_answer_returned(
        password_hash, tmp_path, capsys):
    with _WorkerStandIn() as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
        with _client(cfg) as client:
            started = client.post("/api/v2/review/runs", headers=_headers(**{PROOF_HEADER: PROOF}),
                                  json={"correlation_id": "c-1"})
            assert started.status_code == 200
            relayed = started.json()["result"]
            assert relayed["available"] is True and relayed["result"] == STARTED
            assert relayed["path"]["path"] == "worker_shadow_run"
            assert relayed["path"]["maturity"] == "REFERENCE_GRADE_SHADOW_ONLY"
            minted = client.post("/api/v2/review/runs", headers=_headers(), json={})
            assert minted.status_code == 200
    first, second = worker.requests
    assert first["path"] == "/review/runs" and first["body"] == {"mode": "shadow", "correlation_id": "c-1"}
    assert second["body"] == {"mode": "shadow"}
    for sent in (first, second):
        assert "authorization" not in sent["headers"], "the studio credential never leaves the studio"
        assert PROOF_HEADER.lower() not in sent["headers"], "no proof travels on the start (ID-1)"
        assert set(sent["body"]) <= {"mode", "correlation_id"}, "nothing else crosses (FD-10.3)"
    captured = capsys.readouterr()
    assert PROOF not in captured.out + captured.err and PROOF not in started.text


def test_row_4_a_replay_and_every_refusal_are_the_workers_answer_not_a_transport_fault(password_hash, tmp_path):
    replay = dict(STARTED, result="REPLAYED", advanced=False)
    with _WorkerStandIn(body=replay) as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
        with _client(cfg) as client:
            r = _result(client.post("/api/v2/review/runs", headers=_headers(), json={"correlation_id": "c-1"}))
            assert r["available"] is True and r["result"]["result"] == "REPLAYED" and r["result"]["advanced"] is False
    for refusal in ("REFUSED_MODE", "REFUSED_DEFINITION", "REFUSED_CONFLICT", "REFUSED_UNCONFIGURED"):
        refused = dict(STARTED, result=refusal, started=False, reason="the worker said so")
        with _WorkerStandIn(status=409, body=refused) as worker:
            cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
            with _client(cfg) as client:
                r = _result(client.post("/api/v2/review/runs", headers=_headers(), json={"correlation_id": "c-1"}))
                assert r["available"] is True and r["result"]["result"] == refusal
                assert r["result"]["started"] is False and r["result"]["reason"] == "the worker said so"


# --------------------------------------------------------------------------- #
# row 2
# --------------------------------------------------------------------------- #
def test_row_2_an_older_worker_without_the_route_or_an_unreachable_one_is_a_typed_gap(password_hash, tmp_path):
    with _WorkerStandIn(has_route=False) as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
        with _client(cfg) as client:
            gap = _result(client.post("/api/v2/review/runs", headers=_headers(), json={"correlation_id": "c-1"}))
            assert gap["available"] is False and gap["capability"] == "review_service"
            assert "no start route" in gap["reason"] and gap["result"] is None
    cfg = _config(password_hash, tmp_path, review_service_url="http://127.0.0.1:9")
    with _client(cfg) as client:
        gap = _result(client.post("/api/v2/review/runs", headers=_headers(), json={"correlation_id": "c-1"}))
        assert gap["available"] is False and "unreachable" in gap["reason"]


# --------------------------------------------------------------------------- #
# rows 3, 7, 8: not expressible
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("body", [
    {"workflow": {"workflow_id": "wf-mine", "tasks": []}},
    {"tasks": [{"task_id": "t1", "operation": "do", "provider_id": "openai"}]},
    {"provider_id": "openai"},
    {"definition_digest": "other"},
    {"mode": "live"},
    {"mode": "shadow"},
    {"execution_mode": "LIVE"},
    {"tenant_id": "tenant-b"},
    {"instance_id": "chosen"},
    {"correlation_id": "has space"},
    {"correlation_id": ""},
])
def test_rows_3_7_8_nothing_but_a_typed_correlation_id_is_expressible_and_nothing_goes_out(
        password_hash, tmp_path, body):
    with _WorkerStandIn() as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url)
        with _client(cfg) as client:
            r = client.post("/api/v2/review/runs", headers=_headers(), json={"correlation_id": "c-1", **body}
                            if "correlation_id" not in body else body)
            assert r.status_code == 422, (body, r.text)
    assert worker.requests == [], "refused at the contract before any outbound request"


# --------------------------------------------------------------------------- #
# row 10: the in-process path is unchanged and never reaches the worker
# --------------------------------------------------------------------------- #
def test_row_10_the_in_process_simulate_path_never_reaches_the_worker(password_hash, tmp_path):
    with _WorkerStandIn() as worker:
        cfg = _config(password_hash, tmp_path, review_service_url=worker.url, simulation_provider="1")
        with _client(cfg) as client:
            local = _result(client.post("/api/v2/simulate/run", headers=_headers(), json={
                "workflow": {"workflow_id": "w", "tasks": [{"task_id": "t1", "operation": "prepare",
                                                            "provider_id": "fixture"}]},
                "execution_mode": "DRY_RUN", "max_quanta": 4}))
            assert local["available"] is True and local["governance_hook_configured"] is False
            assert local["governance_hook_permissive"] is False
            relayed = _result(client.post("/api/v2/review/runs", headers=_headers(), json={}))
            assert relayed["available"] is True and relayed["result"]["result"] == "STARTED"
    assert [r["path"] for r in worker.requests] == ["/review/runs"], "one relay; the local run sent nothing"


def test_the_start_route_sits_behind_the_same_gate_as_v1(config):
    with _client(config) as client:
        assert client.post("/api/v2/review/runs", json={}).status_code == 401
        assert client.post("/api/v2/review/runs", headers={"Authorization": basic_auth(pw="wrong")},
                           json={}).status_code == 401


# --------------------------------------------------------------------------- #
# the freeze: six routes, one destination, the manifest agrees
# --------------------------------------------------------------------------- #
def test_the_egress_record_names_six_routes_one_destination_and_the_frontend_manifest_agrees():
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    egress = cfg["external_network_egress"]
    (permitted,) = egress["permitted"]
    assert egress["default"] == "none" and permitted["scheme"] == "https"
    assert len(permitted["routes"]) == 7
    assert permitted["routes"][4:6] == ["POST /review/decisions", "POST /review/runs"]
    assert permitted["start_relay"].startswith("POST /review/runs")
    assert "no workflow, task, provider, digest or credential crosses" in permitted["start_relay"]
    manifest = json.load(open(os.path.join(REPO, "apps", "ugence-governance-studio", "frontend", "security",
                                           "approved-v2-api-operations.json"), encoding="utf-8"))
    assert manifest["review_service_routes_reachable_from_the_studio"] == permitted["routes"]
    from ugence_governance_studio_api.clients.review import REVIEW_ALLOWED_ROUTES

    assert [f"{m} {p}" for m, p in REVIEW_ALLOWED_ROUTES] == permitted["routes"]
    seam = cfg["worker_shadow_run"]
    assert "FD-10.1 START_IS_A_RELAY" in seam["ruling"] and "FD-10.5 TWO_LABELLED_PATHS" in seam["ruling"]
    assert "no configuration value, image package, credential or second egress destination is added" in seam["route"]
    assert "v2_review_start_shadow_run" in seam["contract"]
    assert seam["composition_record"].endswith("composition-record.seam-5.json")
    assert "START_IS_A_RELAY" in cfg["prohibited_definitions"]["agent_execution"]
    assert "FD-10 seam 6" in cfg["front_door_seams"]["ruling"]
    assert list(cfg["configuration_added"])[:6] == ["UGENCE_STUDIO_REVIEW_SERVICE_URL",
                                                   "UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH",
                                                   "UGENCE_STUDIO_TENANT_ID",
                                                   "UGENCE_STUDIO_POLICY_IDENTITIES",
                                                   "UGENCE_STUDIO_SIMULATION_PROVIDER",
                                                   "UGENCE_STUDIO_SYSTEM_REGISTRY_PATH"], "seam 6 added no value (FD-10.4)"
    assert list(cfg["configuration_added"])[6:] == ["UGENCE_STUDIO_DATA_USE_DECLARATIONS_PATH"], \
        "the only later value is seam 8's declarations file (FD-12.2)"
    assert cfg["first_party_packages_in_image"][:13][-1] == "packages/integration/ai-system-registry"
    assert cfg["first_party_packages_in_image"][13:] == ["packages/integration/data-use-admission"], \
        "the only later package is seam 8's (FD-12.2)"


def test_the_second_contract_amendment_is_recorded_in_the_p3e_freeze():
    import hashlib

    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    record = json.load(open(os.path.join(REPO, "apps", "ugence-governance-studio", "contracts",
                                         "openapi_v2.amendments.json"), encoding="utf-8"))
    with open(os.path.join(REPO, "apps", "ugence-governance-studio", "contracts", "openapi_v2.json"), "rb") as fh:
        current = hashlib.sha256(fh.read()).hexdigest()
    a1, a2 = record["amendments"][0:2]
    assert a1["amendment_id"] == "v2-A1" and a2["amendment_id"] == "v2-A2"
    assert a2["previous_sha256"] == a1["sha256"]
    # the committed bytes and the freeze carry the latest amendment (v2-A4 since seam 8);
    # every link from the original freeze onward chains
    assert cfg["frozen"]["openapi_v2_sha256"] == current == record["amendments"][-1]["sha256"]
    previous = record["original_sha256"]
    for amendment in record["amendments"]:
        assert amendment["previous_sha256"] == previous
        previous = amendment["sha256"]
    assert a2["operations_added"] == ["v2_review_start_shadow_run"] and a2["paths_added"] == ["/api/v2/review/runs"]
    assert "v2-A2" in cfg["frozen"]["openapi_v2_amendment"] and "v2-A1" in cfg["frozen"]["openapi_v2_amendment"]
    assert cfg["frozen"]["openapi_sha256"] == "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"
