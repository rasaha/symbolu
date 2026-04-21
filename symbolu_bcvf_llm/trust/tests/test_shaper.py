"""§5.1 TrustShaper unit tests.

Covers: cold-start uniformity, EMA convergence under constant
input, deadband suppression of sub-threshold residual, hinge
variant, softmin down-weighting of outlier source, reset,
input validation.
"""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.trust.shaper import TrustShaper, TrustShaperConfig


def test_cold_start_step0_is_uniform():
    """§5.1 stage 1: 'residual is exactly zero on step 0 → uniform weights'."""
    shaper = TrustShaper(M=3)
    w = shaper.step(np.array([0.5, 0.7, 0.9]))
    np.testing.assert_allclose(w, [1 / 3, 1 / 3, 1 / 3], rtol=0, atol=1e-12)


def test_constant_input_stays_uniform():
    """Constant cost across many steps — residual stays ~0 → uniform."""
    shaper = TrustShaper(M=3)
    for _ in range(100):
        w = shaper.step(np.array([0.42, 0.42, 0.42]))
    np.testing.assert_allclose(w, [1 / 3, 1 / 3, 1 / 3], rtol=0, atol=1e-10)


def test_sub_threshold_residual_suppressed_by_deadband():
    """Deadband k=2·σ: small residuals below threshold → uniform."""
    cfg = TrustShaperConfig(
        ema_alpha=0.5,             # fast convergence for test speed
        deadband_k_sigma=2.0,
    )
    shaper = TrustShaper(M=3, config=cfg)
    # Warm up σ with varied cost.
    rng = np.random.default_rng(seed=0)
    for _ in range(50):
        shaper.step(np.array([0.4, 0.5, 0.6]) + 0.1 * rng.normal(size=3))
    # Tiny perturbation on source 0 — well inside deadband.
    baseline = shaper.history[-1].cost.copy()
    w = shaper.step(baseline + np.array([0.001, 0.0, 0.0]))
    # Weights should remain very close to uniform.
    assert float(np.max(np.abs(w - 1 / 3))) < 0.05


def test_above_threshold_residual_downweights_outlier():
    """Large positive residual on source 0 → trust weight drops."""
    cfg = TrustShaperConfig(ema_alpha=0.1)
    shaper = TrustShaper(M=3, config=cfg)
    # Warm up with baseline.
    for _ in range(20):
        shaper.step(np.array([0.1, 0.1, 0.1]))
    # Spike source 0.
    w = shaper.step(np.array([5.0, 0.1, 0.1]))
    # Source 0 should be down-weighted below uniform.
    assert w[0] < 0.33
    # Sources 1, 2 should be roughly symmetric.
    assert abs(w[1] - w[2]) < 0.02
    # Weights sum to 1.
    assert abs(w.sum() - 1.0) < 1e-12


def test_negative_residual_treated_as_non_outlier():
    """Source whose cost is *below* EMA is not an outlier — no shift."""
    cfg = TrustShaperConfig(ema_alpha=0.1)
    shaper = TrustShaper(M=3, config=cfg)
    for _ in range(20):
        shaper.step(np.array([1.0, 1.0, 1.0]))
    # Negative residual on source 0.
    w = shaper.step(np.array([-5.0, 1.0, 1.0]))
    # Weights should be ~uniform (no source was shifted positive).
    np.testing.assert_allclose(w, [1 / 3, 1 / 3, 1 / 3], rtol=0, atol=0.05)


def test_hinge_variant_behaviour():
    """Hinge `φ(d) = max(d − θ, 0)` with θ=0 tracks positive residual directly."""
    cfg = TrustShaperConfig(
        ema_alpha=0.1,
        use_hinge=True,
        hinge_theta=0.0,
        trust_temperature=1.0,
    )
    shaper = TrustShaper(M=3, config=cfg)
    for _ in range(20):
        shaper.step(np.array([0.1, 0.1, 0.1]))
    w = shaper.step(np.array([3.0, 0.1, 0.1]))
    assert w[0] < 0.3
    assert abs(w[1] - w[2]) < 0.02


def test_m_2_reduces_to_uniform_on_equal_cost():
    """M=2 edge case: identical costs → uniform regardless of config."""
    shaper = TrustShaper(M=2)
    for _ in range(10):
        w = shaper.step(np.array([0.3, 0.3]))
    np.testing.assert_allclose(w, [0.5, 0.5], atol=1e-12)


def test_reset_clears_state():
    shaper = TrustShaper(M=3)
    shaper.step(np.array([0.1, 0.2, 0.3]))
    shaper.step(np.array([5.0, 0.2, 0.3]))
    assert shaper.step_index == 2
    assert len(shaper.history) == 2
    shaper.reset()
    assert shaper.step_index == 0
    assert len(shaper.history) == 0
    # After reset, step 0 again yields uniform.
    w = shaper.step(np.array([99.0, 1.0, 1.0]))
    np.testing.assert_allclose(w, [1 / 3, 1 / 3, 1 / 3], atol=1e-12)


def test_invalid_m_raises():
    with pytest.raises(ValueError):
        TrustShaper(M=0)


def test_wrong_shape_input_raises():
    shaper = TrustShaper(M=3)
    with pytest.raises(ValueError):
        shaper.step(np.array([0.1, 0.2]))


def test_non_finite_input_raises():
    shaper = TrustShaper(M=3)
    with pytest.raises(ValueError):
        shaper.step(np.array([0.1, np.nan, 0.2]))


def test_weights_always_sum_to_one():
    cfg = TrustShaperConfig(ema_alpha=0.3)
    shaper = TrustShaper(M=4, config=cfg)
    rng = np.random.default_rng(seed=42)
    for _ in range(50):
        costs = np.abs(rng.normal(loc=1.0, scale=2.0, size=4))
        w = shaper.step(costs)
        assert abs(w.sum() - 1.0) < 1e-10
        assert (w >= 0.0).all()


def test_history_records_all_stages():
    shaper = TrustShaper(M=3)
    shaper.step(np.array([0.1, 0.2, 0.3]))
    shaper.step(np.array([0.4, 0.2, 0.3]))
    assert len(shaper.history) == 2
    rec = shaper.history[-1]
    assert rec.cost.shape == (3,)
    assert rec.residual.shape == (3,)
    assert rec.shaped.shape == (3,)
    assert rec.weights.shape == (3,)
    assert abs(rec.weights.sum() - 1.0) < 1e-12
