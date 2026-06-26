"""Stage-1 metrics (dependency-free): accuracy, macro-F1, baselines,
entropy<->error correlation, ECE. All operate on masked unit-level tensors.
"""
from __future__ import annotations

from typing import Dict

import torch

from .labels import IGNORE


def _flat(logp: torch.Tensor, labels: torch.Tensor):
    """[B,U,C],[B,U] -> (pred[N], prob[N,C], y[N]) over non-ignored units."""
    B, U, C = logp.shape
    p = logp.exp().reshape(-1, C)
    y = labels.reshape(-1)
    keep = y != IGNORE
    p = p[keep]
    y = y[keep]
    pred = p.argmax(-1)
    return pred, p, y


def accuracy(logp: torch.Tensor, labels: torch.Tensor) -> float:
    pred, _, y = _flat(logp, labels)
    if y.numel() == 0:
        return float("nan")
    return (pred == y).float().mean().item()


def macro_f1(logp: torch.Tensor, labels: torch.Tensor, n_classes: int) -> float:
    pred, _, y = _flat(logp, labels)
    if y.numel() == 0:
        return float("nan")
    f1s = []
    for c in range(n_classes):
        tp = ((pred == c) & (y == c)).sum().item()
        fp = ((pred == c) & (y != c)).sum().item()
        fn = ((pred != c) & (y == c)).sum().item()
        if tp + fp + fn == 0:
            continue                       # class absent in both -> skip
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
    return sum(f1s) / len(f1s) if f1s else float("nan")


def chance_baseline(n_classes: int) -> float:
    return 1.0 / n_classes


def majority_baseline(labels: torch.Tensor) -> float:
    y = labels.reshape(-1)
    y = y[y != IGNORE]
    if y.numel() == 0:
        return float("nan")
    counts = torch.bincount(y)
    return (counts.max().item() / y.numel())


def entropy_error_correlation(logp: torch.Tensor, labels: torch.Tensor) -> float:
    """Pearson r between per-unit predictive entropy and error indicator.

    Uncertainty should be HIGHER when the head is wrong -> expect r > 0.
    """
    B, U, C = logp.shape
    ent = (-(logp.exp() * logp).sum(-1)).reshape(-1)
    pred = logp.argmax(-1).reshape(-1)
    y = labels.reshape(-1)
    keep = y != IGNORE
    ent = ent[keep]
    err = (pred[keep] != y[keep]).float()
    if ent.numel() < 2 or err.std() == 0 or ent.std() == 0:
        return float("nan")
    e = ent - ent.mean()
    u = err - err.mean()
    return ((e * u).mean() / (e.std(unbiased=False) * u.std(unbiased=False))).item()


def expected_calibration_error(logp: torch.Tensor, labels: torch.Tensor,
                               n_bins: int = 10) -> float:
    pred, p, y = _flat(logp, labels)
    if y.numel() == 0:
        return float("nan")
    conf = p.max(-1).values
    correct = (pred == y).float()
    ece = 0.0
    N = y.numel()
    edges = torch.linspace(0, 1, n_bins + 1)
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (conf > lo) & (conf <= hi) if i > 0 else (conf >= lo) & (conf <= hi)
        if m.sum() == 0:
            continue
        ece += (m.float().mean() * (correct[m].mean() - conf[m].mean()).abs()).item()
    return ece


def head_report(head: str, logp: torch.Tensor, labels: torch.Tensor,
                n_classes: int) -> Dict[str, float]:
    return {
        "accuracy": accuracy(logp, labels),
        "macro_f1": macro_f1(logp, labels, n_classes),
        "chance": chance_baseline(n_classes),
        "majority": majority_baseline(labels),
        "entropy_error_corr": entropy_error_correlation(logp, labels),
        "ece": expected_calibration_error(logp, labels),
    }
