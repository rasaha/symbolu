"""Tests for Pramāṇa (valid cognition) computation.

Pramāṇa is high when:
- Coherence is strong (layers agree)
- Entropy is low (certainty)
- Motion is stable (not changing rapidly)
"""

import pytest
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs, OptimizedConfig
from symbolu.chitta_vritti.vritti import compute_pramana
from symbolu.chitta_vritti.engine import ChittaVrittiEngine


class TestPramanaComputation:
    """Test Pramāṇa formula behavior."""

    def test_high_coherence_low_entropy_stable_motion(self):
        """Perfect conditions → high pramāṇa."""
        config = OptimizedConfig()
        pramana = compute_pramana(
            coherence=1.0,
            entropy=0.0,
            motion=0.0,
            config=config
        )
        assert pramana == pytest.approx(1.0)

    def test_low_coherence_reduces_pramana(self):
        """Low coherence should reduce pramāṇa."""
        config = OptimizedConfig()

        high_coherence = compute_pramana(
            coherence=1.0, entropy=0.0, motion=0.0, config=config
        )
        low_coherence = compute_pramana(
            coherence=0.3, entropy=0.0, motion=0.0, config=config
        )

        assert low_coherence < high_coherence

    def test_high_entropy_reduces_pramana(self):
        """High entropy should reduce pramāṇa."""
        config = OptimizedConfig()

        low_entropy = compute_pramana(
            coherence=1.0, entropy=0.0, motion=0.0, config=config
        )
        high_entropy = compute_pramana(
            coherence=1.0, entropy=0.5, motion=0.0, config=config
        )

        assert high_entropy < low_entropy

    def test_entropy_above_ceiling_zeros_pramana(self):
        """Entropy above ceiling should zero the entropy factor."""
        config = OptimizedConfig(pramana_entropy_ceiling=0.3)

        pramana = compute_pramana(
            coherence=1.0,
            entropy=0.5,  # Above 0.3 ceiling
            motion=0.0,
            config=config
        )

        # entropy_factor = max(0, 1 - 0.5/0.3) = max(0, -0.67) = 0
        assert pramana == pytest.approx(0.0)

    def test_high_motion_reduces_pramana(self):
        """High motion should reduce pramāṇa."""
        config = OptimizedConfig()

        stable = compute_pramana(
            coherence=1.0, entropy=0.0, motion=0.0, config=config
        )
        unstable = compute_pramana(
            coherence=1.0, entropy=0.0, motion=0.8, config=config
        )

        assert unstable < stable

    def test_pramana_is_bounded(self):
        """Pramāṇa should always be in [0, 1]."""
        config = OptimizedConfig()

        for coherence in [0.0, 0.5, 1.0]:
            for entropy in [0.0, 0.5, 1.0]:
                for motion in [0.0, 0.5, 1.0]:
                    pramana = compute_pramana(coherence, entropy, motion, config)
                    assert 0.0 <= pramana <= 1.0


class TestPramanaIntegration:
    """Test Pramāṇa in full engine context."""

    def test_all_layers_agree_high_pramana(self):
        """When all layers have identical representations → pramāṇa dominant."""
        dim = 32
        identical = np.ones(dim) / np.sqrt(dim)  # L2 normalized

        inputs = ChittaVrittiInputs(
            phonemic_rep=identical.copy(),
            semantic_rep=identical.copy(),
            structural_rep=identical.copy(),
            temporal_rep=identical.copy(),
            entropy=0.05,
            motion=0.0,
        )

        engine = ChittaVrittiEngine()
        result = engine.compute(inputs)

        # Pramāṇa should be dominant or use fast path
        assert result.dominant_vritti == "pramana" or result.fast_path_used

    def test_fast_path_triggers_for_low_entropy(self):
        """Low entropy + all layers → fast path with high pramāṇa."""
        dim = 32
        rng = np.random.default_rng(42)

        # Similar but not identical representations
        base = rng.random(dim)
        inputs = ChittaVrittiInputs(
            phonemic_rep=base + rng.random(dim) * 0.1,
            semantic_rep=base + rng.random(dim) * 0.1,
            structural_rep=base + rng.random(dim) * 0.1,
            temporal_rep=base + rng.random(dim) * 0.1,
            entropy=0.05,  # Low entropy
            motion=0.0,
        )

        engine = ChittaVrittiEngine()
        result = engine.compute(inputs)

        # Should use fast path
        assert result.fast_path_used
        assert result.vritti["pramana"] > 0.8
