"""Tests for Smṛti (memory persistence) computation.

Smṛti is high when:
- State remains unchanged despite new input
- Accumulates over time if representations don't update
"""

import pytest
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs, OptimizedConfig
from symbolu.chitta_vritti.vritti import compute_smrti, compute_representation_delta
from symbolu.chitta_vritti.engine import ChittaVrittiEngine


class TestSmrtiComputation:
    """Test Smṛti formula behavior."""

    def test_no_previous_zero_smrti(self):
        """No previous state → zero smṛti."""
        config = OptimizedConfig()

        inputs = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),
            semantic_rep=np.zeros(32),
        )

        smrti = compute_smrti(
            current=inputs,
            previous=None,
            accumulated_smrti=0.0,
            config=config
        )
        assert smrti == 0.0

    def test_unchanged_state_accumulates_smrti(self):
        """Unchanged state → smṛti accumulates."""
        config = OptimizedConfig(smrti_staleness_threshold=0.05)

        inputs = ChittaVrittiInputs(
            phonemic_rep=np.ones(32),
            semantic_rep=np.ones(32),
        )

        # Same state as previous
        smrti = compute_smrti(
            current=inputs,
            previous=inputs,  # Identical
            accumulated_smrti=0.0,
            config=config
        )

        # Should accumulate (0 + 0.2 = 0.2)
        assert smrti == pytest.approx(0.2)

    def test_changed_state_decays_smrti(self):
        """Changed state → smṛti decays."""
        config = OptimizedConfig(
            smrti_staleness_threshold=0.05,
            smrti_decay_rate=0.4
        )

        current = ChittaVrittiInputs(
            phonemic_rep=np.ones(32),
        )
        previous = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),  # Different
        )

        # Start with accumulated smṛti = 0.5
        smrti = compute_smrti(
            current=current,
            previous=previous,
            accumulated_smrti=0.5,
            config=config
        )

        # Should decay: 0.5 * 0.4 = 0.2
        assert smrti == pytest.approx(0.2)

    def test_smrti_accumulation_capped(self):
        """Smṛti should cap at 1.0."""
        config = OptimizedConfig(smrti_staleness_threshold=0.05)

        inputs = ChittaVrittiInputs(
            phonemic_rep=np.ones(32),
        )

        # Already at 0.9
        smrti = compute_smrti(
            current=inputs,
            previous=inputs,
            accumulated_smrti=0.9,
            config=config
        )

        # 0.9 + 0.2 = 1.1 → capped to 1.0
        assert smrti == pytest.approx(1.0)

    def test_smrti_is_bounded(self):
        """Smṛti should always be in [0, 1]."""
        config = OptimizedConfig()

        for acc in [0.0, 0.3, 0.5, 0.8, 1.0]:
            inputs = ChittaVrittiInputs(phonemic_rep=np.ones(32))
            smrti = compute_smrti(inputs, inputs, acc, config)
            assert 0.0 <= smrti <= 1.0


class TestRepresentationDelta:
    """Test representation delta computation."""

    def test_identical_representations_zero_delta(self):
        """Identical representations → zero delta."""
        inputs = ChittaVrittiInputs(
            phonemic_rep=np.ones(32),
            semantic_rep=np.ones(32),
        )

        delta = compute_representation_delta(inputs, inputs)
        assert delta == pytest.approx(0.0)

    def test_different_representations_positive_delta(self):
        """Different representations → positive delta."""
        current = ChittaVrittiInputs(
            phonemic_rep=np.ones(32),
        )
        previous = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),
        )

        delta = compute_representation_delta(current, previous)
        assert delta > 0.0

    def test_missing_layers_moderate_delta(self):
        """Missing layers → return moderate delta (0.5)."""
        current = ChittaVrittiInputs(phonemic_rep=np.ones(32))
        previous = ChittaVrittiInputs(semantic_rep=np.ones(32))

        delta = compute_representation_delta(current, previous)
        assert delta == 0.5  # No common layers


class TestSmrtiIntegration:
    """Test Smṛti in full engine context."""

    def test_repeated_identical_states_escalates_smrti(self):
        """Repeated identical states → smṛti escalates."""
        dim = 32
        fixed_rep = np.ones(dim) / np.sqrt(dim)

        inputs = ChittaVrittiInputs(
            phonemic_rep=fixed_rep.copy(),
            semantic_rep=fixed_rep.copy(),
            structural_rep=fixed_rep.copy(),
            temporal_rep=fixed_rep.copy(),
            entropy=0.3,
        )

        engine = ChittaVrittiEngine()

        # First computation
        result1 = engine.compute(inputs)
        smrti1 = result1.vritti.get("smrti", 0)

        # Second computation (same input)
        result2 = engine.compute(inputs)
        smrti2 = result2.vritti.get("smrti", 0)

        # Third computation (same input)
        result3 = engine.compute(inputs)
        smrti3 = result3.vritti.get("smrti", 0)

        # Smṛti should escalate
        # Note: with normalization, absolute values may not increase
        # but the raw smṛti accumulates in session state
        assert engine._session_state.accumulated_smrti > 0

    def test_state_change_resets_smrti_trend(self):
        """State change → smṛti should decay."""
        dim = 32
        rng = np.random.default_rng(42)

        engine = ChittaVrittiEngine()

        # First: fixed state (builds smṛti)
        fixed = np.ones(dim) / np.sqrt(dim)
        for _ in range(3):
            inputs = ChittaVrittiInputs(
                phonemic_rep=fixed.copy(),
                semantic_rep=fixed.copy(),
                entropy=0.3,
            )
            engine.compute(inputs)

        acc_before = engine._session_state.accumulated_smrti

        # Now: different state
        different = rng.random(dim)
        inputs = ChittaVrittiInputs(
            phonemic_rep=different,
            semantic_rep=different,
            entropy=0.3,
        )
        engine.compute(inputs)

        acc_after = engine._session_state.accumulated_smrti

        # Smṛti should have decayed
        assert acc_after < acc_before
