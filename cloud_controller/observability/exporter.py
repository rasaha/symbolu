"""Prometheus Metrics Exporter — exposes controller state for Grafana dashboards.

Publishes controller decision metrics back to Prometheus so operators can
visualize the full control loop in Grafana:

  - action_score, pressure, coherence, plasticity, gain, damping
  - per-input metric gauges (cpu, memory, latency_p99, error_rate, queue_depth)
  - action_score distribution histogram
  - recommendation counts by type (hold, scale_out, scale_in, observe)
  - execution success/failure, rollback count
  - safety bounds state (clamped, cooldown)
  - divergence counts by type
  - approval state tracking (pending, approved, dismissed, expired)
  - feedback loop adjustments
  - pipeline cycle timing and error rate

Three export modes:
  1. Builtin     — lightweight zero-dependency text exposition
  2. Prom Client — full prometheus_client library integration
  3. Disabled    — no-op for testing

Push gateway support via push() for batch/cron deployments.
"""

import logging
import threading
import time
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
    # Push gateway settings
    push_gateway_url: str = ""
    push_gateway_job: str = "ncc"


# ---------------------------------------------------------------------------
# Built-in metric types (zero dependencies)
# ---------------------------------------------------------------------------

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


class BuiltinHistogram:
    """Histogram with bucket counting for Prometheus text exposition.

    Produces standard _bucket{le="..."}, _count, _sum lines.
    """

    DEFAULT_BUCKETS = (0.0, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)

    def __init__(
        self,
        name: str,
        help_text: str,
        buckets: Optional[tuple] = None,
    ):
        self.name = name
        self.help_text = help_text
        self._buckets = buckets or self.DEFAULT_BUCKETS
        self._bucket_counts: List[int] = [0] * len(self._buckets)
        self._inf_count: int = 0  # +Inf bucket
        self._sum: float = 0.0
        self._count: int = 0
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        """Record an observation."""
        with self._lock:
            self._sum += value
            self._count += 1
            placed = False
            for i, bound in enumerate(self._buckets):
                if value <= bound:
                    self._bucket_counts[i] += 1
                    placed = True
                    break
            if not placed:
                self._inf_count += 1

    def expose(self) -> str:
        """Render in Prometheus text exposition format."""
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            cumulative = 0
            for i, bound in enumerate(self._buckets):
                cumulative += self._bucket_counts[i]
                lines.append(f'{self.name}_bucket{{le="{bound}"}} {cumulative}')
            cumulative += self._inf_count
            lines.append(f'{self.name}_bucket{{le="+Inf"}} {cumulative}')
            lines.append(f"{self.name}_count {self._count}")
            lines.append(f"{self.name}_sum {self._sum}")
        return "\n".join(lines)

    def reset(self) -> None:
        with self._lock:
            self._bucket_counts = [0] * len(self._buckets)
            self._inf_count = 0
            self._sum = 0.0
            self._count = 0


