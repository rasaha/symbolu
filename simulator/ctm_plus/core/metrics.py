"""
Metrics collection and reporting for CTM+ simulator.

Collects comprehensive statistics during simulation to enable
comparison between different controller algorithms.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
import statistics
import json


@dataclass
class SimulationMetrics:
    """
    Final metrics from a simulation run.

    This is the output of Simulator.run() - immutable results
    that can be compared across different controllers.
    """

    # Identity
    controller_name: str
    trace_name: str

    # Core metrics
    total_accesses: int = 0
    tier0_hits: int = 0
    tier1_hits: int = 0
    total_misses: int = 0  # Not in any tier

    # Movement metrics
    promotions: int = 0
    demotions: int = 0
    bcvf_rejections: int = 0  # Proposed moves rejected by BCVF

    # Latency metrics (simulated)
    total_latency_ns: int = 0
    latencies: List[int] = field(default_factory=list)

    # Coherence metrics (CTM+ specific)
    coherence_samples: List[float] = field(default_factory=list)
    phase_samples: List[float] = field(default_factory=list)

    # Time series (for plotting)
    hit_rate_over_time: List[float] = field(default_factory=list)
    coherence_over_time: List[float] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        """Overall hit rate (tier0 hits / total accesses)."""
        if self.total_accesses == 0:
            return 0.0
        return self.tier0_hits / self.total_accesses

    @property
    def tier1_hit_rate(self) -> float:
        """Tier 1 hit rate (tier1 hits / total accesses)."""
        if self.total_accesses == 0:
            return 0.0
        return self.tier1_hits / self.total_accesses

    @property
    def miss_rate(self) -> float:
        """Miss rate (misses / total accesses)."""
        if self.total_accesses == 0:
            return 0.0
        return self.total_misses / self.total_accesses

    @property
    def combined_hit_rate(self) -> float:
        """Combined hit rate (tier0 + tier1 hits)."""
        if self.total_accesses == 0:
            return 0.0
        return (self.tier0_hits + self.tier1_hits) / self.total_accesses

    @property
    def avg_latency_ns(self) -> float:
        """Average access latency in nanoseconds."""
        if self.total_accesses == 0:
            return 0.0
        return self.total_latency_ns / self.total_accesses

    @property
    def p99_latency_ns(self) -> float:
        """99th percentile latency."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def move_rate(self) -> float:
        """Move rate (promotions + demotions / total accesses)."""
        if self.total_accesses == 0:
            return 0.0
        return (self.promotions + self.demotions) / self.total_accesses

    @property
    def bcvf_rejection_rate(self) -> float:
        """BCVF rejection rate."""
        total_proposed = self.promotions + self.demotions + self.bcvf_rejections
        if total_proposed == 0:
            return 0.0
        return self.bcvf_rejections / total_proposed

    @property
    def mean_coherence(self) -> float:
        """Mean coherence from samples."""
        if not self.coherence_samples:
            return 0.0
        return statistics.mean(self.coherence_samples)

    @property
    def coherence_std(self) -> float:
        """Standard deviation of coherence."""
        if len(self.coherence_samples) < 2:
            return 0.0
        return statistics.stdev(self.coherence_samples)

    def summary(self) -> str:
        """Return human-readable summary."""
        lines = [
            f"=== {self.controller_name} on {self.trace_name} ===",
            f"Total accesses:    {self.total_accesses:,}",
            f"Tier-0 hit rate:   {self.hit_rate:.2%}",
            f"Tier-1 hit rate:   {self.tier1_hit_rate:.2%}",
            f"Miss rate:         {self.miss_rate:.2%}",
            f"Avg latency:       {self.avg_latency_ns:,.0f} ns",
            f"P99 latency:       {self.p99_latency_ns:,.0f} ns",
            f"Promotions:        {self.promotions:,}",
            f"Demotions:         {self.demotions:,}",
            f"Move rate:         {self.move_rate:.2%}",
        ]
        if self.bcvf_rejections > 0:
            lines.append(f"BCVF rejections:   {self.bcvf_rejections:,} ({self.bcvf_rejection_rate:.1%})")
        if self.coherence_samples:
            lines.append(f"Mean coherence:    {self.mean_coherence:.3f} (σ={self.coherence_std:.3f})")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "controller": self.controller_name,
            "trace": self.trace_name,
            "total_accesses": self.total_accesses,
            "tier0_hits": self.tier0_hits,
            "tier1_hits": self.tier1_hits,
            "total_misses": self.total_misses,
            "hit_rate": self.hit_rate,
            "tier1_hit_rate": self.tier1_hit_rate,
            "miss_rate": self.miss_rate,
            "avg_latency_ns": self.avg_latency_ns,
            "p99_latency_ns": self.p99_latency_ns,
            "promotions": self.promotions,
            "demotions": self.demotions,
            "move_rate": self.move_rate,
            "bcvf_rejections": self.bcvf_rejections,
            "bcvf_rejection_rate": self.bcvf_rejection_rate,
            "mean_coherence": self.mean_coherence,
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)


