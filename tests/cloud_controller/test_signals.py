"""Unit tests for Stage 2 — Signal Pipeline.

Tests cover:
- SignalNormalizer: z-score, ratio, rolling windows, edge cases
- PrometheusClient: response parsing, error handling (mocked HTTP)
- SignalPipeline: end-to-end with mocked Prometheus
"""

import math
import time
import json
import pytest
from unittest.mock import patch, MagicMock

from symbolu.cloud_controller.config import INFRA_KEYS, APP_KEYS, BUSINESS_KEYS
from symbolu.cloud_controller.controller import Controller
from symbolu.cloud_controller.signals.normalizer import (
    SignalNormalizer,
    NormalizerConfig,
    MetricSpec,
    NormalizationResult,
    DEFAULT_METRIC_SPECS,
)
from symbolu.cloud_controller.signals.prometheus import (
    PrometheusClient,
    PrometheusConfig,
    DEFAULT_QUERIES,
    K8S_QUERIES,
)
from symbolu.cloud_controller.signals.pipeline import (
    SignalPipeline,
    PipelineConfig,
    CycleResult,
)


# ============================================================
# Signal Normalizer
# ============================================================

class TestNormalizerRatio:
    def test_ratio_clamps_to_bounds(self):
        """Ratio normalization should clamp to [0, 1]."""
        normalizer = SignalNormalizer()
        result = normalizer.normalize({"error_rate": 1.5})
        assert result["error_rate"] == 1.0
        result = normalizer.normalize({"error_rate": -0.1})
        assert result["error_rate"] == 0.0

    def test_ratio_passthrough(self):
        """Ratio metric already in [0, 1] should pass through."""
        normalizer = SignalNormalizer()
        result = normalizer.normalize({"memory": 0.65})
        assert abs(result["memory"] - 0.65) < 0.01

    def test_ratio_custom_range(self):
        """Ratio with custom range maps correctly."""
        specs = {
            "temp": MetricSpec(name="temp", method="ratio", ratio_low=0.0, ratio_high=100.0),
        }
        normalizer = SignalNormalizer(metric_specs=specs)
        result = normalizer.normalize({"temp": 50.0})
        assert abs(result["temp"] - 0.5) < 0.01
        result = normalizer.normalize({"temp": 100.0})
        assert abs(result["temp"] - 1.0) < 0.01

    def test_ratio_invert(self):
        """Inverted ratio should flip the value."""
        specs = {
            "avail": MetricSpec(name="avail", method="ratio", invert=True),
        }
        normalizer = SignalNormalizer(metric_specs=specs)
        result = normalizer.normalize({"avail": 0.8})
        assert abs(result["avail"] - 0.2) < 0.01


class TestNormalizerZscore:
    def test_zscore_starts_at_midpoint(self):
        """Before enough samples, z-score normalization returns 0.5."""
        normalizer = SignalNormalizer(config=NormalizerConfig(min_samples=10))
        result = normalizer.normalize({"cpu": 0.5})
        assert abs(result["cpu"] - 0.5) < 0.01

    def test_zscore_high_value_maps_high(self):
        """After warmup, a value above mean should map > 0.5."""
        normalizer = SignalNormalizer(config=NormalizerConfig(min_samples=5))
        # Feed steady baseline
        for _ in range(20):
            normalizer.normalize({"cpu": 0.3})
        # Spike
        result = normalizer.normalize({"cpu": 0.9})
        assert result["cpu"] > 0.7

    def test_zscore_low_value_maps_low(self):
        """After warmup, a value below mean should map < 0.5."""
        normalizer = SignalNormalizer(config=NormalizerConfig(min_samples=5))
        for _ in range(20):
            normalizer.normalize({"cpu": 0.7})
        result = normalizer.normalize({"cpu": 0.2})
        assert result["cpu"] < 0.3

    def test_zscore_steady_state_around_half(self):
        """Steady values at the mean should normalize near 0.5."""
        normalizer = SignalNormalizer(config=NormalizerConfig(min_samples=5))
        for _ in range(50):
            normalizer.normalize({"cpu": 0.5})
        result = normalizer.normalize({"cpu": 0.5})
        assert abs(result["cpu"] - 0.5) < 0.05

    def test_zscore_adapts_to_new_baseline(self):
        """After a sustained shift, the new level becomes the baseline."""
        normalizer = SignalNormalizer(
            config=NormalizerConfig(min_samples=5, window_size=30),
        )
        # Old baseline
        for _ in range(30):
            normalizer.normalize({"cpu": 0.3})
        # New sustained level
        for _ in range(50):
            normalizer.normalize({"cpu": 0.8})
        # New level should now be "normal" (near 0.5)
        result = normalizer.normalize({"cpu": 0.8})
        assert 0.4 < result["cpu"] < 0.6


