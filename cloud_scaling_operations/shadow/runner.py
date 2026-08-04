"""Shadow Runner — orchestrates shadow mode operation.

Wires together:
    SignalPipeline → HPAWatcher → DivergenceTracker → ShadowReporter

Runs as a polling loop. Each cycle:
1. Pipeline polls Prometheus, normalizes, runs controller
2. HPA watcher polls current/desired replicas
3. Divergence tracker compares decisions
4. Pending verdicts are evaluated after lookback window
5. Results are logged and accumulated for reporting

Purely observational — zero write permissions needed.
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ugence_cloud_scaling_controller.controller import Controller
from ugence_cloud_scaling_controller.signals.pipeline import (
    SignalPipeline,
    PipelineConfig,
    CycleResult,
)
from ugence_cloud_scaling_controller.signals.prometheus import PrometheusClient
from ugence_cloud_scaling_controller.shadow.hpa_watcher import HPAWatcher, HPASnapshot
from ugence_cloud_scaling_controller.shadow.divergence import (
    DivergenceTracker,
    DivergenceConfig,
    DivergenceRecord,
)
from ugence_cloud_scaling_controller.shadow.reporter import ShadowReporter, ShadowReport
from cloud_scaling_operations.recommend.engine import (
    RecommendEngine,
    RecommendConfig,
    RecommendCycleResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ShadowConfig:
    """Configuration for shadow mode operation."""
    # Pipeline configuration (includes Prometheus, normalizer, controller settings)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    # Divergence tracking
    divergence: DivergenceConfig = field(default_factory=DivergenceConfig)
    # Recommend engine (None = disabled)
    recommend: Optional[RecommendConfig] = None
    # How often to log a periodic status summary (in cycles, 0 = never)
    status_interval_cycles: int = 100


@dataclass
class ShadowCycleResult:
    """Result of one shadow mode cycle."""
    cycle: CycleResult
    hpa: Optional[HPASnapshot]
    divergence: Optional[DivergenceRecord]
    newly_evaluated: List[DivergenceRecord]
    recommend: Optional[RecommendCycleResult] = None


class ShadowRunner:
    """Runs the controller in shadow mode alongside HPA.

    Usage — continuous:
        runner = ShadowRunner(ShadowConfig())
        runner.run(callback=on_cycle)

    Usage — single shot (for testing):
        runner = ShadowRunner(ShadowConfig())
        result = runner.step()

    Usage — report generation:
        report = runner.generate_report(period_label="Week 13")
        print(report.format_report())
    """

    def __init__(
        self,
        config: Optional[ShadowConfig] = None,
        controller: Optional[Controller] = None,
    ):
        self.config = config or ShadowConfig()
        self.pipeline = SignalPipeline(self.config.pipeline, controller=controller)
        self.hpa_watcher = HPAWatcher(
            prometheus=self.pipeline.prometheus,
            namespace=self.config.pipeline.namespace,
            deployment=self.config.pipeline.deployment,
        )
        self.divergence_tracker = DivergenceTracker(self.config.divergence)
        self.reporter = ShadowReporter()
        self.recommend_engine: Optional[RecommendEngine] = None
        if self.config.recommend is not None:
            self.recommend_engine = RecommendEngine(self.config.recommend)
        self._cycle_count = 0
        self._failed_cycles = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._counter_lock = threading.Lock()

    def step(self) -> Optional[ShadowCycleResult]:
        """Execute one shadow mode cycle.

        Returns:
            ShadowCycleResult, or None if pipeline poll failed.
        """
        # 1. Run pipeline (Prometheus → normalize → controller)
        cycle = self.pipeline.poll_once()
        if cycle is None:
            with self._counter_lock:
                self._failed_cycles += 1
                failed = self._failed_cycles
            logger.warning("Pipeline poll failed (total failures: %d)", failed)
            return None

        with self._counter_lock:
            self._cycle_count += 1
            cycle_num = self._cycle_count

        # 2. Poll HPA state
        hpa = self.hpa_watcher.poll()
        if hpa is None:
            logger.debug("HPA state unavailable this cycle")

        # 3. Compare if we have both controller result and HPA state
        divergence = None
        if hpa is not None:
            divergence = self.divergence_tracker.compare(
                action=cycle.action,
                hpa=hpa,
                metrics=cycle.normalized_metrics,
            )

        # 4. Evaluate pending verdicts
        newly_evaluated = self.divergence_tracker.evaluate_pending(
            current_metrics=cycle.normalized_metrics,
        )

        # 5. Run recommend engine if configured
        recommend_result = None
        if self.recommend_engine is not None:
            recommend_result = self.recommend_engine.evaluate(
                action=cycle.action,
                current_replicas=cycle.current_replicas,
            )

        # 6. Periodic status log
        if (
            self.config.status_interval_cycles > 0
            and cycle_num % self.config.status_interval_cycles == 0
        ):
            self._log_status()

        return ShadowCycleResult(
            cycle=cycle,
            hpa=hpa,
            divergence=divergence,
            newly_evaluated=newly_evaluated,
            recommend=recommend_result,
        )

    def run(
        self,
        callback: Optional[Callable[[ShadowCycleResult], None]] = None,
        max_cycles: Optional[int] = None,
    ) -> None:
        """Run the shadow mode polling loop.

        Args:
            callback: Called with each ShadowCycleResult.
            max_cycles: Stop after N cycles (None = run forever).
        """
        self._running = True
        cycle = 0

        while self._running:
            if max_cycles is not None and cycle >= max_cycles:
                break

            try:
                result = self.step()
                if result is not None and callback is not None:
                    callback(result)
            except Exception:
                logger.exception("Shadow mode cycle error")

            cycle += 1

            if self._running and (max_cycles is None or cycle < max_cycles):
                time.sleep(self.config.pipeline.poll_interval)

        self._running = False

    def run_async(
        self,
        callback: Optional[Callable[[ShadowCycleResult], None]] = None,
        max_cycles: Optional[int] = None,
    ) -> threading.Thread:
        """Run shadow mode in a background thread.

        Raises RuntimeError if already running.
        """
        if self._running or (self._thread is not None and self._thread.is_alive()):
            raise RuntimeError("ShadowRunner is already running")
        self._thread = threading.Thread(
            target=self.run,
            args=(callback, max_cycles),
            daemon=True,
        )
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        """Stop the shadow mode loop."""
        self._running = False
        thread = self._thread
        if thread is not None:
            # Generous timeout: poll interval + Prometheus query timeout + buffer
            timeout = self.config.pipeline.poll_interval + 15
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning("Shadow runner thread did not stop within %.0fs timeout", timeout)

    def generate_report(
        self,
        period_label: str = "",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> ShadowReport:
        """Generate a summary report from accumulated divergence records.

        Args:
            period_label: Human-readable period label.
            start_time: Filter start (defaults to all records).
            end_time: Filter end (defaults to all records).
        """
        records = self.divergence_tracker.records
        if start_time is not None or end_time is not None:
            return self.reporter.generate_for_period(
                records,
                start_time=start_time or 0,
                end_time=end_time or time.time(),
                period_label=period_label,
            )
        return self.reporter.generate(records, period_label)

    def format_divergence_log(self) -> str:
        """Format all divergences as a readable log."""
        divs = self.divergence_tracker.divergences
        if not divs:
            return "No divergences recorded."
        return "\n\n".join(d.format_log() for d in divs)

    def _log_status(self) -> None:
        """Log periodic status summary."""
        tracker = self.divergence_tracker
        total = len(tracker.records)
        divs = len(tracker.divergences)
        pending = tracker.pending_count
        hpa_actions = self.hpa_watcher.total_actions

        logger.info(
            "Shadow status: cycle=%d failed=%d total_records=%d divergences=%d "
            "pending=%d hpa_actions=%d",
            self._cycle_count, self._failed_cycles, total, divs, pending, hpa_actions,
        )

    @property
    def cycle_count(self) -> int:
        with self._counter_lock:
            return self._cycle_count

    @property
    def failed_cycles(self) -> int:
        with self._counter_lock:
            return self._failed_cycles

    def reset(self) -> None:
        """Reset all internal state."""
        self.pipeline.controller.reset()
        self.pipeline.normalizer.reset()
        self.hpa_watcher.reset()
        self.divergence_tracker.reset()
        if self.recommend_engine is not None:
            self.recommend_engine.reset()
        with self._counter_lock:
            self._cycle_count = 0
            self._failed_cycles = 0

    def close(self) -> None:
        """Stop and clean up.

        Waits for the background thread to finish before closing the
        pipeline to avoid racing with an in-flight polling cycle.
        """
        self.stop()
        # Only close pipeline resources after thread has stopped
        self.pipeline.prometheus.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
