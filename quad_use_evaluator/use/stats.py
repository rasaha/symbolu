"""Statistical tests for AUROC: bootstrap CIs and the DeLong test for correlated ROC curves.

The DeLong test compares two AUROCs computed on the SAME samples (USE vs baseline), accounting
for their correlation — the correct test for "does USE add predictive value beyond the baseline".
"""

from __future__ import annotations

from typing import Dict

import numpy as np
from scipy import stats as sps


# ------------------------------- fast DeLong -------------------------------------------

def _compute_midrank(x):
    J = np.argsort(x)
    Z = x[J]
    N = len(x)
    T = np.zeros(N, dtype=float)
    i = 0
    while i < N:
        j = i
        while j < N and Z[j] == Z[i]:
            j += 1
        T[i:j] = 0.5 * (i + j - 1) + 1
        i = j
    T2 = np.empty(N, dtype=float)
    T2[J] = T
    return T2


def _fast_delong(preds_sorted_transposed, label_1_count):
    m = label_1_count
    n = preds_sorted_transposed.shape[1] - m
    positive = preds_sorted_transposed[:, :m]
    negative = preds_sorted_transposed[:, m:]
    k = preds_sorted_transposed.shape[0]
    tx = np.empty([k, m], dtype=float)
    ty = np.empty([k, n], dtype=float)
    tz = np.empty([k, m + n], dtype=float)
    for r in range(k):
        tx[r, :] = _compute_midrank(positive[r, :])
        ty[r, :] = _compute_midrank(negative[r, :])
        tz[r, :] = _compute_midrank(preds_sorted_transposed[r, :])
    aucs = tz[:, :m].sum(axis=1) / m / n - float(m + 1.0) / 2.0 / n
    v01 = (tz[:, :m] - tx[:, :]) / n
    v10 = 1.0 - (tz[:, m:] - ty[:, :]) / m
    sx = np.cov(v01)
    sy = np.cov(v10)
    delongcov = sx / m + sy / n
    return aucs, delongcov


def delong_roc_test(y_true: np.ndarray, score1: np.ndarray, score2: np.ndarray) -> Dict:
    """Two-sided DeLong test that AUROC(score1) != AUROC(score2) on the same labels.

    Returns aucs and the two-sided p-value; also a one-sided p for score1 > score2.
    """
    order = (-y_true).argsort(kind="stable")
    label_1_count = int(y_true.sum())
    y = y_true[order]
    preds = np.vstack((score1, score2))[:, order]
    aucs, cov = _fast_delong(preds, label_1_count)
    var = cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]
    if var <= 0:
        z = 0.0
    else:
        z = (aucs[0] - aucs[1]) / np.sqrt(var)
    p_two = float(2 * sps.norm.sf(abs(z)))
    p_one_1gt2 = float(sps.norm.sf(z))   # H1: auc1 > auc2
    return {"auc1": float(aucs[0]), "auc2": float(aucs[1]), "z": float(z),
            "p_two_sided": p_two, "p_one_sided_1_gt_2": p_one_1gt2}


def bootstrap_auroc_ci(y: np.ndarray, score: np.ndarray, n_boot: int = 2000,
                       seed: int = 12345, alpha: float = 0.05) -> Dict:
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(seed)
    N = len(y)
    aucs = []
    for _ in range(n_boot):
        idx = rng.integers(0, N, N)
        yy = y[idx]
        if len(np.unique(yy)) < 2:
            continue
        aucs.append(roc_auc_score(yy, score[idx]))
    aucs = np.array(aucs)
    return {"auc": float(roc_auc_score(y, score)) if len(np.unique(y)) > 1 else float("nan"),
            "lo": float(np.quantile(aucs, alpha / 2)) if len(aucs) else float("nan"),
            "hi": float(np.quantile(aucs, 1 - alpha / 2)) if len(aucs) else float("nan")}


def paired_bootstrap_auroc_diff(y: np.ndarray, s1: np.ndarray, s2: np.ndarray,
                                n_boot: int = 2000, seed: int = 999) -> Dict:
    """Bootstrap the AUROC difference (s1 - s2) on the same samples (robust complement to DeLong)."""
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(seed)
    N = len(y)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, N, N)
        yy = y[idx]
        if len(np.unique(yy)) < 2:
            continue
        diffs.append(roc_auc_score(yy, s1[idx]) - roc_auc_score(yy, s2[idx]))
    diffs = np.array(diffs)
    lo, hi = float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))
    p_one = float((diffs <= 0).mean())   # P(s1 not better than s2)
    return {"mean_diff": float(diffs.mean()) if len(diffs) else float("nan"),
            "lo": lo, "hi": hi, "p_one_sided_s1_gt_s2": p_one, "ci_excludes_0": bool(lo > 0 or hi < 0)}
