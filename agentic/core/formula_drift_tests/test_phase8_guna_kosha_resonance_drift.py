"""
Phase 8 Guna/Kosha Resonance Formulas - Drift Test Suite
=========================================================

Deterministic drift tests for Phase 8 Guna/Kosha resonance formulas:
- Guna Resonance Index
- Kosha Activation Vector
- Kosha Resonance Index

These tests ensure formula outputs remain stable across code changes.
Any modification to formula behavior will fail CI, preventing unintended drift.

Version: 1.0 (Phase 8)
Date: 2025-12-10
"""

import pytest
from symbolu_core.formulas.guna_kosha_resonance import (
    compute_guna_resonance,
    compute_kosha_activation_vector,
    compute_kosha_resonance_index,
    compute_guna_kosha_resonance,
)


# =============================================================================
# CANONICAL FIXTURES (LOCKED OUTPUTS)
# =============================================================================
#
# These test cases lock in the exact formula outputs.
# If formulas change, these tests MUST fail to alert developers.
#


# Tolerance for floating-point comparison
TOLERANCE = 1e-6


# =============================================================================
# GUNA RESONANCE DRIFT TESTS
# =============================================================================


def test_guna_resonance_balanced_canonical():
    """Canonical test: balanced guna distribution."""
    guna_probs = {"sattva": 0.33, "rajas": 0.33, "tamas": 0.34}
    result = compute_guna_resonance(guna_probs)

    # Locked canonical output (entropy-based)
    # Perfect balance → maximum entropy → resonance ≈ 1.0
    expected = 0.9999092749840701
    assert abs(result - expected) < TOLERANCE, \
        f"Guna resonance drift detected: expected {expected}, got {result}"


def test_guna_resonance_moderate_skew_canonical():
    """Canonical test: moderately skewed guna distribution."""
    guna_probs = {"sattva": 0.5, "rajas": 0.3, "tamas": 0.2}
    result = compute_guna_resonance(guna_probs)

    # Locked canonical output
    expected = 0.9372305632161295
    assert abs(result - expected) < TOLERANCE, \
        f"Guna resonance drift detected: expected {expected}, got {result}"


def test_guna_resonance_high_skew_canonical():
    """Canonical test: highly skewed guna distribution."""
    guna_probs = {"sattva": 0.8, "rajas": 0.1, "tamas": 0.1}
    result = compute_guna_resonance(guna_probs)

    # Locked canonical output
    expected = 0.5816718657178868
    assert abs(result - expected) < TOLERANCE, \
        f"Guna resonance drift detected: expected {expected}, got {result}"


def test_guna_resonance_extreme_skew_canonical():
    """Canonical test: extreme skew (almost all one guna)."""
    guna_probs = {"sattva": 0.9, "rajas": 0.05, "tamas": 0.05}
    result = compute_guna_resonance(guna_probs)

    # Locked canonical output
    expected = 0.3589962496465303
    assert abs(result - expected) < TOLERANCE, \
        f"Guna resonance drift detected: expected {expected}, got {result}"


def test_guna_resonance_perfect_skew_canonical():
    """Canonical test: perfect skew (100% one guna)."""
    guna_probs = {"sattva": 1.0, "rajas": 0.0, "tamas": 0.0}
    result = compute_guna_resonance(guna_probs)

    # Locked canonical output (minimum entropy)
    expected = 0.0
    assert abs(result - expected) < TOLERANCE, \
        f"Guna resonance drift detected: expected {expected}, got {result}"


# =============================================================================
# KOSHA ACTIVATION VECTOR DRIFT TESTS
# =============================================================================


def test_kosha_activation_vector_full_canonical():
    """Canonical test: all 5 koshas with values."""
    kosha_probs = {
        "annamaya": 0.3,
        "pranamaya": 0.25,
        "manomaya": 0.2,
        "vijnanamaya": 0.15,
        "anandamaya": 0.1,
    }
    result = compute_kosha_activation_vector(kosha_probs, model="5-layer")

    # Locked canonical output (ordered vector)
    expected = [0.3, 0.25, 0.2, 0.15, 0.1]
    assert result == expected, \
        f"Kosha activation vector drift detected: expected {expected}, got {result}"


def test_kosha_activation_vector_partial_canonical():
    """Canonical test: partial kosha data (some missing)."""
    kosha_probs = {
        "annamaya": 0.5,
        "pranamaya": 0.3,
        # manomaya missing
        "vijnanamaya": 0.2,
        # anandamaya missing
    }
    result = compute_kosha_activation_vector(kosha_probs, model="5-layer")

    # Locked canonical output (missing → 0.0)
    expected = [0.5, 0.3, 0.0, 0.2, 0.0]
    assert result == expected, \
        f"Kosha activation vector drift detected: expected {expected}, got {result}"


# =============================================================================
# KOSHA RESONANCE INDEX DRIFT TESTS
# =============================================================================


def test_kosha_resonance_smooth_descending_canonical():
    """Canonical test: smooth descending pattern (ideal)."""
    vector = [0.3, 0.25, 0.2, 0.15, 0.1]
    result = compute_kosha_resonance_index(vector)

    # Locked canonical output (high resonance for smooth pattern)
    # variance = 0.005, max_variance = 0.8
    # normalized_variance = 0.00625
    # variance_score = 1 - 0.00625 = 0.99375
    # No inversion penalty (descending pattern)
    expected = 0.99375
    assert abs(result - expected) < TOLERANCE, \
        f"Kosha resonance drift detected: expected {expected}, got {result}"