class TestNormalizerEdgeCases:
    def test_nan_value_skipped(self):
        """NaN metrics should be skipped, not crash."""
        normalizer = SignalNormalizer()
        result = normalizer.normalize({"cpu": float('nan'), "memory": 0.5})
        assert "cpu" not in result
        assert "memory" in result

    def test_inf_value_skipped(self):
        """Infinity metrics should be skipped."""
        normalizer = SignalNormalizer()
        result = normalizer.normalize({"cpu": float('inf'), "memory": 0.5})
        assert "cpu" not in result

    def test_unknown_metric_uses_zscore(self):
        """Metrics not in specs should default to z-score normalization."""
        normalizer = SignalNormalizer()
        result = normalizer.normalize({"custom_metric": 42.0})
        assert "custom_metric" in result
        assert 0.0 <= result["custom_metric"] <= 1.0

    def test_zero_std_does_not_crash(self):
        """Constant values (std=0) should not divide by zero."""
        normalizer = SignalNormalizer(config=NormalizerConfig(min_samples=3))
        for _ in range(10):
            normalizer.normalize({"cpu": 0.5})
        result = normalizer.normalize({"cpu": 0.5})
        assert math.isfinite(result["cpu"])

    def test_normalize_detailed_returns_diagnostics(self):
        """Detailed normalization should include z-scores and window stats."""
        normalizer = SignalNormalizer(config=NormalizerConfig(min_samples=3))
        for _ in range(10):
            normalizer.normalize({"cpu": 0.5})
        details = normalizer.normalize_detailed({"cpu": 0.7})
        assert "cpu" in details
        assert details["cpu"].z_score is not None
        assert details["cpu"].window_mean is not None

    def test_reset_clears_windows(self):
        """Reset should clear all rolling windows."""
        normalizer = SignalNormalizer()
        for _ in range(20):
            normalizer.normalize({"cpu": 0.5})
        assert normalizer.get_window_stats("cpu") is not None
        normalizer.reset()
        assert normalizer.get_window_stats("cpu") is None

    def test_reset_single_metric(self):
        """Reset of one metric should not affect others."""
        normalizer = SignalNormalizer()
        for _ in range(5):
            normalizer.normalize({"cpu": 0.5, "memory": 0.6})
        normalizer.reset("cpu")
        assert normalizer.get_window_stats("cpu") is None
        assert normalizer.get_window_stats("memory") is not None


class TestNormalizerWindowStats:
    def test_window_stats_correct(self):
        """Window stats should report correct mean/std/count."""
        normalizer = SignalNormalizer()
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            normalizer.normalize({"cpu": v})
        stats = normalizer.get_window_stats("cpu")
        assert stats is not None
        assert abs(stats["mean"] - 3.0) < 0.01
        assert stats["count"] == 5
        assert abs(stats["min"] - 1.0) < 0.01
        assert abs(stats["max"] - 5.0) < 0.01

    def test_window_respects_max_size(self):
        """Window should not exceed configured max size."""
        normalizer = SignalNormalizer(config=NormalizerConfig(window_size=10))
        for i in range(50):
            normalizer.normalize({"cpu": float(i)})
        stats = normalizer.get_window_stats("cpu")
        assert stats["count"] == 10


# ============================================================
# Prometheus Client
# ============================================================

