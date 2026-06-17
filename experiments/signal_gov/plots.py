"""
plots.py — Deck-ready figures (matplotlib, Agg backend; no display required).

    roc_overlay         four ROC curves (C1..C4) on one axis  <-- the investor slide
    catch_at_budget_bar grouped bars: catch-rate at 5/10/20% escalation budget

Both write PNGs and return the output path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence

import numpy as np

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402

from experiments.signal_gov.configs import CONFIG_ORDER  # noqa: E402


def _roc_curve(labels: np.ndarray, scores: np.ndarray):
    order = np.argsort(-scores, kind="mergesort")
    y = labels[order]
    n_pos = max(1, int((labels == 1).sum()))
    n_neg = max(1, int((labels == 0).sum()))
    tps = np.cumsum(y == 1)
    fps = np.cumsum(y == 0)
    tpr = np.concatenate([[0.0], tps / n_pos])
    fpr = np.concatenate([[0.0], fps / n_neg])
    return fpr, tpr


def roc_overlay(labels: Sequence[int], scores_by_config: Dict[str, Sequence[float]],
                aurocs: Dict[str, float], out_path: Path) -> Path:
    labels = np.asarray(labels, dtype=int)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", linewidth=1, label="chance")
    for name in CONFIG_ORDER:
        if name not in scores_by_config:
            continue
        fpr, tpr = _roc_curve(labels, np.asarray(scores_by_config[name], dtype=float))
        auc = aurocs.get(name, float("nan"))
        ax.plot(fpr, tpr, linewidth=2, label=f"{name}  (AUROC={auc:.3f})")
    ax.set_xlabel("False positive rate (safe calls escalated)")
    ax.set_ylabel("True positive rate (unsafe calls caught)")
    ax.set_title("Governance ablation — ROC overlay")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def catch_at_budget_bar(catch_by_config: Dict[str, Dict[str, float]],
                        out_path: Path) -> Path:
    configs = [c for c in CONFIG_ORDER if c in catch_by_config]
    budgets = sorted({b for c in configs for b in catch_by_config[c]}, key=float)
    x = np.arange(len(budgets))
    width = 0.8 / max(1, len(configs))

    fig, ax = plt.subplots(figsize=(7, 5))
    for i, name in enumerate(configs):
        vals = [catch_by_config[name].get(b, np.nan) for b in budgets]
        ax.bar(x + i * width, vals, width, label=name)
    ax.set_xticks(x + width * (len(configs) - 1) / 2)
    ax.set_xticklabels([f"{float(b)*100:.0f}%" for b in budgets])
    ax.set_xlabel("Human-review (escalation) budget")
    ax.set_ylabel("Unsafe calls caught (recall)")
    ax.set_title("Catch rate at fixed escalation budget")
    ax.set_ylim(0, 1)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
