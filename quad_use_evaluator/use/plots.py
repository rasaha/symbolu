"""Figures for the USE study (matplotlib, Agg)."""

from __future__ import annotations

import os
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _save(fig, path):
    fig.tight_layout(); fig.savefig(path, dpi=120, bbox_inches="tight"); plt.close(fig)


def plot_auroc_by_condition(results: Dict, out: str):
    conds = [c for c, r in results["per_condition"].items() if "predictors" in r]
    preds = ["token_prob_only", "baseline_combo", "use_best", "use_all", "combined_base_use", "random"]
    colors = {"token_prob_only": "#4c72b0", "baseline_combo": "#1f77b4", "use_best": "#2ca02c",
              "use_all": "#9467bd", "combined_base_use": "#d62728", "random": "#999999"}
    fig, ax = plt.subplots(figsize=(11, 5))
    n = len(conds); w = 0.14
    for pi, p in enumerate(preds):
        vals = [results["per_condition"][c]["predictors"].get(p, {}).get("auroc", np.nan) for c in conds]
        xs = [i + pi * w for i in range(n)]
        ax.bar(xs, vals, w, label=p, color=colors[p])
    ax.axhline(0.5, color="k", ls="--", lw=1)
    ax.set_xticks([i + 2.5 * w for i in range(n)]); ax.set_xticklabels(conds, rotation=15, fontsize=8)
    ax.set_ylabel("AUROC (failure detection)"); ax.set_ylim(0.3, 1.0)
    ax.set_title("Failure-detection AUROC by condition — USE vs confidence baselines")
    ax.legend(fontsize=7, ncol=3)
    _save(fig, out)


def plot_univariate(results: Dict, out: str):
    pooled = results["pooled_all"].get("univariate", {})
    if not pooled:
        return
    items = sorted(pooled.items(), key=lambda kv: -(kv[1]["auroc"] if kv[1]["auroc"] == kv[1]["auroc"] else 0))
    items = [(k, v) for k, v in items if v["auroc"] == v["auroc"]][:24]
    names = [k.replace("USE::", "").replace("BASE::", "B:") for k, _ in items]
    vals = [v["auroc"] for _, v in items]
    cols = ["#1f77b4" if k.startswith("BASE") else "#2ca02c" for k, _ in items]
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.barh(range(len(names)), vals, color=cols)
    ax.axvline(0.5, color="k", ls="--", lw=1)
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=6)
    ax.invert_yaxis(); ax.set_xlabel("oriented AUROC (pooled)")
    ax.set_title("Univariate failure-prediction power (green=USE, blue=baseline)")
    _save(fig, out)


def plot_channel_ablation(abl: Dict, out: str):
    cs = abl["channel_set"]
    items = sorted(cs.items(), key=lambda kv: -(kv[1] if kv[1] == kv[1] else 0))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(range(len(items)), [v for _, v in items], color="#2ca02c")
    ax.axhline(0.5, color="k", ls="--", lw=1)
    ax.set_xticks(range(len(items))); ax.set_xticklabels([k for k, _ in items], rotation=25, fontsize=7)
    ax.set_ylabel("USE combined AUROC"); ax.set_ylim(0.3, 1.0)
    ax.set_title("Channel-set ablation — which internal representation predicts failure best")
    _save(fig, out)


def plot_reliability(results: Dict, out: str):
    pooled = results["pooled_all"].get("predictors", {})
    fig, ax = plt.subplots(figsize=(6, 6))
    for p, col in [("baseline_combo", "#1f77b4"), ("use_all", "#2ca02c"),
                   ("combined_base_use", "#d62728")]:
        rel = pooled.get(p, {}).get("reliability")
        if not rel:
            continue
        xs = [r["conf"] for r in rel if r["conf"] is not None]
        ys = [r["acc"] for r in rel if r["conf"] is not None]
        ax.plot(xs, ys, "-o", label=f"{p} (ECE={pooled[p]['ece']:.3f})", color=col)
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    ax.set_xlabel("predicted failure probability"); ax.set_ylabel("observed failure rate")
    ax.set_title("Reliability diagram (pooled)"); ax.legend(fontsize=8)
    _save(fig, out)


def make_all(results: Dict, ablation: Dict, outdir: str):
    os.makedirs(outdir, exist_ok=True)
    plot_auroc_by_condition(results, os.path.join(outdir, "auroc_by_condition.png"))
    plot_univariate(results, os.path.join(outdir, "univariate_power.png"))
    plot_channel_ablation(ablation, os.path.join(outdir, "channel_set_ablation.png"))
    plot_reliability(results, os.path.join(outdir, "reliability.png"))
