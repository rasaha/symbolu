"""Benchmark Harness — validates the scaling controller against canonical traffic patterns.

Runs the controller through synthetic load scenarios, simulates a basic HPA
for head-to-head comparison, and scores both on industry-standard metrics:

  - Reaction time: cycles until first scaling action after demand change
  - Overshoot: max excess replicas beyond demand-optimal
  - Settling time: cycles until replicas stabilize within ±1 of optimal
  - Oscillation count: direction reversals in scaling actions
  - Cost efficiency: replica-cycles vs demand-optimal (lower = less waste)
  - SLO breaches: cycles where capacity < demand (under-provisioned)

Traffic patterns:
  - Step: sudden 3x spike, hold, drop back
  - Ramp: linear increase over N cycles
  - Sinusoidal: periodic daily load pattern
  - Spike: burst then immediate drop (tests overshoot)
  - Oscillating: rapid alternating high/low (tests damping)
  - Plateau: baseline → new steady-state at different level

Usage:
    harness = BenchmarkHarness()
    report = harness.run_all()
    print(report.format())
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from symbolu.cloud_controller.controller import Controller, ActionResult
from symbolu.cloud_controller.config import InfraControllerConfig


# ============================================================
# Traffic Patterns
# ============================================================

class PatternType(Enum):
    STEP = "step"
    RAMP = "ramp"
    SINUSOIDAL = "sinusoidal"
    SPIKE = "spike"
    OSCILLATING = "oscillating"
    PLATEAU = "plateau"


def _demand_to_metrics(demand: float) -> Dict[str, float]:
    """Convert a scalar demand level [0,1] to a metrics dict.

    Demand drives all metrics proportionally — cpu and latency respond
    most directly, error_rate only rises above 0.7 demand (capacity stress),
    queue_depth tracks demand linearly.
    """
    d = max(0.0, min(1.0, demand))
    return {
        "cpu": d,
        "memory": d * 0.7 + 0.1,  # memory lags CPU
        "latency_p99": min(1.0, d * 0.8 + 0.05),
        "error_rate": max(0.0, (d - 0.7) * 2.0),  # errors spike above 70%
        "queue_depth": d * 0.9,
    }


def _optimal_replicas(demand: float, base_replicas: int) -> int:
    """Oracle: how many replicas should exist for this demand level.

    Simple model: replicas scale linearly with demand, with base_replicas
    handling demand=0.5 (the midpoint).
    """
    ratio = demand / 0.5 if demand > 0.0 else 0.5
    return max(1, round(base_replicas * ratio))


def pattern_step(cycle: int, total: int) -> float:
    """Sudden 3x spike at 1/3, drop back at 2/3."""
    if cycle < total // 3:
        return 0.3
    elif cycle < 2 * total // 3:
        return 0.9
    else:
        return 0.3


def pattern_ramp(cycle: int, total: int) -> float:
    """Linear increase from 0.2 to 0.9."""
    return 0.2 + 0.7 * (cycle / max(1, total - 1))


def pattern_sinusoidal(cycle: int, total: int) -> float:
    """Full sine wave: baseline 0.5 with amplitude 0.35."""
    return 0.5 + 0.35 * math.sin(2 * math.pi * cycle / total)


def pattern_spike(cycle: int, total: int) -> float:
    """Short burst at 40% mark, then immediate drop."""
    spike_start = int(total * 0.4)
    spike_end = spike_start + max(3, total // 20)
    if spike_start <= cycle < spike_end:
        return 0.95
    return 0.3


def pattern_oscillating(cycle: int, total: int) -> float:
    """Rapid alternation between high and low every 5 cycles."""
    return 0.85 if (cycle // 5) % 2 == 0 else 0.25


def pattern_plateau(cycle: int, total: int) -> float:
    """Baseline at 0.3, shifts to 0.7 at midpoint, holds."""
    return 0.3 if cycle < total // 2 else 0.7


PATTERNS: Dict[PatternType, Callable[[int, int], float]] = {
    PatternType.STEP: pattern_step,
    PatternType.RAMP: pattern_ramp,
    PatternType.SINUSOIDAL: pattern_sinusoidal,
    PatternType.SPIKE: pattern_spike,
    PatternType.OSCILLATING: pattern_oscillating,
    PatternType.PLATEAU: pattern_plateau,
}


# ============================================================
# HPA Simulator
# ============================================================

class HPASimulator:
    """Simple threshold-based HPA simulator for comparison.

    Models the standard K8s HPA: scales when average CPU > target,
    with a stabilization window (no scale-down for N cycles after scale-up).
    """

    def __init__(
        self,
        target_cpu: float = 0.5,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.3,
        stabilization_window: int = 10,
        max_scale_step: int = 2,
    ):
        self.target_cpu = target_cpu
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.stabilization_window = stabilization_window
        self.max_scale_step = max_scale_step
        self._last_scale_up_cycle: int = -999

    def decide(
        self,
        metrics: Dict[str, float],
        current_replicas: int,
        cycle: int,
    ) -> int:
        """Return replica delta for this cycle."""
        cpu = metrics.get("cpu", 0.5)

        # Scale up: CPU above threshold
        if cpu > self.scale_up_threshold:
            ratio = cpu / self.target_cpu
            desired = max(1, math.ceil(current_replicas * ratio))
            delta = min(desired - current_replicas, self.max_scale_step)
            if delta > 0:
                self._last_scale_up_cycle = cycle
                return delta

        # Scale down: CPU below threshold, but respect stabilization window
        if cpu < self.scale_down_threshold:
            if cycle - self._last_scale_up_cycle < self.stabilization_window:
                return 0  # Stabilization hold
            ratio = cpu / self.target_cpu
            desired = max(1, math.ceil(current_replicas * ratio))
            delta = max(desired - current_replicas, -self.max_scale_step)
            return delta

        return 0

    def reset(self) -> None:
        self._last_scale_up_cycle = -999


# ============================================================
# Benchmark Scorer
# ============================================================

@dataclass
class ScenarioScore:
    """Scoring metrics for a single benchmark scenario."""
    pattern: str
    scaler: str  # "controller" or "hpa"

    # Reaction: cycles from demand change to first scaling action
    reaction_time: int = 0
    # Overshoot: max replicas above optimal at any point
    overshoot: int = 0
    # Settling: cycles from demand change until replicas stay within ±1 of optimal
    settling_time: int = 0
    # Oscillations: number of direction reversals in scaling actions
    oscillation_count: int = 0
    # Cost: total replica-cycles (sum of replicas each cycle)
    replica_cycles: int = 0
    # Optimal cost: total optimal replica-cycles (oracle)
    optimal_replica_cycles: int = 0
    # SLO: cycles where replicas < optimal (under-provisioned)
    slo_breach_cycles: int = 0
    # Total cycles
    total_cycles: int = 0

    @property
    def cost_efficiency(self) -> float:
        """Ratio of actual to optimal replica-cycles. 1.0 = perfect."""
        if self.optimal_replica_cycles == 0:
            return 1.0
        return self.replica_cycles / self.optimal_replica_cycles

    @property
    def slo_breach_rate(self) -> float:
        """Fraction of cycles with SLO breach."""
        if self.total_cycles == 0:
            return 0.0
        return self.slo_breach_cycles / self.total_cycles

    def format(self) -> str:
        lines = [
            f"  {self.scaler:>12s} | react={self.reaction_time:3d} "
            f"settle={self.settling_time:3d} overshoot={self.overshoot:+d} "
            f"osc={self.oscillation_count:2d} "
            f"cost={self.cost_efficiency:.2f}x "
            f"slo_breach={self.slo_breach_rate:.1%}",
        ]
        return lines[0]


def _score_run(
    pattern_name: str,
    scaler_name: str,
    replica_history: List[int],
    delta_history: List[int],
    demand_history: List[float],
    base_replicas: int,
) -> ScenarioScore:
    """Compute scoring metrics from a completed benchmark run."""
    total = len(replica_history)
    optimal_history = [
        _optimal_replicas(d, base_replicas) for d in demand_history
    ]

    score = ScenarioScore(
        pattern=pattern_name,
        scaler=scaler_name,
        total_cycles=total,
    )

    # Reaction time: cycles from first demand change until first non-zero delta
    first_change = None
    for i in range(1, total):
        if abs(demand_history[i] - demand_history[0]) > 0.1:
            first_change = i
            break
    if first_change is not None:
        first_action = None
        for i in range(first_change, total):
            if delta_history[i] != 0:
                first_action = i
                break
        score.reaction_time = (first_action - first_change) if first_action is not None else total

    # Overshoot
    max_over = 0
    for i in range(total):
        over = replica_history[i] - optimal_history[i]
        if over > max_over:
            max_over = over
    score.overshoot = max_over

    # Settling time: from first demand change, cycles until replicas stay within ±1
    if first_change is not None:
        settled_at = total  # default: never settled
        for i in range(first_change, total):
            # Check if from i onward, all within ±1
            all_settled = True
            for j in range(i, min(i + 10, total)):
                if abs(replica_history[j] - optimal_history[j]) > 1:
                    all_settled = False
                    break
            if all_settled:
                settled_at = i
                break
        score.settling_time = settled_at - first_change

    # Oscillation count: direction reversals
    last_dir = 0
    for d in delta_history:
        if d > 0:
            cur_dir = 1
        elif d < 0:
            cur_dir = -1
        else:
            continue
        if last_dir != 0 and cur_dir != last_dir:
            score.oscillation_count += 1
        last_dir = cur_dir

    # Cost efficiency
    score.replica_cycles = sum(replica_history)
    score.optimal_replica_cycles = sum(optimal_history)

    # SLO breaches
    score.slo_breach_cycles = sum(
        1 for i in range(total) if replica_history[i] < optimal_history[i]
    )

    return score


# ============================================================
# Benchmark Harness
# ============================================================

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    cycles_per_pattern: int = 200
    warmup_cycles: int = 60
    base_replicas: int = 5
    controller_config: Optional[InfraControllerConfig] = None


@dataclass
class BenchmarkReport:
    """Complete benchmark results."""
    scores: List[ScenarioScore] = field(default_factory=list)
    config: Optional[BenchmarkConfig] = None

    def format(self) -> str:
        lines = [
            "=" * 78,
            "CLOUD SCALING CONTROLLER — BENCHMARK REPORT",
            "=" * 78,
            "",
        ]

        # Group by pattern
        patterns_seen: List[str] = []
        for s in self.scores:
            if s.pattern not in patterns_seen:
                patterns_seen.append(s.pattern)

        for pattern in patterns_seen:
            lines.append(f"  Pattern: {pattern}")
            lines.append(
                f"  {'':>12s} | {'react':>5s} {'settle':>6s} "
                f"{'over':>5s} {'osc':>4s} {'cost':>6s} {'slo':>10s}"
            )
            lines.append("  " + "-" * 62)
            for s in self.scores:
                if s.pattern == pattern:
                    lines.append(s.format())
            lines.append("")

        # Summary
        ctrl_scores = [s for s in self.scores if s.scaler == "controller"]
        hpa_scores = [s for s in self.scores if s.scaler == "hpa"]

        if ctrl_scores and hpa_scores:
            lines.append("  SUMMARY (controller vs HPA)")
            lines.append("  " + "-" * 40)

            ctrl_avg_react = sum(s.reaction_time for s in ctrl_scores) / len(ctrl_scores)
            hpa_avg_react = sum(s.reaction_time for s in hpa_scores) / len(hpa_scores)
            lines.append(f"  Avg reaction time:  {ctrl_avg_react:5.1f} vs {hpa_avg_react:5.1f}")

            ctrl_avg_cost = sum(s.cost_efficiency for s in ctrl_scores) / len(ctrl_scores)
            hpa_avg_cost = sum(s.cost_efficiency for s in hpa_scores) / len(hpa_scores)
            lines.append(f"  Avg cost efficiency: {ctrl_avg_cost:.2f}x vs {hpa_avg_cost:.2f}x")

            ctrl_total_osc = sum(s.oscillation_count for s in ctrl_scores)
            hpa_total_osc = sum(s.oscillation_count for s in hpa_scores)
            lines.append(f"  Total oscillations:  {ctrl_total_osc:5d} vs {hpa_total_osc:5d}")

            ctrl_slo = sum(s.slo_breach_cycles for s in ctrl_scores)
            hpa_slo = sum(s.slo_breach_cycles for s in hpa_scores)
            lines.append(f"  Total SLO breaches:  {ctrl_slo:5d} vs {hpa_slo:5d}")

            # Winner determination
            ctrl_wins = 0
            hpa_wins = 0
            for c, h in zip(ctrl_scores, hpa_scores):
                c_grade = c.reaction_time + c.settling_time + c.oscillation_count * 5 + c.slo_breach_cycles * 10
                h_grade = h.reaction_time + h.settling_time + h.oscillation_count * 5 + h.slo_breach_cycles * 10
                if c_grade < h_grade:
                    ctrl_wins += 1
                elif h_grade < c_grade:
                    hpa_wins += 1

            lines.append("")
            lines.append(f"  Scenarios won:  controller={ctrl_wins}  hpa={hpa_wins}  "
                         f"tie={len(ctrl_scores) - ctrl_wins - hpa_wins}")

        lines.append("")
        lines.append("=" * 78)
        return "\n".join(lines)


class BenchmarkHarness:
    """Runs the scaling controller through canonical traffic patterns and
    compares against a simulated HPA baseline.

    Usage:
        harness = BenchmarkHarness()
        report = harness.run_all()
        print(report.format())
    """

    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or BenchmarkConfig()

    def run_all(
        self,
        patterns: Optional[List[PatternType]] = None,
    ) -> BenchmarkReport:
        """Run all (or selected) patterns and return the full report."""
        if patterns is None:
            patterns = list(PatternType)

        report = BenchmarkReport(config=self.config)
        for pattern in patterns:
            ctrl_score, hpa_score = self.run_pattern(pattern)
            report.scores.append(ctrl_score)
            report.scores.append(hpa_score)

        return report

    def run_pattern(
        self,
        pattern_type: PatternType,
    ) -> Tuple[ScenarioScore, ScenarioScore]:
        """Run one pattern through controller and HPA, return both scores."""
        pattern_fn = PATTERNS[pattern_type]
        cfg = self.config
        total = cfg.cycles_per_pattern

        # Generate demand trace
        demand_trace = [pattern_fn(i, total) for i in range(total)]

        # Run controller
        ctrl_score = self._run_controller(pattern_type.value, demand_trace)

        # Run HPA
        hpa_score = self._run_hpa(pattern_type.value, demand_trace)

        return ctrl_score, hpa_score

    def _run_controller(
        self,
        pattern_name: str,
        demand_trace: List[float],
    ) -> ScenarioScore:
        """Run the controller through a demand trace."""
        cfg = self.config
        ctrl_config = cfg.controller_config or InfraControllerConfig()
        ctrl = Controller(ctrl_config)

        replicas = cfg.base_replicas
        replica_history: List[int] = []
        delta_history: List[int] = []

        # Warmup with baseline demand
        baseline = demand_trace[0] if demand_trace else 0.3
        for _ in range(cfg.warmup_cycles):
            metrics = _demand_to_metrics(baseline)
            ctrl.step(metrics=metrics, current_replicas=replicas)

        # Run scenario
        for demand in demand_trace:
            metrics = _demand_to_metrics(demand)
            result = ctrl.step(metrics=metrics, current_replicas=replicas)
            delta = result.replica_delta
            replicas = max(1, replicas + delta)
            replica_history.append(replicas)
            delta_history.append(delta)

        return _score_run(
            pattern_name, "controller",
            replica_history, delta_history, demand_trace,
            cfg.base_replicas,
        )

    def _run_hpa(
        self,
        pattern_name: str,
        demand_trace: List[float],
    ) -> ScenarioScore:
        """Run the HPA simulator through a demand trace."""
        cfg = self.config
        hpa = HPASimulator()

        replicas = cfg.base_replicas
        replica_history: List[int] = []
        delta_history: List[int] = []

        for cycle, demand in enumerate(demand_trace):
            metrics = _demand_to_metrics(demand)
            delta = hpa.decide(metrics, replicas, cycle)
            replicas = max(1, replicas + delta)
            replica_history.append(replicas)
            delta_history.append(delta)

        return _score_run(
            pattern_name, "hpa",
            replica_history, delta_history, demand_trace,
            cfg.base_replicas,
        )


# ============================================================
# Parameter Sweep
# ============================================================

@dataclass
class SweepVariant:
    """A named controller configuration variant for parameter sweeps."""
    name: str
    config: InfraControllerConfig

    def __repr__(self) -> str:
        return f"SweepVariant({self.name!r})"


@dataclass
class SweepResult:
    """Aggregated scores for one variant across all patterns."""
    variant_name: str
    scores: List[ScenarioScore] = field(default_factory=list)

    @property
    def avg_reaction(self) -> float:
        return sum(s.reaction_time for s in self.scores) / max(1, len(self.scores))

    @property
    def avg_cost(self) -> float:
        return sum(s.cost_efficiency for s in self.scores) / max(1, len(self.scores))

    @property
    def total_oscillations(self) -> int:
        return sum(s.oscillation_count for s in self.scores)

    @property
    def total_slo_breaches(self) -> int:
        return sum(s.slo_breach_cycles for s in self.scores)

    @property
    def max_overshoot(self) -> int:
        return max((s.overshoot for s in self.scores), default=0)

    @property
    def avg_settling(self) -> float:
        return sum(s.settling_time for s in self.scores) / max(1, len(self.scores))


@dataclass
class SweepReport:
    """Complete parameter sweep results."""
    results: List[SweepResult] = field(default_factory=list)
    hpa_baseline: Optional[SweepResult] = None

    def format(self) -> str:
        lines = [
            "=" * 90,
            "PARAMETER SWEEP RESULTS",
            "=" * 90,
            "",
            f"  {'variant':>20s} | {'react':>5s} {'settle':>6s} "
            f"{'over':>5s} {'osc':>4s} {'cost':>6s} {'slo':>5s}",
            "  " + "-" * 68,
        ]

        all_results = list(self.results)
        if self.hpa_baseline:
            all_results.append(self.hpa_baseline)

        for r in all_results:
            lines.append(
                f"  {r.variant_name:>20s} | "
                f"react={r.avg_reaction:5.1f} "
                f"settle={r.avg_settling:5.1f} "
                f"overshoot={r.max_overshoot:+d} "
                f"osc={r.total_oscillations:2d} "
                f"cost={r.avg_cost:.2f}x "
                f"slo={r.total_slo_breaches:4d}"
            )

        # Find best variant (lowest composite grade)
        if self.results:
            lines.append("")
            lines.append("  RANKING (lower = better)")
            lines.append("  " + "-" * 50)

            ranked = []
            for r in all_results:
                grade = (
                    r.avg_reaction * 1.0
                    + r.avg_settling * 0.5
                    + r.total_oscillations * 20.0
                    + r.total_slo_breaches * 2.0
                    + (r.avg_cost - 1.0) * 100.0  # penalize over-provisioning
                    + r.max_overshoot * 5.0
                )
                ranked.append((grade, r.variant_name))
            ranked.sort()

            for i, (grade, name) in enumerate(ranked):
                marker = " <-- BEST" if i == 0 else ""
                lines.append(f"  {i+1}. {name:>20s}  grade={grade:.0f}{marker}")

        lines.append("")
        lines.append("=" * 90)
        return "\n".join(lines)


def build_sweep_variants() -> List[SweepVariant]:
    """Build the standard parameter sweep variants.

    Sweeps three axes independently, then tests a combined profile:
      1. Threshold sweep: lower action thresholds
      2. Gain sweep: increase G_base
      3. Damping sweep: reduce k_dv
      4. Combined: best of each axis
    """
    variants = []

    # Baseline (defaults)
    variants.append(SweepVariant("defaults", InfraControllerConfig()))

    # Sweep 1: Lower action thresholds
    for recommend_thresh in [0.10, 0.05]:
        cfg = InfraControllerConfig()
        cfg.action_thresholds = {
            "no_action": 0.03,
            "recommend": recommend_thresh,
            "scale_1": 0.20,
            "scale_2": 0.60,
        }
        variants.append(SweepVariant(f"thresh_r{recommend_thresh}", cfg))

    # Sweep 2: Increase G_base
    for g_base in [1.5, 2.0, 2.5]:
        cfg = InfraControllerConfig()
        cfg.G_base = g_base
        variants.append(SweepVariant(f"G_base={g_base}", cfg))

    # Sweep 3: Reduce k_dv (damping sensitivity)
    for k_dv in [0.5, 0.3]:
        cfg = InfraControllerConfig()
        cfg.k_dv = k_dv
        variants.append(SweepVariant(f"k_dv={k_dv}", cfg))

    # Sweep 4: Combined conservative tuning
    cfg = InfraControllerConfig()
    cfg.action_thresholds = {
        "no_action": 0.03,
        "recommend": 0.08,
        "scale_1": 0.20,
        "scale_2": 0.60,
    }
    cfg.G_base = 1.5
    cfg.k_dv = 0.5
    variants.append(SweepVariant("combined_conservative", cfg))

    # Sweep 4b: Combined moderate tuning
    cfg = InfraControllerConfig()
    cfg.action_thresholds = {
        "no_action": 0.03,
        "recommend": 0.05,
        "scale_1": 0.15,
        "scale_2": 0.50,
    }
    cfg.G_base = 2.0
    cfg.k_dv = 0.3
    variants.append(SweepVariant("combined_moderate", cfg))

    return variants


class ParameterSweep:
    """Runs the benchmark across multiple controller configurations
    to find the optimal tuning profile.

    Usage:
        sweep = ParameterSweep()
        report = sweep.run()
        print(report.format())
    """

    def __init__(
        self,
        cycles_per_pattern: int = 200,
        warmup_cycles: int = 60,
        base_replicas: int = 5,
        variants: Optional[List[SweepVariant]] = None,
        patterns: Optional[List[PatternType]] = None,
    ):
        self.cycles = cycles_per_pattern
        self.warmup = warmup_cycles
        self.base_replicas = base_replicas
        self.variants = variants or build_sweep_variants()
        self.patterns = patterns or list(PatternType)

    def run(self) -> SweepReport:
        """Run all variants across all patterns."""
        report = SweepReport()

        # Run each variant
        for variant in self.variants:
            harness = BenchmarkHarness(BenchmarkConfig(
                cycles_per_pattern=self.cycles,
                warmup_cycles=self.warmup,
                base_replicas=self.base_replicas,
                controller_config=variant.config,
            ))

            sweep_result = SweepResult(variant_name=variant.name)
            for pattern in self.patterns:
                ctrl_score, _ = harness.run_pattern(pattern)
                ctrl_score.scaler = variant.name
                sweep_result.scores.append(ctrl_score)

            report.results.append(sweep_result)

        # Run HPA baseline once
        harness = BenchmarkHarness(BenchmarkConfig(
            cycles_per_pattern=self.cycles,
            warmup_cycles=self.warmup,
            base_replicas=self.base_replicas,
        ))
        hpa_result = SweepResult(variant_name="hpa_baseline")
        for pattern in self.patterns:
            _, hpa_score = harness.run_pattern(pattern)
            hpa_result.scores.append(hpa_score)
        report.hpa_baseline = hpa_result

        return report
