"""Outcome Tracker — post-action metric evaluation for learning feedback.

Design doc reference: §5.13, lines 335-341:
  "After each action, track:
   - Did latency decrease within 5 minutes?
   - Did error rate decrease?
   - Did scaling oscillation occur (scale up then down within 10 minutes)?
   - Was the action overridden by a human?
   Feed outcomes back as priority weights for replay buffer entries."

The outcome tracker monitors actions after execution and produces an
OutcomeRecord that can be fed to the replay buffer as priority weights.

This complements the rollback monitor:
  - Rollback monitor: fast (3 min), binary (degraded or not), triggers revert
  - Outcome tracker: slower (5 min), graduated scoring, feeds learning loop
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OutcomeVerdict(Enum):
    """Classification of action outcome."""
    PENDING = "pending"              # Still within evaluation window
    POSITIVE = "positive"            # Metrics improved after action
    NEUTRAL = "neutral"              # Metrics unchanged
    NEGATIVE = "negative"            # Metrics worsened after action
    OSCILLATION = "oscillation"      # Scaled up then down (or vice versa)
    OVERRIDDEN = "overridden"        # Human reverted the action


@dataclass
class OutcomeConfig:
    """Configuration for outcome tracking."""
    # How long to wait before evaluating outcome (seconds)
    evaluation_window_seconds: float = 300.0   # 5 minutes
    # Thresholds for positive/negative classification
    improvement_threshold: float = 0.05  # 5% improvement
    degradation_threshold: float = 0.10  # 10% degradation
    # Oscillation detection window
    oscillation_window_seconds: float = 600.0  # 10 minutes
    # Metrics to evaluate
    tracked_metrics: List[str] = field(default_factory=lambda: [
        "latency_p99", "error_rate", "cpu", "memory",
    ])


@dataclass
class OutcomeRecord:
    """Outcome evaluation for a single executed action."""
    recommendation_id: str
    deployment: str
    namespace: str
    action_delta: int                # +N or -N replicas
    action_timestamp: float
    pre_action_metrics: Dict[str, float]

    # Evaluation results
    verdict: OutcomeVerdict = OutcomeVerdict.PENDING
    verdict_timestamp: float = 0.0
    post_action_metrics: Dict[str, float] = field(default_factory=dict)
    metric_changes: Dict[str, float] = field(default_factory=dict)
    priority_score: float = 0.0      # For replay buffer (0.0 - 1.0)
    verdict_reason: str = ""

    def to_replay_entry(self) -> dict:
        """Convert to replay buffer entry format."""
        return {
            "recommendation_id": self.recommendation_id,
            "deployment": f"{self.namespace}/{self.deployment}",
            "action_delta": self.action_delta,
            "verdict": self.verdict.value,
            "priority": self.priority_score,
            "pre_metrics": dict(self.pre_action_metrics),
            "post_metrics": dict(self.post_action_metrics),
            "metric_changes": dict(self.metric_changes),
        }


class OutcomeTracker:
    """Tracks outcomes of scaling actions for learning feedback.

    Usage:
        tracker = OutcomeTracker(config)
        # After each executed action:
        tracker.record_action("rec-123", "api-gw", "prod", delta=+2, metrics={...})
        # Each polling cycle:
        outcomes = tracker.evaluate(current_metrics)
        for outcome in outcomes:
            replay_buffer.store(outcome.to_replay_entry(), step=current_step)
    """

    def __init__(self, config: Optional[OutcomeConfig] = None):
        self.config = config or OutcomeConfig()
        self._pending: List[OutcomeRecord] = []
        self._history: List[OutcomeRecord] = []
        self._max_history = 1000
        self._lock = threading.Lock()

    def record_action(
        self,
        recommendation_id: str,
        deployment: str,
        namespace: str,
        delta: int,
        pre_action_metrics: Dict[str, float],
        timestamp: Optional[float] = None,
    ) -> OutcomeRecord:
        """Record that a scaling action was executed.

        Args:
            recommendation_id: ID of the executed recommendation.
            deployment: K8s deployment name.
            namespace: K8s namespace.
            delta: Replica delta that was applied (+N or -N).
            pre_action_metrics: Metrics snapshot at time of action.
            timestamp: Action timestamp (defaults to now).

        Returns:
            OutcomeRecord being tracked.
        """
        record = OutcomeRecord(
            recommendation_id=recommendation_id,
            deployment=deployment,
            namespace=namespace,
            action_delta=delta,
            action_timestamp=timestamp or time.time(),
            pre_action_metrics=dict(pre_action_metrics),
        )

        with self._lock:
            self._pending.append(record)

        logger.debug(
            "Outcome tracking started for %s/%s (rec=%s, delta=%+d)",
            namespace, deployment, recommendation_id, delta,
        )
        return record

    def record_override(self, recommendation_id: str) -> Optional[OutcomeRecord]:
        """Mark an action as overridden by a human.

        Args:
            recommendation_id: ID of the overridden recommendation.

        Returns:
            The updated OutcomeRecord, or None if not found.
        """
        with self._lock:
            for record in self._pending:
                if record.recommendation_id == recommendation_id:
                    record.verdict = OutcomeVerdict.OVERRIDDEN
                    record.verdict_timestamp = time.time()
                    record.verdict_reason = "Action was overridden by human operator"
                    record.priority_score = 0.9  # High priority — learn from overrides
                    self._pending.remove(record)
                    self._archive(record)
                    logger.info(
                        "Action %s marked as overridden", recommendation_id,
                    )
                    return record
        return None

    def evaluate(
        self,
        current_metrics: Dict[str, float],
        current_time: Optional[float] = None,
    ) -> List[OutcomeRecord]:
        """Evaluate pending outcomes against current metrics.

        Call this every polling cycle.

        Args:
            current_metrics: Current normalized metrics.
            current_time: Current timestamp (defaults to now).

        Returns:
            List of outcomes that resolved this cycle.
        """
        if current_time is None:
            current_time = time.time()

        resolved = []

        with self._lock:
            still_pending = []
            for record in self._pending:
                elapsed = current_time - record.action_timestamp

                if elapsed < self.config.evaluation_window_seconds:
                    still_pending.append(record)
                    continue

                # Evaluate outcome
                self._evaluate_one(record, current_metrics, current_time)
                resolved.append(record)
                self._archive(record)

            self._pending = still_pending

        for outcome in resolved:
            logger.info(
                "Outcome for %s: %s (priority=%.2f) — %s",
                outcome.recommendation_id,
                outcome.verdict.value,
                outcome.priority_score,
                outcome.verdict_reason,
            )

        return resolved

    def check_oscillation(
        self,
        deployment: str,
        namespace: str,
        new_delta: int,
        current_time: Optional[float] = None,
    ) -> bool:
        """Check if a new action would create a scaling oscillation.

        An oscillation is: scale up then down (or vice versa) within
        the oscillation window.

        Args:
            deployment: K8s deployment name.
            namespace: K8s namespace.
            new_delta: Proposed new scaling delta.
            current_time: Current timestamp.

        Returns:
            True if this would be an oscillation.
        """
        if current_time is None:
            current_time = time.time()

        cutoff = current_time - self.config.oscillation_window_seconds

        with self._lock:
            recent = [
                r for r in (self._pending + self._history)
                if r.deployment == deployment
                and r.namespace == namespace
                and r.action_timestamp > cutoff
            ]

        for record in recent:
            # Opposite direction = oscillation
            if (record.action_delta > 0 and new_delta < 0) or \
               (record.action_delta < 0 and new_delta > 0):
                return True

        return False

    def _evaluate_one(
        self,
        record: OutcomeRecord,
        current_metrics: Dict[str, float],
        current_time: float,
    ) -> None:
        """Evaluate a single outcome record."""
        record.post_action_metrics = dict(current_metrics)
        record.verdict_timestamp = current_time

        # Compute metric changes
        changes = {}
        for metric in self.config.tracked_metrics:
            if metric in record.pre_action_metrics and metric in current_metrics:
                old_val = record.pre_action_metrics[metric]
                new_val = current_metrics[metric]
                if abs(old_val) > 1e-8:
                    # Negative change = improvement (metric decreased = good)
                    changes[metric] = (new_val - old_val) / abs(old_val)
                elif new_val > self.config.degradation_threshold:
                    changes[metric] = 1.0  # Degradation from zero
                else:
                    changes[metric] = 0.0

        record.metric_changes = changes

        if not changes:
            record.verdict = OutcomeVerdict.NEUTRAL
            record.verdict_reason = "No overlapping metrics to evaluate"
            record.priority_score = 0.3
            return

        # Check for oscillation in recent history
        # NOTE: caller (evaluate) already holds self._lock
        is_oscillation = any(
            r.deployment == record.deployment
            and r.namespace == record.namespace
            and r.action_timestamp > record.action_timestamp - self.config.oscillation_window_seconds
            and r.action_timestamp < record.action_timestamp
            and ((r.action_delta > 0) != (record.action_delta > 0))
            for r in self._history
        )

        if is_oscillation:
            record.verdict = OutcomeVerdict.OSCILLATION
            record.verdict_reason = (
                f"Scaling oscillation detected: delta={record.action_delta:+d} "
                f"reverses recent action"
            )
            record.priority_score = 0.85  # High priority — learn from oscillations
            return

        # Classify based on average metric change
        avg_change = sum(changes.values()) / len(changes)

        if avg_change < -self.config.improvement_threshold:
            # Negative change = metrics went down = improvement
            record.verdict = OutcomeVerdict.POSITIVE
            record.verdict_reason = (
                f"Metrics improved by {abs(avg_change):.1%} on average"
            )
            record.priority_score = 0.4  # Moderate — successful action
        elif avg_change > self.config.degradation_threshold:
            # Positive change = metrics went up = degradation
            record.verdict = OutcomeVerdict.NEGATIVE
            record.verdict_reason = (
                f"Metrics degraded by {avg_change:.1%} on average"
            )
            record.priority_score = 0.8  # High — learn from failures
        else:
            record.verdict = OutcomeVerdict.NEUTRAL
            record.verdict_reason = (
                f"Metrics stable (avg change {avg_change:+.1%})"
            )
            record.priority_score = 0.2  # Low — nothing interesting

    def _archive(self, record: OutcomeRecord) -> None:
        """Move to history. Caller must hold lock."""
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    @property
    def pending(self) -> List[OutcomeRecord]:
        with self._lock:
            return list(self._pending)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    @property
    def history(self) -> List[OutcomeRecord]:
        with self._lock:
            return list(self._history)

    def reset(self) -> None:
        with self._lock:
            self._pending.clear()
            self._history.clear()
