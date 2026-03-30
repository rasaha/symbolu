"""Prometheus Metrics Exporter — exposes controller state for Grafana dashboards.

Publishes controller decision metrics back to Prometheus so operators can
visualize the full control loop in Grafana:

  - action_score, pressure, coherence, plasticity, gain, damping
  - recommendation counts by type (hold, scale_out, scale_in, observe)
  - execution success/failure, rollback count
  - feedback loop adjustments
  - pipeline cycle timing

Two export modes:
  1. Push Gateway — POST metrics to a Prometheus Pushgateway (for batch jobs)
  2. HTTP Exposition — expose /metrics endpoint for Prometheus to scrape

When the `prometheus_client` library is unavailable, falls back to a
lightweight built-in exposition format that produces valid Prometheus
text exposition without any external dependencies.
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional prometheus_client dependency
try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    PROM_CLIENT_AVAILABLE = True
except ImportError:
    PROM_CLIENT_AVAILABLE = False


class ExporterMode(Enum):
    """How metrics are exported."""
    DISABLED = "disabled"
    BUILTIN = "builtin"         # Lightweight built-in text exposition
    PROM_CLIENT = "prom_client" # Full prometheus_client library


@dataclass
class ExporterConfig:
    """Configuration for the metrics exporter."""
    # Operating mode (auto-detects prometheus_client availability)
    mode: ExporterMode = ExporterMode.BUILTIN
    # Metric name prefix
    prefix: str = "ncc"        # neural_cloud_controller
    # Labels applied to all metrics
    labels: Dict[str, str] = field(default_factory=lambda: {
        "controller": "neural_cloud",
    })
    # Service/namespace for job-level labels
    service: str = ""
    namespace: str = ""


class BuiltinMetric:
    """A single metric in Prometheus text exposition format."""

    def __init__(self, name: str, help_text: str, metric_type: str = "gauge"):
        self.name = name
        self.help_text = help_text
        self.metric_type = metric_type
        self._value: float = 0.0
        self._labels_values: Dict[str, float] = {}  # label_str → value
        self._lock = threading.Lock()

    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge value."""
        with self._lock:
            if labels:
                key = self._format_labels(labels)
                self._labels_values[key] = value
            else:
                self._value = value

    def inc(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter."""
        with self._lock:
            if labels:
                key = self._format_labels(labels)
                self._labels_values[key] = self._labels_values.get(key, 0.0) + amount
            else:
                self._value += amount

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation (simplified — tracks last value only)."""
        self.set(value, labels)

    def expose(self) -> str:
        """Render in Prometheus text exposition format."""
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} {self.metric_type}",
        ]
        with self._lock:
            if self._labels_values:
                for label_str, val in sorted(self._labels_values.items()):
                    lines.append(f"{self.name}{{{label_str}}} {val}")
            else:
                lines.append(f"{self.name} {self._value}")
        return "\n".join(lines)

    @staticmethod
    def _format_labels(labels: Dict[str, str]) -> str:
        """Format labels as Prometheus label string."""
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return ",".join(parts)

    def reset(self) -> None:
        """Reset metric to zero."""
        with self._lock:
            self._value = 0.0
            self._labels_values.clear()