class MetricsCollector:
    """
    Collects metrics during simulation.

    This is a mutable collector used during simulation,
    which produces an immutable SimulationMetrics at the end.
    """

    def __init__(self, controller_name: str, trace_name: str):
        self.controller_name = controller_name
        self.trace_name = trace_name

        # Counters
        self.total_accesses = 0
        self.tier0_hits = 0
        self.tier1_hits = 0
        self.total_misses = 0
        self.promotions = 0
        self.demotions = 0
        self.bcvf_rejections = 0

        # Latency tracking
        self.total_latency_ns = 0
        self.latencies: List[int] = []
        self._sample_rate = 100  # Sample every N accesses for memory efficiency

        # Coherence tracking
        self.coherence_samples: List[float] = []
        self.phase_samples: List[float] = []

        # Time series
        self.hit_rate_over_time: List[float] = []
        self._hits_window: List[int] = []
        self._window_size = 1000

    def record_access(
        self,
        tier0_hit: bool,
        tier1_hit: bool,
        latency_ns: int,
        coherence: Optional[float] = None,
        phase: Optional[float] = None,
    ) -> None:
        """Record a single memory access."""
        self.total_accesses += 1

        if tier0_hit:
            self.tier0_hits += 1
            self._hits_window.append(1)
        elif tier1_hit:
            self.tier1_hits += 1
            self._hits_window.append(0)
        else:
            self.total_misses += 1
            self._hits_window.append(0)

        self.total_latency_ns += latency_ns

        # Sample latencies for P99 calculation
        if self.total_accesses % self._sample_rate == 0:
            self.latencies.append(latency_ns)

        # Record coherence
        if coherence is not None and self.total_accesses % self._sample_rate == 0:
            self.coherence_samples.append(coherence)
        if phase is not None and self.total_accesses % self._sample_rate == 0:
            self.phase_samples.append(phase)

        # Update hit rate time series
        if len(self._hits_window) > self._window_size:
            self._hits_window.pop(0)
        if self.total_accesses % self._window_size == 0:
            window_hit_rate = sum(self._hits_window) / len(self._hits_window)
            self.hit_rate_over_time.append(window_hit_rate)

    def record_promotion(self) -> None:
        """Record a page promotion."""
        self.promotions += 1

    def record_demotion(self) -> None:
        """Record a page demotion."""
        self.demotions += 1

    def record_bcvf_rejection(self) -> None:
        """Record a BCVF rejection."""
        self.bcvf_rejections += 1

    def finalize(self) -> SimulationMetrics:
        """Convert to immutable SimulationMetrics."""
        return SimulationMetrics(
            controller_name=self.controller_name,
            trace_name=self.trace_name,
            total_accesses=self.total_accesses,
            tier0_hits=self.tier0_hits,
            tier1_hits=self.tier1_hits,
            total_misses=self.total_misses,
            promotions=self.promotions,
            demotions=self.demotions,
            bcvf_rejections=self.bcvf_rejections,
            total_latency_ns=self.total_latency_ns,
            latencies=self.latencies,
            coherence_samples=self.coherence_samples,
            phase_samples=self.phase_samples,
            hit_rate_over_time=self.hit_rate_over_time,
        )


def compare_results(
    baseline: SimulationMetrics, experimental: SimulationMetrics
) -> Dict[str, float]:
    """
    Compare experimental results against baseline.

    Args:
        baseline: Baseline results (e.g., LRU)
        experimental: Experimental results (e.g., CTM+)

    Returns:
        Dictionary of improvement metrics
    """
    def safe_div(a: float, b: float) -> float:
        return a / b if b > 0 else 0.0

    return {
        "hit_rate_improvement": experimental.hit_rate - baseline.hit_rate,
        "hit_rate_improvement_pct": safe_div(experimental.hit_rate, baseline.hit_rate) - 1,
        "latency_improvement_pct": 1 - safe_div(experimental.avg_latency_ns, baseline.avg_latency_ns),
        "p99_latency_improvement_pct": 1 - safe_div(experimental.p99_latency_ns, baseline.p99_latency_ns),
        "move_rate_change": experimental.move_rate - baseline.move_rate,
        "absolute_hit_rate_baseline": baseline.hit_rate,
        "absolute_hit_rate_experimental": experimental.hit_rate,
    }


def print_comparison(
    baseline: SimulationMetrics,
    experimental: SimulationMetrics,
) -> None:
    """Print formatted comparison of results."""
    comp = compare_results(baseline, experimental)

    print(f"\n{'='*60}")
    print(f"COMPARISON: {experimental.controller_name} vs {baseline.controller_name}")
    print(f"Trace: {baseline.trace_name}")
    print(f"{'='*60}")
    print(f"\nHit Rate:")
    print(f"  {baseline.controller_name:15}: {baseline.hit_rate:.2%}")
    print(f"  {experimental.controller_name:15}: {experimental.hit_rate:.2%}")
    print(f"  Improvement:      {comp['hit_rate_improvement']:+.2%} ({comp['hit_rate_improvement_pct']:+.1%} relative)")

    print(f"\nLatency:")
    print(f"  {baseline.controller_name:15}: {baseline.avg_latency_ns:,.0f} ns avg, {baseline.p99_latency_ns:,.0f} ns P99")
    print(f"  {experimental.controller_name:15}: {experimental.avg_latency_ns:,.0f} ns avg, {experimental.p99_latency_ns:,.0f} ns P99")
    print(f"  Improvement:      {comp['latency_improvement_pct']:+.1%} avg, {comp['p99_latency_improvement_pct']:+.1%} P99")

    print(f"\nMovement:")
    print(f"  {baseline.controller_name:15}: {baseline.move_rate:.2%} move rate")
    print(f"  {experimental.controller_name:15}: {experimental.move_rate:.2%} move rate")

    if experimental.bcvf_rejections > 0:
        print(f"  BCVF rejections:  {experimental.bcvf_rejections:,} ({experimental.bcvf_rejection_rate:.1%})")

    print(f"\n{'='*60}")
