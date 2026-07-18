"""B.0.2 — operator mismatch / identifiability calibration (numpy only).

Builds probe operator families ``{N_i}`` as controlled transforms of the true
generative family ``{M_i}`` (exposed via generators.generate_with_assets), to
quantify how operator-product probe power degrades with probe/truth mismatch.

Regimes:
  exact            N_i = M_i,                 s0' = s0
  gauge            N_i = S M_i S^T,           s0' = S s0   (orthogonal S; the
                   principled automaton gauge -> features = S * true_features,
                   an invertible linear map -> predictor-equivalent)
  perturb(eps)     N_i = polar(M_i + eps*G_i),s0' = s0     (re-orthogonalized)
  random           N_i = random orthogonal,   s0' = s0     (unrelated)
  abelian          N_i = positive diagonal (commuting),     s0' = s0
                   -> product depends only on counts (order-blind)
  corrupt(frac)    fraction of N_i replaced by random orthogonal

SYNTHETIC CALIBRATION ONLY: no semantics, no real data, no A', no B-G,
no Symbol-U PASS/FAIL/bottom. Preserves bottom.
"""
from __future__ import annotations

import numpy as np


def _polar_orthogonal(A: np.ndarray) -> np.ndarray:
    """Nearest orthogonal matrix to A (the polar/SVD orthogonal factor U @ Vt).

    Sign of the determinant is preserved (NO forced proper-rotation flip): for an
    orthogonal input — including improper, det=-1, members of the generative
    family — this returns the input exactly, so ε=0 reproduces the exact probe.
    """
    U, _, Vt = np.linalg.svd(A)
    return U @ Vt


def probe_exact(ops, s0, seed=0):
    return [np.array(M, float) for M in ops], np.array(s0, float)


def probe_gauge(ops, s0, seed=0):
    d = len(s0)
    rng = np.random.default_rng(seed + 11)
    Q, _ = np.linalg.qr(rng.standard_normal((d, d)))
    return [Q @ M @ Q.T for M in ops], Q @ np.array(s0, float)


def probe_perturb(ops, s0, eps, seed=0):
    rng = np.random.default_rng(seed + 23)
    N = [_polar_orthogonal(np.array(M, float) + eps * rng.standard_normal(M.shape))
         for M in ops]
    return N, np.array(s0, float)


def probe_random(ops, s0, seed=0):
    d = len(s0)
    rng = np.random.default_rng(seed + 37)
    N = [_polar_orthogonal(rng.standard_normal((d, d))) for _ in ops]
    return N, np.array(s0, float)


def probe_abelian(ops, s0, seed=0):
    """Commuting (positive-diagonal) family -> ordered product is count-only."""
    d = len(s0)
    rng = np.random.default_rng(seed + 53)
    N = [np.diag(np.exp(0.2 * rng.standard_normal(d))) for _ in ops]
    return N, np.array(s0, float)


def probe_corrupt(ops, s0, frac, seed=0):
    d = len(s0)
    rng = np.random.default_rng(seed + 67)
    N = [np.array(M, float) for M in ops]
    k = int(round(frac * len(ops)))
    if k > 0:
        idx = rng.choice(len(ops), size=k, replace=False)
        for i in idx:
            N[i] = _polar_orthogonal(rng.standard_normal((d, d)))
    return N, np.array(s0, float)
