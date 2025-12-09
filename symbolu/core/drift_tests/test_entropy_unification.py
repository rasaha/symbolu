"""
Entropy Formula Unification Tests
==================================

Validates that MLCR and TTOR use identical entropy mix formulas.

UNIFIED FORMULA (frozen in v2.0 specification):
    normalized_entropy = 0.6 * (H_D / H_D_MAX) + 0.4 * (H_G / H_G_MAX)

Where:
    H_D_MAX = ln(10) ≈ 2.302585093
    H_G_MAX = ln(3) ≈ 1.098612289

This test ensures zero drift between TTOR and MLCR entropy computations.
"""

import math
import random
import pytest
from typing import Tuple

# TTOR imports
from symbolu.mechanical.pipeline.ttor.formulas import entropy_mix as ttor_entropy_mix
from symbolu.mechanical.pipeline.ttor.constants import H_D_MAX, H_G_MAX

# MLCR imports
from symbolu.mechanical.mlcr.expert_router import ExpertRouter


# Canonical entropy formula (reference implementation)
def canonical_entropy_mix(H_D: float, H_G: float) -> float:
    """
    Reference implementation of the canonical entropy formula.

    UNIFIED FORMULA (v2.0):
        normalized_entropy = 0.6 * H_D_norm + 0.4 * H_G_norm

    Where:
        H_D_norm = H_D / H_D_MAX (clamped to [0, 1])
        H_G_norm = H_G / H_G_MAX (clamped to [0, 1])
    """
    H_D_norm = max(0.0, min(1.0, H_D / H_D_MAX)) if H_D_MAX > 0 else 0.0
    H_G_norm = max(0.0, min(1.0, H_G / H_G_MAX)) if H_G_MAX > 0 else 0.0

    return 0.6 * H_D_norm + 0.4 * H_G_norm


def generate_random_entropy_samples(n: int, seed: int = 42) -> list:
    """
    Generate n random (H_D, H_G) samples for testing.

    Uses fixed seed for deterministic test results.

    Args:
        n: Number of samples to generate
        seed: Random seed for reproducibility

    Returns:
        List of (H_D, H_G) tuples
    """
    random.seed(seed)
    samples = []

    for _ in range(n):
        # H_D in [0, H_D_MAX]
        H_D = random.uniform(0.0, H_D_MAX)
        # H_G in [0, H_G_MAX]
        H_G = random.uniform(0.0, H_G_MAX)
        samples.append((H_D, H_G))

    return samples


# =============================================================================
# CORE UNIFICATION TESTS
# =============================================================================

class TestEntropyFormulaUnification:
    """Test suite for entropy formula unification between TTOR and MLCR."""

    TOLERANCE = 1e-6

    def test_ttor_matches_canonical(self):
        """Verify TTOR entropy_mix matches canonical formula."""
        samples = generate_random_entropy_samples(20)

        for H_D, H_G in samples:
            # TTOR returns (normalized_entropy, entropy_ratio)
            ttor_result, _ = ttor_entropy_mix(H_D, H_G)
            canonical_result = canonical_entropy_mix(H_D, H_G)

            assert abs(ttor_result - canonical_result) < self.TOLERANCE, (
                f"TTOR drift from canonical: "
                f"H_D={H_D:.6f}, H_G={H_G:.6f} | "
                f"TTOR={ttor_result:.10f}, Canonical={canonical_result:.10f}"
            )

    def test_mlcr_matches_canonical(self):
        """Verify MLCR entropy computation matches canonical formula."""
        samples = generate_random_entropy_samples(20)
        router = ExpertRouter()

        for H_D, H_G in samples:
            mlcr_result = router._compute_normalized_entropy(H_D, H_G)
            canonical_result = canonical_entropy_mix(H_D, H_G)

            assert abs(mlcr_result - canonical_result) < self.TOLERANCE, (
                f"MLCR drift from canonical: "
                f"H_D={H_D:.6f}, H_G={H_G:.6f} | "
                f"MLCR={mlcr_result:.10f}, Canonical={canonical_result:.10f}"
            )

    def test_ttor_mlcr_exact_match(self):
        """Verify TTOR and MLCR entropy computations are identical."""
        samples = generate_random_entropy_samples(20)
        router = ExpertRouter()

        for H_D, H_G in samples:
            # TTOR returns (normalized_entropy, entropy_ratio)
            ttor_result, _ = ttor_entropy_mix(H_D, H_G)
            mlcr_result = router._compute_normalized_entropy(H_D, H_G)

            assert abs(ttor_result - mlcr_result) < self.TOLERANCE, (
                f"TTOR/MLCR drift: "
                f"H_D={H_D:.6f}, H_G={H_G:.6f} | "
                f"TTOR={ttor_result:.10f}, MLCR={mlcr_result:.10f}"
            )


