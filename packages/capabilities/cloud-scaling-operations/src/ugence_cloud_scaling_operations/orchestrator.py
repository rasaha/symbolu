"""Production Orchestrator — full L0→L7 lifecycle runner.

Integrates all 8 layers into a single polling loop for production deployment:

    L0  Metrics Ingestion     → Prometheus polling
    L1  Signal Processing     → Normalizer (z-score + sigmoid)
    L2  State Estimation      → Coherence, Identity, Plasticity, Gain, Damping
    L3  Scaling Logic         → Controller (A_t = d_t * G_t * P_t * S_t)
    L4  Decision Quality      → Confidence scoring, Safety bounds, Approval
    L5  Execution             → K8s actuator, Policy engine, Rollback monitor
    L6  Observability         → Decision log, Metrics exporter, Explainer
    L7  Learning/Adaptation   → Feedback loop, Replay buffer, Outcome tracker

Each cycle:
    1. Poll Prometheus for raw metrics                          (L0)
    2. Normalize signals to [0, 1]                              (L1)
    3. Run controller: coherence, identity, plasticity, gain    (L2+L3)
    4. Evaluate confidence, check safety bounds                 (L4)
    5. Check rollbacks, evaluate outcomes, run feedback          (L5+L7)
    6. Log decision, export metrics, generate explanation        (L6)

The orchestrator is the production counterpart to ShadowRunner:
  - ShadowRunner: observe-only, compares controller vs HPA
  - Orchestrator: full lifecycle, creates recommendations, executes on approval

Human approval is still required for execution by default. Set
auto_approve_threshold to enable autonomous scaling at high confidence.
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ugence_cloud_scaling_controller.controller import Controller, ActionResult
from ugence_cloud_scaling_controller.config import InfraControllerConfig
from ugence_cloud_scaling_controller.signals.pipeline import (
    SignalPipeline,
    PipelineConfig,
    CycleResult,
)
from ugence_cloud_scaling_operations.recommend.engine import (
    RecommendEngine,
    RecommendConfig,
    RecommendCycleResult,
)
from ugence_cloud_scaling_operations.recommend.approval import Recommendation
from ugence_cloud_scaling_controller.explain.explainer import (
    Explainer,
    Explanation,
    Audience,
)
from ugence_cloud_scaling_operations.observability.exporter import (
    MetricsExporter,
    ExporterConfig,
)
from ugence_cloud_scaling_controller.observability.decision_log import (
    DecisionLogFormatter,
    DecisionLogEntry,
)
from ugence_cloud_scaling_operations.observability.metrics_server import (
    MetricsServer,
    MetricsServerConfig,
)
from ugence_cloud_scaling_operations.observability.otel_exporter import (
    OtelExporter,
    OtelExporterConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the production orchestrator."""
    # Sub-system configs
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    recommend: RecommendConfig = field(default_factory=RecommendConfig)
    exporter: ExporterConfig = field(default_factory=ExporterConfig)
    # OpenTelemetry exporter (None = disabled)
    otel: Optional[OtelExporterConfig] = None
    # HTTP metrics server (None = disabled)
    metrics_server: Optional[MetricsServerConfig] = None

    # Auto-approval: if set, recommendations at or above this confidence
    # level are automatically approved without human intervention.
    # Valid values: None (disabled), "low", "medium", "high"
    auto_approve_threshold: Optional[str] = None

    # Status logging interval (in cycles, 0 = disabled)
    status_interval_cycles: int = 100

    # Whether to bootstrap from historical data on startup
    bootstrap_on_start: bool = True


# Confidence level ordering for auto-approve comparison
_CONFIDENCE_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


@dataclass
class OrchestrationCycleResult:
    """Result of one full orchestration cycle (L0→L7)."""
    timestamp: float
    cycle_number: int
    cycle_duration: float

    # L0-L3: Pipeline result
    pipeline: Optional[CycleResult] = None

    # L4: Recommendation result
    recommend: Optional[RecommendCycleResult] = None

    # L5: Execution (if auto-approved)
    auto_approved: bool = False
    approved_recommendation: Optional[Recommendation] = None

    # L5+L7: Rollback verdicts, outcome verdicts, feedback result
    rollback_verdicts: List = field(default_factory=list)
    outcome_verdicts: List = field(default_factory=list)
    feedback_result: Optional[dict] = None

    # L6: Observability
    explanation: Optional[Explanation] = None
    decision_log: Optional[DecisionLogEntry] = None

    @property
    def success(self) -> bool:
        return self.pipeline is not None


