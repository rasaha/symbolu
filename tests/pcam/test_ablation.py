"""
Ablation and Sensitivity Tests - Prove robustness and identify value sources.

These tests show:
1. Which components contribute to PCAM's effectiveness
2. Sensitivity to hyperparameters
3. Stable operating region
"""

import pytest
from typing import Dict, List, Tuple
from dataclasses import dataclass
import copy

from simulator.pcam.traces.generators import SyntheticTraceGenerator
from simulator.pcam.interface import SoftwarePCAMInterface
from simulator.pcam.core.state import AttentionState


@dataclass
class AblationResult:
    """Result of an ablation experiment."""
    variant: str
    coverage: float
    mass_recall: float
    delta_coverage: float  # vs full system
    delta_mass: float


def run_pcam_with_config(
    trace,
    decay_enabled: bool = True,
    decay_rate: float = 0.99,
    anchors_enabled: bool = True,
    num_anchors: int = 4,
    update_frequency: int = 1,  # Update every N steps
    k: int = 64,
) -> Tuple[float, float]:
    """
    Run PCAM with specific configuration.

    Returns: (avg_coverage, avg_mass_recall)
    """
    interface = SoftwarePCAMInterface(
        max_sequences=4,
        max_blocks_per_sequence=512,
    )
    interface.allocate_sequence(0, 512)

    total_coverage = 0
    total_mass = 0

    for i, step in enumerate(trace.steps):
        # Get candidates
        candidates, _, _ = interface.attend(
            query_block_id=step.query_block_id,
            k=k,
            sequence_id=0,
        )
        candidate_ids = set(c[0] for c in candidates)

        # Add anchors if enabled
        if anchors_enabled:
            for anchor in range(num_anchors):
                candidate_ids.add(anchor)

        # Calculate coverage
        true_set = set(step.true_top_k[:k])
        coverage = len(candidate_ids & true_set) / max(1, len(true_set))
        total_coverage += coverage

        # Calculate mass recall
        total_attention = sum(step.attention_scores.values())
        captured = sum(step.attention_scores.get(b, 0) for b in candidate_ids)
        mass_recall = captured / max(0.001, total_attention)
        total_mass += mass_recall

        # Update (maybe)
        if i % update_frequency == 0:
            for block_id, weight in step.attention_scores.items():
                interface.update(step.query_block_id, block_id, weight, 0)

        # Decay (maybe)
        if decay_enabled and i % 10 == 0:
            interface.decay(decay_rate)

        interface.step()

    n = len(trace.steps)
    return total_coverage / n, total_mass / n


