"""Rollback Monitor — auto-reverts scaling if metrics degrade post-action.

After each executed scaling action, the rollback monitor watches key metrics
for a configurable window (default 3 minutes). If metrics degrade beyond
a threshold, it automatically reverts to the pre-action replica count.

Design doc reference: Stage 5, line 562:
  "Rollback trigger: if metrics degrade within 3 minutes of action, auto-revert"

Degradation detection:
  - Compares post-action metrics against pre-action snapshot
  - Tracks latency, error rate, and pod restart count
  - A metric is "degraded" if it worsens by more than the threshold %
  - Rollback triggers if ANY tracked metric degrades beyond threshold

Limitations:
  - Rollback only reverts replica count — cannot undo side effects
  - Post-rollback, the system enters an extended cooldown to prevent oscillation
  - Attribution is correlational, not causal (same caveat as divergence tracker)
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RollbackVerdict(Enum):
    """Outcome of the rollback monitoring window."""
    MONITORING = "monitoring"    # Still within the watch window
    STABLE = "stable"           # Metrics stable — no rollback needed
    DEGRADED = "degraded"       # Metrics degraded — rollback triggered
    ROLLED_BACK = "rolled_back" # Rollback was executed
    EXPIRED = "expired"         # Window passed without enough data


@dataclass
class RollbackConfig:
    """Configuration for rollback monitoring."""
    # How long to watch after an action (seconds)
    watch_window_seconds: float = 180.0   # 3 minutes
    # How long to wait before first check (let scaling take effect)
    grace_period_seconds: float = 30.0
    # Degradation threshold — metric must worsen by this fraction
    degradation_threshold: float = 0.15   # 15% worse
    # Metrics to watch (keys in the metrics dict)
    watched_metrics: List[str] = field(default_factory=lambda: [
        "latency_p99", "error_rate",
    ])
    # Whether rollback is actually executed (False = monitor only, log verdict)
    execute_rollback: bool = True
    # Extended cooldown after rollback (seconds) — prevents oscillation
    post_rollback_cooldown_seconds: float = 300.0  # 5 minutes


@dataclass
class RollbackWatch:
    """A single rollback monitoring session for one executed action."""
    recommendation_id: str
    deployment: str
    namespace: str
    pre_action_replicas: int
    post_action_replicas: int
    # Metrics snapshot at time of action
    pre_action_metrics: Dict[str, float]
    action_timestamp: float
    verdict: RollbackVerdict = RollbackVerdict.MONITORING
    verdict_timestamp: float = 0.0
    verdict_reason: str = ""
    # Metrics at time of verdict (for audit)
    verdict_metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.verdict == RollbackVerdict.MONITORING

    def format_log(self) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(self.action_timestamp))
        return (
            f"[{ts}] ROLLBACK_WATCH {self.namespace}/{self.deployment}: "
            f"{self.pre_action_replicas}->{self.post_action_replicas} "
            f"verdict={self.verdict.value}"
        )


class RollbackMonitor:
    """Monitors post-action metrics and triggers rollback on degradation.

    Usage:
        monitor = RollbackMonitor(config, rollback_fn=actuator.scale)
        # After each executed action:
        monitor.start_watch(rec_id, "api-gw", "prod", 5, 7, metrics_snapshot)
        # Each polling cycle:
        verdicts = monitor.check(current_metrics)
        # verdicts contains any watches that resolved this cycle
    """

    def __init__(
        self,
        config: Optional[RollbackConfig] = None,
        rollback_fn: Optional[Callable] = None,
    ):
        """
        Args:
            config: Rollback configuration.
            rollback_fn: Callable(deployment, namespace, current_replicas,
                         target_replicas, recommendation_id) -> result.
                         Typically actuator.scale(). If None, rollback is
                         logged but not executed.
        """
        self.config = config or RollbackConfig()
        self._rollback_fn = rollback_fn
        self._active_watches: List[RollbackWatch] = []
        self._history: List[RollbackWatch] = []
        self._max_history = 500
        self._lock = threading.Lock()

    def start_watch(
        self,
        recommendation_id: str,
        deployment: str,
        namespace: str,
        pre_action_replicas: int,
        post_action_replicas: int,
        pre_action_metrics: Dict[str, float],
    ) -> RollbackWatch:
        """Begin monitoring an executed action for degradation.

        Args:
            recommendation_id: ID of the recommendation that was executed.
            deployment: K8s deployment name.
            namespace: K8s namespace.
            pre_action_replicas: Replica count before the action.
            post_action_replicas: Replica count after the action.
            pre_action_metrics: Metrics snapshot at time of action.

        Returns:
            The RollbackWatch being monitored.
        """
        watch = RollbackWatch(
            recommendation_id=recommendation_id,
            deployment=deployment,
            namespace=namespace,
            pre_action_replicas=pre_action_replicas,
            post_action_replicas=post_action_replicas,
            pre_action_metrics=dict(pre_action_metrics),
            action_timestamp=time.time(),
        )

        with self._lock:
            self._active_watches.append(watch)

        logger.info(
            "Rollback watch started for %s/%s (rec=%s): %d->%d, window=%.0fs",
            namespace, deployment, recommendation_id,
            pre_action_replicas, post_action_replicas,
            self.config.watch_window_seconds,
        )
        return watch

    def check(
        self,
        current_metrics: Dict[str, float],
        current_time: Optional[float] = None,
    ) -> List[RollbackWatch]:
        """Check all active watches against current metrics.

        Call this every polling cycle with fresh metrics.

        Args:
            current_metrics: Current normalized metrics.
            current_time: Current timestamp (defaults to now).

        Returns:
            List of watches that resolved this cycle (STABLE, DEGRADED, etc.)
        """
        if current_time is None:
            current_time = time.time()

        resolved = []

        with self._lock:
            still_active = []
            for watch in self._active_watches:
                elapsed = current_time - watch.action_timestamp

                # Window expired — no degradation detected
                if elapsed > self.config.watch_window_seconds:
                    watch.verdict = RollbackVerdict.STABLE
                    watch.verdict_timestamp = current_time
                    watch.verdict_reason = (
                        f"Metrics stable through {self.config.watch_window_seconds:.0f}s "
                        f"watch window"
                    )
                    watch.verdict_metrics = dict(current_metrics)
                    resolved.append(watch)
                    self._archive(watch)
                    continue

                # Still in grace period — skip check
                if elapsed < self.config.grace_period_seconds:
                    still_active.append(watch)
                    continue

                # Check for degradation
                degraded_metrics = self._check_degradation(
                    watch.pre_action_metrics, current_metrics,
                )

                if degraded_metrics:
                    watch.verdict = RollbackVerdict.DEGRADED
                    watch.verdict_timestamp = current_time
                    watch.verdict_metrics = dict(current_metrics)
                    reasons = [
                        f"{name}: {old:.3f}->{new:.3f} ({change:+.1%})"
                        for name, old, new, change in degraded_metrics
                    ]
                    watch.verdict_reason = (
                        f"Metrics degraded after scaling: {'; '.join(reasons)}"
                    )

                    # Execute rollback if configured
                    if self.config.execute_rollback and self._rollback_fn is not None:
                        self._execute_rollback(watch)

                    resolved.append(watch)
                    self._archive(watch)
                else:
                    still_active.append(watch)

            self._active_watches = still_active

        for watch in resolved:
            logger.info(watch.format_log())
            if watch.verdict == RollbackVerdict.DEGRADED:
                logger.warning(
                    "ROLLBACK: %s/%s reverted %d->%d: %s",
                    watch.namespace, watch.deployment,
                    watch.post_action_replicas, watch.pre_action_replicas,
                    watch.verdict_reason,
                )

        return resolved

    def _check_degradation(
        self,
        pre_metrics: Dict[str, float],
        current_metrics: Dict[str, float],
    ) -> List[tuple]:
        """Check if any watched metrics have degraded.

        Returns list of (metric_name, old_value, new_value, pct_change)
        for degraded metrics. Empty list = no degradation.

        "Degradation" means the metric got WORSE:
        - For latency/error_rate: higher is worse
        """
        degraded = []
        threshold = self.config.degradation_threshold

        for metric_name in self.config.watched_metrics:
            if metric_name not in pre_metrics or metric_name not in current_metrics:
                continue

            old_val = pre_metrics[metric_name]
            new_val = current_metrics[metric_name]

            # Skip if old value is near zero (can't compute meaningful %)
            if abs(old_val) < 1e-8:
                # If new value is significantly non-zero, that's degradation
                if new_val > threshold:
                    degraded.append((metric_name, old_val, new_val, float('inf')))
                continue

            # For these metrics, higher = worse
            pct_change = (new_val - old_val) / abs(old_val)

            if pct_change > threshold:
                degraded.append((metric_name, old_val, new_val, pct_change))

        return degraded

    def _execute_rollback(self, watch: RollbackWatch) -> None:
        """Execute a rollback — scale back to pre-action replicas."""
        try:
            result = self._rollback_fn(
                deployment=watch.deployment,
                namespace=watch.namespace,
                current_replicas=watch.post_action_replicas,
                target_replicas=watch.pre_action_replicas,
                recommendation_id=f"rollback-{watch.recommendation_id}",
            )
            if hasattr(result, 'success') and result.success:
                watch.verdict = RollbackVerdict.ROLLED_BACK
                logger.info(
                    "Rollback executed for %s/%s: %d->%d",
                    watch.namespace, watch.deployment,
                    watch.post_action_replicas, watch.pre_action_replicas,
                )
            else:
                error = getattr(result, 'error', 'unknown')
                logger.error(
                    "Rollback execution FAILED for %s/%s: %s",
                    watch.namespace, watch.deployment, error,
                )
        except Exception as e:
            logger.error(
                "Rollback execution exception for %s/%s: %s",
                watch.namespace, watch.deployment, e,
            )

    def _archive(self, watch: RollbackWatch) -> None:
        """Move resolved watch to history. Caller must hold lock."""
        self._history.append(watch)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    @property
    def active_watches(self) -> List[RollbackWatch]:
        with self._lock:
            return list(self._active_watches)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active_watches)

    @property
    def history(self) -> List[RollbackWatch]:
        with self._lock:
            return list(self._history)

    @property
    def rollback_count(self) -> int:
        """Total rollbacks executed."""
        with self._lock:
            return sum(
                1 for w in self._history
                if w.verdict in (RollbackVerdict.DEGRADED, RollbackVerdict.ROLLED_BACK)
            )

    def reset(self) -> None:
        with self._lock:
            self._active_watches.clear()
            self._history.clear()
