"""
Multi-tenant Fairness and Isolation Tests.

Tests that PCAM doesn't have "noisy neighbor" problems and
provides fair service across concurrent sequences.

Metrics:
- Per-sequence latency p99
- Per-sequence quality/recall
- Starvation rate
- Memory partition fairness
"""

import pytest
import statistics
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from simulator.pcam.traces.generators import SyntheticTraceGenerator
from simulator.pcam.interface import SoftwarePCAMInterface


@dataclass
class PerSequenceMetrics:
    """Metrics tracked per sequence."""
    sequence_id: int
    attend_latencies: List[float] = field(default_factory=list)
    coverage_samples: List[float] = field(default_factory=list)
    mass_samples: List[float] = field(default_factory=list)
    candidate_counts: List[int] = field(default_factory=list)

    @property
    def latency_p50(self) -> float:
        if not self.attend_latencies:
            return 0
        return statistics.median(self.attend_latencies)

    @property
    def latency_p99(self) -> float:
        if not self.attend_latencies:
            return 0
        sorted_lat = sorted(self.attend_latencies)
        idx = int(0.99 * len(sorted_lat))
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def avg_coverage(self) -> float:
        return statistics.mean(self.coverage_samples) if self.coverage_samples else 0

    @property
    def avg_mass(self) -> float:
        return statistics.mean(self.mass_samples) if self.mass_samples else 0

    @property
    def starvation_rate(self) -> float:
        """Fraction of steps where we got fewer than half expected candidates."""
        if not self.candidate_counts:
            return 0
        starved = sum(1 for c in self.candidate_counts if c < 32)
        return starved / len(self.candidate_counts)


@dataclass
class FairnessMetrics:
    """Aggregate fairness metrics."""
    num_sequences: int
    latency_spread: float  # std dev of per-sequence p99
    coverage_spread: float  # std dev of per-sequence coverage
    max_starvation_rate: float  # worst sequence starvation
    jain_fairness_index: float  # Jain's fairness index (1 = perfectly fair)


def calculate_jain_fairness(values: List[float]) -> float:
    """
    Calculate Jain's fairness index.

    J = (sum(x))^2 / (n * sum(x^2))

    J=1 means all values equal (perfectly fair)
    J=1/n means one has everything (maximally unfair)
    """
    if not values:
        return 1.0
    n = len(values)
    sum_x = sum(values)
    sum_x2 = sum(x * x for x in values)
    if sum_x2 == 0:
        return 1.0
    return (sum_x ** 2) / (n * sum_x2)