# =============================================================================
# BOUNDARY TESTS
# =============================================================================

class TestEntropyBoundaryConditions:
    """Test entropy formula at boundary conditions."""

    TOLERANCE = 1e-6

    def test_zero_entropy(self):
        """Both H_D and H_G at zero should produce normalized_entropy = 0."""
        router = ExpertRouter()

        ttor_result, _ = ttor_entropy_mix(0.0, 0.0)
        mlcr_result = router._compute_normalized_entropy(0.0, 0.0)

        assert ttor_result == 0.0, f"TTOR should return 0.0, got {ttor_result}"
        assert mlcr_result == 0.0, f"MLCR should return 0.0, got {mlcr_result}"

    def test_max_entropy(self):
        """Both H_D and H_G at maximum should produce normalized_entropy = 1.0."""
        router = ExpertRouter()

        ttor_result, _ = ttor_entropy_mix(H_D_MAX, H_G_MAX)
        mlcr_result = router._compute_normalized_entropy(H_D_MAX, H_G_MAX)

        # Expected: 0.6 * 1.0 + 0.4 * 1.0 = 1.0
        assert abs(ttor_result - 1.0) < self.TOLERANCE, f"TTOR should return 1.0, got {ttor_result}"
        assert abs(mlcr_result - 1.0) < self.TOLERANCE, f"MLCR should return 1.0, got {mlcr_result}"

    def test_h_d_only(self):
        """Test with only H_D entropy (H_G = 0)."""
        router = ExpertRouter()

        # H_D at maximum, H_G at zero → normalized_entropy = 0.6
        ttor_result, _ = ttor_entropy_mix(H_D_MAX, 0.0)
        mlcr_result = router._compute_normalized_entropy(H_D_MAX, 0.0)

        expected = 0.6  # 0.6 * 1.0 + 0.4 * 0.0
        assert abs(ttor_result - expected) < self.TOLERANCE, f"TTOR should return {expected}, got {ttor_result}"
        assert abs(mlcr_result - expected) < self.TOLERANCE, f"MLCR should return {expected}, got {mlcr_result}"

    def test_h_g_only(self):
        """Test with only H_G entropy (H_D = 0)."""
        router = ExpertRouter()

        # H_D at zero, H_G at maximum → normalized_entropy = 0.4
        ttor_result, _ = ttor_entropy_mix(0.0, H_G_MAX)
        mlcr_result = router._compute_normalized_entropy(0.0, H_G_MAX)

        expected = 0.4  # 0.6 * 0.0 + 0.4 * 1.0
        assert abs(ttor_result - expected) < self.TOLERANCE, f"TTOR should return {expected}, got {ttor_result}"
        assert abs(mlcr_result - expected) < self.TOLERANCE, f"MLCR should return {expected}, got {mlcr_result}"

    def test_overflow_clamping(self):
        """Test that values above maximum are clamped to 1.0."""
        router = ExpertRouter()

        # H_D and H_G above maximum should be clamped
        ttor_result, _ = ttor_entropy_mix(H_D_MAX * 2, H_G_MAX * 2)
        mlcr_result = router._compute_normalized_entropy(H_D_MAX * 2, H_G_MAX * 2)

        # Both should clamp to 1.0 → result = 0.6 * 1.0 + 0.4 * 1.0 = 1.0
        expected = 1.0
        assert abs(ttor_result - expected) < self.TOLERANCE, f"TTOR should clamp to {expected}, got {ttor_result}"
        assert abs(mlcr_result - expected) < self.TOLERANCE, f"MLCR should clamp to {expected}, got {mlcr_result}"


# =============================================================================
# MLCR NULL HANDLING TESTS
# =============================================================================

