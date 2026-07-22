"""Plots for the bounded Quad retrieval experiment. Matplotlib, headless."""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLORS = {"A": "#444444", "C": "#1f77b4", "D-full": "#d62728", "D-10": "#2ca02c",
          "BD-A": "#17becf", "BD-D": "#9467bd", "BD-D10": "#e377c2"}
BD = ["BD-A", "BD-D", "BD-D10"]


def _bd_traj(trajectories, arm, seed, key):
    t = trajectories[arm][seed]
    return [s["step"] for s in t], [s[key] for s in t]


def _hist_curve(all_arms, arm, seed, key):
    h = all_arms[arm][seed]["history"]
    return [e["step"] for e in h], [e[key] for e in h]


def make_all(all_arms, summ, trajectories, seed0, alpha, outdir):
    os.makedirs(outdir, exist_ok=True)

    # accuracy vs steps (BD arms; D-full final as reference line)
    plt.figure(figsize=(7.5, 4.5))
    for arm in BD:
        s, v = _hist_curve(all_arms, arm, seed0, "val_acc")
        plt.plot(s, v, marker="o", ms=3, color=COLORS[arm], label=arm)
    plt.axhline(summ["D-full"]["final_acc"]["mean"], color=COLORS["D-full"], ls=":",
                label="D-full final")
    plt.axhline(0.95, color="gray", ls="--", alpha=0.5, label="0.95 target")
    plt.xlabel("training step"); plt.ylabel("val accuracy")
    plt.title("Bounded arms: accuracy vs steps (seed %d)" % seed0)
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "accuracy_vs_steps.png"), dpi=110); plt.close()

    # entropy vs steps (BD arms; D-full reference ~0)
    plt.figure(figsize=(7.5, 4.5))
    for arm in BD:
        s, v = _bd_traj(trajectories, arm, seed0, "dyn_entropy_mean")
        plt.plot(s, v, marker="o", ms=3, color=COLORS[arm], label=arm)
    plt.axhline(summ["D-full"]["entropy"]["mean"], color=COLORS["D-full"], ls=":",
                label="D-full final (~0)")
    plt.xlabel("training step"); plt.ylabel("Quad candidate entropy")
    plt.title("Entropy vs steps: bounded avoids collapse (seed %d)" % seed0)
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "entropy_vs_steps.png"), dpi=110); plt.close()

    # margin vs steps (BD arms; alpha bound line; D-full unbounded reference)
    plt.figure(figsize=(7.5, 4.5))
    for arm in BD:
        s, v = _bd_traj(trajectories, arm, seed0, "dyn_margin_mean")
        plt.plot(s, v, marker="o", ms=3, color=COLORS[arm], label=arm)
    plt.axhline(alpha, color="black", ls="--", alpha=0.6, label=f"alpha bound = {alpha}")
    plt.axhline(summ["D-full"]["margin"]["mean"], color=COLORS["D-full"], ls=":",
                label="D-full final (unbounded)")
    plt.xlabel("training step"); plt.ylabel("correct−incorrect Quad margin")
    plt.title("Margin vs steps: bounded stays finite (seed %d)" % seed0)
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "margin_vs_steps.png"), dpi=110); plt.close()

    # pre-normalization projected norms vs steps
    plt.figure(figsize=(7.5, 4.5))
    for arm in BD:
        s, rq = _bd_traj(trajectories, arm, seed0, "pnorm_raw_q_norm")
        _, rk = _bd_traj(trajectories, arm, seed0, "pnorm_raw_k_norm")
        plt.plot(s, rq, color=COLORS[arm], label=f"{arm} raw |q|")
        plt.plot(s, rk, color=COLORS[arm], ls="--", label=f"{arm} raw |k|")
    plt.xlabel("training step"); plt.ylabel("mean raw projected norm (pre-normalization)")
    plt.title("Pre-normalization q/k norms (does training inflate them?) seed %d" % seed0)
    plt.legend(fontsize=7, ncol=3); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "prenorm_norms_vs_steps.png"), dpi=110); plt.close()

    # angular separation vs steps (projected cosine gap)
    plt.figure(figsize=(7.5, 4.5))
    for arm in BD:
        s, v = _bd_traj(trajectories, arm, seed0, "geom_proj_qk_cos_gap")
        plt.plot(s, v, marker="o", ms=3, color=COLORS[arm], label=f"{arm} proj gap")
    plt.xlabel("training step"); plt.ylabel("projected q·k cosine gap (pos−neg)")
    plt.title("Angular separation vs steps (seed %d)" % seed0)
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "angular_separation_vs_steps.png"), dpi=110); plt.close()

    # hard conditions grouped bars (all arms)
    order = ["A", "C", "D-full", "D-10", "BD-A", "BD-D", "BD-D10"]
    conds = ["in_distribution"] + ["longer_context", "higher_distractor", "two_systems"]
    x = np.arange(len(conds)); w = 0.8 / len(order)
    plt.figure(figsize=(10, 5))
    for j, arm in enumerate(order):
        means = [summ[arm]["conditions"][c]["mean"] for c in conds]
        errs = [summ[arm]["conditions"][c]["std"] for c in conds]
        plt.bar(x + j * w, means, w, yerr=errs, capsize=2, color=COLORS[arm], label=arm)
    plt.xticks(x + w * (len(order) - 1) / 2, conds, rotation=12, ha="right", fontsize=8)
    plt.ylabel("exact-match accuracy"); plt.title("Accuracy by condition (mean ± sd, 3 seeds)")
    plt.legend(fontsize=8, ncol=4); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "hard_conditions.png"), dpi=110); plt.close()

    # CPU time to target (per bounded arm mean step time)
    plt.figure(figsize=(6.5, 4))
    labels = [a for a in order if a in all_arms and "history" in list(all_arms[a].values())[0]]
    times = []
    for a in labels:
        ts = [all_arms[a][s].get("mean_step_time", 0.0) * 1000 for s in all_arms[a]]
        times.append(sum(ts) / max(len(ts), 1))
    plt.bar(labels, times, color=[COLORS[a] for a in labels])
    plt.ylabel("mean CPU time / step (ms)"); plt.title("Per-step CPU time (bounded arms)")
    plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "cpu_time.png"), dpi=110); plt.close()
