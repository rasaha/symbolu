"""Tests for the OpenTelemetry Exporter.

Since opentelemetry SDK may not be installed in the test environment,
we primarily test the graceful fallback / no-op behavior and config.
"""

import pytest
from unittest.mock import MagicMock

from symbolu.cloud_controller.observability.otel_exporter import (
    OtelExporter,
    OtelExporterConfig,
    _NullSpan,
    OTEL_AVAILABLE,
)


# ---------------------------------------------------------------------------
# NullSpan
# ---------------------------------------------------------------------------

class TestNullSpan:
    def test_set_attribute_noop(self):
        span = _NullSpan()
        span.set_attribute("key", "value")  # Should not raise

    def test_set_status_noop(self):
        span = _NullSpan()
        span.set_status("ok")  # Should not raise

    def test_record_exception_noop(self):
        span = _NullSpan()
        span.record_exception(ValueError("test"))  # Should not raise

    def test_context_manager(self):
        span = _NullSpan()
        with span as s:
            assert s is span


# ---------------------------------------------------------------------------
# OtelExporterConfig
# ---------------------------------------------------------------------------

class TestOtelExporterConfig:
    def test_defaults(self):
        cfg = OtelExporterConfig()
        assert cfg.enabled is False
        assert cfg.endpoint == "http://localhost:4317"
        assert cfg.protocol == "grpc"
        assert cfg.service_name == "neural-cloud-controller"
        assert cfg.export_interval_ms == 10000
        assert cfg.insecure is True
        assert cfg.prefix == "ncc"

    def test_custom_config(self):
        cfg = OtelExporterConfig(
            enabled=True,
            endpoint="http://collector:4318",
            protocol="http",
            service_name="my-service",
            resource_attributes={"env": "prod"},
        )
        assert cfg.enabled is True
        assert cfg.protocol == "http"
        assert cfg.resource_attributes == {"env": "prod"}


# ---------------------------------------------------------------------------
# OtelExporter — disabled mode (default)
# ---------------------------------------------------------------------------

class TestOtelExporterDisabled:
    def test_disabled_by_default(self):
        exp = OtelExporter()
        assert not exp.enabled

    def test_disabled_with_explicit_config(self):
        exp = OtelExporter(OtelExporterConfig(enabled=False))
        assert not exp.enabled

    def test_record_cycle_noop(self):
        exp = OtelExporter()
        action = MagicMock()
        action.action_score = 0.5
        action.pressure = 0.7
        action.coherence.coherence = 0.8
        action.plasticity.plasticity = 0.6
        action.gain.gain = 1.2
        action.damping.damping = 0.9
        action.identity_deviation = 0.1
        action.recommendation = "hold"
        action.replica_delta = 0
        exp.record_cycle(action, current_replicas=5)  # Should not raise

    def test_record_execution_noop(self):
        exp = OtelExporter()
        exp.record_execution(True)  # Should not raise

    def test_record_rollback_noop(self):
        exp = OtelExporter()
        exp.record_rollback()  # Should not raise

    def test_record_feedback_noop(self):
        exp = OtelExporter()
        exp.record_feedback(3)  # Should not raise

    def test_record_pipeline_error_noop(self):
        exp = OtelExporter()
        exp.record_pipeline_error()  # Should not raise

    def test_trace_cycle_yields_null_span(self):
        exp = OtelExporter()
        with exp.trace_cycle(42) as span:
            assert isinstance(span, _NullSpan)
            span.set_attribute("test", "value")  # No-op

    def test_trace_phase_yields_null_span(self):
        exp = OtelExporter()
        with exp.trace_phase("pipeline") as span:
            assert isinstance(span, _NullSpan)

    def test_shutdown_noop(self):
        exp = OtelExporter()
        exp.shutdown()  # Should not raise


# ---------------------------------------------------------------------------
# OtelExporter — enabled without SDK
# ---------------------------------------------------------------------------

class TestOtelExporterNoSDK:
    def test_enabled_without_sdk_stays_disabled(self):
        """When enabled=True but SDK not installed, should remain disabled."""
        import symbolu.cloud_controller.observability.otel_exporter as mod
        original = mod.OTEL_AVAILABLE
        try:
            mod.OTEL_AVAILABLE = False
            exp = OtelExporter(OtelExporterConfig(enabled=True))
            assert not exp.enabled
        finally:
            mod.OTEL_AVAILABLE = original


# ---------------------------------------------------------------------------
# OtelExporter — enabled with SDK (if available)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not OTEL_AVAILABLE, reason="opentelemetry SDK not installed")
class TestOtelExporterWithSDK:
    def test_init_enables(self):
        exp = OtelExporter(OtelExporterConfig(enabled=True))
        assert exp.enabled
        exp.shutdown()

    def test_record_cycle_with_real_sdk(self):
        exp = OtelExporter(OtelExporterConfig(enabled=True))
        action = MagicMock()
        action.action_score = 0.5
        action.pressure = 0.7
        action.coherence.coherence = 0.8
        action.plasticity.plasticity = 0.6
        action.gain.gain = 1.2
        action.damping.damping = 0.9
        action.identity_deviation = 0.1
        action.recommendation = "scale_out_1"
        action.replica_delta = 1
        exp.record_cycle(action, current_replicas=5, cycle_duration=0.1)
        exp.shutdown()

    def test_trace_cycle_with_real_sdk(self):
        exp = OtelExporter(OtelExporterConfig(enabled=True))
        with exp.trace_cycle(1) as span:
            assert not isinstance(span, _NullSpan)
            span.set_attribute("test", "value")
        exp.shutdown()

    def test_trace_phase_with_real_sdk(self):
        exp = OtelExporter(OtelExporterConfig(enabled=True))
        with exp.trace_phase("pipeline") as span:
            assert not isinstance(span, _NullSpan)
        exp.shutdown()
