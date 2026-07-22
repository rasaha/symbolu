"""Plot generation for the study (spec section 28 item 11). Matplotlib, headless."""

from __future__ import annotations

import os
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ARM_COLORS = {"A": "#444444", "C": "#1f77b4", "D": "#d62728"}
ARM_LABELS = {"A": "Arm A (baseline)", "C": "Arm C (generic relational)",
              "D": "Arm D (Quad-native)"}


def _mean_curve(histories: List[List[Dict]], key: str):
    """Average `key` across seeds at each logged step (assumes aligned step grids).
    Missing keys (e.g. a NaN-dropped mechanism metric) contribute 0.0."""
    steps = [h["step"] for h in histories[0]]
    vals = []
    for i in range(len(steps)):
        vals.append(sum(hs[i].get(key, 0.0) for hs in histories) / len(histories))
    return steps, vals


def plot_curves(per_arm_histories: Dict[str, List[List[Dict]]], outdir: str):
    os.makedirs(outdir, exist_ok=True)

    # 1. accuracy vs steps
    plt.figure(figsize=(7, 4.5))
    for arm, hs in per_arm_histories.items():
        s, v = _mean_curve(hs, "val_acc")
        plt.plot(s, v, marker="o", ms=3, color=ARM_COLORS.get(arm), label=ARM_LABELS.get(arm, arm))
    plt.xlabel("training step"); plt.ylabel("val exact-match accuracy")
    plt.title("MQAR accuracy vs training steps (mean over seeds)")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "accuracy_vs_steps.png"), dpi=110); plt.close()

    # 2. task loss vs steps
    plt.figure(figsize=(7, 4.5))
    for arm, hs in per_arm_histories.items():
        s, v = _mean_curve(hs, "val_task_loss")
        plt.plot(s, v, marker="o", ms=3, color=ARM_COLORS.get(arm), label=ARM_LABELS.get(arm, arm))
    plt.xlabel("training step"); plt.ylabel("val task loss")
    plt.title("Task loss vs training steps (mean over seeds)")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "task_loss_vs_steps.png"), dpi=110); plt.close()

    # 3. correct vs incorrect key Quad score (Arm D)
    if "D" in per_arm_histories:
        plt.figure(figsize=(7, 4.5))
        for arm in [a for a in ("C", "D") if a in per_arm_histories]:
            hs = per_arm_histories[arm]
            s, cor = _mean_curve(hs, "mech_correct_key_score")
            _, inc = _mean_curve(hs, "mech_incorrect_key_score")
            plt.plot(s, cor, color=ARM_COLORS.get(arm), label=f"{arm}: correct-key")
            plt.plot(s, inc, color=ARM_COLORS.get(arm), ls="--", label=f"{arm}: incorrect-key")
        plt.xlabel("training step"); plt.ylabel("mean Quad score")
        plt.title("Correct vs incorrect key Quad score")
        plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
        plt.savefig(os.path.join(outdir, "correct_vs_incorrect_key_score.png"), dpi=110); plt.close()

    # 4. positive-negative margin
    plt.figure(figsize=(7, 4.5))
    for arm, hs in per_arm_histories.items():
        s, v = _mean_curve(hs, "mech_pos_neg_margin")
        plt.plot(s, v, marker="o", ms=3, color=ARM_COLORS.get(arm), label=ARM_LABELS.get(arm, arm))
    plt.xlabel("training step"); plt.ylabel("correct − incorrect Quad score")
    plt.title("Quad positive−negative margin vs steps")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "pos_neg_margin.png"), dpi=110); plt.close()


def plot_grad_norms(per_arm_grad: Dict[str, List[List[Dict]]], outdir: str):
    """5. periodic task and auxiliary gradient norms."""
    os.makedirs(outdir, exist_ok=True)
    plt.figure(figsize=(7, 4.5))
    for arm, gh in per_arm_grad.items():
        if not gh or not gh[0]:
            continue
        steps = [g["step"] for g in gh[0]]
        task = [sum(hs[i]["task_grad_norm"] for hs in gh) / len(gh) for i in range(len(steps))]
        aux = [sum(hs[i]["aux_grad_norm"] for hs in gh) / len(gh) for i in range(len(steps))]
        plt.plot(steps, task, color=ARM_COLORS.get(arm), ls="-", label=f"{arm} task-grad")
        plt.plot(steps, aux, color=ARM_COLORS.get(arm), ls=":", label=f"{arm} aux-grad")
    plt.xlabel("training step"); plt.ylabel("gradient L2 norm (shared params)")
    plt.title("Task vs auxiliary gradient norms")
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "grad_norms.png"), dpi=110); plt.close()


def plot_hard_conditions(hard_results: Dict[str, Dict[str, Dict[str, float]]], outdir: str):
    """7. accuracy under preregistered hard conditions (grouped bars). Also seq-length curve."""
    os.makedirs(outdir, exist_ok=True)
    conditions = list(next(iter(hard_results.values())).keys())
    arms = list(hard_results.keys())
    import numpy as np
    x = np.arange(len(conditions))
    w = 0.8 / max(len(arms), 1)
    plt.figure(figsize=(8, 4.5))
    for j, arm in enumerate(arms):
        means = [hard_results[arm][c]["mean"] for c in conditions]
        errs = [hard_results[arm][c]["std"] for c in conditions]
        plt.bar(x + j * w, means, w, yerr=errs, capsize=3, color=ARM_COLORS.get(arm),
                label=ARM_LABELS.get(arm, arm))
    plt.xticks(x + w * (len(arms) - 1) / 2, conditions, rotation=20, ha="right", fontsize=8)
    plt.ylabel("exact-match accuracy"); plt.title("Accuracy by condition (mean ± sd over seeds)")
    plt.legend(fontsize=8); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "hard_conditions.png"), dpi=110); plt.close()


def plot_seq_len_curve(seqlen_results: Dict[str, Dict[int, Dict[str, float]]], outdir: str):
    """6. accuracy vs sequence length."""
    os.makedirs(outdir, exist_ok=True)
    plt.figure(figsize=(7, 4.5))
    for arm, curve in seqlen_results.items():
        lens = sorted(curve.keys())
        means = [curve[L]["mean"] for L in lens]
        errs = [curve[L]["std"] for L in lens]
        plt.errorbar(lens, means, yerr=errs, marker="o", capsize=3,
                     color=ARM_COLORS.get(arm), label=ARM_LABELS.get(arm, arm))
    plt.xlabel("sequence length (context)"); plt.ylabel("exact-match accuracy")
    plt.title("Accuracy vs sequence length")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "accuracy_vs_seqlen.png"), dpi=110); plt.close()


def plot_cpu_time(per_arm_time: Dict[str, float], outdir: str):
    """8. total CPU time to target (per arm)."""
    os.makedirs(outdir, exist_ok=True)
    arms = list(per_arm_time.keys())
    plt.figure(figsize=(5.5, 4))
    plt.bar(arms, [per_arm_time[a] for a in arms],
            color=[ARM_COLORS.get(a) for a in arms])
    plt.ylabel("total CPU training time (s)"); plt.title("Total CPU time (equal-token budget)")
    plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "cpu_time.png"), dpi=110); plt.close()
