"""Signal Pipeline — Prometheus to Controller bridge.

Wires together:
    Prometheus → Normalizer → Controller.step()

Runs as a polling loop or single-shot for testing.
Produces structured decision logs for each cycle.
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from cloud_controller.controller import Controller, ActionResult
from cloud_controller.config import (
    InfraControllerConfig,
    INFRA_KEYS,
    APP_KEYS,
    BUSINESS_KEYS,
)
from cloud_controller.signals.prometheus import (
    PrometheusClient,
    PrometheusConfig,
    DEFAULT_QUERIES,
    K8S_QUERIES,
)
from cloud_controller.signals.normalizer import (
    SignalNormalizer,
    NormalizerConfig,
    NormalizationResult,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the signal pipeline."""
    # Prometheus connection
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)
    # Normalizer settings
    normalizer: NormalizerConfig = field(default_factory=NormalizerConfig)
    # Controller settings
    controller: InfraControllerConfig = field(default_factory=InfraControllerConfig)
    # Polling interval in seconds
    poll_interval: float = 15.0
    # K8s namespace and deployment to monitor (None = cluster-wide)
    namespace: Optional[str] = None
    deployment: Optional[str] = None
    # Phase schedule: hour → phase name. Hours not listed default to "normal".
    phase_schedule: Dict[int, str] = field(default_factory=lambda: {
        # Example: peak 9-17, off_peak 22-6
        9: "peak", 10: "peak", 11: "peak", 12: "peak",
        13: "peak", 14: "peak", 15: "peak", 16: "peak", 17: "peak",
        22: "off_peak", 23: "off_peak", 0: "off_peak",
        1: "off_peak", 2: "off_peak", 3: "off_peak",
        4: "off_peak", 5: "off_peak", 6: "off_peak",
    })
    # Bootstrap: seconds of historical data to fetch on startup (0 = disabled)
    bootstrap_window_seconds: int = 3600  # Default: 1 hour of history
    # Bootstrap query resolution step
    bootstrap_step: str = "15s"


@dataclass
class CycleResult:
    """Result of one pipeline polling cycle."""
    timestamp: float
    raw_metrics: Dict[str, Optional[float]]
    normalized_metrics: Dict[str, float]
    normalization_details: Dict[str, NormalizationResult]
    k8s_state: Dict[str, Optional[float]]
    action: ActionResult
    phase: str
    current_replicas: int
    deploy_active: bool
    pod_restarts: int


