"""Shared statistical / linear-algebra primitives for the experiments track.

Single home for routines previously duplicated across d0_prime and the B.0.*
harnesses: reproducible RNG, ridge out-of-fold R^2, numerical rank, random
orthogonal families, within-sequence shuffle, percentile/permutation gates,
bootstrap CIs, and Benjamini-Hochberg FDR.

Pure numpy + stdlib. No semantics, no I/O.
"""
from __future__ import annotations

import numpy as np


# ---- reproducible RNG ------------------------------------------------------
def rng(seed: int) -> np.random.Generator:
    """Deterministic generator (never uses global/entropy state)."""
    return np.random.default_rng(seed)


# ---- linear algebra --------------------------------------------------------
def numerical_rank(M: np.ndarray, rel_tol: float = 1e-9) -> int:
    """Rank via singular values above ``rel_tol * sigma_max``."""
    s = np.linalg.svd(np.asarray(M), compute_uv=False)
    if s.size == 0:
        return 0
    return int(np.sum(s > rel_tol * s[0])) if s[0] > 0 else 0


def random_orthogonal_matrices(n: int, d: int, generator: np.random.Generator) -> list[np.ndarray]:
    """``n`` deterministic orthogonal d×d matrices (sign-fixed QR of gaussians)."""
    out = []
    for _ in range(n):
        Q, R = np.linalg.qr(generator.standard_normal((d, d)))
        Q = Q @ np.diag(np.sign(np.diag(R)) + (np.diag(R) == 0))
        out.append(Q)
    return out


def random_orthogonal_family(n: int, d: int = 4, seed: int = 0) -> list[np.ndarray]:
    """Seeded convenience wrapper around :func:`random_orthogonal_matrices`."""
    return random_orthogonal_matrices(n, d, rng(seed))


# ---- regression probe ------------------------------------------------------
def ridge_oof_r2(X: np.ndarray, y: np.ndarray, k: int = 5, lam: float = 1.0,
                 seed: int = 0) -> float:
    """Out-of-fold R^2 of ridge regression (closed form, standardized features).

    Behaviour-identical to the original harness implementation (k-fold on a
    seeded permutation, per-fold z-scoring, intercept via target mean).
    """
    N = len(y)
    folds = np.array_split(rng(seed).permutation(N), k)
    pred = np.zeros(N)
    for f in range(k):
        te = folds[f]
        tr = np.concatenate([folds[j] for j in range(k) if j != f])
        Xtr, Xte, ytr = X[tr], X[te], y[tr]
        mu, sd = Xtr.mean(0), Xtr.std(0); sd[sd == 0] = 1.0
        Xtr = (Xtr - mu) / sd; Xte = (Xte - mu) / sd
        ymu = ytr.mean()
        A = Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1])
        beta = np.linalg.solve(A, Xtr.T @ (ytr - ymu))
        pred[te] = Xte @ beta + ymu
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0


# ---- sequence helper -------------------------------------------------------
def shuffle_within(seqs, generator: np.random.Generator) -> list:
    """Shuffle each sequence's order in place-copy (preserves multiset/counts)."""
    out = []
    for s in seqs:
        t = list(s); generator.shuffle(t); out.append(t)
    return out


# ---- inference gates -------------------------------------------------------
def percentile_gate(observed: float, null_samples, pctl: float = 95) -> dict:
    """Whether ``observed`` exceeds the ``pctl`` percentile of a null sample."""
    null = np.asarray(list(null_samples), float)
    thr = float(np.percentile(null, pctl)) if null.size else float("nan")
    return {"observed": float(observed), "threshold": thr,
            "exceeds": bool(observed > thr),
            "null_mean": float(null.mean()) if null.size else float("nan")}


def permutation_pvalue(observed: float, null_samples) -> float:
    """One-sided permutation p-value, ``(1 + #{null >= obs}) / (1 + n)``."""
    null = np.asarray(list(null_samples), float)
    return float((1 + np.sum(null >= observed)) / (1 + null.size))


def bootstrap_ci(values, n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 0) -> dict:
    """Percentile bootstrap CI of the mean of ``values``."""
    v = np.asarray(list(values), float)
    g = rng(seed)
    means = np.array([g.choice(v, size=v.size, replace=True).mean()
                      for _ in range(n_boot)]) if v.size else np.array([0.0])
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"mean": float(v.mean()) if v.size else 0.0,
            "lo": float(lo), "hi": float(hi),
            "excludes_zero": bool(lo > 0 or hi < 0)}


def benjamini_hochberg(pvals, q: float = 0.05) -> np.ndarray:
    """BH-FDR: boolean array of rejections at level ``q``."""
    p = np.asarray(list(pvals), float)
    m = p.size
    if m == 0:
        return np.array([], dtype=bool)
    order = np.argsort(p)
    thresh = q * (np.arange(1, m + 1) / m)
    passed = p[order] <= thresh
    reject = np.zeros(m, dtype=bool)
    if passed.any():
        kmax = np.max(np.where(passed))
        reject[order[: kmax + 1]] = True
    return reject
