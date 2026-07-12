"""Deterministic numeric primitives on numpy + stdlib only (no scipy/sklearn).

Everything here is pure and seed-explicit. Estimators that *fit* parameters expose
a fit/apply split so callers can guarantee train-only fitting (leakage prevention).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Standardization (fit on train only)
# ---------------------------------------------------------------------------

@dataclass
class Standardizer:
    mean: np.ndarray
    std: np.ndarray

    @staticmethod
    def fit(X: np.ndarray, eps: float = 1e-8) -> "Standardizer":
        X = np.asarray(X, dtype=float)
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std = np.where(std < eps, 1.0, std)
        return Standardizer(mean=mean, std=std)

    def apply(self, X: np.ndarray) -> np.ndarray:
        return (np.asarray(X, dtype=float) - self.mean) / self.std


# ---------------------------------------------------------------------------
# Mahalanobis prototype model (fit on genuine training vectors)
# ---------------------------------------------------------------------------

@dataclass
class GaussianPrototype:
    mean: np.ndarray
    cov_inv: np.ndarray

    @staticmethod
    def fit(X: np.ndarray, ridge: float = 1e-3) -> "GaussianPrototype":
        X = np.asarray(X, dtype=float)
        mean = X.mean(axis=0)
        d = X.shape[1]
        if X.shape[0] > 1:
            cov = np.cov(X, rowvar=False)
            cov = np.atleast_2d(cov)
        else:
            cov = np.eye(d)
        cov = cov + ridge * np.eye(d)
        cov_inv = np.linalg.pinv(cov)
        return GaussianPrototype(mean=mean, cov_inv=cov_inv)

    def mahalanobis(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        diff = X - self.mean
        return np.sqrt(np.maximum(0.0, np.einsum("ij,jk,ik->i", diff, self.cov_inv, diff)))

    def euclidean(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        return np.linalg.norm(X - self.mean, axis=1)


# ---------------------------------------------------------------------------
# Logistic regression (batch gradient descent; deterministic)
# ---------------------------------------------------------------------------

@dataclass
class LogisticRegression:
    w: np.ndarray
    b: float

    @staticmethod
    def fit(X, y, l2: float = 1e-2, lr: float = 0.1, iters: int = 500) -> "LogisticRegression":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        n, d = X.shape
        w = np.zeros(d)
        b = 0.0
        for _ in range(iters):
            z = X @ w + b
            p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
            g = p - y
            gw = X.T @ g / n + l2 * w
            gb = float(g.mean())
            w -= lr * gw
            b -= lr * gb
        return LogisticRegression(w=w, b=b)

    def predict_proba(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        z = X @ self.w + self.b
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


@dataclass
class NearestCentroid:
    centroids: np.ndarray  # (n_classes, d)
    labels: np.ndarray

    @staticmethod
    def fit(X, y) -> "NearestCentroid":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        labels = np.unique(y)
        cents = np.stack([X[y == c].mean(axis=0) for c in labels])
        return NearestCentroid(centroids=cents, labels=labels)

    def score_genuine(self, X, genuine_label) -> np.ndarray:
        """Return a similarity-to-genuine score (negative distance to genuine centroid)."""
        X = np.asarray(X, dtype=float)
        idx = int(np.where(self.labels == genuine_label)[0][0])
        return -np.linalg.norm(X - self.centroids[idx], axis=1)


# ---------------------------------------------------------------------------
# Canonical Correlation Analysis (numpy SVD; fit on train only)
# ---------------------------------------------------------------------------

@dataclass
class CCA:
    x_mean: np.ndarray
    y_mean: np.ndarray
    correlations: np.ndarray

    @staticmethod
    def fit(X, Y, ridge: float = 1e-3, k: Optional[int] = None) -> "CCA":
        X = np.asarray(X, dtype=float)
        Y = np.asarray(Y, dtype=float)
        xm, ym = X.mean(0), Y.mean(0)
        Xc, Yc = X - xm, Y - ym
        n = max(1, X.shape[0] - 1)
        Sxx = Xc.T @ Xc / n + ridge * np.eye(X.shape[1])
        Syy = Yc.T @ Yc / n + ridge * np.eye(Y.shape[1])
        Sxy = Xc.T @ Yc / n
        Sxx_inv_half = _inv_sqrt(Sxx)
        Syy_inv_half = _inv_sqrt(Syy)
        M = Sxx_inv_half @ Sxy @ Syy_inv_half
        s = np.linalg.svd(M, compute_uv=False)
        corr = np.clip(s, 0.0, 1.0)
        if k is not None:
            corr = corr[:k]
        return CCA(x_mean=xm, y_mean=ym, correlations=corr)

    def mean_correlation(self) -> float:
        return float(self.correlations.mean()) if self.correlations.size else 0.0


def _inv_sqrt(S: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh(S)
    vals = np.maximum(vals, 1e-12)
    return vecs @ np.diag(1.0 / np.sqrt(vals)) @ vecs.T


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """AUC via the Mann–Whitney U statistic. labels: 1==positive (genuine)."""
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels)
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ranks for ties
    _assign_tie_ranks(scores, ranks)
    r_pos = ranks[labels == 1].sum()
    n_pos, n_neg = pos.size, neg.size
    u = r_pos - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


def _assign_tie_ranks(scores, ranks):
    order = np.argsort(scores, kind="mergesort")
    s_sorted = scores[order]
    i = 0
    n = len(scores)
    while i < n:
        j = i
        while j + 1 < n and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        if j > i:
            avg = (i + 1 + j + 1) / 2.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
        i = j + 1


def tpr_at_fixed_far(scores: np.ndarray, labels: np.ndarray, far: float) -> float:
    """Detection (TPR) at a fixed false-accept rate. Higher score == more genuine."""
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels)
    neg = np.sort(scores[labels == 0])
    pos = scores[labels == 1]
    if neg.size == 0 or pos.size == 0:
        return float("nan")
    # threshold s.t. fraction of negatives above it == far
    idx = int(np.ceil((1.0 - far) * neg.size)) - 1
    idx = min(max(idx, 0), neg.size - 1)
    thr = neg[idx]
    return float((pos > thr).mean())


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size < 2 or b.size < 2:
        return float("nan")
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt(((a.size - 1) * va + (b.size - 1) * vb) / (a.size + b.size - 2))
    if pooled == 0:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)


def bootstrap_ci(values: np.ndarray, iters: int, alpha: float, seed: int) -> Tuple[float, float, float]:
    """Percentile bootstrap CI of the mean. Returns (point, lo, hi)."""
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if values.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n = values.size
    means = np.empty(iters)
    for i in range(iters):
        idx = rng.integers(0, n, n)
        means[i] = values[idx].mean()
    lo = float(np.quantile(means, alpha / 2))
    hi = float(np.quantile(means, 1 - alpha / 2))
    return float(values.mean()), lo, hi


def paired_bootstrap_diff_ci(a: np.ndarray, b: np.ndarray, iters: int, alpha: float,
                             seed: int) -> Tuple[float, float, float]:
    """Percentile CI of the paired mean difference (a - b)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b
    return bootstrap_ci(d, iters, alpha, seed)