class SignalPipeline:
    """Polls Prometheus, normalizes signals, feeds controller, logs decisions.

    Usage — single shot:
        pipeline = SignalPipeline(PipelineConfig())
        result = pipeline.poll_once()
        print(result.action.explain())

    Usage — continuous polling:
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.run(callback=lambda r: print(r.action.explain()))
    """

    # Expected metric keys that the controller uses for pressure/coherence
    EXPECTED_KEYS = set(INFRA_KEYS + APP_KEYS + BUSINESS_KEYS)

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        controller: Optional[Controller] = None,
    ):
        self.config = config or PipelineConfig()
        self.prometheus = PrometheusClient(self.config.prometheus)
        self.normalizer = SignalNormalizer(
            config=self.config.normalizer,
        )
        self.controller = controller or Controller(self.config.controller)
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def bootstrap(self) -> bool:
        """Fetch historical data from Prometheus and pre-learn all baselines.

        Queries the last `bootstrap_window_seconds` of metric history, then
        replays it through the normalizer and controller so both are calibrated
        from cycle 1. This eliminates the learning phase.

        Returns:
            True if bootstrap succeeded (enough historical data), False otherwise.
        """
        window = self.config.bootstrap_window_seconds
        if window <= 0:
            logger.info("Bootstrap disabled (bootstrap_window_seconds=0)")
            return False

        now = time.time()
        start = now - window

        logger.info(
            "Bootstrapping from %d seconds of history (step=%s)...",
            window,
            self.config.bootstrap_step,
        )

        # 1. Fetch historical time series for each metric
        historical_metrics: Dict[str, list] = {}
        timestamps: Optional[list] = None

        for name, promql, _ in DEFAULT_QUERIES:
            series = self.prometheus.range_query(
                promql,
                start=start,
                end=now,
                step=self.config.bootstrap_step,
            )
            if series:
                if timestamps is None:
                    timestamps = [ts for ts, _ in series]
                historical_metrics[name] = [v for _, v in series]
                logger.debug(
                    "Bootstrap: %s — %d samples", name, len(series),
                )
            else:
                logger.warning("Bootstrap: no data for %s", name)

        if not historical_metrics:
            logger.warning("Bootstrap failed — no historical data available")
            return False

        # 2. Pre-seed the normalizer's rolling windows
        self.normalizer.bootstrap(historical_metrics, timestamps)

        # 3. Build normalized snapshots for the controller
        #    Re-normalize each historical timestep through the (now pre-seeded) normalizer
        n_samples = min(len(v) for v in historical_metrics.values())
        normalized_snapshots = []
        for i in range(n_samples):
            raw = {}
            for name, values in historical_metrics.items():
                if i < len(values):
                    raw[name] = values[i]
            ts = timestamps[i] if timestamps and i < len(timestamps) else now
            normalized = self.normalizer.normalize(raw, timestamp=ts)
            if normalized:
                normalized_snapshots.append(normalized)

        # 4. Bootstrap the controller with normalized snapshots
        self.controller.bootstrap(normalized_snapshots)

        logger.info(
            "Bootstrap complete: %d metrics, %d samples, controller ready",
            len(historical_metrics),
            len(normalized_snapshots),
        )
        return True

    def poll_once(self) -> Optional[CycleResult]:
        """Execute one complete polling cycle.

        Fetches metrics from Prometheus, normalizes them, runs the
        controller, and returns the full result.

        Returns:
            CycleResult with all intermediate and final data, or None on failure.
        """
        now = time.time()

        # 1. Query Prometheus for metrics
        raw_metrics = self.prometheus.query_metrics()

        # Log which metrics failed individually
        failed = {k for k, v in raw_metrics.items() if v is None}
        if failed:
            logger.warning("Metrics failed to query: %s", failed)

        # Filter out failed queries (None values)
        valid_raw = {k: v for k, v in raw_metrics.items() if v is not None}
        if not valid_raw:
            logger.warning("No valid metrics from Prometheus — skipping cycle")
            return None

        # 2. Query K8s state
        k8s_state = self.prometheus.query_k8s_state(
            namespace=self.config.namespace,
            deployment=self.config.deployment,
        )

        # Extract K8s context for controller (safe conversion)
        current_replicas = self._safe_int(k8s_state.get("current_replicas"), default=1)
        desired_replicas = k8s_state.get("desired_replicas")
        pod_restarts = self._safe_int(k8s_state.get("pod_restarts"), default=0)
        # Deploy is active if desired != current (HPA is actively scaling)
        deploy_active = (
            desired_replicas is not None
            and current_replicas != self._safe_int(desired_replicas, default=current_replicas)
        )

        # 3. Normalize metrics
        normalization_details = self.normalizer.normalize_detailed(valid_raw, timestamp=now)
        normalized = {name: r.normalized for name, r in normalization_details.items()}

        # 3b. Warn if expected controller metrics are missing
        missing = self.EXPECTED_KEYS - set(normalized.keys())
        if missing:
            logger.warning("Missing expected metrics after normalization: %s", missing)

        # 4. Determine time phase
        phase = self._get_phase()

        # 5. Run controller
        action = self.controller.step(
            metrics=normalized,
            current_replicas=current_replicas,
            deploy_active=deploy_active,
            phase=phase,
            recent_pod_restarts=pod_restarts,
        )

        result = CycleResult(
            timestamp=now,
            raw_metrics=raw_metrics,
            normalized_metrics=normalized,
            normalization_details=normalization_details,
            k8s_state=k8s_state,
            action=action,
            phase=phase,
            current_replicas=current_replicas,
            deploy_active=deploy_active,
            pod_restarts=pod_restarts,
        )

        logger.info(
            "Cycle %d: pressure=%.2f coherence=%.2f action=%s (%+d replicas)",
            action.step,
            action.pressure,
            action.coherence.coherence,
            action.recommendation,
            action.replica_delta,
        )

        return result

    def run(
        self,
        callback: Optional[Callable[[CycleResult], None]] = None,
        max_cycles: Optional[int] = None,
    ) -> None:
        """Run the polling loop synchronously.

        Args:
            callback: Called with each CycleResult. Use for logging, alerting, etc.
            max_cycles: Stop after this many cycles (None = run forever).
        """
        self._running = True
        cycle = 0

        while self._running:
            if max_cycles is not None and cycle >= max_cycles:
                break

            try:
                result = self.poll_once()
                if result is not None and callback is not None:
                    callback(result)
            except Exception:
                logger.exception("Pipeline cycle error")

            cycle += 1

            if self._running and (max_cycles is None or cycle < max_cycles):
                time.sleep(self.config.poll_interval)

        self._running = False

    def run_async(
        self,
        callback: Optional[Callable[[CycleResult], None]] = None,
        max_cycles: Optional[int] = None,
    ) -> threading.Thread:
        """Run the polling loop in a background thread.

        Raises RuntimeError if already running.

        Returns:
            The background thread (already started).
        """
        if self._running or (self._thread is not None and self._thread.is_alive()):
            raise RuntimeError("SignalPipeline is already running")
        self._thread = threading.Thread(
            target=self.run,
            args=(callback, max_cycles),
            daemon=True,
        )
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False
        thread = self._thread
        if thread is not None:
            # Generous timeout: poll interval + Prometheus query timeout + buffer
            timeout = self.config.poll_interval + 15
            thread.join(timeout=timeout)

    # Valid phase values that the controller/adaptive gain understand
    _VALID_PHASES = {"peak", "normal", "off_peak", "maintenance"}

    @staticmethod
    def _safe_int(value, default: int = 1) -> int:
        """Safely convert a value to int, returning default on failure."""
        if value is None:
            return default
        try:
            return int(round(float(value)))
        except (ValueError, TypeError):
            logger.warning("Could not convert to int: %s, using default %d", value, default)
            return default

    def _get_phase(self) -> str:
        """Determine current time phase from schedule."""
        hour = time.localtime().tm_hour
        phase = self.config.phase_schedule.get(hour, "normal")
        if phase not in self._VALID_PHASES:
            logger.warning("Unknown phase '%s' in schedule, using 'normal'", phase)
            return "normal"
        return phase

    def format_cycle_log(self, result: CycleResult) -> str:
        """Format a cycle result as a human-readable log entry."""
        ts = time.strftime("%H:%M:%S", time.localtime(result.timestamp))

        # Signal summary
        signals = " ".join(
            f"{k}={v:.2f}" for k, v in sorted(result.normalized_metrics.items())
        )

        # Normalization detail for z-score metrics
        zscore_details = []
        for name, detail in sorted(result.normalization_details.items()):
            if detail.method == "zscore" and detail.z_score is not None:
                zscore_details.append(f"{name}: z={detail.z_score:+.2f}")

        lines = [
            f"[{ts}] X_t=[{signals}]",
            f"[{ts}] Coherence={result.action.coherence.coherence:.2f}, "
            f"Resistance={result.action.plasticity.resistance:.2f}, "
            f"Misalignment={result.action.plasticity.misalignment:.2f}",
            f"[{ts}] P_t={result.action.plasticity.plasticity:.2f}, "
            f"G_t={result.action.gain.gain:.2f}, "
            f"d_t={result.action.damping.damping:.2f} "
            f"-> A_t={result.action.action_score:.2f} "
            f"-> {result.action.recommendation.upper().replace('_', ' ')}",
        ]

        if zscore_details:
            lines.append(f"[{ts}] Z-scores: {', '.join(zscore_details)}")

        return "\n".join(lines)

    def close(self) -> None:
        """Stop polling and close connections.

        Waits for the background thread to finish before closing
        Prometheus to avoid racing with an in-flight cycle.
        """
        self.stop()
        # Only close after thread has stopped
        self.prometheus.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