class TestAblations:
    """Ablation study tests."""

    @pytest.fixture
    def generator(self):
        return SyntheticTraceGenerator(seed=42)

    @pytest.fixture
    def chat_trace(self, generator):
        return generator.generate_chat_trace(num_turns=10, tokens_per_turn=(30, 50), top_k=64)

    @pytest.fixture
    def long_context_trace(self, generator):
        return generator.generate_long_context_trace(
            context_length=8192, num_queries=50, top_k=64
        )

    def test_decay_ablation(self, chat_trace):
        """Test impact of removing decay."""
        # Full system
        full_cov, full_mass = run_pcam_with_config(
            chat_trace, decay_enabled=True, decay_rate=0.99
        )

        # No decay
        no_decay_cov, no_decay_mass = run_pcam_with_config(
            chat_trace, decay_enabled=False
        )

        print("\nDECAY ABLATION:")
        print(f"{'Variant':<20} {'Coverage':>12} {'Mass Recall':>12}")
        print("-" * 45)
        print(f"{'Full (decay=0.99)':<20} {full_cov:>12.1%} {full_mass:>12.1%}")
        print(f"{'No decay':<20} {no_decay_cov:>12.1%} {no_decay_mass:>12.1%}")
        print(f"{'Δ (no decay)':<20} {no_decay_cov - full_cov:>+12.1%} {no_decay_mass - full_mass:>+12.1%}")

        # Decay should help prevent stale attention from dominating
        # But for short traces, difference may be small

    def test_anchor_ablation(self, chat_trace):
        """Test impact of removing anchors/sinks."""
        # With anchors
        with_cov, with_mass = run_pcam_with_config(
            chat_trace, anchors_enabled=True, num_anchors=4
        )

        # Without anchors
        without_cov, without_mass = run_pcam_with_config(
            chat_trace, anchors_enabled=False, num_anchors=0
        )

        print("\nANCHOR/SINK ABLATION:")
        print(f"{'Variant':<20} {'Coverage':>12} {'Mass Recall':>12}")
        print("-" * 45)
        print(f"{'With anchors (4)':<20} {with_cov:>12.1%} {with_mass:>12.1%}")
        print(f"{'Without anchors':<20} {without_cov:>12.1%} {without_mass:>12.1%}")
        print(f"{'Δ (no anchors)':<20} {without_cov - with_cov:>+12.1%} {without_mass - with_mass:>+12.1%}")

    def test_update_frequency_ablation(self, chat_trace):
        """Test impact of update frequency."""
        frequencies = [1, 2, 5, 10]

        print("\nUPDATE FREQUENCY ABLATION:")
        print(f"{'Update Freq':>12} {'Coverage':>12} {'Mass Recall':>12}")
        print("-" * 40)

        for freq in frequencies:
            cov, mass = run_pcam_with_config(chat_trace, update_frequency=freq)
            print(f"{f'Every {freq}':>12} {cov:>12.1%} {mass:>12.1%}")

    def test_decay_rate_sensitivity(self, chat_trace):
        """Test sensitivity to decay rate."""
        rates = [0.9, 0.95, 0.99, 0.999, 1.0]

        print("\nDECAY RATE SENSITIVITY:")
        print(f"{'Rate':>12} {'Coverage':>12} {'Mass Recall':>12}")
        print("-" * 40)

        for rate in rates:
            cov, mass = run_pcam_with_config(chat_trace, decay_rate=rate)
            print(f"{rate:>12.3f} {cov:>12.1%} {mass:>12.1%}")


class TestKSensitivity:
    """Tests for K (candidate set size) sensitivity."""

    @pytest.fixture
    def generator(self):
        return SyntheticTraceGenerator(seed=42)

    def test_k_sensitivity_chat(self, generator):
        """Test K sensitivity on chat workload."""
        trace = generator.generate_chat_trace(
            num_turns=10, tokens_per_turn=(30, 50), top_k=256
        )

        k_values = [16, 32, 64, 128, 256]

        print("\nK SENSITIVITY (Chat):")
        print(f"{'K':>8} {'Coverage':>12} {'Mass Recall':>12} {'Compute Red':>14}")
        print("-" * 50)

        for k in k_values:
            cov, mass = run_pcam_with_config(trace, k=k)
            # Compute reduction assumes 4096 context
            compute_red = 1 - (k * 16 / 4096)
            print(f"{k:>8} {cov:>12.1%} {mass:>12.1%} {compute_red:>14.1%}")

    def test_k_sensitivity_long_context(self, generator):
        """Test K sensitivity on long context workload."""
        trace = generator.generate_long_context_trace(
            context_length=16384, num_queries=50, top_k=256
        )

        k_values = [32, 64, 128, 256, 512]

        print("\nK SENSITIVITY (Long Context, 16K):")
        print(f"{'K':>8} {'Coverage':>12} {'Mass Recall':>12} {'Compute Red':>14}")
        print("-" * 50)

        for k in k_values:
            cov, mass = run_pcam_with_config(trace, k=k)
            compute_red = 1 - (k * 16 / 16384)
            print(f"{k:>8} {cov:>12.1%} {mass:>12.1%} {compute_red:>14.1%}")

    def test_adaptive_k_benefit(self, generator):
        """
        Test benefit of adaptive K based on context length.

        Hypothesis: K should scale with log(context) or sqrt(context).
        """
        contexts = [2048, 4096, 8192, 16384, 32768]

        print("\nADAPTIVE K ANALYSIS:")
        print("Comparing fixed K=64 vs K=log2(context)*8")
        print()
        print(f"{'Context':>10} {'Fixed K':>10} {'Adaptive K':>12} {'Fixed Cov':>12} {'Adapt Cov':>12}")
        print("-" * 60)

        for ctx in contexts:
            trace = generator.generate_long_context_trace(
                context_length=ctx, num_queries=20, top_k=256
            )

            # Fixed K
            fixed_k = 64
            fixed_cov, _ = run_pcam_with_config(trace, k=fixed_k)

            # Adaptive K: scales with log2(context)
            import math
            adaptive_k = int(math.log2(ctx) * 8)
            adapt_cov, _ = run_pcam_with_config(trace, k=adaptive_k)

            print(f"{ctx:>10,} {fixed_k:>10} {adaptive_k:>12} {fixed_cov:>12.1%} {adapt_cov:>12.1%}")


