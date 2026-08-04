"""OpenTelemetry Exporter — OTLP metrics and traces for observability backends.

Exports controller metrics and trace spans to any OpenTelemetry-compatible
backend (Jaeger, Datadog, Grafana Cloud, Honeycomb, etc.) via OTLP protocol.

Graceful fallback: when the opentelemetry SDK is not installed, all methods
become no-ops with a single import-time warning. The controller operates
identically with or without this exporter.

Usage — metrics + traces:
    exporter = OtelExporter(OtelExporterConfig(
        endpoint="http://otel-collector:4317",
        service_name="neural-cloud-controller",
    ))
    # Each cycle:
    with exporter.trace_cycle(cycle_number=42) as span:
        action = controller.step(metrics)
        exporter.record_cycle(action, current_replicas=5, cycle_duration=0.12)
        span.set_attribute("ncc.recommendation", action.recommendation)
    # On shutdown:
    exporter.shutdown()

Usage — disabled (no opentelemetry installed):
    exporter = OtelExporter(OtelExporterConfig())
    exporter.record_cycle(action)  # no-op, no error
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

# Optional OpenTelemetry SDK imports
try:
    from opentelemetry import metrics as otel_metrics
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        InMemoryMetricReader,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        SimpleSpanProcessor,
    )
    from opentelemetry.sdk.resources import Resource

    # OTLP exporters — separate optional dependency
    try:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter as _OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter as _OTLPSpanExporter,
        )
        OTLP_GRPC_AVAILABLE = True
    except ImportError:
        OTLP_GRPC_AVAILABLE = False

    try:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter as _OTLPHTTPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as _OTLPHTTPSpanExporter,
        )
        OTLP_HTTP_AVAILABLE = True
    except ImportError:
        OTLP_HTTP_AVAILABLE = False

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    OTLP_GRPC_AVAILABLE = False
    OTLP_HTTP_AVAILABLE = False


@dataclass
class OtelExporterConfig:
    """Configuration for the OpenTelemetry exporter."""
    # Whether OTel export is enabled
    enabled: bool = False
    # OTLP endpoint
    endpoint: str = "http://localhost:4317"
    # Transport protocol: "grpc" or "http"
    protocol: str = "grpc"
    # Service name for resource identification
    service_name: str = "neural-cloud-controller"
    # Additional resource attributes
    resource_attributes: Dict[str, str] = field(default_factory=dict)
    # Metric export interval (milliseconds)
    export_interval_ms: int = 10000
    # Skip TLS verification (development only)
    insecure: bool = True
    # Metric name prefix
    prefix: str = "ncc"


class _NullSpan:
    """No-op span for when OTel is disabled."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: BaseException) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class OtelExporter:
    """OpenTelemetry metrics and traces exporter.

    When opentelemetry SDK is not installed or config.enabled is False,
    all methods are safe no-ops.
    """

    def __init__(self, config: Optional[OtelExporterConfig] = None):
        self.config = config or OtelExporterConfig()
        self._enabled = False
        self._meter = None
        self._tracer = None
        self._meter_provider = None
        self._tracer_provider = None

        # Metric instruments (set during _init_otel)
        self._action_score = None
        self._pressure = None
        self._coherence = None
        self._plasticity = None
        self._gain = None
        self._damping = None
        self._identity_deviation = None
        self._cycles_total = None
        self._recommendations_total = None
        self._executions_total = None
        self._rollbacks_total = None
        self._feedback_total = None
        self._pipeline_errors_total = None
        self._cycle_duration = None
        self._current_replicas = None
        self._target_replicas = None

        if self.config.enabled and OTEL_AVAILABLE:
            self._init_otel()
        elif self.config.enabled and not OTEL_AVAILABLE:
            logger.warning(
                "OpenTelemetry requested but SDK not installed. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-otlp-proto-grpc"
            )

    def _init_otel(self) -> None:
        """Initialize OpenTelemetry providers and instruments."""
        # Resource
        attrs = {"service.name": self.config.service_name}
        attrs.update(self.config.resource_attributes)
        resource = Resource.create(attrs)

        # --- Metrics ---
        metric_exporter = self._create_metric_exporter()
        if metric_exporter is not None:
            reader = PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=self.config.export_interval_ms,
            )
        else:
            # Fallback: in-memory reader (useful for testing)
            reader = InMemoryMetricReader()
            logger.info("OTel: using InMemoryMetricReader (no OTLP exporter available)")

        self._meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[reader],
        )
        self._meter = self._meter_provider.get_meter(
            self.config.service_name, version="1.0.0",
        )

        # --- Traces ---
        span_exporter = self._create_span_exporter()
        self._tracer_provider = TracerProvider(resource=resource)
        if span_exporter is not None:
            processor = BatchSpanProcessor(span_exporter)
            self._tracer_provider.add_span_processor(processor)

        self._tracer = self._tracer_provider.get_tracer(
            self.config.service_name, version="1.0.0",
        )

        # --- Create instruments ---
        p = self.config.prefix
        self._action_score = self._meter.create_gauge(
            f"{p}.action_score", description="Current action score A_t",
        )
        self._pressure = self._meter.create_gauge(
            f"{p}.pressure", description="Demand pressure signal S_t",
        )
        self._coherence = self._meter.create_gauge(
            f"{p}.coherence", description="Signal coherence C_t",
        )
        self._plasticity = self._meter.create_gauge(
            f"{p}.plasticity", description="Plasticity gate P_t",
        )
        self._gain = self._meter.create_gauge(
            f"{p}.gain", description="Adaptive gain G_t",
        )
        self._damping = self._meter.create_gauge(
            f"{p}.damping", description="Damping factor d_t",
        )
        self._identity_deviation = self._meter.create_gauge(
            f"{p}.identity_deviation", description="Identity drift from baseline",
        )
        self._cycles_total = self._meter.create_counter(
            f"{p}.cycles.total", description="Total control cycles executed",
        )
        self._recommendations_total = self._meter.create_counter(
            f"{p}.recommendations.total", description="Recommendations by type",
        )
        self._executions_total = self._meter.create_counter(
            f"{p}.executions.total", description="Scaling executions by result",
        )
        self._rollbacks_total = self._meter.create_counter(
            f"{p}.rollbacks.total", description="Rollback actions triggered",
        )
        self._feedback_total = self._meter.create_counter(
            f"{p}.feedback_adjustments.total",
            description="Feedback loop parameter adjustments",
        )
        self._pipeline_errors_total = self._meter.create_counter(
            f"{p}.pipeline_errors.total", description="Pipeline polling failures",
        )
        self._cycle_duration = self._meter.create_histogram(
            f"{p}.cycle_duration", unit="s",
            description="Time to complete one control cycle",
        )
        self._current_replicas = self._meter.create_gauge(
            f"{p}.current_replicas", description="Current replica count",
        )
        self._target_replicas = self._meter.create_gauge(
            f"{p}.target_replicas",
            description="Target replica count after decision",
        )

        self._enabled = True
        logger.info(
            "OpenTelemetry initialized: endpoint=%s protocol=%s",
            self.config.endpoint, self.config.protocol,
        )

    def _create_metric_exporter(self):
        """Create the appropriate OTLP metric exporter."""
        if self.config.protocol == "grpc" and OTLP_GRPC_AVAILABLE:
            return _OTLPMetricExporter(
                endpoint=self.config.endpoint,
                insecure=self.config.insecure,
            )
        if self.config.protocol == "http" and OTLP_HTTP_AVAILABLE:
            return _OTLPHTTPMetricExporter(
                endpoint=f"{self.config.endpoint}/v1/metrics",
            )
        return None

    def _create_span_exporter(self):
        """Create the appropriate OTLP span exporter."""
        if self.config.protocol == "grpc" and OTLP_GRPC_AVAILABLE:
            return _OTLPSpanExporter(
                endpoint=self.config.endpoint,
                insecure=self.config.insecure,
            )
        if self.config.protocol == "http" and OTLP_HTTP_AVAILABLE:
            return _OTLPHTTPSpanExporter(
                endpoint=f"{self.config.endpoint}/v1/traces",
            )
        return None

    # ------------------------------------------------------------------
    # Recording methods
    # ------------------------------------------------------------------

    def record_cycle(
        self,
        action,
        current_replicas: int = 0,
        cycle_duration: float = 0.0,
    ) -> None:
        """Record metrics from one control cycle."""
        if not self._enabled:
            return

        attrs = {"recommendation": action.recommendation}

        self._action_score.set(action.action_score)
        self._pressure.set(action.pressure)
        self._coherence.set(action.coherence.coherence)
        self._plasticity.set(action.plasticity.plasticity)
        self._gain.set(action.gain.gain)
        self._damping.set(action.damping.damping)
        self._identity_deviation.set(action.identity_deviation)
        self._cycles_total.add(1)
        self._recommendations_total.add(1, attrs)
        if cycle_duration > 0:
            self._cycle_duration.record(cycle_duration)
        if current_replicas > 0:
            self._current_replicas.set(current_replicas)
            self._target_replicas.set(current_replicas + action.replica_delta)

    def record_execution(self, success: bool) -> None:
        """Record a scaling execution result."""
        if not self._enabled:
            return
        self._executions_total.add(
            1, {"result": "success" if success else "failure"},
        )

    def record_rollback(self) -> None:
        """Record a rollback event."""
        if not self._enabled:
            return
        self._rollbacks_total.add(1)

    def record_feedback(self, adjustment_count: int = 1) -> None:
        """Record feedback loop adjustments."""
        if not self._enabled:
            return
        self._feedback_total.add(adjustment_count)

    def record_pipeline_error(self) -> None:
        """Record a pipeline polling failure."""
        if not self._enabled:
            return
        self._pipeline_errors_total.add(1)

    # ------------------------------------------------------------------
    # Tracing
    # ------------------------------------------------------------------

    @contextmanager
    def trace_cycle(self, cycle_number: int = 0) -> Iterator[Any]:
        """Create a trace span for one orchestration cycle.

        Usage:
            with exporter.trace_cycle(42) as span:
                # ... do work ...
                span.set_attribute("ncc.recommendation", "scale_out_1")

        When OTel is disabled, yields a NullSpan (all methods are no-ops).
        """
        if not self._enabled or self._tracer is None:
            yield _NullSpan()
            return

        with self._tracer.start_as_current_span(
            "ncc.orchestration_cycle",
            attributes={"ncc.cycle_number": cycle_number},
        ) as span:
            yield span

    @contextmanager
    def trace_phase(self, phase_name: str) -> Iterator[Any]:
        """Create a child span for a specific phase within a cycle.

        Args:
            phase_name: e.g. "pipeline", "recommend", "execute", "feedback"
        """
        if not self._enabled or self._tracer is None:
            yield _NullSpan()
            return

        with self._tracer.start_as_current_span(
            f"ncc.{phase_name}",
        ) as span:
            yield span

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def shutdown(self) -> None:
        """Flush pending data and shut down providers."""
        if not self._enabled:
            return

        try:
            if self._meter_provider is not None:
                self._meter_provider.shutdown()
        except Exception as e:
            logger.warning("OTel meter provider shutdown error: %s", e)

        try:
            if self._tracer_provider is not None:
                self._tracer_provider.shutdown()
        except Exception as e:
            logger.warning("OTel tracer provider shutdown error: %s", e)

        self._enabled = False
        logger.info("OpenTelemetry exporter shut down")
