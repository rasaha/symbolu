"""Predictive-performance and calibration metrics for failure detection.

Positive class = FAILURE (answer incorrect). Score = predicted failure probability/rank (higher
=> more likely a failure). Univariate features are oriented for failure detection by the caller.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score


def auroc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def auprc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def prf1(y: np.ndarray, prob: np.ndarray, thr: float = 0.5) -> Dict[str, float]:
    pred = (prob >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "threshold": thr}


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    return float(np.mean((prob - y) ** 2))


def expected_calibration_error(y: np.ndarray, prob: np.ndarray, n_bins: int = 10) -> Dict:
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(prob, bins) - 1, 0, n_bins - 1)
    ece = 0.0
    reliability = []
    N = len(y)
    for b in range(n_bins):
        m = idx == b
        if m.sum() == 0:
            reliability.append({"bin": b, "conf": None, "acc": None, "count": 0})
            continue
        conf = float(prob[m].mean())
        acc = float(y[m].mean())
        ece += (m.sum() / N) * abs(acc - conf)
        reliability.append({"bin": b, "conf": conf, "acc": acc, "count": int(m.sum())})
    return {"ece": float(ece), "reliability": reliability}


def full_calibration(y: np.ndarray, prob: np.ndarray) -> Dict:
    cal = expected_calibration_error(y, prob)
    return {"brier": brier(y, prob), "ece": cal["ece"], "reliability": cal["reliability"]}
