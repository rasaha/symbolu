"""Efficiency Estimator — observability-only diagnostic for scaling effectiveness.

Detects whether scaling actions (especially scale-outs) are actually improving
system metrics. This is a pure observation layer — it does NOT modify the
controller's decisions, A_t, pressure, or any signal chain.

The estimator answers a specific question that the controller cannot:

    "When I added replicas, did it actually help?"

By tracking metric deltas across evaluation windows after each scale-out,
it classifies each scaling event as HELPING, NEUTRAL, or NOT_HELPING.
This data feeds into the edge case report to explain *why* excess cost exists.

Architecture:
    EfficiencyEstimator is instantiated per scenario run, receives the same
    metric/replica/delta data the controller sees, but only observes and
    records. It has no feedback path to the controller.

Future hook (not activated):
    Once validated, the estimator's output could inform a delta override
    that caps scale-out when NOT_HELPING for N consecutive cycles. This
    is defined but not connected.

Usage:
    estimator = EfficiencyEstimator()
    for cycle in scenario:
        estimator.observe(cycle, metrics, replicas, delta)
    summary = estimator.summary()
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class EfficiencyState(Enum):
    """Classification of whether a scaling action improved metrics."""
    HELPING = "helping"           # scaling improved system metrics
    NEUTRAL = "neutral"          # no meaningful change
    NOT_HELPING = "not_helping"  # scaling did not improve or worsened metrics


@dataclass
class ScaleOutEvent:
    """Tracks a single scale-out event and its evaluation window."""
    cycle: int
    delta: int                    # positive delta that triggered this event
    replicas_before: int
    replicas_after: int
    metrics_before: Dict[str, float]

    # Filled during evaluation window
    metrics_after: Optional[Dict[str, float]] = None
    evaluation_complete: bool = False

    # Results
    marginal_cpu_change: float = 0.0
    latency_improvement: float = 0.0
    error_improvement: float = 0.0
    utilization_efficiency: float = 0.0
    state: EfficiencyState = EfficiencyState.NEUTRAL
    confidence: float = 0.0


@dataclass
class CycleEfficiency:
    """Per-cycle efficiency observation."""
    cycle: int
    replicas: int
    cpu_per_replica: float
    latency: float
    error_rate: float
    state: EfficiencyState
    confidence: float
    active_event: Optional[ScaleOutEvent] = None


@dataclass
class EfficiencySummary:
    """Aggregated efficiency statistics for a scenario."""
    total_scale_outs: int = 0
    helping_count: int = 0
    neutral_count: int = 0
    not_helping_count: int = 0

    # Per-cycle classification
    total_cycles: int = 0
    cycles_helping: int = 0
    cycles_neutral: int = 0
    cycles_not_helping: int = 0

    # Overlap with excess cost
    not_helping_during_excess: int = 0
    total_excess_cycles: int = 0

    @property
    def pct_helping(self) -> float:
        if self.total_scale_outs == 0:
            return 0.0
        return self.helping_count / self.total_scale_outs * 100

    @property
    def pct_not_helping(self) -> float:
        if self.total_scale_outs == 0:
            return 0.0
        return self.not_helping_count / self.total_scale_outs * 100

    @property
    def pct_cycles_not_helping(self) -> float:
        if self.total_cycles == 0:
            return 0.0
        return self.cycles_not_helping / self.total_cycles * 100

    @property
    def excess_overlap_pct(self) -> float:
        if self.total_excess_cycles == 0:
            return 0.0
        return self.not_helping_during_excess / self.total_excess_cycles * 100


# ============================================================
# Scale-Out Futility Guard
# ============================================================

@dataclass
class ScaleOutFutilityGuard:
    """Blocks scale-out when scaling is provably ineffective.

    Operates as a safe delta override layer between the controller's
    decision and actuation. Only caps positive delta (scale-out) — never
    forces scale-in or modifies negative delta.

    Activation requires ALL of:
      1. NOT_HELPING for >= futility_window consecutive cycles
      2. replicas >= high_replica_threshold
      3. The guard is deterministic and resets immediately when
         efficiency becomes HELPING

    Safety guarantees:
      - NEVER activates below high_replica_threshold
      - NEVER triggers on single-cycle NOT_HELPING
      - NEVER modifies scale-in decisions (negative delta passes through)
      - Resets immediately when efficiency_state becomes HELPING
    """
    futility_window: int = 5
    high_replica_threshold: int = 20

    # Internal state
    _consecutive_not_helping: int = field(default=0, init=False, repr=False)
    _active: bool = field(default=False, init=False, repr=False)
    _blocked_events: int = field(default=0, init=False, repr=False)
    _total_evaluated: int = field(default=0, init=False, repr=False)

    def update(self, efficiency_state: EfficiencyState) -> None:
        """Update consecutive NOT_HELPING counter from estimator output.

        Called once per cycle with the estimator's classification.
        """
        if efficiency_state == EfficiencyState.NOT_HELPING:
            self._consecutive_not_helping += 1
        elif efficiency_state == EfficiencyState.HELPING:
            # Hard reset: HELPING proves scaling is working
            self._consecutive_not_helping = 0
            self._active = False
        else:
            # NEUTRAL: decay slowly (don't reset, but don't accumulate)
            # This prevents a single NEUTRAL cycle from resetting a
            # long NOT_HELPING streak
            pass

    def filter_delta(self, delta: int, current_replicas: int) -> int:
        """Apply futility guard to the controller's delta decision.

        Returns the (possibly modified) delta. Only caps positive delta.
        Negative delta always passes through unchanged.
        """
        self._total_evaluated += 1

        # Determine if guard should be active
        self._active = (
            self._consecutive_not_helping >= self.futility_window
            and current_replicas >= self.high_replica_threshold
        )

        # Only block scale-out (positive delta)
        if self._active and delta > 0:
            self._blocked_events += 1
            return 0

        return delta

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def consecutive_not_helping(self) -> int:
        return self._consecutive_not_helping

    @property
    def blocked_scale_out_events(self) -> int:
        return self._blocked_events

    @property
    def total_evaluated(self) -> int:
        return self._total_evaluated


# ============================================================
# Efficiency Estimator
# ============================================================

class EfficiencyEstimator:
    """Observability-only estimator for scaling effectiveness.

    Tracks each scale-out event and evaluates whether it improved
    system metrics over a short window. Classifies every cycle
    and every scale-out event.

    This module has NO side effects on the controller.
    """

    def __init__(
        self,
        eval_window: int = 5,
        cpu_improvement_threshold: float = 0.03,
        latency_improvement_threshold: float = 0.02,
        error_improvement_threshold: float = 0.01,
    ):
        self.eval_window = eval_window
        self.cpu_thresh = cpu_improvement_threshold
        self.latency_thresh = latency_improvement_threshold
        self.error_thresh = error_improvement_threshold

        # State
        self._events: List[ScaleOutEvent] = []
        self._cycle_log: List[CycleEfficiency] = []
        self._metric_history: List[Dict[str, float]] = []
        self._replica_history: List[int] = []
        self._baseline_cpu_per_replica: Optional[float] = None

        # Tracking current efficiency state
        self._current_state: EfficiencyState = EfficiencyState.NEUTRAL
        self._consecutive_not_helping: int = 0


    def observe(
        self,
        cycle: int,
        metrics: Dict[str, float],
        replicas: int,
        delta: int,
        optimal_replicas: int = 0,
    ) -> CycleEfficiency:
        """Record one cycle of observation. Returns the cycle's classification.

        Called from the harness simulation loop AFTER the controller has
        acted and replicas have been updated. This is purely observational.
        """
        self._metric_history.append(dict(metrics))
        self._replica_history.append(replicas)

        cpu = metrics.get("cpu", 0.0)
        cpu_per_replica = cpu / max(1, replicas)
        latency = metrics.get("latency_p99", 0.0)
        error_rate = metrics.get("error_rate", 0.0)

        # Establish baseline from first few cycles
        if self._baseline_cpu_per_replica is None and len(self._metric_history) >= 3:
            baseline_cpus = []
            for i, m in enumerate(self._metric_history[:3]):
                r = self._replica_history[i]
                baseline_cpus.append(m.get("cpu", 0.0) / max(1, r))
            self._baseline_cpu_per_replica = sum(baseline_cpus) / len(baseline_cpus)

        # Track new scale-out events
        if delta > 0:
            prev_replicas = replicas - delta
            prev_metrics = (
                self._metric_history[-2] if len(self._metric_history) >= 2
                else metrics
            )
            event = ScaleOutEvent(
                cycle=cycle,
                delta=delta,
                replicas_before=prev_replicas,
                replicas_after=replicas,
                metrics_before=dict(prev_metrics),
            )
            self._events.append(event)

        # Evaluate pending events whose windows have closed
        for event in self._events:
            if event.evaluation_complete:
                continue
            cycles_since = cycle - event.cycle
            if cycles_since >= self.eval_window:
                self._evaluate_event(event, metrics, replicas)

        # Classify current cycle
        active_event = self._find_active_event(cycle)
        confidence = 0.0

        if active_event and active_event.evaluation_complete:
            self._current_state = active_event.state
            confidence = active_event.confidence
        elif active_event:
            # Still in evaluation window — tentative classification
            self._current_state = self._tentative_classify(
                active_event, metrics, replicas,
            )
            confidence = 0.3  # low confidence during eval window
        elif not self._events:
            self._current_state = EfficiencyState.NEUTRAL
            confidence = 0.5
        # else: carry forward previous state

        # Update consecutive counter
        if self._current_state == EfficiencyState.NOT_HELPING:
            self._consecutive_not_helping += 1
        else:
            self._consecutive_not_helping = 0

        entry = CycleEfficiency(
            cycle=cycle,
            replicas=replicas,
            cpu_per_replica=cpu_per_replica,
            latency=latency,
            error_rate=error_rate,
            state=self._current_state,
            confidence=confidence,
            active_event=active_event,
        )
        self._cycle_log.append(entry)
        return entry

    def _evaluate_event(
        self,
        event: ScaleOutEvent,
        current_metrics: Dict[str, float],
        current_replicas: int,
    ) -> None:
        """Evaluate a scale-out event after its window has closed."""
        event.evaluation_complete = True
        event.metrics_after = dict(current_metrics)

        before = event.metrics_before
        after = current_metrics

        # 1. Marginal CPU change: did CPU-per-replica decrease?
        cpu_before = before.get("cpu", 0.0) / max(1, event.replicas_before)
        cpu_after = after.get("cpu", 0.0) / max(1, current_replicas)
        event.marginal_cpu_change = cpu_before - cpu_after  # positive = improved

        # 2. Latency improvement
        lat_before = before.get("latency_p99", 0.0)
        lat_after = after.get("latency_p99", 0.0)
        event.latency_improvement = lat_before - lat_after  # positive = improved

        # 3. Error improvement
        err_before = before.get("error_rate", 0.0)
        err_after = after.get("error_rate", 0.0)
        event.error_improvement = err_before - err_after  # positive = improved

        # 4. Utilization efficiency
        if self._baseline_cpu_per_replica and self._baseline_cpu_per_replica > 0:
            event.utilization_efficiency = cpu_after / self._baseline_cpu_per_replica
        else:
            event.utilization_efficiency = 1.0

        # Classify the event
        improvements = 0
        degradations = 0

        if event.latency_improvement > self.latency_thresh:
            improvements += 2  # latency is high-signal
        elif event.latency_improvement < -self.latency_thresh:
            degradations += 1

        if event.error_improvement > self.error_thresh:
            improvements += 2  # errors are critical
        elif event.error_improvement < -self.error_thresh:
            degradations += 1

        if event.marginal_cpu_change > self.cpu_thresh:
            improvements += 1
        elif event.marginal_cpu_change < -self.cpu_thresh:
            degradations += 1

        if improvements >= 2:
            event.state = EfficiencyState.HELPING
            event.confidence = min(1.0, 0.5 + improvements * 0.15)
        elif improvements == 0 and degradations == 0:
            event.state = EfficiencyState.NEUTRAL
            event.confidence = 0.5
        elif degradations > improvements:
            event.state = EfficiencyState.NOT_HELPING
            event.confidence = min(1.0, 0.5 + degradations * 0.15)
        else:
            event.state = EfficiencyState.NEUTRAL
            event.confidence = 0.4

        # Low utilization is a strong NOT_HELPING signal
        if event.utilization_efficiency < 0.3 and event.state != EfficiencyState.HELPING:
            event.state = EfficiencyState.NOT_HELPING
            event.confidence = max(event.confidence, 0.7)

    def _tentative_classify(
        self,
        event: ScaleOutEvent,
        current_metrics: Dict[str, float],
        current_replicas: int,
    ) -> EfficiencyState:
        """Quick classification during the evaluation window."""
        before = event.metrics_before
        lat_before = before.get("latency_p99", 0.0)
        lat_after = current_metrics.get("latency_p99", 0.0)
        err_before = before.get("error_rate", 0.0)
        err_after = current_metrics.get("error_rate", 0.0)

        if (lat_before - lat_after) > self.latency_thresh * 2:
            return EfficiencyState.HELPING
        if (err_before - err_after) > self.error_thresh * 2:
            return EfficiencyState.HELPING

        cpu_per = current_metrics.get("cpu", 0.0) / max(1, current_replicas)
        if (self._baseline_cpu_per_replica
                and cpu_per < self._baseline_cpu_per_replica * 0.2):
            return EfficiencyState.NOT_HELPING

        return EfficiencyState.NEUTRAL

    def _find_active_event(self, cycle: int) -> Optional[ScaleOutEvent]:
        """Find the most recent scale-out event affecting this cycle."""
        for event in reversed(self._events):
            if event.cycle <= cycle <= event.cycle + self.eval_window + 5:
                return event
            if event.cycle < cycle - self.eval_window - 5:
                break
        # If no recent event, return the most recent evaluated one
        for event in reversed(self._events):
            if event.evaluation_complete:
                return event
        return None

    def summary(
        self,
        excess_cycles: Optional[List[int]] = None,
    ) -> EfficiencySummary:
        """Compute aggregate statistics.

        Args:
            excess_cycles: list of cycle indices where replicas > optimal
                (from cost classification). Used to measure overlap.
        """
        s = EfficiencySummary()

        # Event-level stats
        s.total_scale_outs = len(self._events)
        for event in self._events:
            if event.state == EfficiencyState.HELPING:
                s.helping_count += 1
            elif event.state == EfficiencyState.NOT_HELPING:
                s.not_helping_count += 1
            else:
                s.neutral_count += 1

        # Cycle-level stats
        s.total_cycles = len(self._cycle_log)
        for entry in self._cycle_log:
            if entry.state == EfficiencyState.HELPING:
                s.cycles_helping += 1
            elif entry.state == EfficiencyState.NOT_HELPING:
                s.cycles_not_helping += 1
            else:
                s.cycles_neutral += 1

        # Overlap with excess cost
        if excess_cycles is not None:
            excess_set = set(excess_cycles)
            s.total_excess_cycles = len(excess_set)
            not_helping_cycles = {
                e.cycle for e in self._cycle_log
                if e.state == EfficiencyState.NOT_HELPING
            }
            s.not_helping_during_excess = len(
                excess_set & not_helping_cycles
            )

        return s

    @property
    def events(self) -> List[ScaleOutEvent]:
        return list(self._events)

    @property
    def cycle_log(self) -> List[CycleEfficiency]:
        return list(self._cycle_log)

    @property
    def consecutive_not_helping(self) -> int:
        return self._consecutive_not_helping
