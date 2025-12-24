"""Tests for Vikalpa (conceptual branching) computation.

Vikalpa is high when:
- Agreement is uneven across layers (high variance in fractures)
- Entropy is high (multiple interpretations possible)
"""

import pytest
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs, OptimizedConfig
from symbolu.chitta_vritti.vritti import compute_vikalpa, variance
from symbolu.chitta_vritti.engine import ChittaVrittiEngine


class TestVikalpaComputation:
    """Test Vikalpa formula behavior."""

    def test_no_fractures_zero_vikalpa(self):
        """No fractures → zero vikalpa."""
        config = OptimizedConfig()
        vikalpa = compute_vikalpa(
            fractures={},
            entropy=0.8,
            config=config
        )
        assert vikalpa == 0.0

    def test_single_fracture_zero_vikalpa(self):
        """Single fracture (no variance) → zero vikalpa."""
        config = OptimizedConfig()
        vikalpa = compute_vikalpa(
            fractures={("a", "b"): 0.5},
            entropy=0.8,
            config=config
        )
        assert vikalpa == 0.0

    def test_uniform_fractures_low_vikalpa(self):
        """Uniform fractures (low variance) → low vikalpa."""
        config = OptimizedConfig(vikalpa_variance_floor=0.2)

        # All fractures are 0.5 → variance = 0
        vikalpa = compute_vikalpa(
            fractures={("a", "b"): 0.5, ("a", "c"): 0.5, ("b", "c"): 0.5},
            entropy=0.8,
            config=config
        )
        assert vikalpa == 0.0

    def test_high_variance_high_entropy_activates_vikalpa(self):
        """High variance + high entropy → vikalpa activates."""
        config = OptimizedConfig(vikalpa_variance_floor=0.1)

        # Mixed fractures → high variance
        vikalpa = compute_vikalpa(
            fractures={("a", "b"): 0.1, ("a", "c"): 0.9, ("b", "c"): 0.5},
            entropy=0.8,
            config=config
        )
        assert vikalpa > 0.0

    def test_low_entropy_suppresses_vikalpa(self):
        """Low entropy should suppress vikalpa even with high variance."""
        config = OptimizedConfig(vikalpa_variance_floor=0.1)

        # High variance but low entropy
        vikalpa = compute_vikalpa(
            fractures={("a", "b"): 0.1, ("a", "c"): 0.9},
            entropy=0.1,  # Low entropy
            config=config
        )
        assert vikalpa == 0.0

    def test_vikalpa_is_bounded(self):
        """Vikalpa should always be in [0, 1]."""
        config = OptimizedConfig()

        for entropy in [0.0, 0.3, 0.5, 0.8, 1.0]:
            vikalpa = compute_vikalpa(
                fractures={("a", "b"): 0.1, ("a", "c"): 0.9, ("b", "c"): 0.5},
                entropy=entropy,
                config=config
            )
            assert 0.0 <= vikalpa <= 1.0


class TestVarianceHelper:
    """Test the variance helper function."""

    def test_empty_list_zero_variance(self):
        """Empty list → zero variance."""
        assert variance([]) == 0.0

    def test_single_value_zero_variance(self):
        """Single value → zero variance."""
        assert variance([0.5]) == 0.0

    def test_uniform_values_zero_variance(self):
        """Uniform values → zero variance."""
        assert variance([0.5, 0.5, 0.5]) == pytest.approx(0.0)

    def test_varied_values_positive_variance(self):
        """Varied values → positive variance."""
        # [0, 1] → mean=0.5, variance = ((0-0.5)^2 + (1-0.5)^2)/2 = 0.25
        assert variance([0.0, 1.0]) == pytest.approx(0.25)


class TestVikalpaIntegration:
    """Test Vikalpa in full engine context."""

    def test_high_entropy_branching_scenario(self):
        """High entropy with uneven agreement → vikalpa contribution."""
        dim = 32
        rng = np.random.default_rng(42)

        # Create divergent representations
        base = rng.random(dim)
        inputs = ChittaVrittiInputs(
            phonemic_rep=base,
            semantic_rep=base + rng.random(dim) * 0.5,  # Close to base
            structural_rep=rng.random(dim),  # Different
            temporal_rep=base + rng.random(dim) * 0.5,  # Close to base
            entropy=0.7,  # High entropy
            motion=0.3,
        )

        engine = ChittaVrittiEngine()
        result = engine.compute(inputs)

        # Vikalpa should have some presence
        assert result.vritti["vikalpa"] > 0.0
