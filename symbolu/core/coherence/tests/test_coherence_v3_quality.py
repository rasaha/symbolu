"""
Phase 12: Coherence v3 Quality Unit Tests

Tests for _compute_coherence_v3_quality() in CoherenceEngine.

Verifies:
- Range correctness ([0.0, 1.0])
- Soft stability windows behavior
- Divergence penalty
- Determinism
- Graceful handling of missing metrics
"""

import pytest
from symbolu.core.coherence.coherence_engine import CoherenceEngine


class TestCoherenceV3Quality:
    """Unit tests for coherence v3 quality computation."""

    def setup_method(self):
        """Setup test fixtures."""
        self.engine = CoherenceEngine(window=10)

    def test_range_correctness(self):
        """Test that quality score is always in [0.0, 1.0]."""
        # Test various combinations
        test_cases = [
            # (base, v3, resonance, arc_alignment, tension)
            (0.5, 0.5, 0.5, 0.5, 0.5),  # All neutral
            (0.8, 0.8, 0.8, 0.8, 0.2),  # Ideal conditions
            (0.3, 0.3, 0.2, 0.2, 0.9),  # Poor conditions
            (1.0, 1.0, 1.0, 1.0, 0.0),  # Maximum values
            (0.0, 0.0, 0.0, 0.0, 1.0),  # Minimum values
        ]

        for base, v3, res, arc, ten in test_cases:
            quality = self.engine._compute_coherence_v3_quality(
                base=base,
                v3=v3,
                resonance_index=res,
                arc_alignment_index=arc,
                tension_index=ten,
            )

            assert quality is not None, f"Quality should not be None for valid inputs"
            assert 0.0 <= quality <= 1.0, f"Quality {quality} out of range [0, 1]"

    def test_missing_inputs_return_none(self):
        """Test that missing required inputs return None."""
        # Missing base
        quality = self.engine._compute_coherence_v3_quality(
            base=None,
            v3=0.5,
            resonance_index=0.5,
            arc_alignment_index=0.5,
            tension_index=0.5,
        )
        assert quality is None, "Should return None when base is missing"

        # Missing v3
        quality = self.engine._compute_coherence_v3_quality(
            base=0.5,
            v3=None,
            resonance_index=0.5,
            arc_alignment_index=0.5,
            tension_index=0.5,
        )
        assert quality is None, "Should return None when v3 is missing"

    def test_missing_optional_metrics_use_defaults(self):
        """Test that missing optional metrics gracefully default to 0.5."""
        # All optional metrics missing
        quality = self.engine._compute_coherence_v3_quality(
            base=0.6,
            v3=0.6,
            resonance_index=None,
            arc_alignment_index=None,
            tension_index=None,
        )

        assert quality is not None, "Should not return None for missing optional metrics"
        assert 0.0 <= quality <= 1.0, "Quality should be in valid range"

    def test_soft_window_behavior_resonance(self):
        """Test resonance window soft behavior."""
        base, v3 = 0.6, 0.6  # Fixed, no divergence

        # Low resonance (< 0.3) → low quality
        quality_low = self.engine._compute_coherence_v3_quality(
            base=base,
            v3=v3,
            resonance_index=0.2,
            arc_alignment_index=0.5,
            tension_index=0.5,
        )

        # Moderate resonance (0.5) → medium quality
        quality_mid = self.engine._compute_coherence_v3_quality(
            base=base,
            v3=v3,
            resonance_index=0.5,
            arc_alignment_index=0.5,
            tension_index=0.5,
        )

        # High resonance (> 0.7) → high quality
        quality_high = self.engine._compute_coherence_v3_quality(
            base=base,
            v3=v3,
            resonance_index=0.8,
            arc_alignment_index=0.5,
            tension_index=0.5,
        )

        assert quality_low < quality_mid < quality_high, \
            "Higher resonance should yield higher quality"

    def test_soft_window_behavior_arc_alignment(self):
        """Test arc alignment window soft behavior."""
        base, v3 = 0.6, 0.6  # Fixed, no divergence

        # Low arc alignment (< 0.3) → low quality
        quality_low = self.engine._compute_coherence_v3_quality(
            base=base,
            v3=v3,
            resonance_index=0.5,
            arc_alignment_index=0.2,
            tension_index=0.5,
        )

        # High arc alignment (> 0.7) → high quality
        quality_high = self.engine._compute_coherence_v3_quality(
            base=base,
            v3=v3,
            resonance_index=0.5,
            arc_alignment_index=0.8,
            tension_index=0.5,
        )

        assert quality_low < quality_high, \
            "Higher arc alignment should yield higher quality"

    def test_soft_window_behavior_tension(self):
        """Test tension window soft behavior (inverse)."""
        base, v3 = 0.6, 0.6  # Fixed, no divergence

        # Low tension (< 0.3) → high quality
        quality_low_tension = self.engine._compute_coherence_v3_quality(
            base=base,
            v3=v3,
            resonance_index=0.5,
            arc_alignment_index=0.5,
            tension_index=0.2,
        )

        # High tension (> 0.7) → low quality
        quality_high_tension = self.engine._compute_coherence_v3_quality(
            base=base,
            v3=v3,
            resonance_index=0.5,
            arc_alignment_index=0.5,
            tension_index=0.8,
        )

        assert quality_low_tension > quality_high_tension, \
            "Lower tension should yield higher quality"

    def test_divergence_penalty_behavior(self):
        """Test divergence penalty between v1 and v3."""
        # Ideal stability (neutral)
        res, arc, ten = 0.5, 0.5, 0.5

        # No divergence (v3 ≈ base) → high quality
        quality_no_divergence = self.engine._compute_coherence_v3_quality(
            base=0.6,
            v3=0.6,
            resonance_index=res,
            arc_alignment_index=arc,
            tension_index=ten,
        )

        # Small divergence (|v3 - base| = 0.1) → slight penalty
        quality_small_divergence = self.engine._compute_coherence_v3_quality(
            base=0.6,
            v3=0.7,
            resonance_index=res,
            arc_alignment_index=arc,
            tension_index=ten,
        )

        # Large divergence (|v3 - base| >= 0.3) → heavy penalty
        quality_large_divergence = self.engine._compute_coherence_v3_quality(
            base=0.6,
            v3=0.95,
            resonance_index=res,
            arc_alignment_index=arc,
            tension_index=ten,
        )

        assert quality_no_divergence > quality_small_divergence > quality_large_divergence, \
            "Larger divergence should yield lower quality"

    def test_determinism(self):
        """Test that same inputs produce same outputs."""
        inputs = {
            "base": 0.7,
            "v3": 0.75,
            "resonance_index": 0.6,
            "arc_alignment_index": 0.65,
            "tension_index": 0.4,
        }

        # Compute quality multiple times
        quality1 = self.engine._compute_coherence_v3_quality(**inputs)
        quality2 = self.engine._compute_coherence_v3_quality(**inputs)
        quality3 = self.engine._compute_coherence_v3_quality(**inputs)

        assert quality1 == quality2 == quality3, "Same inputs should produce same output"

    def test_ideal_conditions_high_quality(self):
        """Test that ideal conditions produce high quality."""
        # Ideal: high resonance, high arc, low tension, no divergence
        quality = self.engine._compute_coherence_v3_quality(
            base=0.8,
            v3=0.8,
            resonance_index=0.8,
            arc_alignment_index=0.8,
            tension_index=0.2,
        )

        assert quality >= 0.7, f"Ideal conditions should yield high quality, got {quality}"

    def test_poor_conditions_low_quality(self):
        """Test that poor conditions produce low quality."""
        # Poor: low resonance, low arc, high tension, large divergence
        quality = self.engine._compute_coherence_v3_quality(
            base=0.5,
            v3=0.9,
            resonance_index=0.2,
            arc_alignment_index=0.2,
            tension_index=0.9,
        )

        assert quality <= 0.3, f"Poor conditions should yield low quality, got {quality}"

    def test_continuous_window_transitions(self):
        """Test that window transitions are continuous (no sharp jumps)."""
        base, v3 = 0.6, 0.6  # Fixed

        # Test resonance window continuity around 0.3 and 0.7 boundaries
        qualities_resonance = []
        for res in [0.25, 0.3, 0.35, 0.65, 0.7, 0.75]:
            q = self.engine._compute_coherence_v3_quality(
                base=base, v3=v3, resonance_index=res,
                arc_alignment_index=0.5, tension_index=0.5,
            )
            qualities_resonance.append(q)

        # Check monotonic increase (allowing for small floating point errors)
        for i in range(len(qualities_resonance) - 1):
            assert qualities_resonance[i] <= qualities_resonance[i + 1] + 1e-6, \
                f"Window transition should be continuous, got {qualities_resonance}"

    def test_edge_case_all_zeros(self):
        """Test edge case with all zero values."""
        quality = self.engine._compute_coherence_v3_quality(
            base=0.0,
            v3=0.0,
            resonance_index=0.0,
            arc_alignment_index=0.0,
            tension_index=0.0,
        )

        assert quality is not None, "Should handle all-zero inputs"
        assert 0.0 <= quality <= 1.0, "Quality should be in valid range"

    def test_edge_case_all_ones(self):
        """Test edge case with all maximum values."""
        quality = self.engine._compute_coherence_v3_quality(
            base=1.0,
            v3=1.0,
            resonance_index=1.0,
            arc_alignment_index=1.0,
            tension_index=1.0,
        )

        assert quality is not None, "Should handle all-maximum inputs"
        assert 0.0 <= quality <= 1.0, "Quality should be in valid range"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