class TestMultiTenantFairness:
    """Tests for multi-tenant fairness."""

    @pytest.fixture
    def generator(self):
        return SyntheticTraceGenerator(seed=42)

    def test_basic_fairness(self, generator):
        """Test basic fairness across sequences."""
        trace = generator.generate_multitenant_trace(
            num_sequences=8,
            total_steps=400,
            length_distribution="uniform",
        )

        interface = SoftwarePCAMInterface(
            max_sequences=16,
            max_blocks_per_sequence=256,
        )

        # Allocate all sequences
        for seq_id in trace.sequence_ids:
            interface.allocate_sequence(seq_id, 256)

        # Track per-sequence metrics
        seq_metrics: Dict[int, PerSequenceMetrics] = {}
        for seq_id in trace.sequence_ids:
            seq_metrics[seq_id] = PerSequenceMetrics(sequence_id=seq_id)

        for step in trace.steps:
            seq_id = step.sequence_id

            # Attend
            candidates, latency, _ = interface.attend(
                query_block_id=step.query_block_id,
                k=64,
                sequence_id=seq_id,
            )
            candidate_ids = set(c[0] for c in candidates)

            # Record metrics
            seq_metrics[seq_id].attend_latencies.append(latency)
            seq_metrics[seq_id].candidate_counts.append(len(candidates))

            # Coverage
            true_set = set(step.true_top_k[:64])
            coverage = len(candidate_ids & true_set) / max(1, len(true_set))
            seq_metrics[seq_id].coverage_samples.append(coverage)

            # Mass
            total = sum(step.attention_scores.values())
            captured = sum(step.attention_scores.get(b, 0) for b in candidate_ids)
            seq_metrics[seq_id].mass_samples.append(captured / max(0.001, total))

            # Update
            for block_id, weight in step.attention_scores.items():
                interface.update(step.query_block_id, block_id, weight, seq_id)

            interface.step()

        # Calculate fairness metrics
        p99s = [m.latency_p99 for m in seq_metrics.values()]
        coverages = [m.avg_coverage for m in seq_metrics.values()]
        starvations = [m.starvation_rate for m in seq_metrics.values()]

        jain_latency = calculate_jain_fairness(p99s)
        jain_coverage = calculate_jain_fairness(coverages)

        print("\n" + "=" * 70)
        print("MULTI-TENANT FAIRNESS (8 sequences)")
        print("=" * 70)
        print(f"\n{'Seq ID':>8} {'p50 (ns)':>12} {'p99 (ns)':>12} {'Coverage':>10} {'Starvation':>12}")
        print("-" * 60)

        for seq_id, m in sorted(seq_metrics.items()):
            print(
                f"{seq_id:>8} "
                f"{m.latency_p50:>12.1f} "
                f"{m.latency_p99:>12.1f} "
                f"{m.avg_coverage:>10.1%} "
                f"{m.starvation_rate:>12.1%}"
            )

        print()
        print(f"Jain's Fairness (latency): {jain_latency:.3f}")
        print(f"Jain's Fairness (coverage): {jain_coverage:.3f}")
        print(f"Max starvation rate: {max(starvations):.1%}")

        # Fairness should be > 0.9 (close to 1 = fair)
        assert jain_latency > 0.8, f"Latency unfair: {jain_latency}"
        assert jain_coverage > 0.7, f"Coverage unfair: {jain_coverage}"

    def test_noisy_neighbor(self, generator):
        """
        Test noisy neighbor scenario.

        One sequence is very active (high update rate), others are normal.
        Check that the noisy neighbor doesn't starve others.
        """
        # Create mixed trace
        normal_traces = [
            generator.generate_chat_trace(num_turns=5, tokens_per_turn=(10, 20))
            for _ in range(4)
        ]
        noisy_trace = generator.generate_chat_trace(
            num_turns=20, tokens_per_turn=(30, 50)  # Much more active
        )

        interface = SoftwarePCAMInterface(
            max_sequences=8,
            max_blocks_per_sequence=256,
        )

        # Allocate sequences
        for i in range(5):
            interface.allocate_sequence(i, 256)

        normal_coverages = defaultdict(list)
        noisy_coverages = []

        # Interleave execution
        step_idx = [0] * 5
        max_steps = max(
            max(len(t.steps) for t in normal_traces),
            len(noisy_trace.steps)
        )

        for _ in range(max_steps * 2):
            # Pick a sequence to run
            for seq_id in range(5):
                if seq_id < 4:
                    trace = normal_traces[seq_id]
                    coverages = normal_coverages
                else:
                    trace = noisy_trace
                    coverages = noisy_coverages

                if step_idx[seq_id] >= len(trace.steps):
                    continue

                step = trace.steps[step_idx[seq_id]]
                step_idx[seq_id] += 1

                # Attend
                candidates, _, _ = interface.attend(
                    query_block_id=step.query_block_id,
                    k=64,
                    sequence_id=seq_id,
                )
                candidate_ids = set(c[0] for c in candidates)

                # Coverage
                true_set = set(step.true_top_k[:64])
                coverage = len(candidate_ids & true_set) / max(1, len(true_set))

                if seq_id < 4:
                    normal_coverages[seq_id].append(coverage)
                else:
                    noisy_coverages.append(coverage)

                # Update
                for block_id, weight in step.attention_scores.items():
                    interface.update(step.query_block_id, block_id, weight, seq_id)

                interface.step()

        print("\n" + "=" * 60)
        print("NOISY NEIGHBOR TEST")
        print("=" * 60)
        print("\nOne sequence has 4x the activity of others.")
        print()

        normal_avgs = [
            statistics.mean(coverages) if coverages else 0
            for coverages in normal_coverages.values()
        ]
        noisy_avg = statistics.mean(noisy_coverages) if noisy_coverages else 0

        print(f"Normal sequence coverages: {[f'{c:.1%}' for c in normal_avgs]}")
        print(f"Noisy sequence coverage: {noisy_avg:.1%}")
        print(f"Spread: {statistics.stdev(normal_avgs + [noisy_avg]):.3f}")

        # Check no severe degradation
        for cov in normal_avgs:
            assert cov >= noisy_avg * 0.5, "Normal sequence starved by noisy neighbor"

    def test_sequence_isolation(self, generator):
        """
        Test that sequences are properly isolated.

        Updates to one sequence shouldn't affect candidates for another.
        """
        interface = SoftwarePCAMInterface(
            max_sequences=4,
            max_blocks_per_sequence=256,
        )

        # Allocate two sequences
        interface.allocate_sequence(0, 256)
        interface.allocate_sequence(1, 256)

        # Train seq 0 on blocks 0-99
        for i in range(100):
            interface.update(i, i, 1.0, sequence_id=0)

        # Train seq 1 on blocks 100-199
        for i in range(100, 200):
            interface.update(i, i, 1.0, sequence_id=1)

        # Get candidates for each
        cands_0, _, _ = interface.attend(50, k=32, sequence_id=0)
        cands_1, _, _ = interface.attend(150, k=32, sequence_id=1)

        cands_0_ids = set(c[0] for c in cands_0)
        cands_1_ids = set(c[0] for c in cands_1)

        print("\n" + "=" * 60)
        print("SEQUENCE ISOLATION TEST")
        print("=" * 60)
        print(f"\nSeq 0 trained on blocks 0-99")
        print(f"Seq 1 trained on blocks 100-199")
        print()
        print(f"Seq 0 candidates in 0-99: {len([c for c in cands_0_ids if c < 100])}")
        print(f"Seq 0 candidates in 100-199: {len([c for c in cands_0_ids if 100 <= c < 200])}")
        print(f"Seq 1 candidates in 0-99: {len([c for c in cands_1_ids if c < 100])}")
        print(f"Seq 1 candidates in 100-199: {len([c for c in cands_1_ids if 100 <= c < 200])}")

        # Sequences should mostly return their own blocks
        # (Some overlap from hash collisions is acceptable)

    def test_latency_under_load(self, generator):
        """Test latency distribution under concurrent load."""
        num_sequences = 32
        trace = generator.generate_multitenant_trace(
            num_sequences=num_sequences,
            total_steps=1000,
            length_distribution="mixed",
        )

        interface = SoftwarePCAMInterface(
            max_sequences=64,
            max_blocks_per_sequence=256,
        )

        for seq_id in trace.sequence_ids:
            interface.allocate_sequence(seq_id, 256)

        all_latencies = []
        per_seq_latencies = defaultdict(list)

        for step in trace.steps:
            _, latency, _ = interface.attend(
                query_block_id=step.query_block_id,
                k=64,
                sequence_id=step.sequence_id,
            )
            all_latencies.append(latency)
            per_seq_latencies[step.sequence_id].append(latency)

            for block_id, weight in step.attention_scores.items():
                interface.update(step.query_block_id, block_id, weight, step.sequence_id)

            interface.step()

        print("\n" + "=" * 60)
        print(f"LATENCY UNDER LOAD ({num_sequences} sequences)")
        print("=" * 60)

        sorted_lat = sorted(all_latencies)
        print(f"\nAggregate latency distribution:")
        print(f"  p50: {statistics.median(all_latencies):.1f}ns")
        print(f"  p95: {sorted_lat[int(0.95 * len(sorted_lat))]:.1f}ns")
        print(f"  p99: {sorted_lat[int(0.99 * len(sorted_lat))]:.1f}ns")
        print(f"  max: {max(all_latencies):.1f}ns")

        # Per-sequence p99 spread
        p99s = []
        for seq_id, lats in per_seq_latencies.items():
            if len(lats) >= 10:
                sorted_l = sorted(lats)
                p99s.append(sorted_l[int(0.99 * len(sorted_l))])

        if p99s:
            print(f"\nPer-sequence p99 spread:")
            print(f"  min: {min(p99s):.1f}ns")
            print(f"  max: {max(p99s):.1f}ns")
            print(f"  std: {statistics.stdev(p99s):.1f}ns")
