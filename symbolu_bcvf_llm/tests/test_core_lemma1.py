"""§2.6 Lemma 1 invariance — priority tests.

Constructed at kernel level with M=3 sources. Tolerance 1e-10 in fp64
per §2.6.8 / §2.9.5.
"""

from __future__ import annotations

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig, compute_bcvf_cost


def test_lemma_1_constant_bias_zero():
    cfg = BCVFLLMConfig()
    L, V = 5, 50
    rng = np.random.default_rng(seed=42)
    base = rng.random(size=(L, V))
    alpha_10 = rng.random(size=(V,))
    alpha_20 = rng.random(size=(V,))
    # e_{1,0}(l) = alpha_10 (constant)
    # e_{2,0}(l) = alpha_20 (constant)
    # e_{2,1}(l) = alpha_20 - alpha_10 (constant)
    s0 = base
    s1 = base + alpha_10
    s2 = base + alpha_20
    r = compute_bcvf_cost([s0, s1, s2], cfg)
    assert r.total_cost <= 1e-10


def test_lemma_1_linear_drift_zero():
    cfg = BCVFLLMConfig()
    L, V = 5, 50
    rng = np.random.default_rng(seed=42)
    base = rng.random(size=(L, V))
    alpha_10 = rng.random(size=(V,))
    gamma_10 = rng.random(size=(V,))
    alpha_20 = rng.random(size=(V,))
    gamma_20 = rng.random(size=(V,))
    ls = np.arange(L, dtype=np.float64).reshape(L, 1)
    # e_{1,0}(l) = alpha_10 + gamma_10*l
    # e_{2,0}(l) = alpha_20 + gamma_20*l
    # e_{2,1}(l) = (alpha_20-alpha_10) + (gamma_20-gamma_10)*l — still linear.
    s0 = base
    s1 = base + alpha_10 + gamma_10 * ls
    s2 = base + alpha_20 + gamma_20 * ls
    r = compute_bcvf_cost([s0, s1, s2], cfg)
    assert r.total_cost <= 1e-10


def test_lemma_1_quadratic_positive():
    cfg = BCVFLLMConfig()
    L, V = 5, 20
    eta = np.linspace(0.5, 1.0, V)
    ls = np.arange(L, dtype=np.float64).reshape(L, 1)
    s0 = 0.5 * eta * (ls ** 2)
    s1 = np.zeros((L, V), dtype=np.float64)
    s2 = np.zeros((L, V), dtype=np.float64)
    r = compute_bcvf_cost([s0, s1, s2], cfg)
    assert r.total_cost > 0.0
