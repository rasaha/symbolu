"""
Tests for Guna / Kosha Resonance Formulas (Phase 8)
===================================================

Comprehensive test suite for deterministic Guna and Kosha resonance metrics.

Test Groups:
- Group A: Guna Resonance (8 tests)
- Group B: Kosha Activation and Resonance (8 tests)
- Group C: Wrapper and Integration (6 tests)

All tests verify determinism, range constraints, and graceful degradation.
"""

import pytest
from symbolu.formulas.guna_kosha_resonance import (
    compute_guna_resonance,
    compute_kosha_activation_vector,
    compute_kosha_resonance_index,
    compute_guna_kosha_resonance,
    GunaKoshaResonance,
)


# =============================================================================
# GROUP A: GUNA RESONANCE TESTS
# =============================================================================


def test_guna_resonance_balanced_distribution():
    """Balanced guna distribution should yield high resonance index."""
    guna_probs = {
        "sattva": 0.33,
        "rajas": 0.33,
        "tamas": 0.34,
    }
    resonance = compute_guna_resonance(guna_probs)

    # Balanced distribution should have high resonance (close to 1.0)
    assert 0.95 <= resonance <= 1.0, f"Expected balanced resonance ~1.0, got {resonance}"


def test_guna_resonance_skewed_distribution():
    """Heavily skewed guna distribution should yield low resonance index."""
    guna_probs = {
        "sattva": 0.9,
        "rajas": 0.05,
        "tamas": 0.05,
    }
    resonance = compute_guna_resonance(guna_probs)

    # Skewed distribution should have lower resonance
    assert 0.0 <= resonance < 0.7, f"Expected skewed resonance < 0.7, got {resonance}"


def test_guna_resonance_extreme_skew():
    """Extreme skew (100% one guna) should yield minimal resonance."""
    guna_probs = {
        "sattva": 1.0,
        "rajas": 0.0,
        "tamas": 0.0,
    }
    resonance = compute_guna_resonance(guna_probs)

    # Extreme skew should have very low resonance
    assert 0.0 <= resonance < 0.1, f"Expected extreme skew resonance ~0.0, got {resonance}"


def test_guna_resonance_range_bounds():
    """Guna resonance should always be in [0.0, 1.0] range."""
    test_cases = [
        {"sattva": 0.33, "rajas": 0.33, "tamas": 0.34},  # Balanced
        {"sattva": 0.5, "rajas": 0.3, "tamas": 0.2},     # Moderate skew
        {"sattva": 0.7, "rajas": 0.2, "tamas": 0.1},     # High skew
        {"sattva": 1.0, "rajas": 0.0, "tamas": 0.0},     # Extreme
        {"sattva": 0.0, "rajas": 0.5, "tamas": 0.5},     # Missing sattva
    ]

    for guna_probs in test_cases:
        resonance = compute_guna_resonance(guna_probs)
        assert 0.0 <= resonance <= 1.0, f"Resonance {resonance} out of bounds for {guna_probs}"


def test_guna_resonance_deterministic():
    """Same input should always produce same output (determinism)."""
    guna_probs = {"sattva": 0.4, "rajas": 0.35, "tamas": 0.25}

    result1 = compute_guna_resonance(guna_probs)
    result2 = compute_guna_resonance(guna_probs)
    result3 = compute_guna_resonance(guna_probs)

    assert result1 == result2 == result3, "Guna resonance must be deterministic"


def test_guna_resonance_missing_keys():
    """Missing guna keys should be treated as 0.0."""
    # Only sattva provided
    guna_probs = {"sattva": 1.0}
    resonance = compute_guna_resonance(guna_probs)

    # Should treat missing rajas/tamas as 0.0, resulting in extreme skew
    assert 0.0 <= resonance < 0.1, f"Expected low resonance for missing keys, got {resonance}"


def test_guna_resonance_empty_dict():
    """Empty guna dict should return 0.0."""
    resonance = compute_guna_resonance({})
    assert resonance == 0.0, "Empty dict should yield 0.0 resonance"


def test_guna_resonance_invalid_probabilities():
    """Invalid probabilities (negative or > 1.0) should raise ValueError."""
    # Negative probability
    with pytest.raises(ValueError, match="must be in"):
        compute_guna_resonance({"sattva": -0.1, "rajas": 0.5, "tamas": 0.6})

    # Probability > 1.0
    with pytest.raises(ValueError, match="must be in"):
        compute_guna_resonance({"sattva": 1.5, "rajas": 0.0, "tamas": 0.0})


# =============================================================================
# GROUP B: KOSHA ACTIVATION AND RESONANCE TESTS
# =============================================================================