class TestMLCRNullHandling:
    """Test MLCR handling of None values."""

    def test_both_none_returns_default(self):
        """When both H_D and H_G are None, return default 0.5."""
        router = ExpertRouter()
        result = router._compute_normalized_entropy(None, None)
        assert result == 0.5, f"Expected 0.5 for None inputs, got {result}"

    def test_h_d_none_returns_default(self):
        """When H_D is None, return default 0.5."""
        router = ExpertRouter()
        result = router._compute_normalized_entropy(None, 0.5)
        assert result == 0.5, f"Expected 0.5 when H_D is None, got {result}"

    def test_h_g_none_returns_default(self):
        """When H_G is None, return default 0.5."""
        router = ExpertRouter()
        result = router._compute_normalized_entropy(0.5, None)
        assert result == 0.5, f"Expected 0.5 when H_G is None, got {result}"


# =============================================================================
# COMPREHENSIVE GRID TEST
# =============================================================================

@pytest.mark.parametrize("h_d_fraction", [0.0, 0.25, 0.5, 0.75, 1.0])
@pytest.mark.parametrize("h_g_fraction", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_entropy_unification_grid(h_d_fraction: float, h_g_fraction: float):
    """
    Grid test: Verify TTOR/MLCR entropy match across parameter space.

    Tests 25 combinations (5x5 grid) of H_D and H_G fractions.
    """
    tolerance = 1e-6
    router = ExpertRouter()

    # Convert fractions to actual entropy values
    H_D = h_d_fraction * H_D_MAX
    H_G = h_g_fraction * H_G_MAX

    # Compute using both systems
    ttor_result, _ = ttor_entropy_mix(H_D, H_G)
    mlcr_result = router._compute_normalized_entropy(H_D, H_G)
    canonical_result = canonical_entropy_mix(H_D, H_G)

    # All three should match
    assert abs(ttor_result - canonical_result) < tolerance, (
        f"TTOR drift: H_D_frac={h_d_fraction}, H_G_frac={h_g_fraction} | "
        f"TTOR={ttor_result:.10f}, Canonical={canonical_result:.10f}"
    )

    assert abs(mlcr_result - canonical_result) < tolerance, (
        f"MLCR drift: H_D_frac={h_d_fraction}, H_G_frac={h_g_fraction} | "
        f"MLCR={mlcr_result:.10f}, Canonical={canonical_result:.10f}"
    )


# =============================================================================
# REPORT GENERATION
# =============================================================================

def test_generate_entropy_unification_report(tmp_path):
    """
    Generate a JSON report summarizing entropy unification status.

    This report can be consumed by CI pipelines and dashboards.
    """
    import json

    router = ExpertRouter()
    samples = generate_random_entropy_samples(20)
    tolerance = 1e-6

    test_results = []
    drift_count = 0

    for H_D, H_G in samples:
        ttor_result, _ = ttor_entropy_mix(H_D, H_G)
        mlcr_result = router._compute_normalized_entropy(H_D, H_G)
        canonical_result = canonical_entropy_mix(H_D, H_G)

        ttor_drift = abs(ttor_result - canonical_result)
        mlcr_drift = abs(mlcr_result - canonical_result)
        ttor_mlcr_drift = abs(ttor_result - mlcr_result)

        is_drift = (ttor_drift > tolerance or mlcr_drift > tolerance or ttor_mlcr_drift > tolerance)

        if is_drift:
            drift_count += 1

        test_results.append({
            "H_D": round(H_D, 6),
            "H_G": round(H_G, 6),
            "ttor_entropy": round(ttor_result, 10),
            "mlcr_entropy": round(mlcr_result, 10),
            "canonical_entropy": round(canonical_result, 10),
            "ttor_drift": round(ttor_drift, 12),
            "mlcr_drift": round(mlcr_drift, 12),
            "ttor_mlcr_drift": round(ttor_mlcr_drift, 12),
            "drift_detected": is_drift,
        })

    report = {
        "test_suite": "entropy_unification",
        "version": "v2.0",
        "formula": "normalized_entropy = 0.6 * H_D_norm + 0.4 * H_G_norm",
        "tolerance": tolerance,
        "total_samples": len(samples),
        "drift_samples": drift_count,
        "drift_ratio": drift_count / len(samples) if samples else 0.0,
        "status": "OK" if drift_count == 0 else "DRIFT",
        "test_results": test_results,
    }

    # Write to fixed location for CI
    output_path = "/home/user/symbolu/symbolu/core/drift_tests/entropy_unification_report.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    # Assert no drift
    assert drift_count == 0, (
        f"Entropy unification drift detected in {drift_count}/{len(samples)} samples!"
    )
