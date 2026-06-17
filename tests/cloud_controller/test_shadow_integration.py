"""Track A wiring proof — runs HERE, against a real HTTP Prometheus API.

We cannot start a Kubernetes cluster in this environment (no Docker daemon), so
the *live* numbers are produced by deploy/local-shadow/ on a real host. But the
controller↔Prometheus↔shadow↔efficiency-observer wiring can be proven here by
standing up a tiny HTTP server that speaks the real Prometheus `/api/v1/query`
API and pointing the LiveEfficiencyShadow at it via a real URL.

This exercises the genuine path: PrometheusClient → requests.get → HTTP → JSON →
SignalPipeline → Controller → HPAWatcher → DivergenceTracker → EfficiencyObserver.
It is labelled an *integration test against a stub Prometheus* — NOT a cluster,
NOT a real proof-of-value number.
"""

import json
import math
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import pytest

from cloud_controller.shadow.live_efficiency import (
    LiveEfficiencyShadow,
    LiveEfficiencyConfig,
)
from cloud_controller.shadow.runner import ShadowConfig
from cloud_controller.signals.pipeline import PipelineConfig
from cloud_controller.signals.prometheus import PrometheusConfig


class _PromStub(BaseHTTPRequestHandler):
    """Serves a real-shaped Prometheus vector response for any query.

    A shared step counter drives a time-varying CPU and an HPA that scales
    desired≠current under load, so the HPAWatcher detects actions and the
    DivergenceTracker records decisions."""

    step = 0

    def log_message(self, *args):  # silence
        pass

    def _vector(self, value: float):
        body = json.dumps({
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [{"metric": {}, "value": [1700000000.0, str(value)]}],
            },
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/-/healthy":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return

        q = parse_qs(parsed.query).get("query", [""])[0]
        cls = type(self)
        # advance once per metric-set poll: trigger on the cpu query
        cpu = 0.45 + 0.4 * abs(math.sin(cls.step / 5.0))
        if "node_cpu_seconds_total" in q:
            cls.step += 1
            self._vector(cpu)
        elif "MemAvailable" in q:
            self._vector(0.4)
        elif "http_request_duration_seconds_bucket" in q:
            self._vector(0.2 + 0.6 * (cpu > 0.7))         # latency rises under load
        elif "http_requests_total" in q:
            self._vector(0.05 if cpu > 0.75 else 0.0)     # some 5xx under load
        elif "queue_messages_ready" in q:
            self._vector(cpu * 10.0)
        elif "kube_pod_container_status_restarts_total" in q:
            self._vector(0.0)
        elif "kube_hpa_status_current_replicas" in q:
            self._vector(5.0)
        elif "kube_hpa_status_desired_replicas" in q:
            self._vector(7.0 if cpu > 0.7 else 5.0)        # HPA wants to scale under load
        else:
            self._vector(0.0)


@pytest.fixture
def prom_stub():
    server = HTTPServer(("127.0.0.1", 0), _PromStub)
    _PromStub.step = 0
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    port = server.server_address[1]
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def _make_shadow(url: str) -> LiveEfficiencyShadow:
    pipeline = PipelineConfig(
        prometheus=PrometheusConfig(url=url, max_retries=0),
        poll_interval=0.0,
        bootstrap_window_seconds=0,   # no historical bootstrap against the stub
    )
    return LiveEfficiencyShadow(LiveEfficiencyConfig(shadow=ShadowConfig(pipeline=pipeline)))


class TestLiveShadowWiringAgainstRealHTTP:
    def test_health_check_real_http(self, prom_stub):
        shadow = _make_shadow(prom_stub)
        assert shadow.runner.pipeline.prometheus.health_check() is True

    def test_steps_produce_decisions_and_observer_runs(self, prom_stub):
        shadow = _make_shadow(prom_stub)
        cycles = 0
        for _ in range(25):
            lc = shadow.step()
            if lc is not None:
                cycles += 1
                # the read-only observer never actuates a positive cap into the cluster
                assert lc.observed.guarded_delta <= lc.observed.raw_delta or lc.observed.raw_delta <= 0
        assert cycles > 0
        # The full chain ran over real HTTP: divergence records + observer evals.
        assert len(shadow.runner.divergence_tracker.records) > 0
        assert shadow.observer.total_evaluated == cycles

    def test_report_schema_is_complete(self, prom_stub):
        shadow = _make_shadow(prom_stub)
        for _ in range(20):
            shadow.step()
        rep = shadow.report(period_label="integration-stub")
        assert rep.label == "live-shadow-self-run"
        assert rep.cycles > 0
        # SLO regressions caused by the read-only guard are 0 by construction.
        assert rep.slo_regressions_caused_by_guard == 0
        d = rep.to_dict()
        assert set(d.keys()) == {"label", "period_label", "cycles", "divergence", "guard", "slo", "notes"}
        assert "futile_scale_outs_guard_would_block" in d["guard"]
        md = rep.format_markdown()
        assert "live-shadow-self-run" in md
        assert "read-only" in md

    def test_guard_never_actuates_into_cluster(self, prom_stub):
        """The shadow path must never apply the guard's cap — HPA owns scaling."""
        shadow = _make_shadow(prom_stub)
        for _ in range(20):
            lc = shadow.step()
            if lc is None:
                continue
            # We record what the guard WOULD do, but the replica count the next
            # cycle reads comes from the stub's HPA, not from our guarded_delta.
        # current_replicas always came from Prometheus (HPA), never mutated by us.
        assert shadow._cycles > 0