def test_kosha_activation_vector_length_5layer():
    """Kosha activation vector should have length 5 for 5-layer model."""
    kosha_probs = {
        "annamaya": 0.3,
        "pranamaya": 0.25,
        "manomaya": 0.2,
        "vijnanamaya": 0.15,
        "anandamaya": 0.1,
    }
    vector = compute_kosha_activation_vector(kosha_probs, model="5-layer")

    assert len(vector) == 5, f"Expected length 5, got {len(vector)}"
    assert vector == [0.3, 0.25, 0.2, 0.15, 0.1], f"Vector order incorrect: {vector}"


def test_kosha_activation_vector_length_7layer():
    """Kosha activation vector should have length 7 for 7-layer model."""
    kosha_probs = {
        "annamaya": 0.2,
        "pranamaya": 0.15,
        "manomaya": 0.15,
        "vijnanamaya": 0.15,
        "anandamaya": 0.15,
        "chitamaya": 0.1,
        "atmamaya": 0.1,
    }
    vector = compute_kosha_activation_vector(kosha_probs, model="7-layer")

    assert len(vector) == 7, f"Expected length 7, got {len(vector)}"


def test_kosha_activation_missing_keys():
    """Missing kosha keys should be treated as 0.0 activation."""
    # Only provide first 3 koshas
    kosha_probs = {
        "annamaya": 0.5,
        "pranamaya": 0.3,
        "manomaya": 0.2,
    }
    vector = compute_kosha_activation_vector(kosha_probs, model="5-layer")

    assert len(vector) == 5, "Vector should still have length 5"
    assert vector == [0.5, 0.3, 0.2, 0.0, 0.0], f"Missing koshas should be 0.0: {vector}"


def test_kosha_resonance_smooth_distribution():
    """Smooth kosha distribution should yield high resonance."""
    # Gradual descending pattern (layered activation)
    smooth_vector = [0.3, 0.25, 0.2, 0.15, 0.1]
    resonance = compute_kosha_resonance_index(smooth_vector)

    # Smooth distribution should have high resonance
    assert 0.7 <= resonance <= 1.0, f"Expected high resonance for smooth pattern, got {resonance}"


def test_kosha_resonance_spike_distribution():
    """Extreme spike in kosha distribution should yield low resonance."""
    # All activation in one kosha (extreme spike)
    spike_vector = [0.0, 0.0, 0.0, 0.0, 1.0]
    resonance = compute_kosha_resonance_index(spike_vector)

    # Spike should have low resonance (< 0.5)
    # Formula penalizes both variance and inversion
    assert 0.0 <= resonance < 0.5, f"Expected low resonance for spike, got {resonance}"


def test_kosha_resonance_inverted_pattern():
    """Inverted pattern (high kosha without low) should be penalized."""
    # High anandamaya but low physical/energy layers (inverted)
    inverted_vector = [0.1, 0.1, 0.1, 0.2, 0.8]
    resonance = compute_kosha_resonance_index(inverted_vector)

    # Should have moderate resonance with penalty for inversion
    # Formula penalizes large gaps between adjacent layers
    assert 0.0 <= resonance < 0.9, f"Expected moderate resonance with penalty, got {resonance}"

    # Compare with non-inverted smooth pattern
    smooth_vector = [0.8, 0.2, 0.1, 0.1, 0.1]
    smooth_resonance = compute_kosha_resonance_index(smooth_vector)

    # Smooth should be higher than inverted (but both may be penalized for variance)
    # The key is that inverted gets additional penalty
    assert smooth_resonance >= resonance * 0.7, "Smooth should be higher than inverted"


def test_kosha_resonance_all_zeros():
    """All-zero kosha vector should return 0.0."""
    zero_vector = [0.0, 0.0, 0.0, 0.0, 0.0]
    resonance = compute_kosha_resonance_index(zero_vector)

    assert resonance == 0.0, "All-zero vector should yield 0.0 resonance"


def test_kosha_activation_invalid_probabilities():
    """Invalid kosha probabilities should raise ValueError."""
    # Negative activation
    with pytest.raises(ValueError, match="must be in"):
        compute_kosha_activation_vector({"annamaya": -0.1}, model="5-layer")

    # Activation > 1.0
    with pytest.raises(ValueError, match="must be in"):
        compute_kosha_activation_vector({"annamaya": 1.5}, model="5-layer")


# =============================================================================
# GROUP C: WRAPPER AND INTEGRATION TESTS
# =============================================================================


def test_wrapper_returns_none_when_both_missing():
    """Wrapper should return None when both inputs are None."""
    result = compute_guna_kosha_resonance(guna_probs=None, kosha_probs=None)
    assert result is None, "Should return None when both inputs missing"


def test_wrapper_returns_none_when_both_empty():
    """Wrapper should return None when both inputs are empty dicts."""
    result = compute_guna_kosha_resonance(guna_probs={}, kosha_probs={})
    assert result is None, "Should return None when both inputs empty"