class ProductionOrchestrator:
    """Full L0→L7 production orchestration loop.

    Usage — single shot:
        orch = ProductionOrchestrator(OrchestratorConfig())
        result = orch.step()
        print(result.explanation.format_text())

    Usage — continuous:
        orch = ProductionOrchestrator(OrchestratorConfig())
        orch.run(callback=on_cycle, max_cycles=1000)

    Usage — auto-approve high-confidence:
        config = OrchestratorConfig(auto_approve_threshold="high")
        orch = ProductionOrchestrator(config)
        orch.run()  # Automatically executes high-confidence recommendations
    """

    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        controller: Optional[Controller] = None,
    ):
        self.config = config or OrchestratorConfig()

        # L0-L3: Signal pipeline (Prometheus → Normalizer → Controller)
        self.pipeline = SignalPipeline(self.config.pipeline, controller=controller)
        self.controller = self.pipeline.controller

        # L4-L5: Recommend + Execute
        self.recommend_engine = RecommendEngine(self.config.recommend)

        # HARD AUTHORITY GUARD: the recommendation engine must never mint its own
        # execution authority. Auto-approval may only ever drive a non-mutating
        # (dry-run) actuator. A live actuator combined with auto-approval is refused at
        # construction. Authorized live mutation must go through the supported
        # ControlledScalingExecutor path, which requires an external ExecutionAuthorization.
        if self.config.auto_approve_threshold is not None:
            actuator = getattr(self.recommend_engine, "actuator", None)
            if actuator is not None:
                from ugence_cloud_scaling_operations.action.k8s_actuator import ActuatorMode
                if getattr(actuator.config, "mode", None) != ActuatorMode.DRY_RUN:
                    raise RuntimeError(
                        "auto_approve_threshold may not drive a live actuator: an "
                        "auto-approved recommendation cannot authorize its own mutation. "
                        "Use ControlledScalingExecutor with an external "
                        "ExecutionAuthorization for live scaling, or set the actuator to "
                        "DRY_RUN for autonomous simulation."
                    )

        # L6: Observability
        self.explainer = Explainer()
        self.exporter = MetricsExporter(self.config.exporter)
        self.log_formatter = DecisionLogFormatter(
            service=self.config.recommend.service,
            namespace=self.config.recommend.namespace,
        )
        self.otel_exporter = (
            OtelExporter(self.config.otel) if self.config.otel else OtelExporter()
        )
        self.metrics_server: Optional[MetricsServer] = None
        if self.config.metrics_server is not None:
            self.metrics_server = MetricsServer(self.exporter, self.config.metrics_server)

        # State
        self._cycle_count = 0
        self._failed_cycles = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._bootstrapped = False

    def bootstrap(self) -> bool:
        """Bootstrap from historical Prometheus data.

        Pre-learns baselines for normalizer and controller so they
        produce accurate decisions from cycle 1.

        Returns:
            True if bootstrap succeeded.
        """
        success = self.pipeline.bootstrap()
        self._bootstrapped = success
        return success

    def step(self) -> OrchestrationCycleResult:
        """Execute one full L0→L7 orchestration cycle.

        Returns:
            OrchestrationCycleResult with all layer outputs.
        """
        start = time.time()

        with self._lock:
            self._cycle_count += 1
            cycle_num = self._cycle_count

        # === L0-L3: Pipeline (Prometheus → Normalize → Controller) ===
        pipeline_result = self.pipeline.poll_once()

        if pipeline_result is None:
            with self._lock:
                self._failed_cycles += 1
            duration = time.time() - start
            logger.warning("Orchestrator cycle %d: pipeline poll failed", cycle_num)
            self.exporter.record_pipeline_error()
            self.otel_exporter.record_pipeline_error()
            return OrchestrationCycleResult(
                timestamp=start,
                cycle_number=cycle_num,
                cycle_duration=duration,
            )

        action = pipeline_result.action

        # === L4: Confidence + Safety + Recommendation ===
        recommend_result = self.recommend_engine.evaluate(
            action=action,
            current_replicas=pipeline_result.current_replicas,
        )

        # === L4b: Safety metrics ===
        if recommend_result.safety is not None:
            self.exporter.record_safety(recommend_result.safety)

        # === L5+L7: Rollback checks, Outcome evaluation, Feedback ===
        rollback_verdicts = self.recommend_engine.check_rollbacks(
            pipeline_result.normalized_metrics,
        )
        outcome_verdicts = self.recommend_engine.evaluate_outcomes(
            pipeline_result.normalized_metrics,
        )
        feedback_result = self.recommend_engine.process_feedback(
            controller=self.controller,
            outcomes=outcome_verdicts if outcome_verdicts else None,
            rollbacks=rollback_verdicts if rollback_verdicts else None,
        )

        # === L5: Auto-approve if configured and threshold met ===
        auto_approved = False
        approved_rec = None
        if (
            self.config.auto_approve_threshold is not None
            and recommend_result.recommendation is not None
        ):
            rec = recommend_result.recommendation
            rec_confidence = rec.confidence.level.value
            threshold_rank = _CONFIDENCE_ORDER.get(
                self.config.auto_approve_threshold, 99,
            )
            rec_rank = _CONFIDENCE_ORDER.get(rec_confidence, 0)

            if rec_rank >= threshold_rank:
                approved_rec = self.recommend_engine.approve(
                    rec.id,
                    by="auto-approve",
                    reason=f"Confidence {rec_confidence} >= {self.config.auto_approve_threshold}",
                    metrics_snapshot=pipeline_result.normalized_metrics,
                )
                auto_approved = approved_rec is not None
                if auto_approved:
                    logger.info(
                        "Auto-approved %s: %s (%+d replicas)",
                        rec.id, rec_confidence, rec.clamped_delta,
                    )

        # === L6: Observability ===
        # Explanation
        explanation = self.explainer.explain(
            action,
            confidence_level=(
                recommend_result.confidence.level.value
                if recommend_result.confidence else ""
            ),
            safety_clamped=(
                recommend_result.safety.was_clamped
                if recommend_result.safety else False
            ),
            safety_reason=(
                recommend_result.safety.clamp_reason
                if recommend_result.safety else ""
            ),
            suppress_reason=recommend_result.suppress_reason,
        )

        # Decision log entry
        decision_log = self.log_formatter.from_cycle(
            action=action,
            confidence=recommend_result.confidence,
            safety=recommend_result.safety,
            current_replicas=pipeline_result.current_replicas,
            suppressed=recommend_result.suppressed,
            suppress_reason=recommend_result.suppress_reason,
        )

        # Metrics export
        duration = time.time() - start
        self.exporter.record_cycle(
            action,
            current_replicas=pipeline_result.current_replicas,
            cycle_duration=duration,
        )
        self.otel_exporter.record_cycle(
            action,
            current_replicas=pipeline_result.current_replicas,
            cycle_duration=duration,
        )

        # Export execution/rollback/feedback events
        if auto_approved and approved_rec is not None:
            exec_result = approved_rec.execution_result
            if exec_result is not None:
                self.exporter.record_execution(exec_result.success)
                self.otel_exporter.record_execution(exec_result.success)

        for rv in rollback_verdicts:
            if hasattr(rv, 'verdict') and rv.verdict.value in ("degraded", "rolled_back"):
                self.exporter.record_rollback()
                self.otel_exporter.record_rollback()

        if feedback_result and feedback_result.get("adjustments", 0) > 0:
            self.exporter.record_feedback(feedback_result["adjustments"])
            self.otel_exporter.record_feedback(feedback_result["adjustments"])

        # Periodic status
        if (
            self.config.status_interval_cycles > 0
            and cycle_num % self.config.status_interval_cycles == 0
        ):
            self._log_status(cycle_num, action)

        return OrchestrationCycleResult(
            timestamp=start,
            cycle_number=cycle_num,
            cycle_duration=duration,
            pipeline=pipeline_result,
            recommend=recommend_result,
            auto_approved=auto_approved,
            approved_recommendation=approved_rec,
            rollback_verdicts=rollback_verdicts,
            outcome_verdicts=outcome_verdicts,
            feedback_result=feedback_result,
            explanation=explanation,
            decision_log=decision_log,
        )

    def run(
        self,
        callback: Optional[Callable[["OrchestrationCycleResult"], None]] = None,
        max_cycles: Optional[int] = None,
    ) -> None:
        """Run the orchestration loop synchronously.

        Args:
            callback: Called after each cycle with the result.
            max_cycles: Stop after N cycles (None = run forever).
        """
        # Bootstrap on first run if configured
        if self.config.bootstrap_on_start and not self._bootstrapped:
            self.bootstrap()

        # Start HTTP metrics server if configured
        if self.metrics_server is not None and not self.metrics_server.is_running:
            self.metrics_server.start()

        self._running = True
        cycle = 0

        while self._running:
            if max_cycles is not None and cycle >= max_cycles:
                break

            try:
                result = self.step()
                if callback is not None:
                    callback(result)
            except Exception:
                logger.exception("Orchestrator cycle error")

            cycle += 1

            if self._running and (max_cycles is None or cycle < max_cycles):
                time.sleep(self.config.pipeline.poll_interval)

        self._running = False

    def run_async(
        self,
        callback: Optional[Callable[["OrchestrationCycleResult"], None]] = None,
        max_cycles: Optional[int] = None,
    ) -> threading.Thread:
        """Run orchestration in a background thread.

        Raises RuntimeError if already running.
        """
        if self._running or (self._thread is not None and self._thread.is_alive()):
            raise RuntimeError("Orchestrator is already running")
        self._thread = threading.Thread(
            target=self.run,
            args=(callback, max_cycles),
            daemon=True,
        )
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        """Signal the orchestration loop to stop."""
        self._running = False
        thread = self._thread
        if thread is not None:
            timeout = self.config.pipeline.poll_interval + 15
            thread.join(timeout=timeout)

    def approve(
        self,
        recommendation_id: str,
        by: str = "",
        reason: str = "",
    ) -> Optional[Recommendation]:
        """Approve a pending recommendation for execution.

        Delegates to the recommend engine's approve flow:
        Policy check → Actuator → Rollback watch → Outcome tracking.
        """
        return self.recommend_engine.approve(recommendation_id, by=by, reason=reason)

    def dismiss(
        self,
        recommendation_id: str,
        by: str = "",
        reason: str = "",
    ) -> Optional[Recommendation]:
        """Dismiss a pending recommendation."""
        return self.recommend_engine.dismiss(recommendation_id, by=by, reason=reason)

    def check_readiness(self) -> Optional[dict]:
        """Check system readiness for deployments (ArgoCD pre-hook).

        Returns readiness result dict, or None if not configured.
        """
        # Get latest plasticity and stability from the controller's last step
        # This requires running at least one cycle first
        controller = self.controller
        if controller._step == 0:
            return None

        # Use the plasticity gate's last result if available
        return self.recommend_engine.check_readiness(
            plasticity=0.5,   # Would need to cache from last cycle
            stability=0.5,
        )

    def get_metrics(self) -> str:
        """Get Prometheus text exposition for /metrics endpoint."""
        return self.exporter.expose()

    @property
    def cycle_count(self) -> int:
        with self._lock:
            return self._cycle_count

    @property
    def failed_cycles(self) -> int:
        with self._lock:
            return self._failed_cycles

    @property
    def pending_recommendations(self) -> List[Recommendation]:
        return self.recommend_engine.pending

    def _log_status(self, cycle_num: int, action: ActionResult) -> None:
        """Log periodic status summary."""
        pending = self.recommend_engine.pending_count
        logger.info(
            "Orchestrator status: cycle=%d failed=%d pending_recs=%d "
            "action=%s score=%.3f coherence=%.2f",
            cycle_num,
            self._failed_cycles,
            pending,
            action.recommendation,
            action.action_score,
            action.coherence.coherence,
        )

    def reset(self) -> None:
        """Reset all internal state."""
        self.controller.reset()
        self.pipeline.normalizer.reset()
        self.recommend_engine.reset()
        self.exporter.reset()
        # OTel exporter has no reset — counters are cumulative by design
        with self._lock:
            self._cycle_count = 0
            self._failed_cycles = 0
        self._bootstrapped = False

    def close(self) -> None:
        """Stop and release resources."""
        self.stop()
        self.pipeline.prometheus.close()
        self.otel_exporter.shutdown()
        if self.metrics_server is not None and self.metrics_server.is_running:
            self.metrics_server.stop()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
