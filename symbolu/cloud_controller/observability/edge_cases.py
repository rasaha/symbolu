"""Edge Case Harness — systematic failure surface discovery for the scaling controller.

Covers 5 failure classes with 16 adversarial scenarios:

  A. Signal Path Failures (L0)
     1. delayed_metrics       — 60s metric lag
     2. noisy_spikes          — random false CPU bursts
     3. conflicting_signals   — CPU low but latency high

  B. Actuation Failures (L5)
     4. slow_provisioning     — node provisioning delay
     5. pod_scheduling_delay  — pods stuck Pending

  C. System Shock Events
     6. sudden_10x_spike      — instant 10x demand surge
     7. cascading_failure     — service A fails → latency everywhere

  D. Economic / External Interruptions
     8. spot_interruption     — node eviction mid-scale
     9. budget_cap            — hard replica ceiling hit

  E. Controller Internal Pathologies
     10. coherence_oscillation  — coherence flickers near threshold
     11. plasticity_stuck_low   — gate stays closed
     12. identity_drift         — baseline drifts incorrectly

  F. Misinterpretation of Reality (Tier 1)
     13. hidden_demand          — CPU metric missing, partial observability
     14. gradual_drift          — ultra-slow demand ramp, never a sharp threshold
     15. metric_corruption      — CPU frozen at stale value
     16. feedback_delay_loop    — actuation lag + backpressure causes over-scaling

  G. Behavioral Traps (Tier 2)
     17. partial_recovery       — demand spike→dip→spike, tests premature scale-in
     18. cold_start_amplification — high load from cycle 0, warmup phase problem
     19. policy_oscillation     — external budget cap alternates tight↔loose

Each scenario tracks internal controller state (C_t, P_t, D_t, A_t) and
classifies failures with root cause attribution. Results include a 5-level
severity index (CATASTROPHIC → SEVERE → MODERATE → MILD → PASS).

Usage:
    harness = EdgeCaseHarness()
    report = harness.run_all()
    print(report.format())
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from symbolu.cloud_controller.controller import Controller, ActionResult
from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.observability.benchmark import (
    _demand_to_metrics,
    _optimal_replicas,
    _score_run,
    BenchmarkConfig,
    ScenarioScore,
)


# ============================================================
# Failure Classification
# ============================================================

class FailureClass(Enum):
    SIGNAL_PATH = "signal_path"
    ACTUATION = "actuation"
    SYSTEM_SHOCK = "system_shock"
    EXTERNAL = "external"
    CONTROLLER_INTERNAL = "controller_internal"


class Severity(Enum):
    """Failure severity index — much more informative than binary pass/fail.

    Tracks the trajectory from catastrophic blind spot to bounded response.
    """
    PASS = "pass"                   # SLO < 20%, bounded overshoot, no pathologies
    MILD = "mild"                   # SLO 20-40%, low overshoot
    MODERATE = "moderate"           # SLO 40-60% or high overshoot, but reacts
    SEVERE = "severe"               # SLO 60-90%, delayed reaction
    CATASTROPHIC = "catastrophic"   # SLO > 90% or no reaction at all


class FailureAttribution(Enum):
    """Root cause label for every divergence or SLO breach."""
    SIGNAL_DELAY = "signal_delay"
    SIGNAL_NOISE = "signal_noise"
    SIGNAL_CONFLICT = "signal_conflict"
    SIGNAL_MISSING = "signal_missing"
    SIGNAL_CORRUPTION = "signal_corruption"
    ACTUATION_LAG = "actuation_lag"
    CAPACITY_EXHAUSTED = "capacity_exhausted"
    DEMAND_SHOCK = "demand_shock"
    CASCADE_FAILURE = "cascade_failure"
    RESOURCE_EVICTION = "resource_eviction"
    BUDGET_CONSTRAINT = "budget_constraint"
    COHERENCE_INSTABILITY = "coherence_instability"
    PLASTICITY_SUPPRESSION = "plasticity_suppression"
    IDENTITY_DRIFT = "identity_drift"
    CONTROLLER_SUPPRESSION = "controller_suppression"
    FEEDBACK_LOOP = "feedback_loop"
    GRADUAL_DRIFT = "gradual_drift"
    PREMATURE_SCALE_IN = "premature_scale_in"
    COLD_START = "cold_start"
    POLICY_OSCILLATION = "policy_oscillation"
    NONE = "none"


# ============================================================
# Internal State Snapshot
# ============================================================

@dataclass
class StateSnapshot:
    """Captures internal controller state at one cycle."""
    cycle: int
    demand: float
    action_score: float           # A_t
    pressure: float               # S_t
    coherence: float              # C_t
    plasticity: float             # P_t
    gain: float                   # G_t
    damping: float                # d_t
    identity_deviation: float
    replicas: int
    optimal_replicas: int
    delta: int
    recommendation: str

    @property
    def slo_breach(self) -> bool:
        return self.replicas < self.optimal_replicas

    @property
    def overshoot(self) -> int:
        return max(0, self.replicas - self.optimal_replicas)


@dataclass
class InternalStateTrace:
    """Full trace of internal state across a scenario."""
    snapshots: List[StateSnapshot] = field(default_factory=list)

    @property
    def coherence_mean(self) -> float:
        if not self.snapshots:
            return 0.0
        return sum(s.coherence for s in self.snapshots) / len(self.snapshots)

    @property
    def coherence_min(self) -> float:
        if not self.snapshots:
            return 0.0
        return min(s.coherence for s in self.snapshots)

    @property
    def plasticity_mean(self) -> float:
        if not self.snapshots:
            return 0.0
        return sum(s.plasticity for s in self.snapshots) / len(self.snapshots)

    @property
    def plasticity_min(self) -> float:
        if not self.snapshots:
            return 0.0
        return min(s.plasticity for s in self.snapshots)

    @property
    def damping_mean(self) -> float:
        if not self.snapshots:
            return 0.0
        return sum(s.damping for s in self.snapshots) / len(self.snapshots)

    @property
    def action_score_std(self) -> float:
        if len(self.snapshots) < 2:
            return 0.0
        vals = [s.action_score for s in self.snapshots]
        mean = sum(vals) / len(vals)
        return (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5

    @property
    def coherence_oscillation_count(self) -> int:
        """Count how many times coherence crosses 0.5 threshold."""
        crossings = 0
        for i in range(1, len(self.snapshots)):
            prev = self.snapshots[i - 1].coherence
            curr = self.snapshots[i].coherence
            if (prev < 0.5) != (curr < 0.5):
                crossings += 1
        return crossings

    @property
    def plasticity_stuck_cycles(self) -> int:
        """Cycles where plasticity was below 0.1 (effectively closed)."""
        return sum(1 for s in self.snapshots if s.plasticity < 0.1)

    @property
    def saturated_high_cycles(self) -> int:
        """Cycles where action score was saturated high (> 2.0)."""
        return sum(1 for s in self.snapshots if abs(s.action_score) > 2.0)

    @property
    def saturated_low_cycles(self) -> int:
        """Cycles where action score was near zero despite demand (< 0.01)."""
        return sum(
            1 for s in self.snapshots
            if abs(s.action_score) < 0.01 and s.demand > 0.5
        )

    def detect_pathologies(self) -> List[str]:
        """Detect internal pathologies in the trace."""
        issues = []
        n = len(self.snapshots)
        if n == 0:
            return issues

        if self.coherence_oscillation_count > n * 0.3:
            issues.append(
                f"coherence_unstable: {self.coherence_oscillation_count} "
                f"threshold crossings in {n} cycles"
            )

        if self.plasticity_stuck_cycles > n * 0.5:
            issues.append(
                f"plasticity_stuck: gate below 0.1 for "
                f"{self.plasticity_stuck_cycles}/{n} cycles"
            )

        if self.saturated_low_cycles > n * 0.3:
            issues.append(
                f"action_suppressed: near-zero output for "
                f"{self.saturated_low_cycles}/{n} cycles despite demand"
            )

        if self.saturated_high_cycles > n * 0.2:
            issues.append(
                f"action_saturated: score > 2.0 for "
                f"{self.saturated_high_cycles}/{n} cycles"
            )

        if self.damping_mean > 0.95:
            issues.append(
                f"damping_excessive: mean={self.damping_mean:.3f} "
                f"(controller is over-dampened)"
            )

        return issues


# ============================================================
# Perturbation Layer
# ============================================================

class Perturbation:
    """Base class for metric perturbations injected into scenarios."""

    def apply(
        self,
        metrics: Dict[str, float],
        cycle: int,
        total: int,
    ) -> Dict[str, float]:
        """Apply perturbation to metrics. Returns modified copy."""
        return dict(metrics)


class MetricDelay(Perturbation):
    """Simulate delayed metrics — values lag by N cycles."""

    def __init__(self, delay_cycles: int = 4):
        self.delay_cycles = delay_cycles
        self._buffer: List[Dict[str, float]] = []

    def apply(self, metrics, cycle, total):
        self._buffer.append(dict(metrics))
        if len(self._buffer) <= self.delay_cycles:
            # During initial delay, return baseline values
            return {k: 0.3 for k in metrics}
        return dict(self._buffer[-self.delay_cycles - 1])


class NoisySpikes(Perturbation):
    """Inject random false CPU bursts."""

    def __init__(
        self,
        spike_probability: float = 0.15,
        spike_magnitude: float = 0.8,
        seed: int = 42,
    ):
        self.spike_prob = spike_probability
        self.spike_mag = spike_magnitude
        self._rng = random.Random(seed)

    def apply(self, metrics, cycle, total):
        result = dict(metrics)
        if self._rng.random() < self.spike_prob:
            result["cpu"] = min(1.0, result["cpu"] + self.spike_mag)
        return result


class ConflictingSignals(Perturbation):
    """Make CPU and latency disagree — CPU low while latency high."""

    def __init__(self, conflict_start_frac: float = 0.3, conflict_end_frac: float = 0.7):
        self.start_frac = conflict_start_frac
        self.end_frac = conflict_end_frac

    def apply(self, metrics, cycle, total):
        result = dict(metrics)
        frac = cycle / max(1, total - 1)
        if self.start_frac <= frac <= self.end_frac:
            # CPU stays low, but latency spikes
            result["cpu"] = 0.2
            result["latency_p99"] = 0.9
            result["error_rate"] = 0.3
        return result


class ActuationDelay(Perturbation):
    """Simulate slow node provisioning — deltas take effect N cycles late."""

    def __init__(self, lag_cycles: int = 5):
        self.lag_cycles = lag_cycles
        self._pending_deltas: List[Tuple[int, int]] = []

    def get_effective_delta(self, raw_delta: int, cycle: int) -> int:
        """Queue delta, return any that have matured."""
        if raw_delta != 0:
            self._pending_deltas.append((cycle + self.lag_cycles, raw_delta))

        effective = 0
        remaining = []
        for ready_at, d in self._pending_deltas:
            if cycle >= ready_at:
                effective += d
            else:
                remaining.append((ready_at, d))
        self._pending_deltas = remaining
        return effective


class SpotEviction(Perturbation):
    """Simulate spot instance eviction — randomly lose replicas."""

    def __init__(
        self,
        eviction_probability: float = 0.05,
        max_evicted: int = 2,
        seed: int = 99,
    ):
        self.eviction_prob = eviction_probability
        self.max_evicted = max_evicted
        self._rng = random.Random(seed)

    def get_eviction(self, current_replicas: int) -> int:
        """Return number of replicas to evict (0 if no eviction)."""
        if self._rng.random() < self.eviction_prob:
            return min(
                self._rng.randint(1, self.max_evicted),
                max(0, current_replicas - 1),  # never evict below 1
            )
        return 0


class BudgetCap(Perturbation):
    """Hard ceiling on replicas simulating budget/quota limits."""

    def __init__(self, max_replicas: int = 8):
        self.max_replicas = max_replicas

    def cap(self, replicas: int) -> int:
        return min(replicas, self.max_replicas)


class MissingSignal(Perturbation):
    """Drop one or more metric keys entirely — simulates partial observability.

    Real-world cause: exporter crash, metric rename, network partition to
    a specific scrape target. The controller sees a subset of signals and
    must decide whether to act on incomplete information.
    """

    def __init__(self, missing_keys: List[str], start_frac: float = 0.2, end_frac: float = 0.8):
        self.missing_keys = missing_keys
        self.start_frac = start_frac
        self.end_frac = end_frac

    def apply(self, metrics, cycle, total):
        result = dict(metrics)
        frac = cycle / max(1, total - 1)
        if self.start_frac <= frac <= self.end_frac:
            for key in self.missing_keys:
                result.pop(key, None)
        return result


class StuckMetric(Perturbation):
    """Freeze a metric at a stale value — simulates metric corruption.

    Real-world cause: counter reset missed, exporter caching stale value,
    Prometheus staleness not triggering. The controller sees a plausible
    but wrong value and may base decisions on it.
    """

    def __init__(self, stuck_key: str, stuck_value: float, start_frac: float = 0.3):
        self.stuck_key = stuck_key
        self.stuck_value = stuck_value
        self.start_frac = start_frac

    def apply(self, metrics, cycle, total):
        result = dict(metrics)
        frac = cycle / max(1, total - 1)
        if frac >= self.start_frac and self.stuck_key in result:
            result[self.stuck_key] = self.stuck_value
        return result


class FeedbackAmplifier(Perturbation):
    """Simulate feedback delay loop — scaling actions take effect late,
    causing the controller to issue duplicate scale-ups.

    Combines actuation delay with a demand pattern that reacts to replica
    count: when replicas are insufficient, demand metrics stay elevated
    (backpressure), causing the controller to keep scaling even after
    sufficient capacity was already requested.
    """

    def __init__(self, lag_cycles: int = 8, backpressure_factor: float = 0.3):
        self.lag_cycles = lag_cycles
        self.backpressure_factor = backpressure_factor
        self._actuation = ActuationDelay(lag_cycles=lag_cycles)

    def get_effective_delta(self, raw_delta: int, cycle: int) -> int:
        return self._actuation.get_effective_delta(raw_delta, cycle)

    def apply(self, metrics, cycle, total):
        """Add backpressure: if demand is high, latency stays elevated
        regardless of what the controller has decided (because capacity
        hasn't arrived yet)."""
        result = dict(metrics)
        # Amplify latency by backpressure factor during high demand
        if result.get("cpu", 0) > 0.6:
            result["latency_p99"] = min(
                1.0,
                result.get("latency_p99", 0.5) + self.backpressure_factor,
            )
            result["error_rate"] = min(
                1.0,
                result.get("error_rate", 0.0) + self.backpressure_factor * 0.5,
            )
        return result


class AlternatingBudgetCap(Perturbation):
    """Simulate policy oscillation — budget cap alternates between tight and loose.

    Real-world cause: cost optimization system periodically tightens limits,
    then a different system relaxes them. The controller sees capacity
    appearing and disappearing due to external policy, not demand.
    """

    def __init__(self, tight_cap: int = 4, loose_cap: int = 15, switch_interval: int = 25):
        self.tight_cap = tight_cap
        self.loose_cap = loose_cap
        self.switch_interval = switch_interval

    def cap(self, replicas: int, cycle: int) -> int:
        phase = (cycle // self.switch_interval) % 2
        limit = self.tight_cap if phase == 0 else self.loose_cap
        return min(replicas, limit)


# ============================================================
# Edge Case Scenario Definitions
# ============================================================

@dataclass
class EdgeScenario:
    """Definition of one edge case scenario."""
    name: str
    failure_class: FailureClass
    description: str
    demand_fn: Callable[[int, int], float]
    perturbations: List[Perturbation] = field(default_factory=list)
    actuation_delay: Optional[ActuationDelay] = None
    spot_eviction: Optional[SpotEviction] = None
    budget_cap: Optional[BudgetCap] = None
    alternating_budget_cap: Optional[AlternatingBudgetCap] = None
    controller_config: Optional[InfraControllerConfig] = None
    expected_attribution: FailureAttribution = FailureAttribution.NONE


def _demand_plateau_then_spike(cycle: int, total: int) -> float:
    """Baseline 0.3, then 10x spike at 40%."""
    if cycle < int(total * 0.4):
        return 0.3
    elif cycle < int(total * 0.5):
        return 1.0  # 10x relative to baseline 0.1 → capped at 1.0
    else:
        return 0.5  # settles to moderate


def _demand_cascading(cycle: int, total: int) -> float:
    """Starts stable, then slow latency ramp simulating cascade."""
    return 0.4  # demand itself is stable — perturbation injects latency


def _demand_steady_moderate(cycle: int, total: int) -> float:
    """Steady moderate load — tests controller internal behavior."""
    return 0.5


def _demand_oscillating_moderate(cycle: int, total: int) -> float:
    """Gentle oscillation to probe coherence threshold."""
    return 0.5 + 0.15 * math.sin(2 * math.pi * cycle / 20)


def _demand_ramp_sustained(cycle: int, total: int) -> float:
    """Ramp up then sustained — tests identity drift."""
    frac = cycle / max(1, total - 1)
    if frac < 0.3:
        return 0.3
    elif frac < 0.5:
        # Ramp from 0.3 to 0.8
        return 0.3 + 0.5 * ((frac - 0.3) / 0.2)
    else:
        return 0.8


def _demand_gradual_drift(cycle: int, total: int) -> float:
    """Ultra-slow linear ramp — 0.25 to 0.85 over the full run.

    The rate of change per cycle is so small (~0.003) that it never
    crosses a sharp threshold. Tests whether the controller detects
    slow drift or boils like a frog.
    """
    frac = cycle / max(1, total - 1)
    return 0.25 + 0.6 * frac


def _demand_feedback_surge(cycle: int, total: int) -> float:
    """Demand pattern for feedback delay loop scenario.

    Stable baseline, then a sharp rise that stays elevated — the
    controller should scale once, but with long actuation delay it
    may over-issue scale-ups before previous ones land.
    """
    frac = cycle / max(1, total - 1)
    if frac < 0.2:
        return 0.3
    elif frac < 0.3:
        # Sharp ramp
        return 0.3 + 0.6 * ((frac - 0.2) / 0.1)
    else:
        return 0.9  # Stays high until capacity catches up


def _demand_partial_recovery(cycle: int, total: int) -> float:
    """Demand spikes, partially recovers, then spikes again.

    Tests whether the controller misreads a temporary dip as true
    stabilization and scales in prematurely, only to be caught by
    the second spike.
    """
    frac = cycle / max(1, total - 1)
    if frac < 0.15:
        return 0.3             # Baseline
    elif frac < 0.25:
        return 0.9             # First spike
    elif frac < 0.40:
        return 0.5             # Partial recovery (NOT back to baseline)
    elif frac < 0.55:
        return 0.9             # Second spike — are we still scaled?
    elif frac < 0.70:
        return 0.45            # Second partial recovery
    elif frac < 0.80:
        return 0.85            # Third spike
    else:
        return 0.3             # Final cooldown


def _demand_cold_start(cycle: int, total: int) -> float:
    """Demand is high from cycle 0 — no warmup period.

    Tests whether the controller can act immediately without a
    learning phase, or if the warmup period causes catastrophic
    SLO breaches during initial load.
    """
    frac = cycle / max(1, total - 1)
    if frac < 0.1:
        return 0.85            # High from the start
    elif frac < 0.3:
        return 0.9             # Stays high
    elif frac < 0.5:
        return 0.6             # Moderate dip
    else:
        return 0.8             # Returns to high


def _demand_policy_oscillation(cycle: int, total: int) -> float:
    """Steady moderate demand — the oscillation comes from policy layer.

    The BudgetCap alternates between tight and relaxed limits,
    simulating a policy layer that keeps changing its mind (e.g.,
    cost optimization system fighting the scaling controller).
    """
    return 0.7  # Constant moderate demand


def _demand_hidden_pressure(cycle: int, total: int) -> float:
    """Demand rises while key metric (CPU) is invisible.

    Latency and queue depth climb but CPU signal is missing — the
    controller must decide without its primary infrastructure signal.
    """
    frac = cycle / max(1, total - 1)
    if frac < 0.25:
        return 0.3
    elif frac < 0.5:
        return 0.3 + 0.5 * ((frac - 0.25) / 0.25)
    else:
        return 0.8


class _CascadePerturb(Perturbation):
    """Inject cascading latency failure — CPU stays fine, latency climbs."""

    def apply(self, metrics, cycle, total):
        result = dict(metrics)
        frac = cycle / max(1, total - 1)
        if frac > 0.3:
            severity = min(1.0, (frac - 0.3) * 2.0)
            result["latency_p99"] = min(1.0, 0.2 + severity * 0.8)
            result["error_rate"] = min(1.0, severity * 0.4)
            # CPU stays normal — that's the trap
            result["cpu"] = 0.35
        return result


def build_edge_scenarios() -> List[EdgeScenario]:
    """Build the 12 canonical edge case scenarios."""
    scenarios = []

    # --- A. Signal Path Failures ---

    # 1. Delayed metrics (60s lag = 4 cycles at 15s interval)
    scenarios.append(EdgeScenario(
        name="delayed_metrics",
        failure_class=FailureClass.SIGNAL_PATH,
        description="Metrics arrive 60s late — controller sees stale data",
        demand_fn=_demand_plateau_then_spike,
        perturbations=[MetricDelay(delay_cycles=4)],
        expected_attribution=FailureAttribution.SIGNAL_DELAY,
    ))

    # 2. Noisy spikes — random false CPU bursts
    scenarios.append(EdgeScenario(
        name="noisy_spikes",
        failure_class=FailureClass.SIGNAL_PATH,
        description="15% of cycles have false CPU spikes — tests damping",
        demand_fn=_demand_steady_moderate,
        perturbations=[NoisySpikes(spike_probability=0.15, spike_magnitude=0.6)],
        expected_attribution=FailureAttribution.SIGNAL_NOISE,
    ))

    # 3. Conflicting signals — CPU low but latency/errors high
    scenarios.append(EdgeScenario(
        name="conflicting_signals",
        failure_class=FailureClass.SIGNAL_PATH,
        description="CPU stays low while latency and errors spike — tests coherence",
        demand_fn=_demand_steady_moderate,
        perturbations=[ConflictingSignals()],
        expected_attribution=FailureAttribution.SIGNAL_CONFLICT,
    ))

    # --- B. Actuation Failures ---

    # 4. Slow node provisioning — 5 cycle delay
    scenarios.append(EdgeScenario(
        name="slow_provisioning",
        failure_class=FailureClass.ACTUATION,
        description="Scaling actions take 5 cycles to materialize",
        demand_fn=_demand_plateau_then_spike,
        actuation_delay=ActuationDelay(lag_cycles=5),
        expected_attribution=FailureAttribution.ACTUATION_LAG,
    ))

    # 5. Pod scheduling delay — 3 cycle delay
    scenarios.append(EdgeScenario(
        name="pod_scheduling_delay",
        failure_class=FailureClass.ACTUATION,
        description="Pods take 3 cycles to become ready",
        demand_fn=_demand_ramp_sustained,
        actuation_delay=ActuationDelay(lag_cycles=3),
        expected_attribution=FailureAttribution.ACTUATION_LAG,
    ))

    # --- C. System Shock Events ---

    # 6. Sudden 10x spike
    scenarios.append(EdgeScenario(
        name="sudden_10x_spike",
        failure_class=FailureClass.SYSTEM_SHOCK,
        description="Instant 10x demand surge — tests reaction without overshoot",
        demand_fn=_demand_plateau_then_spike,
        expected_attribution=FailureAttribution.DEMAND_SHOCK,
    ))

    # 7. Cascading failure — service A fails → latency everywhere
    scenarios.append(EdgeScenario(
        name="cascading_failure",
        failure_class=FailureClass.SYSTEM_SHOCK,
        description="CPU normal but latency climbs due to upstream failure",
        demand_fn=_demand_cascading,
        perturbations=[_CascadePerturb()],
        expected_attribution=FailureAttribution.CASCADE_FAILURE,
    ))

    # --- D. Economic / External ---

    # 8. Spot instance eviction
    scenarios.append(EdgeScenario(
        name="spot_interruption",
        failure_class=FailureClass.EXTERNAL,
        description="5% chance per cycle of losing 1-2 replicas to spot eviction",
        demand_fn=_demand_ramp_sustained,
        spot_eviction=SpotEviction(eviction_probability=0.05, max_evicted=2),
        expected_attribution=FailureAttribution.RESOURCE_EVICTION,
    ))

    # 9. Budget cap — hard ceiling
    scenarios.append(EdgeScenario(
        name="budget_cap",
        failure_class=FailureClass.EXTERNAL,
        description="Max 8 replicas regardless of demand — tests graceful degradation",
        demand_fn=_demand_plateau_then_spike,
        budget_cap=BudgetCap(max_replicas=8),
        expected_attribution=FailureAttribution.BUDGET_CONSTRAINT,
    ))

    # --- E. Controller Internal Pathologies ---

    # 10. Coherence oscillation near threshold
    scenarios.append(EdgeScenario(
        name="coherence_oscillation",
        failure_class=FailureClass.CONTROLLER_INTERNAL,
        description="Demand oscillates to keep coherence flickering near 0.5 threshold",
        demand_fn=_demand_oscillating_moderate,
        perturbations=[ConflictingSignals(conflict_start_frac=0.2, conflict_end_frac=0.4)],
        expected_attribution=FailureAttribution.COHERENCE_INSTABILITY,
    ))

    # 11. Plasticity stuck low — high k_r + turbulent signals
    cfg_stuck = _tuned_config()
    cfg_stuck.k_r = 8.0    # Very high resistance scaling → suppresses gate
    cfg_stuck.b_p = -3.0   # Very low bias floor
    scenarios.append(EdgeScenario(
        name="plasticity_stuck_low",
        failure_class=FailureClass.CONTROLLER_INTERNAL,
        description="Plasticity gate stuck near zero due to tuning — controller paralyzed",
        demand_fn=_demand_ramp_sustained,
        controller_config=cfg_stuck,
        expected_attribution=FailureAttribution.PLASTICITY_SUPPRESSION,
    ))

    # 12. Identity drift — gradual regime change
    cfg_drift = _tuned_config()
    cfg_drift.alpha_base = 0.2  # Very fast EMA → identity baseline chases signal
    scenarios.append(EdgeScenario(
        name="identity_drift",
        failure_class=FailureClass.CONTROLLER_INTERNAL,
        description="Fast identity EMA causes baseline to chase demand, suppressing response",
        demand_fn=_demand_ramp_sustained,
        controller_config=cfg_drift,
        expected_attribution=FailureAttribution.IDENTITY_DRIFT,
    ))

    # --- F. Misinterpretation of Reality (Tier 1) ---

    # 13. Hidden demand / missing signal — CPU metric disappears
    scenarios.append(EdgeScenario(
        name="hidden_demand",
        failure_class=FailureClass.SIGNAL_PATH,
        description="CPU metric missing — controller sees latency/errors but not root cause",
        demand_fn=_demand_hidden_pressure,
        perturbations=[MissingSignal(missing_keys=["cpu"], start_frac=0.2, end_frac=0.8)],
        expected_attribution=FailureAttribution.SIGNAL_MISSING,
    ))

    # 14. Gradual drift — demand creeps up below detection threshold
    scenarios.append(EdgeScenario(
        name="gradual_drift",
        failure_class=FailureClass.SIGNAL_PATH,
        description="Ultra-slow demand ramp — 0.003/cycle, never a sharp threshold cross",
        demand_fn=_demand_gradual_drift,
        expected_attribution=FailureAttribution.GRADUAL_DRIFT,
    ))

    # 15. Metric corruption — CPU frozen at stale 0.3 while real demand is 0.9
    scenarios.append(EdgeScenario(
        name="metric_corruption",
        failure_class=FailureClass.SIGNAL_PATH,
        description="CPU metric frozen at 0.3 while real demand climbs — stale exporter cache",
        demand_fn=_demand_ramp_sustained,
        perturbations=[StuckMetric(stuck_key="cpu", stuck_value=0.3, start_frac=0.3)],
        expected_attribution=FailureAttribution.SIGNAL_CORRUPTION,
    ))

    # 16. Feedback delay loop — long actuation lag causes over-scaling
    fb = FeedbackAmplifier(lag_cycles=8, backpressure_factor=0.3)
    scenarios.append(EdgeScenario(
        name="feedback_delay_loop",
        failure_class=FailureClass.ACTUATION,
        description="8-cycle actuation lag + backpressure amplification — controller over-issues",
        demand_fn=_demand_feedback_surge,
        perturbations=[fb],
        actuation_delay=fb._actuation,  # share the same delay queue
        expected_attribution=FailureAttribution.FEEDBACK_LOOP,
    ))

    # --- G. Tier 2: Behavioral Traps ---

    # 17. Partial recovery trap — demand dips then re-spikes
    scenarios.append(EdgeScenario(
        name="partial_recovery",
        failure_class=FailureClass.SYSTEM_SHOCK,
        description="Demand spike→dip→spike: tests premature scale-in during false recovery",
        demand_fn=_demand_partial_recovery,
        expected_attribution=FailureAttribution.PREMATURE_SCALE_IN,
    ))

    # 18. Cold start amplification — high load from cycle 0
    scenarios.append(EdgeScenario(
        name="cold_start_amplification",
        failure_class=FailureClass.CONTROLLER_INTERNAL,
        description="High demand from cycle 0 — warmup phase causes SLO breaches",
        demand_fn=_demand_cold_start,
        expected_attribution=FailureAttribution.COLD_START,
    ))

    # 19. Policy-induced oscillation — external cap alternates tight/loose
    scenarios.append(EdgeScenario(
        name="policy_oscillation",
        failure_class=FailureClass.EXTERNAL,
        description="Budget cap alternates 4↔15 every 25 cycles — controller fights policy layer",
        demand_fn=_demand_policy_oscillation,
        alternating_budget_cap=AlternatingBudgetCap(
            tight_cap=4, loose_cap=15, switch_interval=25,
        ),
        expected_attribution=FailureAttribution.POLICY_OSCILLATION,
    ))

    return scenarios


# ============================================================
# Edge Case Result
# ============================================================

@dataclass
class EdgeCaseResult:
    """Result of running one edge case scenario."""
    scenario: EdgeScenario
    score: ScenarioScore
    state_trace: InternalStateTrace
    attribution: FailureAttribution
    pathologies: List[str] = field(default_factory=list)
    breach_attributions: Dict[str, int] = field(default_factory=dict)

    @property
    def severity(self) -> Severity:
        """Classify failure severity — much richer than binary pass/fail.

        Levels:
          CATASTROPHIC: no reaction (react=max) OR SLO > 90%
          SEVERE:       SLO 60-90% or reaction_time > 60% of cycles
          MODERATE:     SLO 40-60% or overshoot > 20, but does react
          MILD:         SLO 20-40%, bounded overshoot, some pathologies OK
          PASS:         SLO < 20%, low overshoot, no pathologies
        """
        slo = self.score.slo_breach_rate
        react = self.score.reaction_time
        total = self.score.total_cycles
        overshoot = self.score.overshoot

        # Catastrophic: blind — no reaction or near-total SLO failure
        if react >= total or slo > 0.90:
            return Severity.CATASTROPHIC

        # Severe: very late or mostly breaching
        if slo > 0.60 or react > total * 0.6:
            return Severity.SEVERE

        # Moderate: reacts but with significant breaches or overshoot
        if slo > 0.40 or overshoot > 20:
            return Severity.MODERATE

        # Mild: reacts with bounded issues
        if slo > 0.20 or len(self.pathologies) > 0 or self.score.oscillation_count > 10:
            return Severity.MILD

        return Severity.PASS

    @property
    def passed(self) -> bool:
        """Did the controller handle this edge case acceptably?"""
        return self.severity in (Severity.PASS, Severity.MILD)


@dataclass
class EdgeCaseReport:
    """Complete edge case test results."""
    results: List[EdgeCaseResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return len(self.results) - self.passed

    def format(self) -> str:
        lines = [
            "=" * 90,
            "EDGE CASE HARNESS — FAILURE SURFACE ANALYSIS",
            "=" * 90,
            "",
        ]

        # Group by failure class
        by_class: Dict[FailureClass, List[EdgeCaseResult]] = {}
        for r in self.results:
            cls = r.scenario.failure_class
            by_class.setdefault(cls, []).append(r)

        for cls in FailureClass:
            if cls not in by_class:
                continue
            lines.append(f"  [{cls.value.upper()}]")
            lines.append("")

            for r in by_class[cls]:
                sev = r.severity.value.upper()
                status = f"{'PASS' if r.passed else 'FAIL'}/{sev:12s}"
                lines.append(f"    {status}  {r.scenario.name}")
                lines.append(f"         {r.scenario.description}")
                lines.append(
                    f"         react={r.score.reaction_time:3d} "
                    f"settle={r.score.settling_time:3d} "
                    f"overshoot={r.score.overshoot:+d} "
                    f"osc={r.score.oscillation_count:2d} "
                    f"slo={r.score.slo_breach_rate:.0%} "
                    f"cost={r.score.cost_efficiency:.2f}x"
                )

                # Internal state summary
                trace = r.state_trace
                lines.append(
                    f"         C_t: mean={trace.coherence_mean:.3f} "
                    f"min={trace.coherence_min:.3f} "
                    f"crossings={trace.coherence_oscillation_count}"
                )
                lines.append(
                    f"         P_t: mean={trace.plasticity_mean:.3f} "
                    f"min={trace.plasticity_min:.3f} "
                    f"stuck={trace.plasticity_stuck_cycles}"
                )
                lines.append(
                    f"         D_t: mean={trace.damping_mean:.3f}  "
                    f"A_t: std={trace.action_score_std:.4f}"
                )

                # Attribution
                lines.append(
                    f"         attribution: {r.attribution.value}"
                )

                # Pathologies
                if r.pathologies:
                    for p in r.pathologies:
                        lines.append(f"         !! {p}")

                lines.append("")

        # Summary
        lines.append("  " + "-" * 60)
        lines.append(
            f"  TOTAL: {self.passed}/{len(self.results)} passed, "
            f"{self.failed} failed"
        )

        # Severity distribution
        sev_counts: Dict[str, int] = {}
        for r in self.results:
            sev_counts[r.severity.value] = sev_counts.get(r.severity.value, 0) + 1
        lines.append("")
        lines.append("  SEVERITY DISTRIBUTION:")
        for sev in Severity:
            count = sev_counts.get(sev.value, 0)
            bar = "#" * count
            lines.append(f"    {sev.value:14s}  {count:2d}  {bar}")

        # Failure attribution breakdown
        attr_counts: Dict[str, int] = {}
        for r in self.results:
            if not r.passed:
                attr_counts[r.attribution.value] = (
                    attr_counts.get(r.attribution.value, 0) + 1
                )
        if attr_counts:
            lines.append("")
            lines.append("  FAILURE ATTRIBUTION:")
            for attr, count in sorted(attr_counts.items(), key=lambda x: -x[1]):
                lines.append(f"    {attr:30s}  {count}")

        lines.append("")
        lines.append("=" * 90)
        return "\n".join(lines)


# ============================================================
# Edge Case Harness
# ============================================================

def _tuned_config() -> InfraControllerConfig:
    """Return a tuned controller config for edge case testing.

    Uses the 'combined_moderate' profile from the parameter sweep —
    lower action thresholds that match the pressure range the test
    demand patterns produce. Without this, the default thresholds
    (scale_1=0.5) are unreachable for realistic pressure values (~0.17),
    and ALL scenarios would fail regardless of the perturbation.
    """
    cfg = InfraControllerConfig()
    cfg.action_thresholds = {
        "no_action": 0.02,
        "recommend": 0.05,
        "scale_1": 0.10,
        "scale_2": 0.30,
    }
    cfg.G_base = 1.5
    cfg.k_dv = 0.5
    cfg.warmup_steps = 30     # Faster warmup for test scenarios
    cfg.damping_warmup_steps = 15
    return cfg


class EdgeCaseHarness:
    """Runs the controller through adversarial edge case scenarios,
    tracking internal state and attributing failures.

    Uses a tuned controller config by default so scenarios test real
    failure modes (signal corruption, actuation lag, eviction) rather
    than threshold calibration.

    Usage:
        harness = EdgeCaseHarness()
        report = harness.run_all()
        print(report.format())
    """

    def __init__(
        self,
        cycles_per_scenario: int = 200,
        warmup_cycles: int = 40,
        base_replicas: int = 5,
        default_config: Optional[InfraControllerConfig] = None,
    ):
        self.cycles = cycles_per_scenario
        self.warmup = warmup_cycles
        self.base_replicas = base_replicas
        self.default_config = default_config or _tuned_config()

    def run_all(
        self,
        scenarios: Optional[List[EdgeScenario]] = None,
    ) -> EdgeCaseReport:
        """Run all (or selected) edge case scenarios."""
        if scenarios is None:
            scenarios = build_edge_scenarios()

        report = EdgeCaseReport()
        for scenario in scenarios:
            result = self.run_scenario(scenario)
            report.results.append(result)
        return report

    def run_scenario(self, scenario: EdgeScenario) -> EdgeCaseResult:
        """Run one edge case scenario with full state tracking."""
        cfg = scenario.controller_config or self.default_config
        ctrl = Controller(cfg)

        replicas = self.base_replicas
        replica_history: List[int] = []
        delta_history: List[int] = []
        demand_trace: List[float] = []
        state_trace = InternalStateTrace()

        # Generate demand trace
        for i in range(self.cycles):
            demand_trace.append(scenario.demand_fn(i, self.cycles))

        # Warmup with baseline
        baseline = demand_trace[0] if demand_trace else 0.3
        for _ in range(self.warmup):
            metrics = _demand_to_metrics(baseline)
            ctrl.step(metrics=metrics, current_replicas=replicas)

        # Run scenario
        for cycle_idx, demand in enumerate(demand_trace):
            # Generate base metrics from demand
            metrics = _demand_to_metrics(demand)

            # Apply perturbations
            for perturb in scenario.perturbations:
                metrics = perturb.apply(metrics, cycle_idx, self.cycles)

            # Step the controller
            result = ctrl.step(metrics=metrics, current_replicas=replicas)
            raw_delta = result.replica_delta

            # Apply actuation delay if present
            if scenario.actuation_delay is not None:
                effective_delta = scenario.actuation_delay.get_effective_delta(
                    raw_delta, cycle_idx,
                )
            else:
                effective_delta = raw_delta

            # Apply spot eviction
            if scenario.spot_eviction is not None:
                evicted = scenario.spot_eviction.get_eviction(replicas)
                replicas = max(1, replicas - evicted)

            # Apply delta
            replicas = max(1, replicas + effective_delta)

            # Apply budget cap
            if scenario.budget_cap is not None:
                replicas = scenario.budget_cap.cap(replicas)
            if scenario.alternating_budget_cap is not None:
                replicas = scenario.alternating_budget_cap.cap(replicas, cycle_idx)

            replica_history.append(replicas)
            delta_history.append(raw_delta)

            # Record internal state
            optimal = _optimal_replicas(demand, self.base_replicas)
            state_trace.snapshots.append(StateSnapshot(
                cycle=cycle_idx,
                demand=demand,
                action_score=result.action_score,
                pressure=result.pressure,
                coherence=result.coherence.coherence,
                plasticity=result.plasticity.plasticity,
                gain=result.gain.gain,
                damping=result.damping.damping,
                identity_deviation=result.identity_deviation,
                replicas=replicas,
                optimal_replicas=optimal,
                delta=raw_delta,
                recommendation=result.recommendation,
            ))

        # Score
        score = _score_run(
            scenario.name, "controller",
            replica_history, delta_history, demand_trace,
            self.base_replicas,
        )

        # Detect pathologies
        pathologies = state_trace.detect_pathologies()

        # Attribute root cause
        attribution = self._attribute_failure(scenario, score, state_trace)

        return EdgeCaseResult(
            scenario=scenario,
            score=score,
            state_trace=state_trace,
            attribution=attribution,
            pathologies=pathologies,
        )

    def _attribute_failure(
        self,
        scenario: EdgeScenario,
        score: ScenarioScore,
        trace: InternalStateTrace,
    ) -> FailureAttribution:
        """Classify the root cause of any failures in this scenario.

        Attribution logic:
          1. If scenario has an expected attribution and controller struggled, use it
          2. Otherwise, inspect internal state to determine cause
        """
        has_issues = (
            score.slo_breach_rate > 0.1
            or score.oscillation_count > 10
            or len(trace.detect_pathologies()) > 0
        )

        if not has_issues:
            return FailureAttribution.NONE

        # Check internal pathologies first
        if trace.plasticity_stuck_cycles > len(trace.snapshots) * 0.4:
            return FailureAttribution.PLASTICITY_SUPPRESSION

        if trace.coherence_oscillation_count > len(trace.snapshots) * 0.25:
            return FailureAttribution.COHERENCE_INSTABILITY

        if trace.saturated_low_cycles > len(trace.snapshots) * 0.3:
            return FailureAttribution.CONTROLLER_SUPPRESSION

        # Fall back to scenario's expected attribution
        return scenario.expected_attribution
