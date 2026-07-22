"""Figures for the SCC observer study (matplotlib, Agg)."""

from __future__ import annotations

import os
from typing import Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _save(fig, path):
    fig.tight_layout(); fig.savefig(path, dpi=120, bbox_inches="tight"); plt.close(fig)


def plot_arms_by_condition(res: Dict, out: str):
    conds = [c for c in res["per_condition"] if "arms" in res["per_condition"][c]]
    arm_order = ["1_confidence", "2_conf_entail", "3_conf_ground", "7_cg_T", "9_full_scc", "9b_cg_full_scc"]
    fig, ax = plt.subplots(figsize=(11, 5))
    n = len(conds); w = 0.13
    for ai, a in enumerate(arm_order):
        vals = [res["per_condition"][c]["arms"].get(a, {}).get("auroc", np.nan) for c in conds]
        ax.bar([i + ai * w for i in range(n)], vals, w, label=a)
    ax.axhline(0.5, color="k", ls="--", lw=1)
    ax.set_xticks([i + 2.5 * w for i in range(n)]); ax.set_xticklabels(conds, rotation=15, fontsize=8)
    ax.set_ylabel("failure-detection AUROC"); ax.set_ylim(0.4, 1.02)
    ax.set_title("Arm AUROC by condition (grounding is a closed-world oracle)")
    ax.legend(fontsize=7, ncol=3)
    _save(fig, out)


def plot_increments(res: Dict, out: str):
    """Pooled ΔAUROC of each term over each base."""
    pooled = res["pooled"].get("increments", {})
    terms = list(pooled.keys())
    bases = ["over_confidence", "over_conf_entail", "over_conf_entail_ground"]
    fig, ax = plt.subplots(figsize=(9, 5))
    w = 0.25
    for bi, base in enumerate(bases):
        vals = [pooled.get(t, {}).get(base, {}).get("delta_auroc", np.nan) for t in terms]
        ax.bar([i + bi * w for i in range(len(terms))], vals, w, label=base)
    ax.axhline(0.005, color="g", ls=":", lw=1, label="practical threshold 0.005")
    ax.axhline(0.0, color="k", lw=0.8)
    ax.set_xticks([i + w for i in range(len(terms))]); ax.set_xticklabels(terms)
    ax.set_ylabel("pooled ΔAUROC (term added to base)")
    ax.set_title("Incremental value of each SCC term over baselines (pooled)")
    ax.legend(fontsize=8)
    _save(fig, out)


def plot_term_alone(res: Dict, out: str):
    pooled = res["pooled"]
    ta = pooled.get("term_alone", {})
    conf = pooled.get("arms", {}).get("1_confidence", {}).get("auroc", np.nan)
    grnd = pooled.get("arms", {}).get("3_conf_ground", {}).get("auroc", np.nan)
    fig, ax = plt.subplots(figsize=(8, 5))
    items = list(ta.items())
    ax.bar([k for k, _ in items], [v for _, v in items], color="#2ca02c", label="SCC term alone")
    ax.axhline(conf, color="#1f77b4", ls="--", label=f"confidence ({conf:.3f})")
    ax.axhline(grnd, color="#d62728", ls="--", label=f"conf+grounding ({grnd:.3f})")
    ax.axhline(0.5, color="k", ls=":", lw=1)
    ax.set_ylabel("AUROC (pooled)"); ax.set_ylim(0.4, 1.02)
    ax.set_title("Each SCC term alone vs confidence and grounding")
    ax.legend(fontsize=8)
    _save(fig, out)


def plot_reliability(res: Dict, out: str):
    pooled = res["pooled"].get("arms", {})
    fig, ax = plt.subplots(figsize=(6, 6))
    for a, col in [("1_confidence", "#1f77b4"), ("7_cg_T", "#2ca02c"), ("9b_cg_full_scc", "#d62728")]:
        rel = pooled.get(a, {}).get("reliability")
        if not rel:
            continue
        xs = [r["conf"] for r in rel if r["conf"] is not None]
        ys = [r["acc"] for r in rel if r["conf"] is not None]
        ax.plot(xs, ys, "-o", label=f"{a} (ECE={pooled[a]['ece']:.3f})", color=col)
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set_xlabel("predicted failure prob"); ax.set_ylabel("observed failure rate")
    ax.set_title("Reliability diagram (pooled)"); ax.legend(fontsize=8)
    _save(fig, out)


def make_all(res: Dict, outdir: str):
    os.makedirs(outdir, exist_ok=True)
    plot_arms_by_condition(res, os.path.join(outdir, "arms_by_condition.png"))
    plot_increments(res, os.path.join(outdir, "increments.png"))
    plot_term_alone(res, os.path.join(outdir, "term_alone.png"))
    plot_reliability(res, os.path.join(outdir, "reliability.png"))
