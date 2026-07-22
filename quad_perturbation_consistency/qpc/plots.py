"""All figures for the perturbation-consistency study (matplotlib, Agg backend)."""

from __future__ import annotations

import os
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ARMS = ["BD-A", "BD-D", "BD-Sync", "BD-Sync-Early", "BD-Shuffled"]
COLORS = {"BD-A": "#1f77b4", "BD-D": "#d62728", "BD-Sync": "#2ca02c",
          "BD-Sync-Early": "#9467bd", "BD-Shuffled": "#ff7f0e"}
HARD = ["longer_context", "higher_distractor", "two_systems"]
CONDS = ["in_distribution"] + HARD


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def plot_generalization(summ: Dict, out: str):
    fig, ax = plt.subplots(figsize=(9, 5))
    n = len(CONDS); w = 0.15
    for ai, arm in enumerate(ARMS):
        if arm not in summ:
            continue
        means = [summ[arm]["conditions"][c]["mean"] for c in CONDS]
        errs = [summ[arm]["conditions"][c]["std"] for c in CONDS]
        xs = [i + ai * w for i in range(n)]
        ax.bar(xs, means, w, yerr=errs, capsize=2, label=arm, color=COLORS[arm])
    ax.set_xticks([i + 2 * w for i in range(n)])
    ax.set_xticklabels(CONDS, rotation=15)
    ax.set_ylabel("accuracy"); ax.set_ylim(0, 1.05)
    ax.set_title("Generalization by condition (mean ± sd over seeds) — benchmark is BD-A")
    ax.axhline(0.0, color="k", lw=0.5); ax.legend(fontsize=8, ncol=3)
    _save(fig, out)


def plot_meanhard_delta(comparisons: Dict, out: str):
    """Per-seed paired delta (arm - BD-A) on mean-hard generalization."""
    fig, ax = plt.subplots(figsize=(8, 5))
    arms = [a for a in ["BD-Sync", "BD-Sync-Early", "BD-Shuffled", "BD-D"] if a in comparisons]
    for ai, arm in enumerate(arms):
        deltas = comparisons[arm]["delta_per_seed"]
        xs = [ai + (j - len(deltas) / 2) * 0.03 for j in range(len(deltas))]
        ax.scatter(xs, deltas, color=COLORS.get(arm, "#333"), s=25, alpha=0.7)
        ax.scatter([ai], [comparisons[arm]["mean_delta"]], color="k", marker="_", s=800)
        ci = comparisons[arm]["bootstrap_ci95"]
        ax.plot([ai, ai], [ci["lo"], ci["hi"]], color="k", lw=1.5)
    ax.axhline(0, color="r", lw=1, ls="--")
    ax.set_xticks(range(len(arms))); ax.set_xticklabels(arms, rotation=10)
    ax.set_ylabel("mean-hard accuracy − BD-A (per seed)")
    ax.set_title("Paired improvement over BD-A (dots=seeds, bar=mean, line=bootstrap 95% CI)")
    _save(fig, out)


def plot_progressive(prog: Dict[str, List[Dict]], out_cons: str, out_acc: str):
    """prog[arm] = mean per-level curve (list of dicts with level,label,perturb_stability,accuracy)."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for arm in ARMS:
        if arm not in prog:
            continue
        levels = [d["level"] for d in prog[arm]]
        stab = [d["perturb_stability"] for d in prog[arm]]
        ax.plot(levels, stab, "-o", label=arm, color=COLORS[arm])
    labels = [d["label"] for d in prog[ARMS[0]]]
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=20, fontsize=8)
    ax.set_ylabel("perturbation stability (1 − JS/logC)")
    ax.set_title("Attention-consistency degradation across the perturbation progression")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    _save(fig, out_cons)

    fig, ax = plt.subplots(figsize=(9, 5))
    for arm in ARMS:
        if arm not in prog:
            continue
        levels = [d["level"] for d in prog[arm]]
        acc = [d["accuracy"] for d in prog[arm]]
        ax.plot(levels, acc, "-o", label=arm, color=COLORS[arm])
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=20, fontsize=8)
    ax.set_ylabel("task accuracy"); ax.set_ylim(0, 1.05)
    ax.set_title("Task-accuracy degradation across the perturbation progression")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    _save(fig, out_acc)


def plot_health(summ: Dict, out: str):
    metrics = [("attn_entropy_norm", "entropy (norm)"),
               ("head_diversity_js", "head diversity (JS)"),
               ("head_specialization_sel_std", "specialization (sel-acc std)"),
               ("perturb_stability", "perturb stability"),
               ("retrieval_stability", "retrieval stability"),
               ("headmean_select_acc", "selection accuracy")]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for (key, title), ax in zip(metrics, axes.flat):
        vals, errs, cols, labs = [], [], [], []
        for arm in ARMS:
            if arm not in summ or key not in summ[arm]:
                continue
            vals.append(summ[arm][key]["mean"]); errs.append(summ[arm][key]["std"])
            cols.append(COLORS[arm]); labs.append(arm)
        ax.bar(range(len(vals)), vals, yerr=errs, capsize=2, color=cols)
        ax.set_xticks(range(len(labs))); ax.set_xticklabels(labs, rotation=25, fontsize=7)
        ax.set_title(title, fontsize=10)
    fig.suptitle("Attention health & stability (mean ± sd over seeds)")
    _save(fig, out)


def plot_causal(causal: Dict, out: str):
    """causal[arm] = {'clean':x, 'attn_zero_all':y, 'retained':y/x} on in_distribution."""
    fig, ax = plt.subplots(figsize=(8, 5))
    arms = [a for a in ARMS if a in causal]
    clean = [causal[a]["clean"] for a in arms]
    zero = [causal[a]["attn_zero_all"] for a in arms]
    xs = range(len(arms)); w = 0.38
    ax.bar([x - w / 2 for x in xs], clean, w, label="clean", color="#4c72b0")
    ax.bar([x + w / 2 for x in xs], zero, w, label="attn zeroed (all layers)", color="#c44e52")
    ax.axhline(causal.get("chance", 0.06), color="k", ls="--", lw=1, label="chance")
    ax.set_xticks(list(xs)); ax.set_xticklabels(arms, rotation=15)
    ax.set_ylabel("in-distribution accuracy"); ax.set_ylim(0, 1.05)
    ax.set_title("Guardrail 1 — Quad-retrieval causal necessity (zeroing attention → chance)")
    ax.legend(fontsize=8)
    _save(fig, out)


def make_all(summ, comparisons, prog, causal, outdir):
    os.makedirs(outdir, exist_ok=True)
    plot_generalization(summ, os.path.join(outdir, "generalization_by_condition.png"))
    plot_meanhard_delta(comparisons, os.path.join(outdir, "paired_delta_vs_BDA.png"))
    plot_progressive(prog, os.path.join(outdir, "progressive_consistency.png"),
                     os.path.join(outdir, "progressive_accuracy.png"))
    plot_health(summ, os.path.join(outdir, "attention_health.png"))
    plot_causal(causal, os.path.join(outdir, "causal_necessity.png"))
