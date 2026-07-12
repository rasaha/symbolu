"""Mathematical core: second-order invariance and finite-difference noise gain.

These are the deterministic facts the whole study leans on:
  * Delta^2 annihilates constant and linear (affine) sequences.
  * Delta^2 of a quadratic a+bt+ct^2 is exactly 2c.
  * White-noise variance gain: Var(Delta d) = 2 sigma^2, Var(Delta^2 d) = 6 sigma^2
    (the 6x amplification that hurts the second-order detector on slow signals).
"""

from __future__ import annotations

import numpy as np

from cyber_security.kill_study.detectors import second_difference


def _sd_1d(x: np.ndarray) -> np.ndarray:
    return second_difference(x.reshape(-1, 1))


def test_second_difference_constant_is_zero():
    x = np.full(50, 3.14)
    sd = _sd_1d(x)
    assert np.allclose(sd[2:], 0.0, atol=1e-12)


def test_second_difference_linear_is_zero():
    t = np.arange(60, dtype=float)
    x = 2.0 + 0.7 * t
    sd = _sd_1d(x)
    assert np.allclose(sd[2:], 0.0, atol=1e-9)


def test_second_difference_quadratic_is_2c():
    t = np.arange(60, dtype=float)
    c = 0.25
    x = 1.0 + 0.3 * t + c * t * t
    d = x.reshape(-1, 1)
    a = d[2:] - 2.0 * d[1:-1] + d[:-2]
    assert np.allclose(a, 2.0 * c, atol=1e-9)


def test_noise_variance_gain_first_and_second_difference():
    rng = np.random.default_rng(12345)
    sigma = 0.7
    n = 400_000
    x = rng.normal(0.0, sigma, size=n)
    d1 = x[1:] - x[:-1]
    d2 = x[2:] - 2.0 * x[1:-1] + x[:-2]
    # Var(Delta d) = 2 sigma^2 ; Var(Delta^2 d) = 6 sigma^2
    assert np.isclose(d1.var(), 2.0 * sigma**2, rtol=0.03)
    assert np.isclose(d2.var(), 6.0 * sigma**2, rtol=0.03)


def test_second_order_blind_to_linear_but_not_abrupt():
    """Peak second-order signal is far larger for an abrupt step than for a
    slow linear ramp of the same total displacement — the study's core claim."""
    t = np.arange(200, dtype=float)
    ramp = np.clip((t - 80) / 100.0, 0.0, 1.0) * 4.0     # slow linear
    step = (t >= 80).astype(float) * 4.0                  # abrupt
    peak_ramp = np.abs(_sd_1d(ramp)[2:]).max()
    peak_step = np.abs(_sd_1d(step)[2:]).max()
    assert peak_step > 10.0 * max(peak_ramp, 1e-9)
