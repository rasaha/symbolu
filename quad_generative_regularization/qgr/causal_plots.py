"""Plots for the causal localization analysis. Matplotlib, headless."""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ARMS = ["C", "D-full", "BD-A", "BD-D", "BD-D10"]
COLORS = {"C": "#1f77b4", "D-full": "#d62728", "BD-A": "#17becf",
          "BD-D": "#9467bd", "BD-D10": "#e377c2"}


def make_all(agg, seed0_detail, conds, outdir):
    os.makedirs(outdir, exist_ok=True)

    # 1. retained accuracy under each ablation (in-distribution), grouped by arm
    ablations = ["attn_zero_aux", "attn_zero_all", "attn_shuffle_aux", "attn_mean_aux",
                 "attn_zero_L0", "ff_zero_aux", "ff_zero_all"]
    x = np.arange(len(ablations)); w = 0.8 / len(ARMS)
    plt.figure(figsize=(11, 5))
    for j, arm in enumerate(ARMS):
        vals = [agg[arm][ab]["in_distribution"]["retained"] for ab in ablations]
        plt.bar(x + j * w, vals, w, color=COLORS[arm], label=arm)
    plt.axhline(0.25, color="gray", ls=":", alpha=0.6, label="chance retained (~0.25)")
    plt.xticks(x + w * (len(ARMS) - 1) / 2, ablations, rotation=20, ha="right", fontsize=8)
    plt.ylabel("retained accuracy fraction (ablated / clean)")
    plt.title("Pathway ablation: fraction of in-distribution accuracy retained")
    plt.legend(fontsize=8, ncol=3); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "ablation_retained_indist.png"), dpi=110); plt.close()

    # 2. attention ablation effect across conditions (retained fraction)
    plt.figure(figsize=(9, 5))
    xc = np.arange(len(conds)); w = 0.8 / len(ARMS)
    for j, arm in enumerate(ARMS):
        vals = [agg[arm]["attn_zero_all"][c]["retained"] for c in conds]
        plt.bar(xc + j * w, vals, w, color=COLORS[arm], label=arm)
    plt.xticks(xc + w * (len(ARMS) - 1) / 2, conds, rotation=12, ha="right", fontsize=8)
    plt.ylabel("retained accuracy (attn_zero_all / clean)")
    plt.title("Quad-retrieval necessity by condition (zero all attention)")
    plt.legend(fontsize=8, ncol=3); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "attn_ablation_by_condition.png"), dpi=110); plt.close()

    # 3. pathway importance: IG attention fraction + patch recovery per arm (seed0)
    plt.figure(figsize=(8, 4.8))
    ig = [seed0_detail[a].get("ig", {}).get("attn_frac", float("nan")) for a in ARMS]
    rec = [seed0_detail[a].get("patching", {}).get("recovery", float("nan")) for a in ARMS]
    xa = np.arange(len(ARMS)); w = 0.38
    plt.bar(xa - w/2, ig, w, label="IG attention fraction", color="#4c72b0")
    plt.bar(xa + w/2, rec, w, label="activation-patching recovery", color="#dd8452")
    plt.xticks(xa, ARMS, fontsize=9); plt.ylabel("attribution / recovery")
    plt.title("Quad-retrieval pathway importance (seed 0)")
    plt.legend(fontsize=8); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "pathway_importance.png"), dpi=110); plt.close()

    # 4. linear probe accuracy per representation per arm (seed0)
    feats = ["hidden", "proj_q", "proj_k"]
    plt.figure(figsize=(8, 4.8))
    xf = np.arange(len(feats)); w = 0.8 / len(ARMS)
    for j, arm in enumerate(ARMS):
        vals = [seed0_detail[arm].get("probe", {}).get(f, float("nan")) for f in feats]
        plt.bar(xf + j * w, vals, w, color=COLORS[arm], label=arm)
    plt.xticks(xf + w * (len(ARMS) - 1) / 2, feats, fontsize=9)
    plt.ylabel("linear-probe accuracy (predict answer token)")
    plt.title("Where is the answer linearly decodable? (seed 0)")
    plt.legend(fontsize=8, ncol=3); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "probe_accuracy.png"), dpi=110); plt.close()
