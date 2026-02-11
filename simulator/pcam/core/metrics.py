"""
Metrics collection for PCAM validation.

Implements the mandatory metrics from Appendix H:
- tok/s (throughput)
- p50/p95/p99 latency
- Quality proxy
- Memory budget sweep
- Multi-tenant behavior
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import statistics
import math


@dataclass
class LatencyStats:
    """Latency distribution statistics."""
    samples: List[float] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def p50(self) -> float:
        """Median latency."""
        if not self.samples:
            return 0.0
        return statistics.median(self.samples)

    @property
    def p95(self) -> float:
        """95th percentile latency."""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(0.95 * len(sorted_samples))
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    @property
    def p99(self) -> float:
        """99th percentile latency."""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(0.99 * len(sorted_samples))
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    @property
    def min(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def max(self) -> float:
        return max(self.samples) if self.samples else 0.0

    def add(self, latency: float) -> None:
        """Add a latency sample."""
        self.samples.append(latency)

    def to_dict(self) -> Dict:
        """Convert to dictionary for reporting."""
        return {
            "count": self.count,
            "mean_ns": self.mean,
            "p50_ns": self.p50,
            "p95_ns": self.p95,
            "p99_ns": self.p99,
            "min_ns": self.min,
            "max_ns": self.max,
        }


@dataclass
class QualityMetrics:
    """Quality proxy metrics."""
    # Candidate coverage: fraction of true top-K captured
    candidate_coverage_samples: List[float] = field(default_factory=list)

    # Retention quality: correlation with optimal
    retention_quality_samples: List[float] = field(default_factory=list)

    # Hit rate: fraction of useful candidates
    hit_rate_samples: List[float] = field(default_factory=list)

    # Mass recall: fraction of total attention mass captured by candidates
    mass_recall_samples: List[float] = field(default_factory=list)

    @property
    def mean_coverage(self) -> float:
        """Mean candidate coverage."""
        return statistics.mean(self.candidate_coverage_samples) if self.candidate_coverage_samples else 0.0

    @property
    def mean_retention_quality(self) -> float:
        """Mean retention quality."""
        return statistics.mean(self.retention_quality_samples) if self.retention_quality_samples else 0.0

    @property
    def mean_hit_rate(self) -> float:
        """Mean hit rate."""
        return statistics.mean(self.hit_rate_samples) if self.hit_rate_samples else 0.0

    @property
    def mean_mass_recall(self) -> float:
        """Mean attention mass recall."""
        return statistics.mean(self.mass_recall_samples) if self.mass_recall_samples else 0.0

    @property
    def ppl_proxy(self) -> float:
        """Perplexity proxy ratio (1.0 = no degradation).

        Calibrated to match empirical sparse attention research.
        Mass recall (fraction of attention mass preserved) is the
        primary signal — it directly measures information retention.
        Coverage (top-K overlap) is a secondary structural signal.

        When mass recall is high (>95%), low coverage indicates the
        model drops low-weight blocks, which has minimal PPL impact.

          ppl_ratio = 1.0 + (1 - mass_recall) * 1.5 + (1 - coverage) * 0.1
        """
        mass_recall = self.mean_mass_recall if self.mass_recall_samples else self.mean_coverage
        coverage = self.mean_coverage
        # Mass recall is the dominant signal: losing 5% of attention mass ≈ 7.5% PPL increase
        info_loss = (1.0 - mass_recall) * 1.5
        # Coverage is a weak structural signal: missing top-K entries that carry little mass
        coverage_penalty = (1.0 - coverage) * 0.1
        return 1.0 + info_loss + coverage_penalty

    def add_coverage(self, coverage: float) -> None:
        self.candidate_coverage_samples.append(coverage)

    def add_retention_quality(self, quality: float) -> None:
        self.retention_quality_samples.append(quality)

    def add_hit_rate(self, hit_rate: float) -> None:
        self.hit_rate_samples.append(hit_rate)

    def add_mass_recall(self, mass_recall: float) -> None:
        self.mass_recall_samples.append(mass_recall)

    def to_dict(self) -> Dict:
        return {
            "mean_coverage": self.mean_coverage,
            "mean_retention_quality": self.mean_retention_quality,
            "mean_hit_rate": self.mean_hit_rate,
            "mean_mass_recall": self.mean_mass_recall,
            "ppl_proxy": round(self.ppl_proxy, 4),
            "coverage_samples": len(self.candidate_coverage_samples),
        }


@dataclass
class ThroughputMetrics:
    """Throughput metrics."""
    total_tokens: int = 0
    total_time_ns: float = 0.0
    attend_ops: int = 0
    update_ops: int = 0

    @property
    def tokens_per_second(self) -> float:
        """Throughput in tokens/second."""
        if self.total_time_ns <= 0:
            return 0.0
        return self.total_tokens / (self.total_time_ns / 1e9)

    @property
    def attend_ops_per_second(self) -> float:
        """ATTEND operations per second."""
        if self.total_time_ns <= 0:
            return 0.0
        return self.attend_ops / (self.total_time_ns / 1e9)

    @property
    def update_ops_per_second(self) -> float:
        """UPDATE operations per second."""
        if self.total_time_ns <= 0:
            return 0.0
        return self.update_ops / (self.total_time_ns / 1e9)

    def to_dict(self) -> Dict:
        return {
            "total_tokens": self.total_tokens,
            "total_time_ns": self.total_time_ns,
            "tokens_per_second": self.tokens_per_second,
            "attend_ops_per_second": self.attend_ops_per_second,
            "update_ops_per_second": self.update_ops_per_second,
        }


@dataclass
class MemoryMetrics:
    """Memory usage metrics."""
    peak_entries: int = 0
    peak_sequences: int = 0
    total_edges: int = 0

    # Memory budget tracking
    budget_percentage: float = 1.0  # Current budget as fraction of full
    effective_context_length: int = 0

    def to_dict(self) -> Dict:
        return {
            "peak_entries": self.peak_entries,
            "peak_sequences": self.peak_sequences,
            "total_edges": self.total_edges,
            "budget_percentage": self.budget_percentage,
            "effective_context_length": self.effective_context_length,
        }


@dataclass
class BankMetrics:
    """Bank conflict and utilization metrics."""
    total_conflicts: int = 0
    total_accesses: int = 0
    peak_queue_depth: int = 0
    bank_utilizations: List[float] = field(default_factory=list)

    @property
    def conflict_rate(self) -> float:
        """Fraction of accesses with conflicts."""
        if self.total_accesses <= 0:
            return 0.0
        return self.total_conflicts / self.total_accesses

    @property
    def mean_utilization(self) -> float:
        """Mean bank utilization."""
        return statistics.mean(self.bank_utilizations) if self.bank_utilizations else 0.0

    def to_dict(self) -> Dict:
        return {
            "total_conflicts": self.total_conflicts,
            "total_accesses": self.total_accesses,
            "conflict_rate": self.conflict_rate,
            "peak_queue_depth": self.peak_queue_depth,
            "mean_utilization": self.mean_utilization,
        }


@dataclass
class PCAMMetrics:
    """
    Complete PCAM metrics for validation.

    Aggregates all metric categories as specified in Appendix H.
    """
    # Latency metrics
    attend_latency: LatencyStats = field(default_factory=LatencyStats)
    update_latency: LatencyStats = field(default_factory=LatencyStats)

    # Quality metrics
    quality: QualityMetrics = field(default_factory=QualityMetrics)

    # Throughput metrics
    throughput: ThroughputMetrics = field(default_factory=ThroughputMetrics)

    # Memory metrics
    memory: MemoryMetrics = field(default_factory=MemoryMetrics)

    # Bank metrics
    banks: BankMetrics = field(default_factory=BankMetrics)

    # Controller name for comparison
    controller_name: str = "pcam"

    def check_acceptance_gates(
        self,
        baseline_metrics: Optional["PCAMMetrics"] = None,
        thresholds: Optional[Dict] = None,
    ) -> Dict[str, bool]:
        """
        Check if metrics meet acceptance criteria.

        Args:
            baseline_metrics: Baseline to compare against
            thresholds: Override default thresholds

        Returns:
            Dict of gate_name -> passed
        """
        from .config import AcceptanceThresholds
        thresh = AcceptanceThresholds()
        if thresholds:
            for k, v in thresholds.items():
                setattr(thresh, k, v)

        gates = {}

        # Gate G1: Quality-preserving memory reduction
        gates["g1_memory_reduction"] = (
            self.memory.budget_percentage <= (1 - thresh.min_memory_reduction) or
            self.memory.effective_context_length >= thresh.min_context_multiplier * 4096
        )

        # Gate G2: Throughput win
        if baseline_metrics:
            throughput_gain = (
                (self.throughput.tokens_per_second - baseline_metrics.throughput.tokens_per_second) /
                baseline_metrics.throughput.tokens_per_second
                if baseline_metrics.throughput.tokens_per_second > 0 else 0
            )
            gates["g2_throughput"] = throughput_gain >= thresh.min_throughput_improvement
        else:
            gates["g2_throughput"] = True  # No baseline to compare

        # Gate G3: Tail latency control
        if baseline_metrics and baseline_metrics.attend_latency.p99 > 0:
            p99_overhead = (
                (self.attend_latency.p99 - baseline_metrics.attend_latency.p99) /
                baseline_metrics.attend_latency.p99
            )
            gates["g3_tail_latency"] = p99_overhead <= thresh.max_p99_overhead
        else:
            gates["g3_tail_latency"] = self.attend_latency.p99 <= thresh.max_attend_p99_ns

        # Hardware feasibility gates
        gates["hw_attend_p50"] = self.attend_latency.p50 <= thresh.max_attend_p50_ns
        gates["hw_attend_p99"] = self.attend_latency.p99 <= thresh.max_attend_p99_ns
        gates["hw_attend_throughput"] = (
            self.throughput.attend_ops_per_second >= thresh.min_attend_throughput
        )

        # Quality gate
        gates["quality_coverage"] = (
            self.quality.mean_coverage >= thresh.min_candidate_coverage
        )

        return gates

    def to_dict(self) -> Dict:
        """Convert all metrics to dictionary."""
        return {
            "controller": self.controller_name,
            "attend_latency": self.attend_latency.to_dict(),
            "update_latency": self.update_latency.to_dict(),
            "quality": self.quality.to_dict(),
            "throughput": self.throughput.to_dict(),
            "memory": self.memory.to_dict(),
            "banks": self.banks.to_dict(),
        }

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"=== PCAM Metrics: {self.controller_name} ===",
            f"",
            f"Latency:",
            f"  ATTEND p50: {self.attend_latency.p50:.1f}ns, p99: {self.attend_latency.p99:.1f}ns",
            f"  UPDATE p50: {self.update_latency.p50:.1f}ns, p99: {self.update_latency.p99:.1f}ns",
            f"",
            f"Throughput:",
            f"  Tokens/sec: {self.throughput.tokens_per_second:,.0f}",
            f"  ATTEND ops/sec: {self.throughput.attend_ops_per_second:,.0f}",
            f"  UPDATE ops/sec: {self.throughput.update_ops_per_second:,.0f}",
            f"",
            f"Quality:",
            f"  Coverage: {self.quality.mean_coverage:.1%}",
            f"  Hit rate: {self.quality.mean_hit_rate:.1%}",
            f"",
            f"Memory:",
            f"  Budget: {self.memory.budget_percentage:.0%}",
            f"  Peak entries: {self.memory.peak_entries:,}",
            f"",
            f"Banks:",
            f"  Conflict rate: {self.banks.conflict_rate:.1%}",
            f"  Peak queue: {self.banks.peak_queue_depth}",
        ]
        return "\n".join(lines)


class MetricsCollector:
    """
    Collects metrics during simulation.

    Usage:
        collector = MetricsCollector("pcam")
        collector.record_attend(latency_ns, candidates, true_top_k)
        collector.record_update(latency_ns)
        metrics = collector.finalize()
    """

    def __init__(self, controller_name: str = "pcam"):
        self.metrics = PCAMMetrics(controller_name=controller_name)
        self._start_time_ns: Optional[float] = None

    def start(self) -> None:
        """Mark simulation start."""
        import time
        self._start_time_ns = time.time_ns()

    def record_attend(
        self,
        latency_ns: float,
        candidates: List[int],
        true_top_k: Optional[List[int]] = None,
        bank_conflicts: int = 0,
        attention_scores: Optional[Dict[int, float]] = None,
    ) -> None:
        """Record an ATTEND operation."""
        self.metrics.attend_latency.add(latency_ns)
        self.metrics.throughput.attend_ops += 1
        self.metrics.banks.total_accesses += 1
        self.metrics.banks.total_conflicts += bank_conflicts

        # Calculate coverage if ground truth provided
        if true_top_k:
            overlap = len(set(candidates) & set(true_top_k))
            coverage = overlap / len(true_top_k) if true_top_k else 1.0
            self.metrics.quality.add_coverage(coverage)

        # Calculate mass recall if attention scores provided
        if attention_scores:
            total_attention = sum(attention_scores.values())
            if total_attention > 0:
                captured = sum(attention_scores.get(b, 0) for b in candidates)
                mass_recall = captured / total_attention
                self.metrics.quality.add_mass_recall(mass_recall)

    def record_update(
        self,
        latency_ns: float,
        count: int = 1,
    ) -> None:
        """Record UPDATE operation(s)."""
        self.metrics.update_latency.add(latency_ns)
        self.metrics.throughput.update_ops += count

    def record_token(self, count: int = 1) -> None:
        """Record token generation."""
        self.metrics.throughput.total_tokens += count

    def record_hit_rate(self, hits: int, total: int) -> None:
        """Record hit rate."""
        if total > 0:
            self.metrics.quality.add_hit_rate(hits / total)

    def record_memory(
        self,
        entries: int,
        sequences: int,
        edges: int,
        budget_pct: float,
    ) -> None:
        """Record memory state."""
        self.metrics.memory.peak_entries = max(self.metrics.memory.peak_entries, entries)
        self.metrics.memory.peak_sequences = max(self.metrics.memory.peak_sequences, sequences)
        self.metrics.memory.total_edges = edges
        self.metrics.memory.budget_percentage = budget_pct

    def finalize(self) -> PCAMMetrics:
        """Finalize and return metrics."""
        import time
        if self._start_time_ns:
            self.metrics.throughput.total_time_ns = time.time_ns() - self._start_time_ns
        return self.metrics