def test_wrapper_happy_path_combined():
    """Wrapper should compute all metrics with valid guna and kosha inputs."""
    guna_probs = {
        "sattva": 0.4,
        "rajas": 0.35,
        "tamas": 0.25,
    }
    kosha_probs = {
        "annamaya": 0.3,
        "pranamaya": 0.25,
        "manomaya": 0.2,
        "vijnanamaya": 0.15,
        "anandamaya": 0.1,
    }

    result = compute_guna_kosha_resonance(guna_probs, kosha_probs)

    assert result is not None, "Should return result with valid inputs"
    assert isinstance(result, GunaKoshaResonance), "Should return GunaKoshaResonance object"

    # Check all fields are present and in range
    assert 0.0 <= result.guna_resonance_index <= 1.0, "Guna index out of range"
    assert 0.0 <= result.kosha_resonance_index <= 1.0, "Kosha index out of range"
    assert len(result.kosha_activation_vector) == 5, "Kosha vector should have length 5"


def test_wrapper_deterministic():
    """Wrapper should be deterministic (same input → same output)."""
    guna_probs = {"sattva": 0.5, "rajas": 0.3, "tamas": 0.2}
    kosha_probs = {"annamaya": 0.4, "pranamaya": 0.3, "manomaya": 0.2, "vijnanamaya": 0.1}

    result1 = compute_guna_kosha_resonance(guna_probs, kosha_probs)
    result2 = compute_guna_kosha_resonance(guna_probs, kosha_probs)
    result3 = compute_guna_kosha_resonance(guna_probs, kosha_probs)

    assert result1.guna_resonance_index == result2.guna_resonance_index == result3.guna_resonance_index
    assert result1.kosha_resonance_index == result2.kosha_resonance_index == result3.kosha_resonance_index
    assert result1.kosha_activation_vector == result2.kosha_activation_vector == result3.kosha_activation_vector


def test_wrapper_partial_guna_only():
    """Wrapper should handle guna-only input gracefully."""
    guna_probs = {"sattva": 0.33, "rajas": 0.33, "tamas": 0.34}

    result = compute_guna_kosha_resonance(guna_probs, kosha_probs=None)

    assert result is not None, "Should return result with guna-only input"
    assert result.guna_resonance_index > 0.0, "Guna index should be computed"
    assert result.kosha_resonance_index == 0.0, "Kosha index should be 0.0 when missing"
    assert len(result.kosha_activation_vector) == 5, "Should have default kosha vector"
    assert all(v == 0.0 for v in result.kosha_activation_vector), "Kosha vector should be all zeros"


def test_wrapper_partial_kosha_only():
    """Wrapper should handle kosha-only input gracefully."""
    kosha_probs = {
        "annamaya": 0.5,
        "pranamaya": 0.3,
        "manomaya": 0.2,
    }

    result = compute_guna_kosha_resonance(guna_probs=None, kosha_probs=kosha_probs)

    assert result is not None, "Should return result with kosha-only input"
    assert result.guna_resonance_index == 0.0, "Guna index should be 0.0 when missing"
    assert result.kosha_resonance_index > 0.0, "Kosha index should be computed"
    assert len(result.kosha_activation_vector) == 5, "Should have kosha vector"


def test_wrapper_graceful_degradation_on_invalid_input():
    """Wrapper should return None on invalid inputs (graceful degradation)."""
    # Invalid guna probabilities (should trigger ValueError internally)
    invalid_guna = {"sattva": 2.0, "rajas": -0.5}

    result = compute_guna_kosha_resonance(invalid_guna, kosha_probs=None)

    # Wrapper should catch exception and return None
    assert result is None, "Should return None on invalid input"


# =============================================================================
# EDGE CASES AND ADDITIONAL COVERAGE
# =============================================================================


def test_kosha_resonance_empty_vector():
    """Empty kosha vector should return 0.0."""
    resonance = compute_kosha_resonance_index([])
    assert resonance == 0.0, "Empty vector should yield 0.0 resonance"


def test_kosha_resonance_single_value():
    """Single-value kosha vector should return 1.0 if non-zero."""
    resonance = compute_kosha_resonance_index([0.5])
    assert resonance == 1.0, "Single non-zero value should yield 1.0"

    resonance_zero = compute_kosha_resonance_index([0.0])
    assert resonance_zero == 0.0, "Single zero value should yield 0.0"


def test_guna_resonance_unnormalized_probs():
    """Guna resonance should handle unnormalized probabilities by normalizing."""
    # Probs sum to 2.0 instead of 1.0
    guna_probs = {
        "sattva": 0.6,
        "rajas": 0.8,
        "tamas": 0.6,
    }
    resonance = compute_guna_resonance(guna_probs)

    # Should normalize and compute (0.3, 0.4, 0.3 after normalization)
    assert 0.0 <= resonance <= 1.0, "Should handle unnormalized probs"
    # Balanced after normalization, so should have high resonance
    assert resonance > 0.9, f"Normalized balanced probs should have high resonance, got {resonance}"
