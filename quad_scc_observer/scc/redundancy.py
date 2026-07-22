"""Redundancy analysis: how much of each SCC term's signal overlaps existing baselines.

For each SCC feature we report its oriented univariate AUROC and its maximum absolute Pearson
correlation with confidence (A::), entailment (B::), and grounding (C::) features. This documents
overlaps such as "E identical to grounding", "T correlates with confidence".
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from use import metrics
from .evaluate import impute
from . import arms


def _max_abs_corr(x: np.ndarray, group: np.ndarray) -> float:
    if group.size == 0:
        return float("nan")
    best = 0.0
    for j in range(group.shape[1]):
        g = group[:, j]
        if np.std(x) < 1e-9 or np.std(g) < 1e-9:
            continue
        c = abs(float(np.corrcoef(x, g)[0, 1]))
        best = max(best, c)
    return best


def compute(pool: Dict[str, np.ndarray]) -> Dict:
    P = impute(pool)
    y = P["label_failure"].astype(int)
    g = arms.group_names(P)
    A = np.column_stack([P[n] for n in g["A"]]) if g["A"] else np.zeros((len(y), 0))
    B = np.column_stack([P[n] for n in g["B"]]) if g["B"] else np.zeros((len(y), 0))
    C = np.column_stack([P[n] for n in g["C"]]) if g["C"] else np.zeros((len(y), 0))
    out = {}
    for t in arms.TERMS:
        out[t] = {}
        for name in g[t]:
            x = P[name]
            auc = metrics.auroc(y, x) if len(np.unique(y)) > 1 else float("nan")
            out[t][name] = {
                "oriented_auroc": float(max(auc, 1 - auc)) if auc == auc else float("nan"),
                "max_corr_confidence": _max_abs_corr(x, A),
                "max_corr_entailment": _max_abs_corr(x, B),
                "max_corr_grounding": _max_abs_corr(x, C),
            }
    return out
