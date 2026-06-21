"""Lightweight supervised probes (numpy-only, CPU) + metrics for the Bhava/ontology probe.

Models: L2-regularized logistic regression (GD) and a ridge classifier (closed form on ±1).
Evaluation: k-fold out-of-fold (OOF) predictions → accuracy / AUROC / F1 / Brier, bootstrap CIs,
paired comparison vs a reference feature set (McNemar + paired bootstrap), and a Hewitt–Liang
selectivity control (same probe on permuted labels).

Pure numpy so it runs on CPU with no torch and is unit-testable on toy data.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np

# Reuse the project's exact paired stats so probe + ablation report the same way.
from .metrics import mcnemar_exact, paired_bootstrap_ci


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def _standardize(train: np.ndarray, X: np.ndarray) -> np.ndarray:
    mu = train.mean(axis=0, keepdims=True)
    sd = train.std(axis=0, keepdims=True)
    sd[sd < 1e-8] = 1.0
    return (X - mu) / sd


def _logreg_fit(X: np.ndarray, y: np.ndarray, l2: float = 1.0,
                lr: float = 0.1, iters: int = 500, class_weight: bool = True) -> np.ndarray:
    """L2-regularized, class-weighted logistic regression (full-batch GD). Returns weights (+bias).

    Class weighting (inverse frequency) stops the probe collapsing to the majority class under
    imbalance — essential here, where the base model is right/wrong at very uneven rates.
    """
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    w = np.zeros(d + 1)
    sw = np.ones(n)
    if class_weight:
        for c in (0, 1):
            m = (y == c)
            cnt = int(m.sum())
            if cnt > 0:
                sw[m] = n / (2.0 * cnt)
    swsum = sw.sum()
    for _ in range(iters):
        z = Xb @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        grad = Xb.T @ (sw * (p - y)) / swsum
        grad[:-1] += l2 * w[:-1] / n   # L2 on weights, not bias
        w -= lr * grad
    return w


def _logreg_proba(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    return 1.0 / (1.0 + np.exp(-np.clip(Xb @ w, -30, 30)))


def _ridge_fit(X: np.ndarray, y: np.ndarray, l2: float = 1.0) -> np.ndarray:
    """Ridge regression on ±1 targets (closed form). Returns weights (+bias)."""
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    t = 2.0 * y - 1.0
    A = Xb.T @ Xb
    reg = l2 * np.eye(d + 1)
    reg[-1, -1] = 0.0  # no penalty on bias
    w = np.linalg.solve(A + reg, Xb.T @ t)
    return w


def _ridge_decision(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    s = Xb @ w
    return 1.0 / (1.0 + np.exp(-np.clip(s, -30, 30)))  # squash to [0,1] for AUROC/Brier


_MODELS: Dict[str, Tuple[Callable, Callable]] = {
    "logreg": (lambda X, y, l2: _logreg_fit(X, y, l2=l2), _logreg_proba),
    "ridge": (lambda X, y, l2: _ridge_fit(X, y, l2=l2), _ridge_decision),
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def auroc(y: np.ndarray, p: np.ndarray) -> float:
    """Rank-based AUROC. Returns NaN if only one class present."""
    y = np.asarray(y)
    pos = p[y == 1]
    neg = p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1)
    # average ranks for ties
    _, inv, counts = np.unique(p, return_inverse=True, return_counts=True)
    sums = np.zeros(len(counts))
    np.add.at(sums, inv, ranks)
    avg = sums / counts
    ranks = avg[inv]
    r_pos = ranks[y == 1].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def f1(y: np.ndarray, p: np.ndarray, thr: float = 0.5) -> float:
    pred = (p >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    denom = 2 * tp + fp + fn
    return float(2 * tp / denom) if denom else 0.0


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def accuracy(y: np.ndarray, p: np.ndarray, thr: float = 0.5) -> float:
    return float(((p >= thr).astype(int) == y).mean())


def balanced_accuracy(y: np.ndarray, p: np.ndarray, thr: float = 0.5) -> float:
    """Mean per-class recall — imbalance-robust (chance = 0.5 regardless of class skew)."""
    pred = (p >= thr).astype(int)
    recalls = []
    for c in (0, 1):
        m = (y == c)
        if m.sum() > 0:
            recalls.append(float((pred[m] == c).mean()))
    return float(np.mean(recalls)) if recalls else 0.0


def auroc_ci(y: np.ndarray, p: np.ndarray, n_boot: int = 1000, seed: int = 0):
    """Bootstrap CI for AUROC (resample examples). Returns (point, lo, hi)."""
    y = np.asarray(y)
    point = auroc(y, p)
    if math.isnan(point):
        return float("nan"), float("nan"), float("nan")
    rng = np.random.RandomState(seed)
    n = len(y)
    vals = []
    for _ in range(n_boot):
        s = rng.randint(0, n, n)
        a = auroc(y[s], p[s])
        if not math.isnan(a):
            vals.append(a)
    if not vals:
        return float(point), float("nan"), float("nan")
    vals.sort()
    lo = vals[int(0.025 * len(vals))]
    hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))]
    return float(point), float(lo), float(hi)


# ---------------------------------------------------------------------------
# k-fold OOF evaluation
# ---------------------------------------------------------------------------

def kfold_indices(n: int, k: int, seed: int = 0) -> List[np.ndarray]:
    rng = np.random.RandomState(seed)
    idx = rng.permutation(n)
    return [idx[i::k] for i in range(k)]


def _pca_fit(Xtr_s: np.ndarray, dim: int) -> np.ndarray:
    """Top-`dim` principal directions of standardized train data. Returns [dim, d]."""
    # Xtr_s already ~zero-mean per column (standardized). SVD of the data matrix.
    _, _, Vt = np.linalg.svd(Xtr_s, full_matrices=False)
    return Vt[:dim]


def oof_predict(X: np.ndarray, y: np.ndarray, model: str = "logreg",
                k: int = 5, l2: float = 1.0, seed: int = 0,
                pca_dim: int = 64) -> np.ndarray:
    """Out-of-fold predicted probabilities, aligned to X's row order.

    For high-dim feature sets (d > pca_dim, e.g. the 4096-d hidden baseline), PCA-reduce to
    pca_dim INSIDE each fold (fit on train only). Without this, a logistic probe on 4096 dims with
    ~100 examples overfits so badly it scores below chance out-of-fold — a broken baseline that
    invalidates any "X beats hidden" comparison. Low-dim sets (bhava 13-d, state 32-d) are
    untouched. pca_dim<=0 disables.
    """
    n = len(y)
    k = max(2, min(k, n))
    fit, proba = _MODELS[model]
    folds = kfold_indices(n, k, seed)
    oof = np.full(n, np.nan)
    for f in range(k):
        test = folds[f]
        train = np.concatenate([folds[j] for j in range(k) if j != f])
        if len(test) == 0 or len(train) == 0:
            continue
        Xtr_s = _standardize(X[train], X[train])
        Xte_s = _standardize(X[train], X[test])
        if pca_dim and Xtr_s.shape[1] > pca_dim and pca_dim < len(train):
            comp = _pca_fit(Xtr_s, pca_dim)        # fit on train only (no leakage)
            Xtr_s = Xtr_s @ comp.T
            Xte_s = Xte_s @ comp.T
        w = fit(Xtr_s, y[train], l2)
        oof[test] = proba(w, Xte_s)
    # any unassigned (degenerate) → 0.5
    oof[np.isnan(oof)] = 0.5
    return oof


def _metrics_from_oof(y: np.ndarray, oof: np.ndarray, oof_ctrl: np.ndarray, yp: np.ndarray,
                      dim: int, n_boot: int, seed: int) -> Dict:
    acc = accuracy(y, oof)
    bal_acc = balanced_accuracy(y, oof)
    correct = ((oof >= 0.5).astype(int) == y).astype(float)
    au, au_lo, au_hi = auroc_ci(y, oof, n_boot=n_boot, seed=seed + 11)
    bal_ctrl = balanced_accuracy(yp, oof_ctrl)
    chance = max(float(y.mean()), float(1 - y.mean()))
    decodable = bool(not math.isnan(au_lo) and au_lo > 0.5)
    return {
        "n": int(len(y)), "dim": int(dim),
        "accuracy": acc, "balanced_accuracy": bal_acc,
        "auroc": au, "auroc_ci": [au_lo, au_hi],
        "f1": f1(y, oof), "brier": brier(y, oof),
        "chance": float(chance), "control_balanced_accuracy": float(bal_ctrl),
        "selectivity": float(bal_acc - bal_ctrl),
        "beats_chance": decodable,
        "oof_correct": [float(x) for x in correct],
    }


def evaluate_feature_set(X: np.ndarray, y: np.ndarray, *, model: str = "logreg",
                         k: int = 5, l2: float = 1.0, seed: int = 0,
                         n_boot: int = 2000, pca_dim: int = 64) -> Dict:
    """OOF metrics on a single prebuilt matrix (global fold-internal PCA). Used by tests."""
    y = np.asarray(y).astype(int)
    oof = oof_predict(X, y, model=model, k=k, l2=l2, seed=seed, pca_dim=pca_dim)
    rng = np.random.RandomState(seed + 7)
    yp = rng.permutation(y)
    oof_ctrl = oof_predict(X, yp, model=model, k=k, l2=l2, seed=seed, pca_dim=pca_dim)
    return _metrics_from_oof(y, oof, oof_ctrl, yp, X.shape[1], n_boot, seed)


def _oof_from_groups(group_arrays, y, reduce_groups, pca_dim, model, k, l2, seed):
    """OOF probabilities where HIGH-DIM groups (hidden) are PCA-reduced PER GROUP, per fold.

    Reducing hidden to a few dims BEFORE concatenating with the 12-d Bhava prevents the 4096-d
    hidden from swamping Bhava in `hidden_plus_bhava` — the bug that made the complement test
    meaningless. PCA is fit on train only (no leakage). Returns (oof, total_dim).
    """
    n = len(y)
    k = max(2, min(k, n))
    fit, proba = _MODELS[model]
    folds = kfold_indices(n, k, seed)
    oof = np.full(n, np.nan)
    total_dim = 0
    for f in range(k):
        test = folds[f]
        train = np.concatenate([folds[j] for j in range(k) if j != f])
        if len(test) == 0 or len(train) == 0:
            continue
        parts_tr, parts_te = [], []
        for name, A in group_arrays.items():
            Atr = _standardize(A[train], A[train])
            Ate = _standardize(A[train], A[test])
            if name in reduce_groups and Atr.shape[1] > pca_dim and 0 < pca_dim < len(train):
                comp = _pca_fit(Atr, pca_dim)
                Atr, Ate = Atr @ comp.T, Ate @ comp.T
            parts_tr.append(Atr)
            parts_te.append(Ate)
        Xtr = np.hstack(parts_tr)
        Xte = np.hstack(parts_te)
        total_dim = Xtr.shape[1]
        w = fit(Xtr, y[train], l2)
        oof[test] = proba(w, Xte)
    oof[np.isnan(oof)] = 0.5
    return oof, total_dim


def evaluate_groups(group_arrays: Dict[str, np.ndarray], y: np.ndarray, *,
                    reduce_groups, pca_dim: int = 24, model: str = "logreg",
                    k: int = 5, l2: float = 1.0, seed: int = 0, n_boot: int = 2000) -> Dict:
    """Evaluate a feature set defined as named groups, PCA-reducing hidden groups per-fold."""
    y = np.asarray(y).astype(int)
    oof, dim = _oof_from_groups(group_arrays, y, reduce_groups, pca_dim, model, k, l2, seed)
    rng = np.random.RandomState(seed + 7)
    yp = rng.permutation(y)
    oof_ctrl, _ = _oof_from_groups(group_arrays, yp, reduce_groups, pca_dim, model, k, l2, seed)
    return _metrics_from_oof(y, oof, oof_ctrl, yp, dim, n_boot, seed)


def paired_vs_reference(y: Sequence[int], correct_ref: Sequence[float],
                        correct_cand: Sequence[float]) -> Dict:
    """Paired comparison of two feature sets' per-example OOF correctness (cand vs ref)."""
    a = [bool(x) for x in correct_ref]
    b = [bool(x) for x in correct_cand]
    mc = mcnemar_exact(a, b)
    pt, lo, hi = paired_bootstrap_ci([float(x) for x in a], [float(x) for x in b])
    return {
        "delta_acc": pt, "ci": [lo, hi], "mcnemar_p": mc["p_value"],
        "significant": (mc["p_value"] < 0.05) and (lo > 0 or hi < 0),
        "direction": "cand_better" if pt > 0 else ("ref_better" if pt < 0 else "tie"),
    }