def _mock_prom_response(result_type, result):
    """Create a mock Prometheus API response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "status": "success",
        "data": {
            "resultType": result_type,
            "result": result,
        },
    }
    resp.raise_for_status = MagicMock()
    return resp


class TestPrometheusClient:
    def test_instant_query_vector(self):
        """Should extract float from vector result."""
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        mock_resp = _mock_prom_response("vector", [
            {"metric": {"__name__": "cpu"}, "value": [1234567890, "0.82"]},
        ])
        with patch.object(client._session, "get", return_value=mock_resp):
            value = client.instant_query("test_query")
        assert abs(value - 0.82) < 0.001

    def test_instant_query_scalar(self):
        """Should extract float from scalar result."""
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        mock_resp = _mock_prom_response("scalar", [1234567890, "0.42"])
        with patch.object(client._session, "get", return_value=mock_resp):
            value = client.instant_query("test_query")
        assert abs(value - 0.42) < 0.001

    def test_instant_query_empty_result(self):
        """Empty result should return None."""
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        mock_resp = _mock_prom_response("vector", [])
        with patch.object(client._session, "get", return_value=mock_resp):
            value = client.instant_query("test_query")
        assert value is None

    def test_instant_query_error_returns_none(self):
        """Failed query should return None, not crash."""
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "status": "error",
            "error": "bad query",
        }
        resp.raise_for_status = MagicMock()
        with patch.object(client._session, "get", return_value=resp):
            value = client.instant_query("bad{query")
        assert value is None

    def test_range_query_extracts_series(self):
        """Range query should return list of (timestamp, value) tuples."""
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        mock_resp = _mock_prom_response("matrix", [
            {
                "metric": {"__name__": "cpu"},
                "values": [
                    [1000, "0.50"],
                    [1015, "0.55"],
                    [1030, "0.60"],
                ],
            },
        ])
        with patch.object(client._session, "get", return_value=mock_resp):
            series = client.range_query("test", 1000, 1030, "15s")
        assert len(series) == 3
        assert series[0] == (1000.0, 0.50)
        assert series[2] == (1030.0, 0.60)

    def test_network_error_retries(self):
        """Should retry on network errors up to max_retries."""
        import requests as req_lib
        config = PrometheusConfig(
            url="http://fake:9090",
            max_retries=2,
            retry_delay_seconds=0.01,
        )
        client = PrometheusClient(config)
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise req_lib.ConnectionError("connection refused")
            return _mock_prom_response("vector", [
                {"metric": {}, "value": [123, "0.99"]},
            ])

        with patch.object(client._session, "get", side_effect=side_effect):
            value = client.instant_query("test")
        assert abs(value - 0.99) < 0.001
        assert call_count == 3  # 2 retries + 1 success

    def test_network_error_exhausts_retries(self):
        """After exhausting retries, should return None."""
        import requests as req_lib
        config = PrometheusConfig(
            url="http://fake:9090",
            max_retries=1,
            retry_delay_seconds=0.01,
        )
        client = PrometheusClient(config)
        with patch.object(
            client._session, "get",
            side_effect=req_lib.ConnectionError("down"),
        ):
            value = client.instant_query("test")
        assert value is None

    def test_query_metrics_returns_all(self):
        """query_metrics should return a dict for all default queries."""
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        mock_resp = _mock_prom_response("vector", [
            {"metric": {}, "value": [123, "0.5"]},
        ])
        with patch.object(client._session, "get", return_value=mock_resp):
            results = client.query_metrics()
        assert len(results) == len(DEFAULT_QUERIES)
        for name, _, _ in DEFAULT_QUERIES:
            assert name in results

    def test_health_check(self):
        """Health check should return True when Prometheus responds 200."""
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.object(client._session, "get", return_value=mock_resp):
            assert client.health_check() is True

    def test_health_check_failure(self):
        """Health check should return False on connection error."""
        import requests as req_lib
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        with patch.object(
            client._session, "get",
            side_effect=req_lib.ConnectionError("down"),
        ):
            assert client.health_check() is False


# ============================================================
# Signal Pipeline (integration with mocked Prometheus)
# ============================================================

def _make_mock_prometheus_client(metrics=None, k8s_state=None):
    """Create a PrometheusClient mock that returns canned data."""
    if metrics is None:
        metrics = {
            "cpu": 0.78,
            "memory": 0.42,
            "latency_p99": 0.340,
            "error_rate": 0.08,
            "queue_depth": 247.0,
        }
    if k8s_state is None:
        k8s_state = {
            "pod_restarts": 0.0,
            "current_replicas": 5.0,
            "desired_replicas": 5.0,
        }

    mock = MagicMock(spec=PrometheusClient)
    mock.query_metrics.return_value = metrics
    mock.query_k8s_state.return_value = k8s_state
    return mock


class TestSignalPipeline:
    def test_poll_once_produces_result(self):
        """Single poll should produce a CycleResult with all fields."""
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.prometheus = _make_mock_prometheus_client()

        result = pipeline.poll_once()
        assert result is not None
        assert isinstance(result, CycleResult)
        assert result.action is not None
        assert result.action.recommendation is not None
        assert len(result.normalized_metrics) > 0
        assert all(0.0 <= v <= 1.0 for v in result.normalized_metrics.values())

    def test_poll_returns_none_when_no_metrics(self):
        """If Prometheus returns no valid data, poll should return None."""
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.prometheus = _make_mock_prometheus_client(
            metrics={"cpu": None, "memory": None},
        )

        result = pipeline.poll_once()
        assert result is None

    def test_pipeline_extracts_replicas(self):
        """Pipeline should extract current_replicas from K8s state."""
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.prometheus = _make_mock_prometheus_client(
            k8s_state={"current_replicas": 8.0, "desired_replicas": 8.0, "pod_restarts": 0.0},
        )

        result = pipeline.poll_once()
        assert result.current_replicas == 8

    def test_pipeline_detects_deploy_active(self):
        """If desired != current replicas, deploy_active should be True."""
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.prometheus = _make_mock_prometheus_client(
            k8s_state={"current_replicas": 5.0, "desired_replicas": 8.0, "pod_restarts": 0.0},
        )

        result = pipeline.poll_once()
        assert result.deploy_active is True

    def test_pipeline_stable_deploy(self):
        """If desired == current replicas, deploy_active should be False."""
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.prometheus = _make_mock_prometheus_client(
            k8s_state={"current_replicas": 5.0, "desired_replicas": 5.0, "pod_restarts": 0.0},
        )

        result = pipeline.poll_once()
        assert result.deploy_active is False

    def test_pipeline_handles_missing_k8s_state(self):
        """Missing K8s metrics should not crash pipeline."""
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.prometheus = _make_mock_prometheus_client(
            k8s_state={"current_replicas": None, "desired_replicas": None, "pod_restarts": None},
        )

        result = pipeline.poll_once()
        assert result is not None
        assert result.current_replicas == 1  # Default fallback

    def test_multiple_cycles_accumulate(self):
        """Multiple cycles should build up normalizer history."""
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.prometheus = _make_mock_prometheus_client()

        results = []
        for _ in range(20):
            r = pipeline.poll_once()
            if r is not None:
                results.append(r)

        assert len(results) == 20
        # Controller step count should increment
        assert results[-1].action.step == 20

    def test_format_cycle_log(self):
        """Cycle log should contain key information."""
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.prometheus = _make_mock_prometheus_client()

        result = pipeline.poll_once()
        log = pipeline.format_cycle_log(result)
        assert "X_t=" in log
        assert "Coherence=" in log
        assert "P_t=" in log
        assert "A_t=" in log

    def test_run_with_max_cycles(self):
        """Run with max_cycles should stop after N cycles."""
        pipeline = SignalPipeline(PipelineConfig(poll_interval=0.001))
        pipeline.prometheus = _make_mock_prometheus_client()

        results = []
        pipeline.run(callback=lambda r: results.append(r), max_cycles=5)
        assert len(results) == 5

    def test_normalizer_warmup_to_accurate(self):
        """Over many cycles, normalizer should produce meaningful values."""
        pipeline = SignalPipeline(
            PipelineConfig(
                normalizer=NormalizerConfig(min_samples=5, window_size=30),
            )
        )
        # Steady state
        pipeline.prometheus = _make_mock_prometheus_client(
            metrics={"cpu": 0.30, "memory": 0.40, "latency_p99": 0.100,
                     "error_rate": 0.01, "queue_depth": 50.0},
        )
        for _ in range(30):
            pipeline.poll_once()

        # Now spike CPU and latency
        pipeline.prometheus = _make_mock_prometheus_client(
            metrics={"cpu": 0.90, "memory": 0.40, "latency_p99": 0.500,
                     "error_rate": 0.01, "queue_depth": 50.0},
        )
        result = pipeline.poll_once()
        # CPU and latency should normalize high (> 0.5), others near 0.5
        assert result.normalized_metrics["cpu"] > 0.6
        assert result.normalized_metrics["latency_p99"] > 0.6


# ============================================================
# Audit Round — Integration & Edge Cases
# ============================================================

class TestQuerySpecAlignment:
    def test_prometheus_query_names_match_normalizer_specs(self):
        """All Prometheus query names should have a matching normalizer spec."""
        query_names = {name for name, _, _ in DEFAULT_QUERIES}
        spec_names = set(DEFAULT_METRIC_SPECS.keys())
        unknown = query_names - spec_names
        assert not unknown, f"Prometheus queries without normalizer specs: {unknown}"

    def test_prometheus_query_names_match_controller_groups(self):
        """All controller metric group keys should be covered by Prometheus queries."""
        query_names = {name for name, _, _ in DEFAULT_QUERIES}
        controller_keys = set(INFRA_KEYS + APP_KEYS + BUSINESS_KEYS)
        missing = controller_keys - query_names
        assert not missing, f"Controller expects metrics not in Prometheus queries: {missing}"


class TestPromQLInjection:
    def test_valid_labels_accepted(self):
        """Normal K8s labels should pass validation."""
        client = PrometheusClient()
        assert client._validate_label("default") is True
        assert client._validate_label("my-app-v2") is True
        assert client._validate_label("kube-system") is True
        assert client._validate_label("app.kubernetes.io/name") is True

    def test_injection_attempt_rejected(self):
        """Labels with PromQL injection should be rejected."""
        client = PrometheusClient()
        assert client._validate_label('myapp"} or 1=1 #') is False
        assert client._validate_label("default{}") is False
        assert client._validate_label("ns\ninjection") is False

    def test_nan_from_prometheus_filtered(self):
        """NaN values from Prometheus should be filtered to None."""
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        # Prometheus returns "NaN" as string in JSON
        mock_resp = _mock_prom_response("vector", [
            {"metric": {}, "value": [123, "NaN"]},
        ])
        with patch.object(client._session, "get", return_value=mock_resp):
            value = client.instant_query("test")
        assert value is None  # NaN should be filtered


class TestPipelineControllerInjection:
    def test_pipeline_accepts_external_controller(self):
        """Pipeline should use injected controller instead of creating one."""
        ctrl = Controller()
        pipeline = SignalPipeline(PipelineConfig(), controller=ctrl)
        assert pipeline.controller is ctrl

    def test_pipeline_creates_controller_when_not_injected(self):
        """Without injection, pipeline creates its own controller."""
        pipeline = SignalPipeline(PipelineConfig())
        assert pipeline.controller is not None
        assert isinstance(pipeline.controller, Controller)


class TestPipelinePhaseValidation:
    def test_invalid_phase_falls_back_to_normal(self):
        """Unknown phase in schedule should fall back to 'normal'."""
        config = PipelineConfig(
            phase_schedule={h: "invalid_phase" for h in range(24)},
        )
        pipeline = SignalPipeline(config)
        phase = pipeline._get_phase()
        assert phase == "normal"

    def test_valid_phases_accepted(self):
        """All valid phase values should be accepted."""
        for phase_name in ("peak", "normal", "off_peak", "maintenance"):
            config = PipelineConfig(
                phase_schedule={h: phase_name for h in range(24)},
            )
            pipeline = SignalPipeline(config)
            assert pipeline._get_phase() == phase_name


class TestPipelineSafeInt:
    def test_safe_int_normal(self):
        """Normal float values should convert correctly."""
        assert SignalPipeline._safe_int(5.0) == 5
        assert SignalPipeline._safe_int(5.4) == 5
        assert SignalPipeline._safe_int(5.6) == 6

    def test_safe_int_none(self):
        """None should return default."""
        assert SignalPipeline._safe_int(None, default=1) == 1

    def test_safe_int_invalid(self):
        """Invalid values should return default without crashing."""
        assert SignalPipeline._safe_int("abc", default=3) == 3
        assert SignalPipeline._safe_int("", default=1) == 1


class TestPipelineRunAsyncGuard:
    """Pipeline.run_async should reject double starts."""

    def test_double_start_raises(self):
        pipeline = SignalPipeline(PipelineConfig(poll_interval=0.01))
        # Mock so it doesn't actually hit Prometheus
        pipeline.poll_once = MagicMock(return_value=None)
        pipeline.run_async(max_cycles=100)
        try:
            with pytest.raises(RuntimeError, match="already running"):
                pipeline.run_async(max_cycles=100)
        finally:
            pipeline.stop()


# ============================================================
# Bootstrap — Scaling Learning Phase Elimination
# ============================================================

class TestNormalizerBootstrap:
    def test_bootstrap_fills_window(self):
        """After bootstrap, z-score normalization should work immediately."""
        normalizer = SignalNormalizer(config=NormalizerConfig(min_samples=10))
        # Without bootstrap, first normalize returns 0.5 (no data)
        result_cold = normalizer.normalize({"cpu": 0.9})
        assert abs(result_cold["cpu"] - 0.5) < 0.01  # No data -> midpoint

        # Now bootstrap with history
        normalizer.reset()
        normalizer.bootstrap({"cpu": [0.3] * 50})
        # After bootstrap, a spike should normalize high
        result_warm = normalizer.normalize({"cpu": 0.9})
        assert result_warm["cpu"] > 0.7  # Spike relative to baseline

    def test_bootstrap_multiple_metrics(self):
        """Bootstrap should work for multiple metrics simultaneously."""
        normalizer = SignalNormalizer(config=NormalizerConfig(min_samples=5))
        normalizer.bootstrap({
            "cpu": [0.3] * 30,
            "latency_p99": [0.1] * 30,
            "queue_depth": [50.0] * 30,
        })
        # All metrics should have populated windows
        assert normalizer.get_window_stats("cpu") is not None
        assert normalizer.get_window_stats("cpu")["count"] == 30
        assert normalizer.get_window_stats("latency_p99") is not None
        assert normalizer.get_window_stats("queue_depth") is not None

    def test_bootstrap_empty_is_noop(self):
        """Empty bootstrap should not crash."""
        normalizer = SignalNormalizer()
        normalizer.bootstrap({})
        assert normalizer.get_window_stats("cpu") is None

    def test_bootstrap_nan_filtered(self):
        """NaN values in bootstrap data should be skipped."""
        normalizer = SignalNormalizer()
        normalizer.bootstrap({"cpu": [0.3, float('nan'), 0.4, 0.35]})
        stats = normalizer.get_window_stats("cpu")
        assert stats is not None
        assert stats["count"] == 3  # NaN skipped


def _make_mock_prom_with_history(
    instant_metrics=None,
    k8s_state=None,
    range_data=None,
):
    """Create a PrometheusClient mock that supports both instant and range queries."""
    if instant_metrics is None:
        instant_metrics = {
            "cpu": 0.78,
            "memory": 0.42,
            "latency_p99": 0.340,
            "error_rate": 0.08,
            "queue_depth": 247.0,
        }
    if k8s_state is None:
        k8s_state = {
            "pod_restarts": 0.0,
            "current_replicas": 5.0,
            "desired_replicas": 5.0,
        }
    if range_data is None:
        # 100 samples of steady-state data
        now = time.time()
        range_data = {
            "cpu": [(now - (100 - i) * 15, 0.35 + i * 0.001) for i in range(100)],
            "memory": [(now - (100 - i) * 15, 0.40) for i in range(100)],
            "latency_p99": [(now - (100 - i) * 15, 0.12) for i in range(100)],
            "error_rate": [(now - (100 - i) * 15, 0.02) for i in range(100)],
            "queue_depth": [(now - (100 - i) * 15, 55.0) for i in range(100)],
        }

    mock = MagicMock(spec=PrometheusClient)
    mock.query_metrics.return_value = instant_metrics
    mock.query_k8s_state.return_value = k8s_state

    # range_query returns data based on the query name embedded in the call
    def range_side_effect(query, start, end, step="15s"):
        for name, series in range_data.items():
            if name in query:
                return series
        return None
    mock.range_query.side_effect = range_side_effect

    return mock


class TestPipelineBootstrap:
    def test_bootstrap_succeeds_with_history(self):
        """Pipeline bootstrap should succeed when Prometheus has history."""
        pipeline = SignalPipeline(PipelineConfig(bootstrap_window_seconds=3600))
        pipeline.prometheus = _make_mock_prom_with_history()

        result = pipeline.bootstrap()
        assert result is True
        assert pipeline.controller.bootstrapped

    def test_bootstrap_disabled_when_zero(self):
        """bootstrap_window_seconds=0 should skip bootstrap."""
        pipeline = SignalPipeline(PipelineConfig(bootstrap_window_seconds=0))
        pipeline.prometheus = _make_mock_prom_with_history()

        result = pipeline.bootstrap()
        assert result is False

    def test_bootstrap_fails_gracefully_no_data(self):
        """When Prometheus has no history, bootstrap should return False."""
        pipeline = SignalPipeline(PipelineConfig(bootstrap_window_seconds=3600))
        mock = MagicMock(spec=PrometheusClient)
        mock.range_query.return_value = None
        pipeline.prometheus = mock

        result = pipeline.bootstrap()
        assert result is False

    def test_bootstrap_then_poll_works(self):
        """Full flow: bootstrap then poll should produce accurate results."""
        pipeline = SignalPipeline(PipelineConfig(bootstrap_window_seconds=3600))
        mock = _make_mock_prom_with_history()
        pipeline.prometheus = mock

        # Bootstrap
        assert pipeline.bootstrap() is True

        # Now poll — should work and controller should be past warmup
        result = pipeline.poll_once()
        assert result is not None
        assert result.action.step > 100  # Past warmup

    def test_bootstrap_seeds_normalizer(self):
        """After bootstrap, normalizer should have populated windows."""
        pipeline = SignalPipeline(PipelineConfig(
            bootstrap_window_seconds=3600,
            normalizer=NormalizerConfig(min_samples=10),
        ))
        pipeline.prometheus = _make_mock_prom_with_history()

        pipeline.bootstrap()

        # Normalizer should have data for CPU
        stats = pipeline.normalizer.get_window_stats("cpu")
        assert stats is not None
        assert stats["count"] > 10


class TestK8sStateQueryConstruction:
    """The kube-state-metrics queries must use modern names with a legacy
    fallback, label the HPA series by `horizontalpodautoscaler` (not
    `deployment`), and splice selectors so the PromQL is always well-formed."""

    def _capture(self, namespace=None, deployment=None):
        client = PrometheusClient(PrometheusConfig(url="http://fake:9090"))
        seen = []
        with patch.object(client, "instant_query",
                          side_effect=lambda q: (seen.append(q), 1.0)[1]):
            client.query_k8s_state(namespace=namespace, deployment=deployment)
        return seen

    def test_modern_name_with_legacy_fallback(self):
        joined = " ".join(self._capture())
        assert "kube_horizontalpodautoscaler_status_current_replicas" in joined
        assert "kube_horizontalpodautoscaler_status_desired_replicas" in joined
        assert "kube_hpa_status_current_replicas" in joined   # legacy fallback kept
        assert " or " in joined

    def test_hpa_filtered_by_horizontalpodautoscaler_label(self):
        qs = self._capture(namespace="boutique", deployment="frontend")
        hpa_q = next(q for q in qs if "horizontalpodautoscaler_status_current" in q)
        assert 'namespace="boutique"' in hpa_q
        assert 'horizontalpodautoscaler="frontend"' in hpa_q
        assert 'deployment="frontend"' not in hpa_q   # HPA series is not labelled by deployment

    def test_pod_restarts_selector_inside_metric(self):
        pr = next(q for q in self._capture(namespace="boutique") if "restarts_total" in q)
        assert 'kube_pod_container_status_restarts_total{namespace="boutique"}[10m]' in pr
        assert "[10m]{" not in pr   # no malformed selector-after-range

    def test_no_filters_yields_valid_promql(self):
        qs = self._capture()
        for q in qs:
            assert "__NSSEL__" not in q and "__HPASEL__" not in q
        pr = next(q for q in qs if "restarts_total" in q)
        assert "restarts_total[10m]" in pr
