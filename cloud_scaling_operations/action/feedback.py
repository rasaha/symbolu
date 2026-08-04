"""L6 → L4 Feedback Loop — closes the learning loop from outcomes to controller.

Takes observability verdicts (L6) and adjusts controller parameters (L4)
to improve future decisions. This is the key differentiator from static
scaling systems — the controller learns from its own outcomes.

Signal sources (L6):
  - OutcomeTracker: POSITIVE/NEGATIVE/NEUTRAL/OSCILLATION/OVERRIDDEN
  - DivergenceTracker: CONTROLLER_CORRECT/HPA_CORRECT/BOTH_REASONABLE
  - RollbackMonitor: STABLE/DEGRADED/ROLLED_BACK

Adjustment targets (L4):
  - AdaptiveGain: G_base, G_max (scaling aggressiveness)
  - Damping: k_dv, k_dc (volatility suppression)
  - PlasticityGate: b_p (openness to change)
  - ConfidenceScorer thresholds (recommendation sensitivity)

Safety constraints:
  - All parameter changes are rate-limited (max ±10% per feedback cycle)
  - Parameters are clamped to hard bounds
  - Minimum sample size before adjustments (default 3 verdicts)
  - Feedback can be disabled at any time without losing state

Attribution caveat:
  Verdicts are correlational, not causal. A POSITIVE outcome after
  scale-out doesn't prove scaling helped — traffic may have dropped
  independently. This loop uses *directional* signals with conservative
  step sizes, not aggressive optimization.
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from cloud_scaling_operations.action.outcome import OutcomeRecord, OutcomeVerdict
from cloud_scaling_operations.action.rollback import RollbackWatch, RollbackVerdict

# Lazy import to avoid circular: feedback → divergence → shadow → engine → feedback
# DivergenceRecord and Verdict are only needed at runtime, not module load.
_divergence_types_loaded = False
_Verdict = None
_DivergenceRecord_type = None


def _ensure_divergence_types():
    global _divergence_types_loaded, _Verdict, _DivergenceRecord_type
    if not _divergence_types_loaded:
        from ugence_cloud_scaling_controller.shadow.divergence import Verdict, DivergenceRecord
        _Verdict = Verdict
        _DivergenceRecord_type = DivergenceRecord
        _divergence_types_loaded = True

logger = logging.getLogger(__name__)


class FeedbackSignal(Enum):
    """Aggregated signal direction from L6 verdicts."""
    BOOST = "boost"        # Outcomes suggest more aggressive scaling
    DAMPEN = "dampen"      # Outcomes suggest more cautious scaling
    NEUTRAL = "neutral"    # No clear signal — hold parameters


@dataclass
class FeedbackConfig:
    """Configuration for the L6 → L4 feedback loop."""
    # Whether feedback adjustments are enabled (False = monitor only)
    enabled: bool = True
    # Rate limit: maximum fractional change per feedback cycle
    max_adjustment_rate: float = 0.10     # ±10% per cycle
    # Minimum verdicts in window before adjusting
    min_verdicts_for_adjustment: int = 3
    # How far back to look for verdicts (seconds)
    verdict_window_seconds: float = 1800.0  # 30 minutes
    # Step sizes for each adjustment direction
    gain_boost_step: float = 0.05         # +5% G_base on positive signal
    gain_dampen_step: float = 0.08        # -8% G_base on negative signal
    damping_boost_step: float = 0.10      # +10% k_dv/k_dc on negative signal
    plasticity_bias_step: float = 0.05    # Shift b_p toward more/less openness
    # Hard bounds (never adjust beyond these)
    g_base_bounds: tuple = (0.3, 3.0)
    g_max_bounds: tuple = (1.0, 5.0)
    k_dv_bounds: tuple = (0.2, 3.0)
    k_dc_bounds: tuple = (0.1, 2.0)
    b_p_bounds: tuple = (-2.0, 0.0)


@dataclass
class FeedbackAdjustment:
    """Record of a single parameter adjustment."""
    timestamp: float
    parameter: str
    old_value: float
    new_value: float
    delta: float
    signal: str          # "boost" or "dampen"
    reason: str

    def format_log(self) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        return (
            f"[{ts}] FEEDBACK [{self.signal}] {self.parameter}: "
            f"{self.old_value:.4f} → {self.new_value:.4f} "
            f"(Δ{self.delta:+.4f}) — {self.reason}"
        )


@dataclass
class FeedbackCycleResult:
    """Result of one feedback evaluation cycle."""
    signal: FeedbackSignal
    adjustments: List[FeedbackAdjustment] = field(default_factory=list)
    # Verdict counts in the window
    positive_count: int = 0
    negative_count: int = 0
    oscillation_count: int = 0
    rollback_count: int = 0
    controller_correct_count: int = 0
    hpa_correct_count: int = 0
    total_verdicts: int = 0
    # Whether adjustments were actually applied
    applied: bool = False
    skip_reason: str = ""


class FeedbackLoop:
    """Adjusts L4 controller parameters based on L6 observability outcomes.

    Usage:
        loop = FeedbackLoop(config)

        # Each polling cycle, after evaluating outcomes and divergences:
        result = loop.process(
            controller=controller,
            outcomes=resolved_outcomes,
            rollbacks=resolved_rollbacks,
            divergences=resolved_divergences,
        )
        # result.adjustments contains what was changed

        # Feed high-value outcomes to replay buffer:
        for entry in loop.to_replay_entries(outcomes):
            controller.replay_buffer.store(entry, step=current_step)
    """

    def __init__(self, config: Optional[FeedbackConfig] = None):
        self.config = config or FeedbackConfig()
        self._history: List[FeedbackCycleResult] = []
        self._adjustment_history: List[FeedbackAdjustment] = []
        self._max_history = 500
        self._lock = threading.Lock()
        # Rolling verdict counts (for trend detection across cycles)
        self._recent_outcomes: List[OutcomeRecord] = []
        self._recent_rollbacks: List[RollbackWatch] = []
        self._recent_divergences: list = []

    def process(
        self,
        controller,
        outcomes: Optional[List[OutcomeRecord]] = None,
        rollbacks: Optional[List[RollbackWatch]] = None,
        divergences: Optional[list] = None,
        current_time: Optional[float] = None,
    ) -> FeedbackCycleResult:
        """Process L6 verdicts and adjust L4 parameters.

        Args:
            controller: The Controller instance to adjust.
                        Must have adaptive_gain, damping, and plasticity_gate.
            outcomes: Resolved OutcomeRecords from OutcomeTracker.
            rollbacks: Resolved RollbackWatches from RollbackMonitor.
            divergences: Resolved DivergenceRecords from DivergenceTracker.
            current_time: Current timestamp (defaults to now).

        Returns:
            FeedbackCycleResult with signal direction and adjustments made.
        """
        if current_time is None:
            current_time = time.time()

        with self._lock:
            # 1. Accumulate new verdicts
            if outcomes:
                self._recent_outcomes.extend(outcomes)
            if rollbacks:
                self._recent_rollbacks.extend(rollbacks)
            if divergences:
                self._recent_divergences.extend(
                    d for d in divergences
                    if hasattr(d, 'is_divergence') and d.is_divergence
                )

            # 2. Prune old verdicts outside the window
            cutoff = current_time - self.config.verdict_window_seconds
            self._recent_outcomes = [
                o for o in self._recent_outcomes
                if o.verdict_timestamp > cutoff
            ]
            self._recent_rollbacks = [
                r for r in self._recent_rollbacks
                if r.verdict_timestamp > cutoff
            ]
            self._recent_divergences = [
                d for d in self._recent_divergences
                if (d.verdict_timestamp if d.verdict_timestamp else d.timestamp) > cutoff
            ]

            # 3. Count verdicts
            counts = self._count_verdicts()
            total = counts["total"]

            # 4. Determine signal direction
            signal = self._compute_signal(counts)

        result = FeedbackCycleResult(
            signal=signal,
            positive_count=counts["positive"],
            negative_count=counts["negative"],
            oscillation_count=counts["oscillation"],
            rollback_count=counts["rollback"],
            controller_correct_count=counts["controller_correct"],
            hpa_correct_count=counts["hpa_correct"],
            total_verdicts=total,
        )

        # 5. Check minimum sample size
        if total < self.config.min_verdicts_for_adjustment:
            result.skip_reason = (
                f"Insufficient verdicts: {total} < "
                f"{self.config.min_verdicts_for_adjustment}"
            )
            self._record_cycle(result)
            return result

        # 6. Check if feedback is enabled
        if not self.config.enabled:
            result.skip_reason = "Feedback disabled"
            self._record_cycle(result)
            return result

        # 7. Apply adjustments if signal is not neutral
        if signal != FeedbackSignal.NEUTRAL:
            adjustments = self._apply_adjustments(controller, signal, counts, current_time)
            result.adjustments = adjustments
            result.applied = len(adjustments) > 0

        self._record_cycle(result)

        if result.applied:
            logger.info(
                "Feedback loop applied %d adjustments (signal=%s, verdicts=%d)",
                len(result.adjustments), signal.value, total,
            )
        return result

    def _count_verdicts(self) -> Dict[str, int]:
        """Count verdict types across all signal sources."""
        counts = {
            "positive": 0,
            "negative": 0,
            "oscillation": 0,
            "overridden": 0,
            "neutral": 0,
            "rollback": 0,
            "stable": 0,
            "controller_correct": 0,
            "hpa_correct": 0,
            "total": 0,
        }

        for o in self._recent_outcomes:
            if o.verdict == OutcomeVerdict.POSITIVE:
                counts["positive"] += 1
            elif o.verdict == OutcomeVerdict.NEGATIVE:
                counts["negative"] += 1
            elif o.verdict == OutcomeVerdict.OSCILLATION:
                counts["oscillation"] += 1
            elif o.verdict == OutcomeVerdict.OVERRIDDEN:
                counts["overridden"] += 1
            else:
                counts["neutral"] += 1

        for r in self._recent_rollbacks:
            if r.verdict in (RollbackVerdict.DEGRADED, RollbackVerdict.ROLLED_BACK):
                counts["rollback"] += 1
            elif r.verdict == RollbackVerdict.STABLE:
                counts["stable"] += 1

        _ensure_divergence_types()
        for d in self._recent_divergences:
            if d.verdict == _Verdict.CONTROLLER_CORRECT:
                counts["controller_correct"] += 1
            elif d.verdict == _Verdict.HPA_CORRECT:
                counts["hpa_correct"] += 1

        counts["total"] = (
            counts["positive"] + counts["negative"] + counts["oscillation"]
            + counts["overridden"] + counts["rollback"] + counts["stable"]
            + counts["controller_correct"] + counts["hpa_correct"]
            + counts["neutral"]
        )
        return counts

    def _compute_signal(self, counts: Dict[str, int]) -> FeedbackSignal:
        """Determine the overall feedback direction.

        Scoring (design doc §5.15 — L6→L4 signal weights):
          +1 per POSITIVE, CONTROLLER_CORRECT, STABLE
          -1 per NEGATIVE, OVERRIDDEN, ROLLBACK
          -2 per OSCILLATION (strong dampen signal)
          -0.5 per HPA_CORRECT (mild dampen — we were wrong but not dangerously)
        """
        score = 0.0
        score += counts["positive"] * 1.0
        score += counts["controller_correct"] * 1.0
        score += counts["stable"] * 1.0
        score -= counts["negative"] * 1.0
        score -= counts["overridden"] * 1.0
        score -= counts["rollback"] * 1.0
        score -= counts["oscillation"] * 2.0
        score -= counts["hpa_correct"] * 0.5

        total = counts["total"]
        if total == 0:
            return FeedbackSignal.NEUTRAL

        # Normalize to [-1, 1] range
        normalized = score / total

        if normalized > 0.2:
            return FeedbackSignal.BOOST
        elif normalized < -0.2:
            return FeedbackSignal.DAMPEN
        else:
            return FeedbackSignal.NEUTRAL

    def _apply_adjustments(
        self,
        controller,
        signal: FeedbackSignal,
        counts: Dict[str, int],
        timestamp: float,
    ) -> List[FeedbackAdjustment]:
        """Apply parameter adjustments to the controller."""
        adjustments = []

        if signal == FeedbackSignal.BOOST:
            adjustments.extend(self._boost(controller, counts, timestamp))
        elif signal == FeedbackSignal.DAMPEN:
            adjustments.extend(self._dampen(controller, counts, timestamp))

        with self._lock:
            self._adjustment_history.extend(adjustments)
            if len(self._adjustment_history) > self._max_history:
                self._adjustment_history = self._adjustment_history[-self._max_history:]

        return adjustments

    def _boost(
        self, controller, counts: Dict[str, int], timestamp: float,
    ) -> List[FeedbackAdjustment]:
        """Apply boost adjustments — make controller more aggressive."""
        adjustments = []
        cfg = self.config

        # Increase G_base (scaling magnitude)
        adj = self._adjust_param(
            controller.adaptive_gain, "G_base",
            delta=cfg.gain_boost_step,
            bounds=cfg.g_base_bounds,
            timestamp=timestamp,
            signal="boost",
            reason=f"Positive outcomes ({counts['positive']}P, "
                   f"{counts['controller_correct']}CC)",
        )
        if adj:
            adjustments.append(adj)

        # Decrease b_p (open plasticity gate more) — less negative = more open
        adj = self._adjust_param(
            controller.plasticity_gate, "b_p",
            delta=cfg.plasticity_bias_step,
            bounds=cfg.b_p_bounds,
            timestamp=timestamp,
            signal="boost",
            reason="Opening plasticity gate after positive outcomes",
        )
        if adj:
            adjustments.append(adj)

        return adjustments

    def _dampen(
        self, controller, counts: Dict[str, int], timestamp: float,
    ) -> List[FeedbackAdjustment]:
        """Apply dampen adjustments — make controller more cautious."""
        adjustments = []
        cfg = self.config

        # Decrease G_base (reduce scaling magnitude)
        adj = self._adjust_param(
            controller.adaptive_gain, "G_base",
            delta=-cfg.gain_dampen_step,
            bounds=cfg.g_base_bounds,
            timestamp=timestamp,
            signal="dampen",
            reason=f"Negative outcomes ({counts['negative']}N, "
                   f"{counts['oscillation']}Osc, {counts['rollback']}RB)",
        )
        if adj:
            adjustments.append(adj)

        # Increase k_dv (dampen more on variance)
        adj = self._adjust_param(
            controller.damping, "k_dv",
            delta=cfg.damping_boost_step,
            bounds=cfg.k_dv_bounds,
            timestamp=timestamp,
            signal="dampen",
            reason="Increasing variance sensitivity after negative outcomes",
        )
        if adj:
            adjustments.append(adj)

        # Increase k_dc (dampen more on coherence instability)
        adj = self._adjust_param(
            controller.damping, "k_dc",
            delta=cfg.damping_boost_step * 0.5,
            bounds=cfg.k_dc_bounds,
            timestamp=timestamp,
            signal="dampen",
            reason="Increasing coherence damping after negative outcomes",
        )
        if adj:
            adjustments.append(adj)

        # Decrease b_p (close plasticity gate) — more negative = more closed
        adj = self._adjust_param(
            controller.plasticity_gate, "b_p",
            delta=-cfg.plasticity_bias_step,
            bounds=cfg.b_p_bounds,
            timestamp=timestamp,
            signal="dampen",
            reason=f"Closing plasticity gate after "
                   f"{counts['oscillation']} oscillations, "
                   f"{counts['rollback']} rollbacks",
        )
        if adj:
            adjustments.append(adj)

        # If oscillations detected, also reduce G_max
        if counts["oscillation"] > 0:
            adj = self._adjust_param(
                controller.adaptive_gain, "G_max",
                delta=-cfg.gain_dampen_step * 2,
                bounds=cfg.g_max_bounds,
                timestamp=timestamp,
                signal="dampen",
                reason=f"Reducing max gain after {counts['oscillation']} oscillations",
            )
            if adj:
                adjustments.append(adj)

        return adjustments

    def _adjust_param(
        self,
        module,
        attr: str,
        delta: float,
        bounds: tuple,
        timestamp: float,
        signal: str,
        reason: str,
    ) -> Optional[FeedbackAdjustment]:
        """Adjust a single parameter with rate limiting and bounds clamping.

        Args:
            module: Object owning the parameter (e.g., controller.adaptive_gain).
            attr: Attribute name (e.g., "G_base").
            delta: Desired change (+ or -). Will be rate-limited.
            bounds: (min, max) hard bounds.
            timestamp: Current time.
            signal: "boost" or "dampen".
            reason: Human-readable reason.

        Returns:
            FeedbackAdjustment if change was made, None if no change needed.
        """
        old_value = getattr(module, attr, None)
        if old_value is None:
            logger.warning(
                "Attribute %s not found on %s, skipping adjustment",
                attr, type(module).__name__,
            )
            return None

        # Rate limit: cap delta at max_adjustment_rate of current value,
        # but use 1% of the bounds range as a floor to prevent stall near zero
        bounds_range = bounds[1] - bounds[0]
        min_step = bounds_range * 0.01
        max_delta = max(abs(old_value) * self.config.max_adjustment_rate, min_step)
        clamped_delta = max(-max_delta, min(max_delta, delta))

        new_value = old_value + clamped_delta

        # Apply bounds
        new_value = max(bounds[0], min(bounds[1], new_value))

        # Skip if no meaningful change
        if abs(new_value - old_value) < 1e-8:
            return None

        setattr(module, attr, new_value)

        adj = FeedbackAdjustment(
            timestamp=timestamp,
            parameter=attr,
            old_value=old_value,
            new_value=new_value,
            delta=new_value - old_value,
            signal=signal,
            reason=reason,
        )

        logger.info(adj.format_log())
        return adj

    @staticmethod
    def to_replay_entries(outcomes: List[OutcomeRecord]) -> List[dict]:
        """Convert resolved outcomes to replay buffer entries.

        Only includes outcomes with meaningful signal (POSITIVE, NEGATIVE,
        OSCILLATION, OVERRIDDEN). Neutral outcomes are excluded.
        """
        entries = []
        for outcome in outcomes:
            if outcome.verdict in (
                OutcomeVerdict.POSITIVE,
                OutcomeVerdict.NEGATIVE,
                OutcomeVerdict.OSCILLATION,
                OutcomeVerdict.OVERRIDDEN,
            ):
                entries.append(outcome.to_replay_entry())
        return entries

    def _record_cycle(self, result: FeedbackCycleResult) -> None:
        with self._lock:
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    @property
    def history(self) -> List[FeedbackCycleResult]:
        with self._lock:
            return list(self._history)

    @property
    def adjustment_history(self) -> List[FeedbackAdjustment]:
        with self._lock:
            return list(self._adjustment_history)

    @property
    def total_adjustments(self) -> int:
        with self._lock:
            return len(self._adjustment_history)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._adjustment_history.clear()
            self._recent_outcomes.clear()
            self._recent_rollbacks.clear()
            self._recent_divergences.clear()