def test_kosha_resonance_extreme_spike_canonical():
    """Canonical test: extreme spike (all in last kosha)."""
    vector = [0.0, 0.0, 0.0, 0.0, 1.0]
    result = compute_kosha_resonance_index(vector)

    # Locked canonical output
    # variance = 0.16, max_variance = 0.8
    # normalized_variance = 0.2
    # variance_score = 1 - 0.2 = 0.8
    # Inversion penalty: gap from 0.0 to 1.0 = 1.0, penalty = 1.0 * 0.5 = 0.5
    # resonance = 0.8 * (1 - 0.5) = 0.4
    expected = 0.4
    assert abs(result - expected) < TOLERANCE, \
        f"Kosha resonance drift detected: expected {expected}, got {result}"


def test_kosha_resonance_inverted_pattern_canonical():
    """Canonical test: inverted pattern (high kosha without low)."""
    vector = [0.1, 0.1, 0.1, 0.2, 0.8]
    result = compute_kosha_resonance_index(vector)

    # Locked canonical output
    # This has both variance and inversion penalties
    # Expected value based on formula implementation
    expected = 0.6349
    assert abs(result - expected) < TOLERANCE, \
        f"Kosha resonance drift detected: expected {expected}, got {result}"


def test_kosha_resonance_uniform_canonical():
    """Canonical test: uniform distribution (all equal)."""
    vector = [0.2, 0.2, 0.2, 0.2, 0.2]
    result = compute_kosha_resonance_index(vector)

    # Locked canonical output (perfect uniformity → zero variance → max resonance)
    # variance = 0.0
    # variance_score = 1.0
    # No inversion (uniform)
    expected = 1.0
    assert abs(result - expected) < TOLERANCE, \
        f"Kosha resonance drift detected: expected {expected}, got {result}"


# =============================================================================
# WRAPPER FUNCTION DRIFT TESTS
# =============================================================================


def test_wrapper_combined_canonical():
    """Canonical test: wrapper with both guna and kosha inputs."""
    guna_probs = {"sattva": 0.4, "rajas": 0.35, "tamas": 0.25}
    kosha_probs = {
        "annamaya": 0.3,
        "pranamaya": 0.25,
        "manomaya": 0.2,
        "vijnanamaya": 0.15,
        "anandamaya": 0.1,
    }

    result = compute_guna_kosha_resonance(guna_probs, kosha_probs)

    # Locked canonical outputs
    expected_guna = 0.9835386311891134  # From guna resonance formula
    expected_kosha = 0.99375  # From kosha resonance formula
    expected_vector = [0.3, 0.25, 0.2, 0.15, 0.1]

    assert result is not None, "Wrapper should return result with valid inputs"
    assert abs(result.guna_resonance_index - expected_guna) < TOLERANCE, \
        f"Guna resonance drift in wrapper: expected {expected_guna}, got {result.guna_resonance_index}"
    assert abs(result.kosha_resonance_index - expected_kosha) < TOLERANCE, \
        f"Kosha resonance drift in wrapper: expected {expected_kosha}, got {result.kosha_resonance_index}"
    assert result.kosha_activation_vector == expected_vector, \
        f"Kosha vector drift in wrapper: expected {expected_vector}, got {result.kosha_activation_vector}"


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


def test_guna_resonance_deterministic():
    """Guna resonance must be deterministic (same input → same output)."""
    guna_probs = {"sattva": 0.45, "rajas": 0.35, "tamas": 0.2}

    results = [compute_guna_resonance(guna_probs) for _ in range(10)]

    # All results must be identical
    assert len(set(results)) == 1, \
        f"Guna resonance is non-deterministic: got {len(set(results))} different outputs"


def test_kosha_resonance_deterministic():
    """Kosha resonance must be deterministic (same input → same output)."""
    vector = [0.4, 0.3, 0.2, 0.1, 0.0]

    results = [compute_kosha_resonance_index(vector) for _ in range(10)]

    # All results must be identical
    assert len(set(results)) == 1, \
        f"Kosha resonance is non-deterministic: got {len(set(results))} different outputs"


def test_wrapper_deterministic():
    """Wrapper function must be deterministic."""
    guna_probs = {"sattva": 0.5, "rajas": 0.3, "tamas": 0.2}
    kosha_probs = {"annamaya": 0.4, "pranamaya": 0.3, "manomaya": 0.2, "vijnanamaya": 0.1}

    results = [compute_guna_kosha_resonance(guna_probs, kosha_probs) for _ in range(10)]

    # Extract indices for comparison
    guna_indices = [r.guna_resonance_index for r in results]
    kosha_indices = [r.kosha_resonance_index for r in results]

    assert len(set(guna_indices)) == 1, "Wrapper guna resonance is non-deterministic"
    assert len(set(kosha_indices)) == 1, "Wrapper kosha resonance is non-deterministic"


# =============================================================================
# EDGE CASE DRIFT TESTS
# =============================================================================


def test_guna_resonance_empty_dict():
    """Empty guna dict must always return 0.0."""
    result = compute_guna_resonance({})
    assert result == 0.0, f"Empty guna dict drift: expected 0.0, got {result}"


def test_kosha_resonance_all_zeros():
    """All-zero kosha vector must always return 0.0."""
    result = compute_kosha_resonance_index([0.0, 0.0, 0.0, 0.0, 0.0])
    assert result == 0.0, f"All-zero kosha drift: expected 0.0, got {result}"


def test_kosha_resonance_single_value_nonzero():
    """Single non-zero value must always return 1.0."""
    result = compute_kosha_resonance_index([0.5])
    assert result == 1.0, f"Single-value kosha drift: expected 1.0, got {result}"


def test_wrapper_returns_none_for_empty_inputs():
    """Wrapper must return None when both inputs are empty."""
    result = compute_guna_kosha_resonance({}, {})
    assert result is None, f"Wrapper empty inputs drift: expected None, got {result}"
