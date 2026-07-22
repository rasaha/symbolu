"""Plots for the perturbation-consistency study. Matplotlib, headless."""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLORS = {"BD-A": "#17becf", "BD-D": "#d62728", "BD-Sync": "#2ca02c",
          "BD-Sync-Early": "#ff7f0e", "Shuffled-Pair": "#9467bd"}
ARMS = ["BD-A", "BD-D", "BD-Sync", "BD-Sync-Early", "Shuffled-Pair"]


def make_all(agg, per_seed, seeds, hard_conds, ood_conds, outdir):
    os.makedirs(outdir, exist_ok=True)

    # 1. training curves (val acc vs steps, seed 0)
    plt.figure(figsize=(7.5, 4.5))
    for arm in ARMS:
        h = per_seed[arm][seeds[0]]["history"]
        plt.plot([e["step"] for e in h], [e["val_acc"] for e in h],
                 marker="o", ms=3, color=COLORS[arm], label=arm)
    plt.xlabel("training step"); plt.ylabel("val accuracy"); plt.title("Training curves (seed %d)" % seeds[0])
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "training_curves.png"), dpi=110); plt.close()

    # 2. generalization comparison (gen score + ood, mean±sd) with BD-A reference line
    plt.figure(figsize=(8, 4.8))
    x = np.arange(len(ARMS)); w = 0.38
    gen = [agg[a]["gen_score"]["mean"] for a in ARMS]
    gerr = [agg[a]["gen_score"]["std"] for a in ARMS]
    ood = [agg[a]["ood_score"]["mean"] for a in ARMS]
    oerr = [agg[a]["ood_score"]["std"] for a in ARMS]
    plt.bar(x - w/2, gen, w, yerr=gerr, capsize=3, label="hard-condition score", color="#4c72b0")
    plt.bar(x + w/2, ood, w, yerr=oerr, capsize=3, label="OOD-suite score", color="#dd8452")
    plt.axhline(agg["BD-A"]["gen_score"]["mean"], color=COLORS["BD-A"], ls=":", label="BD-A hard bar")
    plt.xticks(x, ARMS, rotation=12, ha="right", fontsize=8); plt.ylabel("mean accuracy")
    plt.title("Generalization vs BD-A (mean ± sd, 5 seeds)")
    plt.legend(fontsize=8); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "generalization_comparison.png"), dpi=110); plt.close()

    # 3. hard conditions grouped bars
    conds = ["in_distribution"] + hard_conds
    xc = np.arange(len(conds)); w = 0.8 / len(ARMS)
    plt.figure(figsize=(9, 4.8))
    for j, arm in enumerate(ARMS):
        means = [agg[arm]["conditions"][c]["mean"] for c in conds]
        errs = [agg[arm]["conditions"][c]["std"] for c in conds]
        plt.bar(xc + j*w, means, w, yerr=errs, capsize=2, color=COLORS[arm], label=arm)
    plt.xticks(xc + w*(len(ARMS)-1)/2, conds, rotation=12, ha="right", fontsize=8)
    plt.ylabel("accuracy"); plt.title("Accuracy by condition (mean ± sd, 5 seeds)")
    plt.legend(fontsize=8, ncol=3); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "hard_conditions.png"), dpi=110); plt.close()

    # 4. entropy & diversity (health)
    plt.figure(figsize=(8, 4.8))
    ent = [agg[a]["diagnostics"]["entropy"]["mean"] for a in ARMS]
    div = [agg[a]["diagnostics"]["cross_head_diversity"]["mean"] for a in ARMS]
    spec = [agg[a]["diagnostics"]["head_specialization"]["mean"] for a in ARMS]
    x = np.arange(len(ARMS)); w = 0.27
    plt.bar(x - w, ent, w, label="entropy", color="#4c72b0")
    plt.bar(x, div, w, label="cross-head diversity", color="#55a868")
    plt.bar(x + w, spec, w, label="head specialization", color="#c44e52")
    plt.xticks(x, ARMS, rotation=12, ha="right", fontsize=8)
    plt.title("Attention-organization health (mean, 5 seeds)")
    plt.legend(fontsize=8); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "entropy_diversity.png"), dpi=110); plt.close()

    # 5. progressive-perturbation degradation curves (seed 0)
    plt.figure(figsize=(7.5, 4.5))
    for arm in ARMS:
        curve = per_seed[arm][seeds[0]].get("stability_curve")
        if curve:
            plt.plot(range(len(curve)), curve, marker="o", color=COLORS[arm], label=arm)
    plt.xlabel("perturbation stage (0=original .. 5=multi-system)")
    plt.ylabel("retrieval distribution drift (JS)")
    plt.title("Progressive-perturbation degradation (seed %d)" % seeds[0])
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "progressive_degradation.png"), dpi=110); plt.close()

    # 6. causal guardrail (retained fraction under attention ablation, seed 0)
    plt.figure(figsize=(7, 4.3))
    rf = [per_seed[a][seeds[0]].get("guardrail_causal", {}).get("retained_frac", float("nan"))
          for a in ARMS]
    plt.bar(ARMS, rf, color=[COLORS[a] for a in ARMS])
    plt.axhline(0.40, color="red", ls="--", alpha=0.6, label="binding-causal threshold")
    plt.axhline(0.25, color="gray", ls=":", alpha=0.6, label="chance")
    plt.ylabel("retained acc (attn zeroed / clean)"); plt.title("Guardrail 1: Quad retrieval still causal?")
    plt.xticks(rotation=12, ha="right", fontsize=8); plt.legend(fontsize=8)
    plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "causal_guardrail.png"), dpi=110); plt.close()
