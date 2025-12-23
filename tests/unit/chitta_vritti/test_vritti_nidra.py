"""Tests for Nidrā (dormancy) computation.

Nidrā is high when:
- Representations are missing or weak
- This is the ONLY vṛtti that increases when signals are missing (INV-CV-4)
"""

import pytest
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs
from symbolu.chitta_vritti.vritti import compute_nidra
from symbolu.chitta_vritti.engine import ChittaVrittiEngine


class TestNidraComputation:
    """Test Nidrā formula behavior."""

    def test_all_layers_present_zero_nidra(self):
        """All layers present → zero nidrā."""
        inputs = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),
            semantic_rep=np.zeros(32),
            structural_rep=np.zeros(32),
            temporal_rep=np.zeros(32),
        )

        nidra = compute_nidra(inputs)
        assert nidra == 0.0

    def test_one_missing_quarter_nidra(self):
        """One layer missing → nidrā = 0.25."""
        inputs = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),
            semantic_rep=np.zeros(32),
            structural_rep=np.zeros(32),
            # temporal_rep missing
        )

        nidra = compute_nidra(inputs)
        assert nidra == pytest.approx(0.25)

    def test_two_missing_half_nidra(self):
        """Two layers missing → nidrā = 0.5."""
        inputs = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),
            semantic_rep=np.zeros(32),
            # structural_rep and temporal_rep missing
        )

        nidra = compute_nidra(inputs)
        assert nidra == pytest.approx(0.5)

    def test_three_missing_three_quarters_nidra(self):
        """Three layers missing → nidrā = 0.75."""
        inputs = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),
            # only phonemic present
        )

        nidra = compute_nidra(inputs)
        assert nidra == pytest.approx(0.75)

    def test_all_missing_full_nidra(self):
        """All layers missing → nidrā = 1.0."""
        inputs = ChittaVrittiInputs()  # All None

        nidra = compute_nidra(inputs)
        assert nidra == pytest.approx(1.0)

    def test_nidra_is_bounded(self):
        """Nidrā should always be in [0, 1]."""
        # Test all combinations
        test_cases = [
            (True, True, True, True),   # 0 missing
            (True, True, True, False),  # 1 missing
            (True, True, False, False), # 2 missing
            (True, False, False, False),# 3 missing
            (False, False, False, False),# 4 missing
        ]

        for phon, sem, struct, temp in test_cases:
            inputs = ChittaVrittiInputs(
                phonemic_rep=np.zeros(32) if phon else None,
                semantic_rep=np.zeros(32) if sem else None,
                structural_rep=np.zeros(32) if struct else None,
                temporal_rep=np.zeros(32) if temp else None,
            )
            nidra = compute_nidra(inputs)
            assert 0.0 <= nidra <= 1.0


class TestNidraIntegration:
    """Test Nidrā in full engine context."""

    def test_missing_signals_nidra_escalation(self):
        """Missing signals → nidrā escalation."""
        # Three missing
        inputs = ChittaVrittiInputs(
            phonemic_rep=np.ones(32),
            # others missing
        )

        engine = ChittaVrittiEngine()
        result = engine.compute(inputs)

        # Nidrā should be dominant (3/4 = 0.75 raw)
        assert result.dominant_vritti == "nidra"
        assert result.fast_path_used  # Fast path for nidrā

    def test_nidra_fast_path_for_mostly_missing(self):
        """3+ missing layers → nidrā fast path."""
        inputs = ChittaVrittiInputs(
            semantic_rep=np.ones(32),
            # 3 missing
        )

        engine = ChittaVrittiEngine()
        result = engine.compute(inputs)

        assert result.fast_path_used
        assert result.dominant_vritti == "nidra"

    def test_partial_presence_balanced(self):
        """2 layers present → moderate nidrā."""
        dim = 32
        rng = np.random.default_rng(42)

        inputs = ChittaVrittiInputs(
            phonemic_rep=rng.random(dim),
            semantic_rep=rng.random(dim),
            # 2 missing → nidrā = 0.5
            entropy=0.3,
        )

        engine = ChittaVrittiEngine()
        result = engine.compute(inputs)

        # Nidrā should be present but not necessarily dominant
        assert result.vritti["nidra"] > 0.0
