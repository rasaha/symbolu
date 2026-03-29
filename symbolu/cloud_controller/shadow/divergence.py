"""Divergence Tracker — compares controller vs HPA decisions.

Records every point where the controller and HPA disagree,
tracks outcomes (verdicts), and maintains a history for reporting.

A divergence occurs when:
- HPA scales but controller says hold (HPA aggressive)
- Controller recommends scaling but HPA holds (controller ahead)
- Both scale but in opposite directions or different magnitudes

Verdicts are assigned after a lookback window (default 5 minutes)
by checking whether metrics improved, degraded, or stayed the same.

IMPORTANT LIMITATION — Attribution Causality:
Verdicts are based on *correlation*, not causation. When HPA scales
and metrics stabilize, we cannot prove whether HPA prevented degradation
or scaling was unnecessary. Similarly, metrics may improve or degrade
for reasons entirely unrelated to scaling decisions (deploy, traffic
shift, cache warm-up, etc.). Treat verdicts as directional signals
for human review, not ground truth.
"""

import math
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from symbolu.cloud_controller.controller import ActionResult
from symbolu.cloud_controller.shadow.hpa_watcher import HPASnapshot

logger = logging.getLogger(__name__)


class Verdict(Enum):
    """Outcome classification for a divergence."""
    PENDING = "pending"              # Not yet evaluated
    CONTROLLER_CORRECT = "controller_correct"  # Controller was right to disagree
    HPA_CORRECT = "hpa_correct"      # HPA was right, controller was wrong
    BOTH_REASONABLE = "both_reasonable"  # Both actions would have been fine
    INCONCLUSIVE = "inconclusive"    # Can't determine winner


class DivergenceType(Enum):
    """Classification of the disagreement."""
    HPA_SCALES_CONTROLLER_HOLDS = "hpa_scales_controller_holds"
    CONTROLLER_SCALES_HPA_HOLDS = "controller_scales_hpa_holds"
    OPPOSITE_DIRECTION = "opposite_direction"
    MAGNITUDE_DIFFERS = "magnitude_differs"
    AGREEMENT = "agreement"


@dataclass
class DivergenceRecord:
    """A single divergence event between controller and HPA."""
    timestamp: float
    divergence_type: DivergenceType

    # Controller state
    controller_recommendation: str
    controller_delta: int
    controller_action_score: float
    controller_pressure: float
    controller_coherence: float
    controller_explanation: str

    # HPA state
    hpa_current: int
    hpa_desired: int
    hpa_delta: int

    # Metrics at time of divergence
    metrics_snapshot: Dict[str, float]

    # Verdict (assigned later after lookback)
    verdict: Verdict = Verdict.PENDING
    verdict_timestamp: Optional[float] = None
    verdict_reason: str = ""

    # Cost estimation
    estimated_cost_impact: float = 0.0  # Positive = saved, negative = cost of being wrong

    @property
    def is_divergence(self) -> bool:
        return self.divergence_type != DivergenceType.AGREEMENT

    def format_log(self) -> str:
        """Format as human-readable divergence log entry."""
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        if not self.is_divergence:
            return (
                f"[{ts}] AGREEMENT — Both: {self.controller_recommendation} "
                f"(replicas: {self.hpa_current})"
            )

        lines = [
            f"[{ts}] DIVERGENCE ({self.divergence_type.value})",
            f"  HPA action:        {self.hpa_current} → {self.hpa_desired} ({self.hpa_delta:+d})",
            f"  Controller action:  {self.controller_recommendation.upper()} "
            f"({self.controller_delta:+d})",
            f"  Coherence:         {self.controller_coherence:.2f}",
            f"  Pressure:          {self.controller_pressure:.2f}",
            f"  Action Score:      {self.controller_action_score:.3f}",
        ]

        if self.verdict != Verdict.PENDING:
            if self.verdict_timestamp is not None and self.verdict_timestamp > 0:
                vts = time.strftime("%H:%M:%S", time.localtime(self.verdict_timestamp))
            else:
                vts = "??:??:??"
            lines.append(f"  Verdict [{vts}]:   {self.verdict.value}")
            if self.verdict_reason:
                lines.append(f"  Reason:           {self.verdict_reason}")
            if self.estimated_cost_impact != 0:
                sign = "saved" if self.estimated_cost_impact > 0 else "cost"
                lines.append(
                    f"  Cost impact:      ${abs(self.estimated_cost_impact):.2f} ({sign})"
                )

        return "\n".join(lines)