class TestComponentContributions:
    """Test contribution of each component."""

    @pytest.fixture
    def generator(self):
        return SyntheticTraceGenerator(seed=42)

    def test_full_ablation_matrix(self, generator):
        """Run full ablation matrix."""
        trace = generator.generate_chat_trace(
            num_turns=10, tokens_per_turn=(30, 50), top_k=64
        )

        configs = [
            ("Full system", True, True, 0.99, 1),
            ("No decay", False, True, 0.99, 1),
            ("No anchors", True, False, 0.99, 1),
            ("Slow decay", True, True, 0.999, 1),
            ("Fast decay", True, True, 0.9, 1),
            ("Update/5", True, True, 0.99, 5),
            ("Update/10", True, True, 0.99, 10),
            ("Minimal", False, False, 1.0, 10),
        ]

        print("\n" + "=" * 70)
        print("FULL ABLATION MATRIX")
        print("=" * 70)
        print(f"{'Variant':<20} {'Decay':>8} {'Anchors':>8} {'Coverage':>10} {'Mass':>10}")
        print("-" * 60)

        baseline_cov = None

        for name, decay, anchors, rate, freq in configs:
            cov, mass = run_pcam_with_config(
                trace,
                decay_enabled=decay,
                anchors_enabled=anchors,
                decay_rate=rate,
                update_frequency=freq,
            )

            if baseline_cov is None:
                baseline_cov = cov

            print(f"{name:<20} {str(decay):>8} {str(anchors):>8} {cov:>10.1%} {mass:>10.1%}")

        print()
        print("Note: Minimal = no decay, no anchors, update every 10 steps")

    def test_component_value_attribution(self, generator):
        """
        Attribute value to each component.

        Shows: "X% of value comes from decay, Y% from anchors, etc."
        """
        trace = generator.generate_long_context_trace(
            context_length=8192, num_queries=50, top_k=64
        )

        # Baseline: minimal system
        minimal_cov, minimal_mass = run_pcam_with_config(
            trace, decay_enabled=False, anchors_enabled=False, update_frequency=10
        )

        # Full system
        full_cov, full_mass = run_pcam_with_config(
            trace, decay_enabled=True, anchors_enabled=True, update_frequency=1
        )

        # Add each component incrementally
        with_updates, _ = run_pcam_with_config(
            trace, decay_enabled=False, anchors_enabled=False, update_frequency=1
        )
        with_anchors, _ = run_pcam_with_config(
            trace, decay_enabled=False, anchors_enabled=True, update_frequency=1
        )
        with_decay, _ = run_pcam_with_config(
            trace, decay_enabled=True, anchors_enabled=False, update_frequency=1
        )

        total_gain = full_cov - minimal_cov
        update_contrib = with_updates - minimal_cov
        anchor_contrib = with_anchors - with_updates
        decay_contrib = full_cov - with_anchors

        print("\n" + "=" * 60)
        print("COMPONENT VALUE ATTRIBUTION")
        print("=" * 60)
        print(f"\nBaseline (minimal): {minimal_cov:.1%}")
        print(f"Full system: {full_cov:.1%}")
        print(f"Total improvement: {total_gain:+.1%}")
        print()
        print("Contribution by component:")
        if total_gain > 0:
            print(f"  Frequent updates: {update_contrib:+.1%} ({update_contrib/total_gain:.0%} of gain)")
            print(f"  Anchors/sinks: {anchor_contrib:+.1%}")
            print(f"  Decay: {decay_contrib:+.1%}")
        else:
            print("  (No significant gain)")
