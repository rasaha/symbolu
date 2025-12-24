"""Tests for Viparyaya (misperception) computation.

Viparyaya is high when:
- Layers confidently oppose each other (high fracture + high confidence)
- Represents semantic inversion / confident disagreement
"""

import pytest
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs, OptimizedConfig
from symbolu.chitta_vritti.vritti import compute_viparyaya
from symbolu.chitta_vritti.engine import ChittaVrittiEngine


class TestViparyayaComputation:
    """Test Viparyaya formula behavior."""

    def test_no_fractures_zero_viparyaya(self):
        """No fractures → zero viparyaya."""
        config = OptimizedConfig()
        viparyaya = compute_viparyaya(
            fractures={},
            confidence=1.0,
            config=config
        )
        assert viparyaya == 0.0

    def test_low_fractures_zero_viparyaya(self):
        """Low fractures (< 0.7) → zero viparyaya."""
        config = OptimizedConfig()
        viparyaya = compute_viparyaya(
            fractures={("a", "b"): 0.5, ("a", "c"): 0.4},
            confidence=1.0,
            config=config
        )
        assert viparyaya == 0.0

    def test_high_fracture_activates_viparyaya(self):
        """High fracture (> 0.7) → viparyaya activates."""
        config = OptimizedConfig()
        viparyaya = compute_viparyaya(
            fractures={("a", "b"): 0.9},  # High fracture
            confidence=1.0,
            config=config
        )
        assert viparyaya > 0.0

    def test_max_fracture_full_confidence_high_viparyaya(self):
        """Max fracture (1.0) + full confidence → high viparyaya."""
        config = OptimizedConfig()
        viparyaya = compute_viparyaya(
            fractures={("a", "b"): 1.0},
            confidence=1.0,
            config=config
        )
        # (1.0 - 0.7) / 0.3 * 1.0 = 1.0
        assert viparyaya == pytest.approx(1.0)

    def test_low_confidence_reduces_viparyaya(self):
        """Low confidence should reduce viparyaya."""
        config = OptimizedConfig()

        high_conf = compute_viparyaya(
            fractures={("a", "b"): 0.9},
            confidence=1.0,
            config=config
        )
        low_conf = compute_viparyaya(
            fractures={("a", "b"): 0.9},
            confidence=0.3,
            config=config
        )

        assert low_conf < high_conf

    def test_viparyaya_is_bounded(self):
        """Viparyaya should always be in [0, 1]."""
        config = OptimizedConfig()

        for frac in [0.0, 0.5, 0.7, 0.85, 1.0]:
            for conf in [0.0, 0.5, 1.0]:
                viparyaya = compute_viparyaya(
                    fractures={("a", "b"): frac},
                    confidence=conf,
                    config=config
                )
                assert 0.0 <= viparyaya <= 1.0


class TestViparyayaIntegration:
    """Test Viparyaya in full engine context."""

    def test_opposing_layers_high_viparyaya(self):
        """Opposite representations → high viparyaya."""
        dim = 32

        # Create opposing vectors
        vec_a = np.zeros(dim)
        vec_a[0] = 1.0  # Points in +x

        vec_b = np.zeros(dim)
        vec_b[0] = -1.0  # Points in -x (opposite)

        inputs = ChittaVrittiInputs(
            semantic_rep=vec_a,
            structural_rep=vec_b,
            entropy=0.3,
            motion=0.1,
            confidence=1.0,
        )

        engine = ChittaVrittiEngine()
        result = engine.compute(inputs)

        # Viparyaya should be significant
        assert result.vritti["viparyaya"] > 0.1

    def test_viparyaya_blocks_fast_path(self):
        """High viparyaya should block fast path (safety gate)."""
        dim = 32

        # Create opposing but otherwise "good" conditions
        vec_a = np.zeros(dim)
        vec_a[0] = 1.0

        vec_b = np.zeros(dim)
        vec_b[0] = -1.0

        # Use vec_a for 3 layers, vec_b for 1 (creates opposition)
        inputs = ChittaVrittiInputs(
            phonemic_rep=vec_a,
            semantic_rep=vec_a,
            structural_rep=vec_b,  # Opposing
            temporal_rep=vec_a,
            entropy=0.05,  # Low entropy would normally trigger fast path
            motion=0.0,
        )

        engine = ChittaVrittiEngine()
        result = engine.compute(inputs)

        # Should NOT use fast path due to viparyaya safety gate
        assert not result.fast_path_used