@dataclass
class DivergenceConfig:
    """Configuration for divergence tracking."""
    # Lookback window for verdict evaluation (seconds)
    verdict_lookback_seconds: float = 300.0  # 5 minutes
    # Thresholds for metric improvement detection
    improvement_threshold: float = 0.1  # 10% improvement = metrics got better
    degradation_threshold: float = 0.1  # 10% degradation = metrics got worse
    # Cost per pod per minute (for savings estimation)
    cost_per_pod_minute: float = 0.03


class DivergenceTracker:
    """Tracks divergences between controller and HPA over time.

    Each polling cycle, compare() is called with the controller's
    ActionResult and the HPA's current snapshot. If they disagree,
    a DivergenceRecord is created.

    After the lookback window, evaluate_pending() assigns verdicts
    based on whether metrics improved or degraded.
    """

    def __init__(self, config: Optional[DivergenceConfig] = None):
        self.config = config or DivergenceConfig()
        self._records: List[DivergenceRecord] = []
        self._max_history = 10000

    def compare(
        self,
        action: ActionResult,
        hpa: HPASnapshot,
        metrics: Dict[str, float],
    ) -> DivergenceRecord:
        """Compare controller recommendation against HPA action.

        Args:
            action: Controller's ActionResult from this cycle.
            hpa: Current HPA snapshot.
            metrics: Current normalized metrics.

        Returns:
            DivergenceRecord (may be agreement — check is_divergence).
        """
        ctrl_delta = action.replica_delta
        hpa_delta = hpa.delta

        divergence_type = self._classify(ctrl_delta, hpa_delta)

        # Safely access coherence — may be None in edge cases
        coherence_val = 0.0
        if action.coherence is not None:
            coherence_val = action.coherence.coherence

        record = DivergenceRecord(
            timestamp=time.time(),
            divergence_type=divergence_type,
            controller_recommendation=action.recommendation,
            controller_delta=ctrl_delta,
            controller_action_score=action.action_score,
            controller_pressure=action.pressure,
            controller_coherence=coherence_val,
            controller_explanation=action.explain(),
            hpa_current=hpa.current_replicas,
            hpa_desired=hpa.desired_replicas,
            hpa_delta=hpa_delta,
            metrics_snapshot=dict(metrics),
        )

        self._records.append(record)
        if len(self._records) > self._max_history:
            self._records = self._records[-self._max_history:]

        if record.is_divergence:
            logger.info("Divergence: %s", divergence_type.value)

        return record

    @staticmethod
    def _classify(ctrl_delta: int, hpa_delta: int) -> DivergenceType:
        """Classify the type of divergence between controller and HPA."""
        ctrl_action = ctrl_delta != 0
        hpa_action = hpa_delta != 0

        if not ctrl_action and not hpa_action:
            return DivergenceType.AGREEMENT

        if hpa_action and not ctrl_action:
            return DivergenceType.HPA_SCALES_CONTROLLER_HOLDS

        if ctrl_action and not hpa_action:
            return DivergenceType.CONTROLLER_SCALES_HPA_HOLDS

        # Both scale
        if (ctrl_delta > 0) != (hpa_delta > 0):
            return DivergenceType.OPPOSITE_DIRECTION

        if abs(ctrl_delta) != abs(hpa_delta):
            return DivergenceType.MAGNITUDE_DIFFERS

        return DivergenceType.AGREEMENT

    def evaluate_pending(
        self,
        current_metrics: Dict[str, float],
        current_time: Optional[float] = None,
    ) -> List[DivergenceRecord]:
        """Evaluate pending verdicts for records past the lookback window.

        Compares current metrics against the metrics at divergence time
        to determine who was right.

        Args:
            current_metrics: Current normalized metrics.
            current_time: Current timestamp (defaults to now).

        Returns:
            List of records that received verdicts this call.
        """
        if current_time is None:
            current_time = time.time()

        newly_evaluated = []
        for record in self._records:
            if record.verdict != Verdict.PENDING:
                continue
            if current_time - record.timestamp < self.config.verdict_lookback_seconds:
                continue

            verdict, reason, cost = self._evaluate_one(record, current_metrics)
            record.verdict = verdict
            record.verdict_timestamp = current_time
            record.verdict_reason = reason
            record.estimated_cost_impact = cost
            newly_evaluated.append(record)

            logger.info(
                "Verdict for divergence at %s: %s — %s",
                time.strftime("%H:%M:%S", time.localtime(record.timestamp)),
                verdict.value,
                reason,
            )

        return newly_evaluated

    def _evaluate_one(
        self,
        record: DivergenceRecord,
        current_metrics: Dict[str, float],
    ) -> tuple:
        """Evaluate a single divergence record.

        Returns: (verdict, reason, cost_impact)
        """
        # Compute metric change: positive = metrics improved (went down),
        # negative = metrics degraded (went up)
        # Filter NaN/infinity values from both sides
        changes = {}
        for key in record.metrics_snapshot:
            if key in current_metrics:
                old_val = record.metrics_snapshot[key]
                new_val = current_metrics[key]
                if math.isfinite(old_val) and math.isfinite(new_val):
                    changes[key] = old_val - new_val

        if not changes:
            logger.debug(
                "No valid overlapping metrics for verdict at %s "
                "(snapshot keys=%s, current keys=%s)",
                time.strftime("%H:%M:%S", time.localtime(record.timestamp)),
                list(record.metrics_snapshot.keys()),
                list(current_metrics.keys()),
            )
            return Verdict.INCONCLUSIVE, "No overlapping metrics for comparison", 0.0

        avg_change = sum(changes.values()) / len(changes)
        improved = avg_change > self.config.improvement_threshold
        degraded = avg_change < -self.config.degradation_threshold

        div_type = record.divergence_type
        elapsed_min = self.config.verdict_lookback_seconds / 60.0

        if div_type == DivergenceType.HPA_SCALES_CONTROLLER_HOLDS:
            # HPA scaled, controller said hold
            if improved:
                # Metrics improved — HPA's scaling helped (or coincidence)
                pods_extra = abs(record.hpa_delta)
                cost_of_inaction = pods_extra * elapsed_min * self.config.cost_per_pod_minute
                return (
                    Verdict.HPA_CORRECT,
                    "Metrics improved after HPA scaled",
                    -cost_of_inaction,
                )
            elif degraded:
                # Metrics degraded despite HPA scaling — something else going on
                return (
                    Verdict.INCONCLUSIVE,
                    "Metrics degraded despite HPA scaling",
                    0.0,
                )
            else:
                # Metrics stable — HPA action was unnecessary, controller was right
                pods_wasted = abs(record.hpa_delta)
                cost_saved = pods_wasted * elapsed_min * self.config.cost_per_pod_minute
                return (
                    Verdict.CONTROLLER_CORRECT,
                    f"Metrics stable without scaling — {pods_wasted} pods unnecessary "
                    f"for {elapsed_min:.0f} min",
                    cost_saved,
                )

        elif div_type == DivergenceType.CONTROLLER_SCALES_HPA_HOLDS:
            # Controller recommended scaling, HPA stayed put
            if degraded:
                # Metrics got worse — controller was right to recommend scaling
                return (
                    Verdict.CONTROLLER_CORRECT,
                    "Metrics degraded — earlier scaling would have helped",
                    0.0,
                )
            elif improved:
                # Metrics improved without scaling — HPA was right to hold
                return (
                    Verdict.HPA_CORRECT,
                    "Metrics improved without scaling",
                    0.0,
                )
            else:
                return (
                    Verdict.BOTH_REASONABLE,
                    "Metrics stable — neither action critical",
                    0.0,
                )

        elif div_type == DivergenceType.OPPOSITE_DIRECTION:
            # Controller and HPA disagree on direction
            if improved:
                return (
                    Verdict.INCONCLUSIVE,
                    "Metrics improved — unclear which direction was correct",
                    0.0,
                )
            elif degraded:
                return (
                    Verdict.INCONCLUSIVE,
                    "Metrics degraded — unclear which direction was correct",
                    0.0,
                )
            else:
                return (
                    Verdict.INCONCLUSIVE,
                    "Opposite scaling directions — inconclusive outcome",
                    0.0,
                )

        else:
            # Magnitude differs
            return (
                Verdict.BOTH_REASONABLE,
                "Both agreed on direction, magnitude differs",
                0.0,
            )

    @property
    def records(self) -> List[DivergenceRecord]:
        return list(self._records)

    @property
    def divergences(self) -> List[DivergenceRecord]:
        """Only actual divergences (excludes agreements)."""
        return [r for r in self._records if r.is_divergence]

    @property
    def pending_count(self) -> int:
        """Count of divergences awaiting verdict (agreements are excluded)."""
        return sum(1 for r in self._records if r.is_divergence and r.verdict == Verdict.PENDING)

    def reset(self) -> None:
        self._records.clear()
