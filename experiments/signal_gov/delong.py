"""
delong.py — Paired AUROC significance test (DeLong, 1988; fast version Sun & Xu, 2014).

Used to test whether C4's AUROC differs from C3's on the SAME samples (correlated
ROC curves). Pure numpy; the normal tail is computed via math.erfc (no scipy).

Reference: X. Sun and W. Xu, "Fast Implementation of DeLong's Algorithm for Comparing
the Areas Under Correlated Receiver Operating Characteristic Curves," IEEE SPL, 2014.

`delong_roc_test(labels, scores_a, scores_b)` returns (auc_a, auc_b, p_value), with a
two-sided p-value for H0: AUC_a == AUC_b. Returns p=nan when there are too few
samples in either class to estimate the covariance (e.g. <2 positives or <2 negatives).
"""

from __future__ import annotations

import math
from typing import Tuple

import numpy as np


def _compute_midrank(x: np.ndarray) -> np.ndarray:
    J = np.argsort(x, kind="mergesort")
    Z = x[J]
    n = len(x)
    T = np.zeros(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j < n and Z[j] == Z[i]:
            j += 1
        T[i:j] = 0.5 * (i + j - 1) + 1.0
        i = j
    T2 = np.empty(n, dtype=float)
    T2[J] = T
    return T2


def _fast_delong(predictions_sorted_transposed: np.ndarray, m: int):
    """Compute AUCs and DeLong covariance.

    `predictions_sorted_transposed` is a (k x N) array of k predictors with the m
    positive examples first, then the n negatives.
    """
    n = predictions_sorted_transposed.shape[1] - m
    positive = predictions_sorted_transposed[:, :m]
    negative = predictions_sorted_transposed[:, m:]
    k = predictions_sorted_transposed.shape[0]

    tx = np.empty([k, m], dtype=float)
    ty = np.empty([k, n], dtype=float)
    tz = np.empty([k, m + n], dtype=float)
    for r in range(k):
        tx[r, :] = _compute_midrank(positive[r, :])
        ty[r, :] = _compute_midrank(negative[r, :])
        tz[r, :] = _compute_midrank(predictions_sorted_transposed[r, :])

    aucs = tz[:, :m].sum(axis=1) / m / n - (m + 1.0) / 2.0 / n
    v01 = (tz[:, :m] - tx[:, :]) / n
    v10 = 1.0 - (tz[:, m:] - ty[:, :]) / m
    sx = np.cov(v01)
    sy = np.cov(v10)
    delongcov = sx / m + sy / n
    return aucs, np.atleast_2d(delongcov)


def _norm_sf(z: float) -> float:
    """Upper-tail of the standard normal via erfc."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def delong_roc_test(labels, scores_a, scores_b) -> Tuple[float, float, float]:
    labels = np.asarray(labels, dtype=int)
    scores_a = np.asarray(scores_a, dtype=float)
    scores_b = np.asarray(scores_b, dtype=float)

    m = int((labels == 1).sum())
    n = int((labels == 0).sum())
    if m < 2 or n < 2:
        # Covariance is undefined; still report AUCs for reference.
        from experiments.signal_gov.metrics import roc_auc
        return roc_auc(labels, scores_a), roc_auc(labels, scores_b), float("nan")

    order = np.argsort(-labels, kind="mergesort")  # positives (label 1) first
    preds = np.vstack((scores_a, scores_b))[:, order]
    aucs, cov = _fast_delong(preds, m)

    l = np.array([[1.0, -1.0]])
    var = float(l.dot(cov).dot(l.T)[0, 0])
    if var <= 0:
        p = 1.0 if aucs[0] == aucs[1] else 0.0
    else:
        z = (aucs[0] - aucs[1]) / math.sqrt(var)
        p = 2.0 * _norm_sf(abs(z))
    return float(aucs[0]), float(aucs[1]), float(min(1.0, max(0.0, p)))
