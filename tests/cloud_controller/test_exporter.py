"""Tests for the Prometheus Metrics Exporter."""

import pytest
from unittest.mock import MagicMock
from symbolu.cloud_controller.controller import Controller, ActionResult
from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.observability.exporter import (
    BuiltinHistogram,
    BuiltinMetric,
    ExporterConfig,
    ExporterMode,
    MetricsExporter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def controller():
    return Controller(InfraControllerConfig())


@pytest.fixture
def exporter():
    return MetricsExporter(ExporterConfig(mode=ExporterMode.BUILTIN))


def _make_action(controller) -> ActionResult:
    return controller.step(
        metrics={"cpu": 0.7, "memory": 0.6, "latency_p99": 0.5, "error_rate": 0.01},
        current_replicas=5,
    )


# ---------------------------------------------------------------------------
# BuiltinMetric
# ---------------------------------------------------------------------------

class TestBuiltinMetric:
    def test_gauge_set_and_expose(self):
        m = BuiltinMetric("test_gauge", "A test gauge", "gauge")
        m.set(42.5)
        text = m.expose()
        assert "# HELP test_gauge A test gauge" in text
        assert "# TYPE test_gauge gauge" in text
        assert "test_gauge 42.5" in text

    def test_counter_inc(self):
        m = BuiltinMetric("test_counter", "A counter", "counter")
        m.inc()
        m.inc(3.0)
        text = m.expose()
        assert "test_counter 4.0" in text

    def test_labels(self):
        m = BuiltinMetric("test_labeled", "With labels", "counter")
        m.inc(labels={"method": "GET"})
        m.inc(labels={"method": "POST"})
        m.inc(labels={"method": "GET"})
        text = m.expose()
        assert 'method="GET"' in text
        assert 'method="POST"' in text
        # GET should be 2.0
        assert 'test_labeled{method="GET"} 2.0' in text
        assert 'test_labeled{method="POST"} 1.0' in text

    def test_reset(self):
        m = BuiltinMetric("test_reset", "Reset test", "gauge")
        m.set(99.0)
        m.reset()
        text = m.expose()
        assert "test_reset 0.0" in text

    def test_observe_sets_value(self):
        m = BuiltinMetric("test_hist", "Histogram", "gauge")
        m.observe(0.123)
        text = m.expose()
        assert "0.123" in text

    def test_multiple_labels_sorted(self):
        m = BuiltinMetric("test_multi", "Multi labels", "gauge")
        m.set(1.0, labels={"b": "2", "a": "1"})
        text = m.expose()
        # Labels should be sorted: a before b
        assert 'a="1",b="2"' in text


# ---------------------------------------------------------------------------
# MetricsExporter — Disabled mode
# ---------------------------------------------------------------------------

class TestExporterDisabled:
    def test_disabled_mode(self):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        assert exp.mode == ExporterMode.DISABLED
        assert exp.expose() == ""

    def test_disabled_record_cycle_noop(self, controller):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        action = _make_action(controller)
        exp.record_cycle(action)  # Should not raise

    def test_disabled_record_execution_noop(self):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        exp.record_execution(True)  # Should not raise

    def test_disabled_record_rollback_noop(self):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        exp.record_rollback()  # Should not raise

    def test_disabled_record_feedback_noop(self):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        exp.record_feedback(5)  # Should not raise


# ---------------------------------------------------------------------------
# MetricsExporter — Builtin mode
# ---------------------------------------------------------------------------

class TestExporterBuiltin:
    def test_builtin_mode(self, exporter):
        assert exporter.mode == ExporterMode.BUILTIN

    def test_record_cycle(self, exporter, controller):
        action = _make_action(controller)
        exporter.record_cycle(action, current_replicas=5, cycle_duration=0.15)
        text = exporter.expose()

        # Check all controller state metrics are present
        assert "ncc_action_score" in text
        assert "ncc_pressure" in text
        assert "ncc_coherence" in text
        assert "ncc_plasticity" in text
        assert "ncc_gain" in text
        assert "ncc_damping" in text
        assert "ncc_identity_deviation" in text
        assert "ncc_cycles_total" in text
        assert "ncc_cycle_duration_seconds" in text
        assert "ncc_current_replicas" in text
        assert "ncc_target_replicas" in text

    def test_record_multiple_cycles_increments_counter(self, exporter, controller):
        for _ in range(3):
            action = _make_action(controller)
            exporter.record_cycle(action, current_replicas=5)
        text = exporter.expose()
        assert "ncc_cycles_total 3.0" in text

    def test_record_execution_success(self, exporter):
        exporter.record_execution(True)
        text = exporter.expose()
        assert 'result="success"' in text

    def test_record_execution_failure(self, exporter):
        exporter.record_execution(False)
        text = exporter.expose()
        assert 'result="failure"' in text

    def test_record_rollback(self, exporter):
        exporter.record_rollback()
        exporter.record_rollback()
        text = exporter.expose()
        assert "ncc_rollbacks_total 2.0" in text

    def test_record_feedback(self, exporter):
        exporter.record_feedback(3)
        text = exporter.expose()
        assert "ncc_feedback_adjustments_total 3.0" in text

    def test_recommendation_label_tracking(self, exporter, controller):
        action = _make_action(controller)
        exporter.record_cycle(action, current_replicas=5)
        text = exporter.expose()
        assert "ncc_recommendations_total" in text
        # Should have the recommendation type as a label
        assert f'recommendation="{action.recommendation}"' in text

    def test_expose_format_valid_prometheus(self, exporter, controller):
        action = _make_action(controller)
        exporter.record_cycle(action, current_replicas=5)
        text = exporter.expose()
        # Every metric should have HELP and TYPE lines
        lines = text.strip().split("\n")
        help_count = sum(1 for l in lines if l.startswith("# HELP"))
        type_count = sum(1 for l in lines if l.startswith("# TYPE"))
        assert help_count == type_count
        assert help_count > 0

    def test_reset_clears_all(self, exporter, controller):
        action = _make_action(controller)
        exporter.record_cycle(action, current_replicas=5)
        exporter.record_rollback()
        exporter.reset()
        text = exporter.expose()
        # After reset, counters should be 0
        assert "ncc_cycles_total 0.0" in text
        assert "ncc_rollbacks_total 0.0" in text

    def test_custom_prefix(self, controller):
        exp = MetricsExporter(ExporterConfig(prefix="myapp"))
        action = _make_action(controller)
        exp.record_cycle(action)
        text = exp.expose()
        assert "myapp_action_score" in text
        assert "myapp_cycles_total" in text

    def test_zero_replicas_skips_replica_metrics(self, exporter, controller):
        action = _make_action(controller)
        exporter.record_cycle(action, current_replicas=0)
        text = exporter.expose()
        # current_replicas should remain at 0 (default) when not set
        assert "ncc_current_replicas 0.0" in text


# ---------------------------------------------------------------------------
# MetricsExporter — prom_client mode fallback
# ---------------------------------------------------------------------------

class TestExporterPromClientFallback:
    def test_falls_back_to_builtin_when_unavailable(self):
        """When requesting prom_client but it's not installed, should fall back."""
        import symbolu.cloud_controller.observability.exporter as mod
        original = mod.PROM_CLIENT_AVAILABLE
        try:
            mod.PROM_CLIENT_AVAILABLE = False
            exp = MetricsExporter(ExporterConfig(mode=ExporterMode.PROM_CLIENT))
            # Should fall back to builtin
            assert exp.mode == ExporterMode.BUILTIN
        finally:
            mod.PROM_CLIENT_AVAILABLE = original


# ---------------------------------------------------------------------------
# BuiltinHistogram
# ---------------------------------------------------------------------------

class TestBuiltinHistogram:
    def test_observe_and_expose(self):
        h = BuiltinHistogram("test_hist", "A histogram", buckets=(0.1, 0.5, 1.0))
        h.observe(0.05)
        h.observe(0.3)
        h.observe(0.8)
        h.observe(5.0)
        text = h.expose()

        assert "# HELP test_hist A histogram" in text
        assert "# TYPE test_hist histogram" in text
        # 0.05 <= 0.1: bucket 0.1 cumulative = 1
        assert 'test_hist_bucket{le="0.1"} 1' in text
        # 0.3 <= 0.5: bucket 0.5 cumulative = 2
        assert 'test_hist_bucket{le="0.5"} 2' in text
        # 0.8 <= 1.0: bucket 1.0 cumulative = 3
        assert 'test_hist_bucket{le="1.0"} 3' in text
        # 5.0 > 1.0: +Inf cumulative = 4
        assert 'test_hist_bucket{le="+Inf"} 4' in text
        assert "test_hist_count 4" in text
        assert "test_hist_sum" in text

    def test_empty_histogram(self):
        h = BuiltinHistogram("empty", "Empty", buckets=(1.0,))
        text = h.expose()
        assert 'empty_bucket{le="1.0"} 0' in text
        assert 'empty_bucket{le="+Inf"} 0' in text
        assert "empty_count 0" in text
        assert "empty_sum 0.0" in text

    def test_reset(self):
        h = BuiltinHistogram("reset_h", "Reset", buckets=(1.0,))
        h.observe(0.5)
        h.observe(2.0)
        h.reset()
        text = h.expose()
        assert "reset_h_count 0" in text
        assert "reset_h_sum 0.0" in text

    def test_cumulative_buckets(self):
        """Buckets are cumulative — each includes all lower buckets."""
        h = BuiltinHistogram("cum", "Cumulative", buckets=(0.1, 0.5, 1.0))
        h.observe(0.05)  # goes in 0.1 bucket
        text = h.expose()
        # All buckets >= 0.1 should include this observation
        assert 'cum_bucket{le="0.1"} 1' in text
        assert 'cum_bucket{le="0.5"} 1' in text
        assert 'cum_bucket{le="1.0"} 1' in text
        assert 'cum_bucket{le="+Inf"} 1' in text


# ---------------------------------------------------------------------------
# MetricsExporter — New metrics (safety, divergence, pipeline errors, approvals)
# ---------------------------------------------------------------------------

class TestExporterNewMetrics:
    def test_record_safety(self, exporter):
        safety = MagicMock()
        safety.was_clamped = True
        safety.in_cooldown = True
        safety.cooldown_remaining = 12.5
        exporter.record_safety(safety)
        text = exporter.expose()
        assert "ncc_safety_clamped_total 1.0" in text
        assert "ncc_cooldown_active 1.0" in text
        assert "ncc_cooldown_remaining_seconds 12.5" in text

    def test_record_safety_not_clamped(self, exporter):
        safety = MagicMock()
        safety.was_clamped = False
        safety.in_cooldown = False
        safety.cooldown_remaining = 0.0
        exporter.record_safety(safety)
        text = exporter.expose()
        assert "ncc_safety_clamped_total 0.0" in text
        assert "ncc_cooldown_active 0.0" in text

    def test_record_divergence(self, exporter):
        exporter.record_divergence("direction")
        exporter.record_divergence("magnitude")
        exporter.record_divergence("direction")
        text = exporter.expose()
        assert 'divergence_type="direction"' in text
        assert 'divergence_type="magnitude"' in text

    def test_record_pipeline_error(self, exporter):
        exporter.record_pipeline_error()
        exporter.record_pipeline_error()
        text = exporter.expose()
        assert "ncc_pipeline_errors_total 2.0" in text

    def test_record_approval_state(self, exporter):
        exporter.record_approval_state("pending", 3)
        exporter.record_approval_state("approved", 7)
        text = exporter.expose()
        assert 'state="pending"' in text
        assert 'state="approved"' in text

    def test_input_metric_gauges(self, exporter, controller):
        action = _make_action(controller)
        exporter.record_cycle(action, current_replicas=5)
        text = exporter.expose()
        assert "ncc_input_metric_value" in text
        assert 'metric_name="cpu"' in text

    def test_action_score_histogram(self, exporter, controller):
        action = _make_action(controller)
        exporter.record_cycle(action, current_replicas=5, cycle_duration=0.1)
        text = exporter.expose()
        assert "ncc_action_score_distribution" in text
        assert "_bucket" in text
        assert "_count" in text
        assert "_sum" in text

    def test_cycle_duration_histogram(self, exporter, controller):
        action = _make_action(controller)
        exporter.record_cycle(action, current_replicas=5, cycle_duration=0.15)
        text = exporter.expose()
        assert "ncc_cycle_duration_histogram_seconds" in text

    def test_disabled_safety_noop(self):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        safety = MagicMock()
        safety.was_clamped = True
        safety.in_cooldown = True
        safety.cooldown_remaining = 10.0
        exp.record_safety(safety)  # Should not raise

    def test_disabled_divergence_noop(self):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        exp.record_divergence("test")  # Should not raise

    def test_disabled_pipeline_error_noop(self):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        exp.record_pipeline_error()  # Should not raise

    def test_disabled_approval_state_noop(self):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        exp.record_approval_state("pending", 5)  # Should not raise

    def test_push_disabled_returns_false(self):
        exp = MetricsExporter(ExporterConfig(mode=ExporterMode.DISABLED))
        assert exp.push("http://localhost:9091") is False

    def test_push_no_url_returns_false(self, exporter):
        assert exporter.push() is False
