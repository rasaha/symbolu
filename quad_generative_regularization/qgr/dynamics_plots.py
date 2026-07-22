"""Plots for the Quad score dynamics analysis. Matplotlib, headless."""

from __future__ import annotations

import os
from typing import Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLORS = {"A": "#444444", "C": "#1f77b4", "D": "#d62728"}
LABELS = {"A": "Arm A (baseline)", "C": "Arm C (generic off-path)", "D": "Arm D (Quad-native)"}


def _traj(trajectories, arm, seed, key):
    t = trajectories[arm][seed]
    return [s["step"] for s in t], [s[key] for s in t]


def make_all(trajectories: Dict, final: Dict, seed0: int, outdir: str):
    os.makedirs(outdir, exist_ok=True)
    arms = list(trajectories.keys())

    # 3. entropy trajectory + 4. gradient trajectories + margin/pos-neg
    for key, fname, ylab, title, logy in [
        ("dyn_entropy_mean", "entropy_trajectory.png", "Quad candidate entropy (nats)",
         "Entropy trajectory (seed %d)" % seed0, False),
        ("dyn_margin_mean", "margin_trajectory.png", "correct−incorrect Quad score",
         "Score margin trajectory (seed %d)" % seed0, False),
        ("grad_grad_wrt_score", "grad_wrt_score_trajectory.png", "|dL_task/dS^Q|",
         "Task gradient norm w.r.t. Quad score (seed %d)" % seed0, True),
    ]:
        plt.figure(figsize=(7, 4.5))
        for arm in arms:
            s, v = _traj(trajectories, arm, seed0, key)
            plt.plot(s, v, marker="o", ms=3, color=COLORS[arm], label=LABELS[arm])
        if logy:
            plt.yscale("log")
        plt.xlabel("training step"); plt.ylabel(ylab); plt.title(title)
        plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
        plt.savefig(os.path.join(outdir, fname), dpi=110); plt.close()

    # 4b. all gradient norms for Arm D (score/hidden/Wq/Wk)
    plt.figure(figsize=(7, 4.5))
    for key, lab in [("grad_grad_wrt_score", "d/dS^Q"), ("grad_grad_wrt_hidden", "d/dhidden"),
                     ("grad_grad_wrt_Wq", "d/dW_q"), ("grad_grad_wrt_Wk", "d/dW_k")]:
        s, v = _traj(trajectories, "D", seed0, key)
        plt.plot(s, v, marker="o", ms=3, label=lab)
    plt.yscale("log"); plt.xlabel("training step"); plt.ylabel("gradient L2 norm")
    plt.title("Arm D task-gradient norms (seed %d)" % seed0)
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "grad_norms_armD.png"), dpi=110); plt.close()

    # pos vs neg score trajectory
    plt.figure(figsize=(7, 4.5))
    for arm in arms:
        s, pos = _traj(trajectories, arm, seed0, "dyn_pos_score_mean")
        _, neg = _traj(trajectories, arm, seed0, "dyn_neg_score_mean")
        plt.plot(s, pos, color=COLORS[arm], label=f"{arm} correct")
        plt.plot(s, neg, color=COLORS[arm], ls="--", label=f"{arm} incorrect")
    plt.xlabel("training step"); plt.ylabel("mean Quad score")
    plt.title("Correct vs incorrect Quad score (seed %d)" % seed0)
    plt.legend(fontsize=7, ncol=3); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "pos_neg_score_trajectory.png"), dpi=110); plt.close()

    # 5. final score-distribution histogram (per arm, seed0)
    plt.figure(figsize=(7.5, 4.5))
    for arm in arms:
        snap = trajectories[arm][seed0][-1]
        counts = np.array(snap["dyn_hist_counts"])
        lo, hi = snap["dyn_hist_range"]; bins = snap["dyn_hist_bins"]
        centers = np.linspace(lo, hi, bins)
        counts = counts / max(counts.sum(), 1)
        plt.plot(centers, counts, color=COLORS[arm], label=LABELS[arm])
    plt.xlabel("Quad candidate logit S^Q"); plt.ylabel("fraction of candidates")
    plt.title("Final Quad score distribution over candidates (seed %d)" % seed0)
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "score_distribution.png"), dpi=110); plt.close()

    # 6. hidden-state vs projected geometry (bar: separation gap by stage)
    plt.figure(figsize=(7, 4.5))
    x = np.arange(len(arms)); w = 0.38
    hid = [final[a]["geom_hidden_cos_gap"]["mean"] for a in arms]
    proj = [final[a]["geom_proj_qk_cos_gap"]["mean"] for a in arms]
    plt.bar(x - w/2, hid, w, label="hidden-state cosine gap (pos−neg)", color="#8888cc")
    plt.bar(x + w/2, proj, w, label="projected q·k cosine gap (pos−neg)", color="#cc8844")
    plt.xticks(x, [LABELS[a] for a in arms], fontsize=8)
    plt.ylabel("separation gap (pos − neg)")
    plt.title("Where separation originates: hidden geometry vs Quad projection")
    plt.legend(fontsize=8); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "hidden_vs_projection_geometry.png"), dpi=110); plt.close()

    # 4c. temperature counterfactual (final entropy vs T, per arm)
    plt.figure(figsize=(7, 4.5))
    for arm in arms:
        bt = final[arm]["temp"]["by_temp"]
        temps = sorted(float(t) for t in bt)
        frac = [bt[str(t)]["entropy_frac_of_uniform"] for t in temps]
        plt.plot(temps, frac, marker="o", color=COLORS[arm], label=LABELS[arm])
    plt.axhline(1.0, color="gray", ls=":", alpha=0.6, label="uniform (max entropy)")
    plt.xscale("log"); plt.xlabel("temperature T (offline, applied to trained S^Q)")
    plt.ylabel("entropy / uniform-entropy")
    plt.title("Temperature counterfactual: can softening restore entropy?")
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "temperature_counterfactual.png"), dpi=110); plt.close()