# ---------------------------------------------------------------------------
# MetricsExporter
# ---------------------------------------------------------------------------

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

    Usage — push gateway:
        exporter = MetricsExporter(ExporterConfig())
        exporter.record_cycle(action_result)
        exporter.push("http://pushgateway:9091")
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

    # ------------------------------------------------------------------
    # Builtin initialization
    # ------------------------------------------------------------------

    def _init_builtin(self, p: str) -> None:
        """Initialize built-in metrics."""
        self._metrics: Dict[str, BuiltinMetric] = {}
        self._histograms: Dict[str, BuiltinHistogram] = {}

        # --- Controller state gauges ---
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

        # --- Per-input metric gauges ---
        self._metrics["input_metric"] = BuiltinMetric(
            f"{p}_input_metric_value",
            "Raw input metric value by name",
            "gauge",
        )

        # --- Counters ---
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
        self._metrics["divergences_total"] = BuiltinMetric(
            f"{p}_divergences_total",
            "Divergences between controller and HPA by type",
            "counter",
        )
        self._metrics["pipeline_errors_total"] = BuiltinMetric(
            f"{p}_pipeline_errors_total",
            "Pipeline polling failures",
            "counter",
        )

        # --- Safety / cooldown ---
        self._metrics["safety_clamped_total"] = BuiltinMetric(
            f"{p}_safety_clamped_total",
            "Times safety bounds clamped a proposed delta",
            "counter",
        )
        self._metrics["cooldown_active"] = BuiltinMetric(
            f"{p}_cooldown_active",
            "Whether cooldown is currently active (0 or 1)",
            "gauge",
        )
        self._metrics["cooldown_remaining_seconds"] = BuiltinMetric(
            f"{p}_cooldown_remaining_seconds",
            "Seconds remaining in cooldown period",
            "gauge",
        )

        # --- Approval state ---
        self._metrics["approvals_by_state"] = BuiltinMetric(
            f"{p}_approvals_by_state",
            "Current approval counts by state",
            "gauge",
        )

        # --- Timing ---
        self._metrics["cycle_duration_seconds"] = BuiltinMetric(
            f"{p}_cycle_duration_seconds",
            "Time to complete one control cycle",
            "gauge",
        )

        # --- Replica state ---
        self._metrics["current_replicas"] = BuiltinMetric(
            f"{p}_current_replicas", "Current replica count", "gauge",
        )
        self._metrics["target_replicas"] = BuiltinMetric(
            f"{p}_target_replicas", "Target replica count after decision", "gauge",
        )

        # --- Histograms ---
        self._histograms["action_score_distribution"] = BuiltinHistogram(
            f"{p}_action_score_distribution",
            "Distribution of action scores across cycles",
            buckets=(0.0, 0.05, 0.1, 0.2, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0),
        )
        self._histograms["cycle_duration_histogram"] = BuiltinHistogram(
            f"{p}_cycle_duration_histogram_seconds",
            "Distribution of control cycle durations",
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        )

    # ------------------------------------------------------------------
    # prometheus_client initialization
    # ------------------------------------------------------------------

    def _init_prom_client(self, p: str) -> None:
        """Initialize prometheus_client metrics."""
        reg = self._registry

        # Controller state
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

        # Per-input metric gauges
        self._pc_input_metric = Gauge(
            f"{p}_input_metric_value", "Raw input metric value by name",
            ["metric_name"], registry=reg,
        )

        # Counters
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
        self._pc_divergences = Counter(
            f"{p}_divergences_total",
            "Divergences between controller and HPA by type",
            ["divergence_type"], registry=reg,
        )
        self._pc_pipeline_errors = Counter(
            f"{p}_pipeline_errors_total", "Pipeline polling failures", registry=reg,
        )
        self._pc_safety_clamped = Counter(
            f"{p}_safety_clamped_total",
            "Times safety bounds clamped a proposed delta", registry=reg,
        )

        # Safety / cooldown gauges
        self._pc_cooldown_active = Gauge(
            f"{p}_cooldown_active",
            "Whether cooldown is currently active (0 or 1)", registry=reg,
        )
        self._pc_cooldown_remaining = Gauge(
            f"{p}_cooldown_remaining_seconds",
            "Seconds remaining in cooldown period", registry=reg,
        )

        # Approval state
        self._pc_approvals = Gauge(
            f"{p}_approvals_by_state", "Current approval counts by state",
            ["state"], registry=reg,
        )

        # Timing / histograms
        self._pc_cycle_duration = Histogram(
            f"{p}_cycle_duration_seconds",
            "Time to complete one control cycle",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=reg,
        )
        self._pc_action_score_dist = Histogram(
            f"{p}_action_score_distribution",
            "Distribution of action scores across cycles",
            buckets=[0.0, 0.05, 0.1, 0.2, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0],
            registry=reg,
        )

        # Replica state
        self._pc_current_replicas = Gauge(
            f"{p}_current_replicas", "Current replica count", registry=reg,
        )
        self._pc_target_replicas = Gauge(
            f"{p}_target_replicas", "Target replica count after decision", registry=reg,
        )

    # ------------------------------------------------------------------
    # Recording methods
    # ------------------------------------------------------------------

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

        # Per-input metric gauges
        for metric_name, value in action.metrics_snapshot.items():
            m["input_metric"].set(value, labels={"metric_name": metric_name})

        # Histograms
        self._histograms["action_score_distribution"].observe(
            abs(action.action_score),
        )
        if duration > 0:
            self._histograms["cycle_duration_histogram"].observe(duration)

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
        self._pc_action_score_dist.observe(abs(action.action_score))
        if current_replicas > 0:
            self._pc_current_replicas.set(current_replicas)
            self._pc_target_replicas.set(current_replicas + action.replica_delta)

        # Per-input metric gauges
        for metric_name, value in action.metrics_snapshot.items():
            self._pc_input_metric.labels(metric_name=metric_name).set(value)

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

    def record_safety(self, safety_result) -> None:
        """Record safety bounds state from a SafetyResult.

        Args:
            safety_result: A SafetyResult with was_clamped, in_cooldown,
                          cooldown_remaining fields.
        """
        if self._mode == ExporterMode.DISABLED:
            return

        if self._mode == ExporterMode.BUILTIN:
            m = self._metrics
            if safety_result.was_clamped:
                m["safety_clamped_total"].inc()
            m["cooldown_active"].set(1.0 if safety_result.in_cooldown else 0.0)
            m["cooldown_remaining_seconds"].set(safety_result.cooldown_remaining)
        else:
            if safety_result.was_clamped:
                self._pc_safety_clamped.inc()
            self._pc_cooldown_active.set(1.0 if safety_result.in_cooldown else 0.0)
            self._pc_cooldown_remaining.set(safety_result.cooldown_remaining)

    def record_divergence(self, divergence_type: str) -> None:
        """Record a divergence event between controller and HPA.

        Args:
            divergence_type: The DivergenceType value string.
        """
        if self._mode == ExporterMode.DISABLED:
            return
        if self._mode == ExporterMode.BUILTIN:
            self._metrics["divergences_total"].inc(
                labels={"divergence_type": divergence_type},
            )
        else:
            self._pc_divergences.labels(divergence_type=divergence_type).inc()

    def record_pipeline_error(self) -> None:
        """Record a pipeline polling failure."""
        if self._mode == ExporterMode.DISABLED:
            return
        if self._mode == ExporterMode.BUILTIN:
            self._metrics["pipeline_errors_total"].inc()
        else:
            self._pc_pipeline_errors.inc()

    def record_approval_state(self, state: str, count: int) -> None:
        """Record current approval counts by state.

        Args:
            state: Approval state ("pending", "approved", "dismissed", "expired").
            count: Current count for that state.
        """
        if self._mode == ExporterMode.DISABLED:
            return
        if self._mode == ExporterMode.BUILTIN:
            self._metrics["approvals_by_state"].set(
                float(count), labels={"state": state},
            )
        else:
            self._pc_approvals.labels(state=state).set(float(count))

    # ------------------------------------------------------------------
    # Exposition
    # ------------------------------------------------------------------

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
        for histogram in self._histograms.values():
            sections.append(histogram.expose())
        return "\n\n".join(sections) + "\n"

    # ------------------------------------------------------------------
    # Push gateway
    # ------------------------------------------------------------------

    def push(self, gateway_url: str = "", job: str = "") -> bool:
        """Push metrics to a Prometheus Pushgateway.

        Uses prometheus_client.push_to_gateway if available, otherwise
        falls back to urllib POST of text exposition.

        Args:
            gateway_url: Pushgateway URL (e.g. "http://pushgateway:9091").
                        Defaults to config.push_gateway_url.
            job: Job label. Defaults to config.push_gateway_job.

        Returns:
            True if push succeeded, False on failure.
        """
        if self._mode == ExporterMode.DISABLED:
            return False

        url = gateway_url or self.config.push_gateway_url
        job_name = job or self.config.push_gateway_job
        if not url:
            logger.warning("Push gateway URL not configured")
            return False

        # Try prometheus_client push_to_gateway first
        if self._mode == ExporterMode.PROM_CLIENT and PROM_CLIENT_AVAILABLE:
            try:
                from prometheus_client import push_to_gateway
                push_to_gateway(url, job_name, self._registry)
                logger.debug("Pushed metrics via prometheus_client to %s", url)
                return True
            except Exception as e:
                logger.warning("prometheus_client push failed: %s", e)
                return False

        # Fallback: urllib POST of text exposition
        try:
            import urllib.request
            import urllib.error

            text = self.expose()
            push_url = f"{url.rstrip('/')}/metrics/job/{job_name}"
            data = text.encode("utf-8")

            req = urllib.request.Request(
                push_url,
                data=data,
                headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status < 300:
                    logger.debug("Pushed metrics to %s (status %d)", push_url, resp.status)
                    return True
                logger.warning("Push gateway returned %d", resp.status)
                return False
        except Exception as e:
            logger.warning("Push gateway request failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def mode(self) -> ExporterMode:
        return self._mode

    def reset(self) -> None:
        """Reset all metrics to zero."""
        if self._mode == ExporterMode.BUILTIN:
            for metric in self._metrics.values():
                metric.reset()
            for histogram in self._histograms.values():
                histogram.reset()
