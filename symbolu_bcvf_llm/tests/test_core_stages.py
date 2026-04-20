"""§2.8.5–§2.8.8: stage-unit tests for the five BCVF stage functions."""

from __future__ import annotations

import numpy as np

from symbolu_bcvf_llm.core import (
    compute_disagreement,
    compute_disagreement_acceleration,
    compute_disagreement_velocity,
    pseudo_huber,
    smooth_gate,
)


def test_compute_disagreement_shape_broadcast():
    rng = np.random.default_rng(seed=42)
    p_i = rng.random(size=(3, 1, 5, 32000))
    p_j = rng.random(size=(3, 1, 5, 32000))
    out = compute_disagreement(p_i, p_j)
    assert out.shape == (3, 1, 5, 32000)


def test_compute_disagreement_translation_invariant():
    rng = np.random.default_rng(seed=42)
    p_i = rng.random(size=(5, 100))
    p_j = rng.random(size=(5, 100))
    c = rng.random(size=(100,))
    base = compute_disagreement(p_i, p_j)
    shifted = compute_disagreement(p_i + c, p_j + c)
    np.testing.assert_allclose(base, shifted, rtol=0, atol=1e-12)


def test_compute_disagreement_acceleration_constant_bias_zero():
    L, V = 5, 100
    rng = np.random.default_rng(seed=42)
    alpha = rng.random(size=(V,))
    e = np.broadcast_to(alpha, (L, V)).astype(np.float64)
    a = compute_disagreement_acceleration(e, step_l=1.0)
    assert a.shape == (L - 2, V)
    assert float(np.max(np.abs(a))) <= 1e-10


def test_compute_disagreement_acceleration_linear_drift_zero():
    L, V = 5, 100
    rng = np.random.default_rng(seed=42)
    alpha = rng.random(size=(V,))
    gamma = rng.random(size=(V,))
    ls = np.arange(L, dtype=np.float64).reshape(L, 1)
    e = alpha + gamma * ls
    a = compute_disagreement_acceleration(e, step_l=1.0)
    assert float(np.max(np.abs(a))) <= 1e-10


def test_compute_disagreement_acceleration_quadratic_positive():
    L, V = 5, 10
    rng = np.random.default_rng(seed=42)
    eta = rng.random(size=(V,)) + 0.5
    ls = np.arange(L, dtype=np.float64).reshape(L, 1)
    # e(l) = 0.5 * eta * l^2 ⇒ a(l*) = eta
    e = 0.5 * eta * (ls ** 2)
    a = compute_disagreement_acceleration(e, step_l=1.0)
    for lstar in range(a.shape[0]):
        np.testing.assert_allclose(a[lstar], eta, rtol=0, atol=1e-10)


def test_compute_disagreement_velocity_shape():
    L, V = 7, 50
    e = np.zeros((L, V))
    v = compute_disagreement_velocity(e, step_l=1.0)
    assert v.shape == (L - 1, V)


def test_smooth_gate_shape():
    e = np.zeros((3, 3, 32000))
    out = smooth_gate(e, threshold=0.1, beta=200.0)
    assert out.shape == (3, 3)


def test_smooth_gate_threshold_midpoint():
    V = 100
    e = np.zeros(V)
    e[0] = 0.1  # ||e||_2 == 0.1 == T
    g = smooth_gate(e, threshold=0.1, beta=200.0)
    assert abs(float(g) - 0.5) < 1e-7


def test_smooth_gate_below_floor_suppressed():
    V = 50
    e = np.zeros(V)
    # ||e|| = T - 2/β = 0.1 - 0.01 = 0.09
    e[0] = 0.1 - 2.0 / 200.0
    g = smooth_gate(e, threshold=0.1, beta=200.0)
    assert float(g) < 0.2


def test_smooth_gate_above_floor_open():
    V = 50
    e = np.zeros(V)
    e[0] = 0.1 + 2.0 / 200.0
    g = smooth_gate(e, threshold=0.1, beta=200.0)
    assert float(g) > 0.8


def test_smooth_gate_clipping_no_nan_no_inf():
    V = 50
    e = np.zeros(V)
    e[0] = 100.0
    g = smooth_gate(e, threshold=0.1, beta=200.0)
    assert np.isfinite(g).all()
    assert abs(float(g) - 1.0) < 1e-6


def test_smooth_gate_none_weight_equivalent_to_ones():
    V = 32
    rng = np.random.default_rng(seed=42)
    e = rng.random(size=(4, V)).astype(np.float64)
    g_none = smooth_gate(e, threshold=0.1, beta=200.0, weight_vector=None)
    g_ones = smooth_gate(
        e, threshold=0.1, beta=200.0, weight_vector=np.ones(V, dtype=np.float64)
    )
    np.testing.assert_allclose(g_none, g_ones, rtol=0, atol=1e-10)


def test_pseudo_huber_zero_exact():
    out = pseudo_huber(np.array(0.0), delta=0.5)
    assert float(out) == 0.0


def test_pseudo_huber_quadratic_regime():
    r = 0.01
    penalty = float(pseudo_huber(np.array(r), delta=0.5))
    assert abs(penalty - (r * r) / 2.0) < 1e-8


def test_pseudo_huber_linear_regime():
    r = 100.0
    delta = 0.5
    penalty = float(pseudo_huber(np.array(r), delta=delta))
    asymptote = delta * r - (delta * delta) / 2.0
    assert abs(penalty - asymptote) / penalty < 0.01


def test_pseudo_huber_monotonic():
    rs = np.linspace(0.0, 10.0, 101)
    out = pseudo_huber(rs, delta=0.5)
    assert np.all(np.diff(out) >= 0.0)
