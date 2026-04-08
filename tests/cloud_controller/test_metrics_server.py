"""Tests for the HTTP Metrics Server."""

import time
import urllib.request
import urllib.error
import pytest

from symbolu.cloud_controller.observability.exporter import (
    ExporterConfig,
    ExporterMode,
    MetricsExporter,
)
from symbolu.cloud_controller.observability.metrics_server import (
    MetricsServer,
    MetricsServerConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def exporter():
    return MetricsExporter(ExporterConfig(mode=ExporterMode.BUILTIN))


@pytest.fixture
def server(exporter):
    """Create a server on a random high port, auto-stop after test."""
    config = MetricsServerConfig(host="127.0.0.1", port=0)
    # Port 0 isn't supported by HTTPServer directly; use a fixed high port
    config = MetricsServerConfig(host="127.0.0.1", port=19876)
    srv = MetricsServer(exporter, config)
    yield srv
    if srv.is_running:
        srv.stop()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestMetricsServerConstruction:
    def test_default_config(self):
        exp = MetricsExporter()
        srv = MetricsServer(exp)
        assert srv.config.host == "0.0.0.0"
        assert srv.config.port == 9090
        assert srv.config.metrics_path == "/metrics"
        assert srv.config.health_path == "/healthz"

    def test_custom_config(self):
        exp = MetricsExporter()
        cfg = MetricsServerConfig(host="127.0.0.1", port=8080, metrics_path="/m")
        srv = MetricsServer(exp, cfg)
        assert srv.config.port == 8080
        assert srv.config.metrics_path == "/m"

    def test_not_running_initially(self):
        exp = MetricsExporter()
        srv = MetricsServer(exp)
        assert not srv.is_running


# ---------------------------------------------------------------------------
# Start / Stop
# ---------------------------------------------------------------------------

class TestMetricsServerLifecycle:
    def test_start_and_stop(self, server):
        server.start()
        assert server.is_running
        server.stop()
        assert not server.is_running

    def test_double_start_raises(self, server):
        server.start()
        with pytest.raises(RuntimeError, match="already running"):
            server.start()

    def test_stop_when_not_running_is_noop(self, server):
        server.stop()  # Should not raise

    def test_context_manager(self, exporter):
        cfg = MetricsServerConfig(host="127.0.0.1", port=19877)
        with MetricsServer(exporter, cfg) as srv:
            assert srv.is_running
        assert not srv.is_running


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

class TestMetricsServerEndpoints:
    def test_metrics_endpoint(self, server, exporter):
        server.start()
        time.sleep(0.1)  # Let server thread start

        url = f"{server.metrics_url}"
        resp = urllib.request.urlopen(url, timeout=5)
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "ncc_action_score" in body

    def test_health_endpoint(self, server):
        server.start()
        time.sleep(0.1)

        url = f"{server.url}/healthz"
        resp = urllib.request.urlopen(url, timeout=5)
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert body == "ok"

    def test_404_for_unknown_path(self, server):
        server.start()
        time.sleep(0.1)

        url = f"{server.url}/unknown"
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url, timeout=5)
        assert exc_info.value.code == 404

    def test_metrics_reflect_recorded_data(self, server, exporter):
        from symbolu.cloud_controller.controller import Controller
        from symbolu.cloud_controller.config import InfraControllerConfig

        ctrl = Controller(InfraControllerConfig())
        action = ctrl.step(
            metrics={"cpu": 0.7, "memory": 0.5},
            current_replicas=3,
        )
        exporter.record_cycle(action, current_replicas=3, cycle_duration=0.1)

        server.start()
        time.sleep(0.1)

        resp = urllib.request.urlopen(server.metrics_url, timeout=5)
        body = resp.read().decode("utf-8")
        assert "ncc_cycles_total 1.0" in body


# ---------------------------------------------------------------------------
# URL properties
# ---------------------------------------------------------------------------

class TestMetricsServerURLs:
    def test_url_property(self):
        exp = MetricsExporter()
        cfg = MetricsServerConfig(host="0.0.0.0", port=9090)
        srv = MetricsServer(exp, cfg)
        assert srv.url == "http://127.0.0.1:9090"

    def test_metrics_url_property(self):
        exp = MetricsExporter()
        cfg = MetricsServerConfig(host="127.0.0.1", port=8080, metrics_path="/prom")
        srv = MetricsServer(exp, cfg)
        assert srv.metrics_url == "http://127.0.0.1:8080/prom"
