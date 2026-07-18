"""guna_vritti_metrics.py — torch-free (numpy) metrics + decision logic for the Guna/Vritti probe harness.
Operates on numpy arrays of predictions/labels so it is CPU-testable without torch. No model-as-judge.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

try:
    from .guna_vritti_heads import GUNA_NAMES, VRITTI_NAMES, DECISIONS, formula_available
except ImportError:  # direct-path import
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from conscious_generation_training.guna_vritti_heads import (  # type: ignore
        GUNA_NAMES, VRITTI_NAMES, DECISIONS, formula_available)


def auroc(scores: np.ndarray, labels: np.ndarray) -> Optional[float]:
    """Rank-based (Mann-Whitney) AUROC for one binary dimension. None if a class is absent."""
    scores = np.asarray(scores, float); labels = np.asarray(labels, int)
    n_pos, n_neg = int((labels == 1).sum()), int((labels == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    order = scores.argsort()
    ranks = np.empty(len(scores), float)
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ranks for ties
    _, inv, counts = np.unique(scores, return_inverse=True, return_counts=True)
    avg = {}
    sums = np.zeros(len(counts));
    for r, g in zip(ranks, inv):
        sums[g] += r
    for g in range(len(counts)):
        avg[g] = sums[g] / counts[g]
    ranks = np.array([avg[g] for g in inv])
    return round((ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg), 4)


def guna_metrics(pred_scores: np.ndarray, labels: np.ndarray) -> Dict:
    """pred_scores/labels: [N, 6] in [0,1] / {0,1}. BCE + per-dim & macro/micro AUROC + prevalence."""
    p = np.clip(np.asarray(pred_scores, float), 1e-7, 1 - 1e-7)
    y = np.asarray(labels, float)
    bce = float(np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p))))
    per_dim = {GUNA_NAMES[i]: auroc(p[:, i], y[:, i]) for i in range(p.shape[1])}
    valid = [v for v in per_dim.values() if v is not None]
    macro = round(float(np.mean(valid)), 4) if valid else None
    micro = auroc(p.reshape(-1), y.reshape(-1).astype(int))
    return {"bce": round(bce, 4), "per_dim_auroc": per_dim, "macro_auroc": macro, "micro_auroc": micro,
            "label_prevalence": {GUNA_NAMES[i]: round(float(y[:, i].mean()), 4) for i in range(y.shape[1])},
            "calibration": {GUNA_NAMES[i]: {"mean_pred": round(float(p[:, i].mean()), 4),
                                            "mean_label": round(float(y[:, i].mean()), 4)}
                            for i in range(y.shape[1])}, "n": int(len(y))}


def vritti_metrics(pred_probs: np.ndarray, labels: np.ndarray) -> Dict:
    """pred_probs: [N,5]; labels: [N] int. CE + accuracy + macro/per-class F1 + confusion + prevalence."""
    p = np.clip(np.asarray(pred_probs, float), 1e-7, 1.0)
    y = np.asarray(labels, int)
    n, k = p.shape
    ce = float(np.mean(-np.log(p[np.arange(n), y])))
    pred = p.argmax(1)
    acc = float((pred == y).mean())
    conf = np.zeros((k, k), int)
    for t, q in zip(y, pred):
        conf[t, q] += 1
    f1 = {}
    for c in range(k):
        tp = int(((pred == c) & (y == c)).sum()); fp = int(((pred == c) & (y != c)).sum())
        fn = int(((pred != c) & (y == c)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1[VRITTI_NAMES[c]] = round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0
    return {"cross_entropy": round(ce, 4), "accuracy": round(acc, 4),
            "macro_f1": round(float(np.mean(list(f1.values()))), 4), "per_class_f1": f1,
            "confusion": conf.tolist(),
            "label_prevalence": {VRITTI_NAMES[c]: round(float((y == c).mean()), 4) for c in range(k)},
            "n": int(n)}


def decide(*, formula_ok: bool, label_source: str, guna: Optional[Dict], vritti: Optional[Dict],
           shape_only: bool = False, env_ok: bool = True,
           auroc_min: float = 0.60, f1_above_chance: float = 0.10) -> str:
    """Pre-registered decision label. Never invents a formula: formula_ok=False -> FORMULA_UNAVAILABLE."""
    if not formula_ok:
        return "CG_GUNA_VRITTI_FORMULA_UNAVAILABLE"
    if not env_ok:
        return "CG_GUNA_VRITTI_ENV_UNAVAILABLE"
    if shape_only or guna is None or vritti is None:
        return "CG_GUNA_VRITTI_SHAPE_ONLY_PASS"
    if label_source not in ("audit_derived", "human", "real"):
        return "CG_GUNA_VRITTI_SYNTHETIC_ONLY"          # synthetic labels can't validate signal
    # real labels: did the heads learn signal above chance?
    g_ok = guna.get("macro_auroc") is not None and guna["macro_auroc"] >= auroc_min
    chance_f1 = 1.0 / max(1, len(vritti.get("per_class_f1", {}) or {1: 1}))
    v_ok = vritti.get("macro_f1", 0.0) >= chance_f1 + f1_above_chance
    return "CG_GUNA_VRITTI_LEARNS_SIGNAL" if (g_ok or v_ok) else "CG_GUNA_VRITTI_NO_LEARNABLE_SIGNAL"
