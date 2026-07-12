"""Verification metrics + participant/session-clustered bootstrap.

Higher score == more genuine (label 1). Reuses the frozen AUC/TAR primitives from
``numerics`` and adds ROC/DET/EER/FAR/FRR/balanced-accuracy and clustered resampling
(so confidence intervals respect the non-independence of sessions within a participant).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from cyber_security.behavioral_biometrics.numerics import auc, tpr_at_fixed_far


def roc_curve(scores: np.ndarray, labels: np.ndarray) -> Dict[str, List[float]]:
    scores = np.asarray(scores, float)
    labels = np.asarray(labels)
    order = np.argsort(-scores, kind="mergesort")
    s, y = scores[order], labels[order]
    P = max(1, int((labels == 1).sum()))
    N = max(1, int((labels == 0).sum()))
    tp = np.cumsum(y == 1)
    fp = np.cumsum(y == 0)
    tpr = tp / P
    fpr = fp / N
    return {"fpr": [0.0] + fpr.tolist(), "tpr": [0.0] + tpr.tolist(),
            "thresholds": [float("inf")] + s.tolist()}


def det_curve(scores: np.ndarray, labels: np.ndarray) -> Dict[str, List[float]]:
    roc = roc_curve(scores, labels)
    fnr = [1.0 - t for t in roc["tpr"]]
    return {"fpr": roc["fpr"], "fnr": fnr}


def eer(scores: np.ndarray, labels: np.ndarray) -> float:
    """Equal error rate: where FAR == FRR along the ROC."""
    roc = roc_curve(scores, labels)
    fpr = np.array(roc["fpr"])
    fnr = 1.0 - np.array(roc["tpr"])
    diff = fpr - fnr
    idx = int(np.argmin(np.abs(diff)))
    return float((fpr[idx] + fnr[idx]) / 2.0)


def far_frr_at(scores: np.ndarray, labels: np.ndarray, threshold: float) -> Tuple[float, float]:
    scores = np.asarray(scores, float)
    labels = np.asarray(labels)
    neg = scores[labels == 0]
    pos = scores[labels == 1]
    far = float((neg >= threshold).mean()) if neg.size else float("nan")
    frr = float((pos < threshold).mean()) if pos.size else float("nan")
    return far, frr


def balanced_accuracy(scores: np.ndarray, labels: np.ndarray, threshold: float) -> float:
    far, frr = far_frr_at(scores, labels, threshold)
    tar = 1.0 - frr
    tnr = 1.0 - far
    return float((tar + tnr) / 2.0)


def threshold_at_far(scores: np.ndarray, labels: np.ndarray, far: float) -> float:
    scores = np.asarray(scores, float)
    labels = np.asarray(labels)
    neg = np.sort(scores[labels == 0])
    if neg.size == 0:
        return 0.0
    idx = int(np.ceil((1.0 - far) * neg.size)) - 1
    return float(neg[min(max(idx, 0), neg.size - 1)])


def summary(scores, labels, fixed_far: float = 0.05) -> Dict[str, Any]:
    scores = np.asarray(scores, float)
    labels = np.asarray(labels)
    thr = threshold_at_far(scores, labels, fixed_far)
    far, frr = far_frr_at(scores, labels, thr)
    e = eer(scores, labels)
    return {
        "auc": auc(scores, labels),
        "eer": e,
        "tar_at_far": tpr_at_fixed_far(scores, labels, fixed_far),
        "far": far, "frr": frr, "fixed_far": fixed_far,
        "balanced_accuracy": balanced_accuracy(scores, labels, thr),
        "n_genuine": int((labels == 1).sum()), "n_impostor": int((labels == 0).sum()),
    }


# ---- clustered bootstrap (resample whole groups) ----

def _metric(fn, scores, labels):
    return fn(scores, labels)


def clustered_bootstrap_ci(scores, labels, groups, *, metric="auc", iters=2000,
                           alpha=0.05, seed=0) -> Dict[str, float]:
    scores = np.asarray(scores, float)
    labels = np.asarray(labels)
    groups = np.asarray(groups)
    fn = {"auc": auc, "eer": eer}[metric]
    uniq = np.unique(groups)
    rng = np.random.default_rng(seed)
    vals = []
    idx_by_group = {g: np.where(groups == g)[0] for g in uniq}
    for _ in range(iters):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        rows = np.concatenate([idx_by_group[g] for g in pick])
        if len(set(labels[rows].tolist())) < 2:
            continue
        vals.append(fn(scores[rows], labels[rows]))
    point = fn(scores, labels)
    if not vals:
        return {"point": point, "lo": float("nan"), "hi": float("nan")}
    return {"point": float(point), "lo": float(np.quantile(vals, alpha / 2)),
            "hi": float(np.quantile(vals, 1 - alpha / 2))}


def clustered_paired_auc_diff(scores_a, scores_b, labels, groups, *, iters=2000,
                              alpha=0.05, seed=0) -> Dict[str, float]:
    """CI of AUC(a) - AUC(b) over the SAME rows, resampling whole groups (clusters)."""
    a = np.asarray(scores_a, float)
    b = np.asarray(scores_b, float)
    labels = np.asarray(labels)
    groups = np.asarray(groups)
    uniq = np.unique(groups)
    idx_by_group = {g: np.where(groups == g)[0] for g in uniq}
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(iters):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        rows = np.concatenate([idx_by_group[g] for g in pick])
        if len(set(labels[rows].tolist())) < 2:
            continue
        diffs.append(auc(a[rows], labels[rows]) - auc(b[rows], labels[rows]))
    point = auc(a, labels) - auc(b, labels)
    if not diffs:
        return {"point": point, "lo": float("nan"), "hi": float("nan")}
    return {"point": float(point), "lo": float(np.quantile(diffs, alpha / 2)),
            "hi": float(np.quantile(diffs, 1 - alpha / 2))}