class MetricsExporter:
    """Exports controller metrics for Prometheus/Grafana.

    Usage — builtin mode (no dependencies):
        exporter = MetricsExporter(ExporterConfig())
        exporter.record_cycle(action_result, cycle_duration=0.15)
        text = exporter.expose()
        # Serve `text` on /metrics endpoint

    Usage — prometheus_client mode:
        exporter = MetricsExporter(ExporterConfig(mode=ExporterMode.PROM_CLIENT))
        exporter.record_cycle(action_result, cycle_duration=0.15)
        # Use prometheus_client's built-in WSGI app or generate_latest()
    """

    def __init__(self, config: Optional[ExporterConfig] = None):
        self.config = config or ExporterConfig()
        p = self.config.prefix

        if self.config.mode == ExporterMode.PROM_CLIENT and PROM_CLIENT_AVAILABLE:
            self._mode = ExporterMode.PROM_CLIENT
            self._registry = CollectorRegistry()
            self._init_prom_client(p)
        elif self.config.mode != ExporterMode.DISABLED:
            self._mode = ExporterMode.BUILTIN
            self._registry = None
            self._init_builtin(p)
        else:
            self._mode = ExporterMode.DISABLED
            self._registry = None

    def _init_builtin(self, p: str) -> None:
        """Initialize built-in metrics."""
        self._metrics: Dict[str, BuiltinMetric] = {}

        # Controller state gauges
        for name, help_text in [
            ("action_score", "Current action score A_t"),
            ("pressure", "Demand pressure signal S_t"),
            ("coherence", "Signal coherence C_t"),
            ("plasticity", "Plasticity gate P_t"),
            ("gain", "Adaptive gain G_t"),
            ("damping", "Damping factor d_t"),
            ("identity_deviation", "Identity drift from baseline"),
        ]:
            self._metrics[name] = BuiltinMetric(
                f"{p}_{name}", help_text, "gauge",
            )

        # Counters
        self._metrics["cycles_total"] = BuiltinMetric(
            f"{p}_cycles_total", "Total control cycles executed", "counter",
        )
        self._metrics["recommendations_total"] = BuiltinMetric(
            f"{p}_recommendations_total",
            "Recommendations by type",
            "counter",
        )
        self._metrics["executions_total"] = BuiltinMetric(
            f"{p}_executions_total",
            "Scaling executions by result",
            "counter",
        )
        self._metrics["rollbacks_total"] = BuiltinMetric(
            f"{p}_rollbacks_total",
            "Rollback actions triggered",
            "counter",
        )
        self._metrics["feedback_adjustments_total"] = BuiltinMetric(
            f"{p}_feedback_adjustments_total",
            "Feedback loop parameter adjustments",
            "counter",
        )

        # Timing
        self._metrics["cycle_duration_seconds"] = BuiltinMetric(
            f"{p}_cycle_duration_seconds",
            "Time to complete one control cycle",
            "gauge",
        )

        # Replica state
        self._metrics["current_replicas"] = BuiltinMetric(
            f"{p}_current_replicas", "Current replica count", "gauge",
        )
        self._metrics["target_replicas"] = BuiltinMetric(
            f"{p}_target_replicas", "Target replica count after decision", "gauge",
        )

    def _init_prom_client(self, p: str) -> None:
        """Initialize prometheus_client metrics."""
        reg = self._registry

        self._pc_action_score = Gauge(
            f"{p}_action_score", "Current action score A_t", registry=reg,
        )
        self._pc_pressure = Gauge(
            f"{p}_pressure", "Demand pressure signal S_t", registry=reg,
        )
        self._pc_coherence = Gauge(
            f"{p}_coherence", "Signal coherence C_t", registry=reg,
        )
        self._pc_plasticity = Gauge(
            f"{p}_plasticity", "Plasticity gate P_t", registry=reg,
        )
        self._pc_gain = Gauge(
            f"{p}_gain", "Adaptive gain G_t", registry=reg,
        )
        self._pc_damping = Gauge(
            f"{p}_damping", "Damping factor d_t", registry=reg,
        )
        self._pc_identity_deviation = Gauge(
            f"{p}_identity_deviation", "Identity drift from baseline", registry=reg,
        )
        self._pc_cycles = Counter(
            f"{p}_cycles_total", "Total control cycles executed", registry=reg,
        )
        self._pc_recommendations = Counter(
            f"{p}_recommendations_total", "Recommendations by type",
            ["recommendation"], registry=reg,
        )
        self._pc_executions = Counter(
            f"{p}_executions_total", "Scaling executions by result",
            ["result"], registry=reg,
        )
        self._pc_rollbacks = Counter(
            f"{p}_rollbacks_total", "Rollback actions triggered", registry=reg,
        )
        self._pc_feedback = Counter(
            f"{p}_feedback_adjustments_total",
            "Feedback loop parameter adjustments", registry=reg,
        )
        self._pc_cycle_duration = Histogram(
            f"{p}_cycle_duration_seconds",
            "Time to complete one control cycle",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=reg,
        )
        self._pc_current_replicas = Gauge(
            f"{p}_current_replicas", "Current replica count", registry=reg,
        )
        self._pc_target_replicas = Gauge(
            f"{p}_target_replicas", "Target replica count after decision", registry=reg,
        )

    def record_cycle(
        self,
        action,
        current_replicas: int = 0,
        cycle_duration: float = 0.0,
    ) -> None:
        """Record metrics from one control cycle.

        Args:
            action: Controller ActionResult.
            current_replicas: Current replica count.
            cycle_duration: How long the cycle took (seconds).
        """
        if self._mode == ExporterMode.DISABLED:
            return

        if self._mode == ExporterMode.BUILTIN:
            self._record_builtin(action, current_replicas, cycle_duration)
        else:
            self._record_prom_client(action, current_replicas, cycle_duration)

    def _record_builtin(self, action, current_replicas: int, duration: float) -> None:
        """Record using built-in metrics."""
        m = self._metrics
        m["action_score"].set(action.action_score)
        m["pressure"].set(action.pressure)
        m["coherence"].set(action.coherence.coherence)
        m["plasticity"].set(action.plasticity.plasticity)
        m["gain"].set(action.gain.gain)
        m["damping"].set(action.damping.damping)
        m["identity_deviation"].set(action.identity_deviation)
        m["cycles_total"].inc()
        m["recommendations_total"].inc(
            labels={"recommendation": action.recommendation},
        )
        m["cycle_duration_seconds"].set(duration)
        if current_replicas > 0:
            m["current_replicas"].set(current_replicas)
            m["target_replicas"].set(current_replicas + action.replica_delta)

    def _record_prom_client(self, action, current_replicas: int, duration: float) -> None:
        """Record using prometheus_client."""
        self._pc_action_score.set(action.action_score)
        self._pc_pressure.set(action.pressure)
        self._pc_coherence.set(action.coherence.coherence)
        self._pc_plasticity.set(action.plasticity.plasticity)
        self._pc_gain.set(action.gain.gain)
        self._pc_damping.set(action.damping.damping)
        self._pc_identity_deviation.set(action.identity_deviation)
        self._pc_cycles.inc()
        self._pc_recommendations.labels(recommendation=action.recommendation).inc()
        self._pc_cycle_duration.observe(duration)
        if current_replicas > 0:
            self._pc_current_replicas.set(current_replicas)
            self._pc_target_replicas.set(current_replicas + action.replica_delta)

    def record_execution(self, success: bool) -> None:
        """Record a scaling execution result."""
        if self._mode == ExporterMode.DISABLED:
            return
        result = "success" if success else "failure"
        if self._mode == ExporterMode.BUILTIN:
            self._metrics["executions_total"].inc(labels={"result": result})
        else:
            self._pc_executions.labels(result=result).inc()

    def record_rollback(self) -> None:
        """Record a rollback event."""
        if self._mode == ExporterMode.DISABLED:
            return
        if self._mode == ExporterMode.BUILTIN:
            self._metrics["rollbacks_total"].inc()
        else:
            self._pc_rollbacks.inc()

    def record_feedback(self, adjustment_count: int = 1) -> None:
        """Record feedback loop adjustments."""
        if self._mode == ExporterMode.DISABLED:
            return
        if self._mode == ExporterMode.BUILTIN:
            self._metrics["feedback_adjustments_total"].inc(adjustment_count)
        else:
            self._pc_feedback.inc(adjustment_count)

    def expose(self) -> str:
        """Generate Prometheus text exposition format.

        Returns:
            String suitable for serving on /metrics endpoint.
        """
        if self._mode == ExporterMode.DISABLED:
            return ""

        if self._mode == ExporterMode.PROM_CLIENT:
            return generate_latest(self._registry).decode("utf-8")

        # Built-in exposition
        sections = []
        for metric in self._metrics.values():
            sections.append(metric.expose())
        return "\n\n".join(sections) + "\n"

    @property
    def mode(self) -> ExporterMode:
        return self._mode

    def reset(self) -> None:
        """Reset all metrics to zero."""
        if self._mode == ExporterMode.BUILTIN:
            for metric in self._metrics.values():
                metric.reset()
