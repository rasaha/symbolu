#!/usr/bin/env python3
"""
BPC Diagnostic Plots
======================

Generate all required diagnostic plots from training logs:
  - Train/val loss curves for A0..A7
  - Logit std + entropy curves
  - Explained variance curve for PCA
  - z variance per-dimension over training
  - Scaling-law fit plot (log-log) with alpha values
  - Activation patching KL distributions
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_metrics(metrics_path: str) -> List[Dict]:
    """Load metrics from JSONL file."""
    entries = []
    with open(metrics_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def plot_training_curves(
    run_dir: str,
    ablations: List[str] = None,
    output_path: str = None,
):
    """
    Plot train/val loss curves for all ablation conditions.
    Reads from {run_dir}/{ablation}/metrics.jsonl
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available")
        return

    if ablations is None:
        ablations = [f"A{i}" for i in range(8)]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    colors = plt.cm.tab10(np.linspace(0, 1, len(ablations)))

    # 1. Train loss
    ax = axes[0, 0]
    for i, abl in enumerate(ablations):
        path = Path(run_dir) / abl / "metrics.jsonl"
        if not path.exists():
            continue
        entries = load_metrics(str(path))
        steps = [e["step"] for e in entries if "ce_loss" in e]
        losses = [e["ce_loss"] for e in entries if "ce_loss" in e]
        if steps:
            ax.plot(steps, losses, color=colors[i], label=abl, alpha=0.7)
    ax.set_xlabel("Step")
    ax.set_ylabel("CE Loss")
    ax.set_title("Training CE Loss")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 2. Val loss
    ax = axes[0, 1]
    for i, abl in enumerate(ablations):
        path = Path(run_dir) / abl / "metrics.jsonl"
        if not path.exists():
            continue
        entries = load_metrics(str(path))
        steps = [e["step"] for e in entries if "val_loss" in e]
        losses = [e["val_loss"] for e in entries if "val_loss" in e]
        if steps:
            ax.plot(steps, losses, color=colors[i], label=abl, alpha=0.7, marker="o", markersize=3)
    ax.set_xlabel("Step")
    ax.set_ylabel("Val Loss")
    ax.set_title("Validation Loss")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 3. Logit std
    ax = axes[0, 2]
    for i, abl in enumerate(ablations):
        path = Path(run_dir) / abl / "metrics.jsonl"
        if not path.exists():
            continue
        entries = load_metrics(str(path))
        steps = [e["step"] for e in entries if "logit_std" in e]
        stds = [e["logit_std"] for e in entries if "logit_std" in e]
        if steps:
            ax.plot(steps, stds, color=colors[i], label=abl, alpha=0.7)
    ax.set_xlabel("Step")
    ax.set_ylabel("Logit Std")
    ax.set_title("Logit Standard Deviation (Anti-Calibration)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 4. Entropy
    ax = axes[1, 0]
    for i, abl in enumerate(ablations):
        path = Path(run_dir) / abl / "metrics.jsonl"
        if not path.exists():
            continue
        entries = load_metrics(str(path))
        steps = [e["step"] for e in entries if "entropy" in e]
        ents = [e["entropy"] for e in entries if "entropy" in e]
        if steps:
            ax.plot(steps, ents, color=colors[i], label=abl, alpha=0.7)
    ax.set_xlabel("Step")
    ax.set_ylabel("Entropy")
    ax.set_title("Output Entropy")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 5. z variance (BPC runs only)
    ax = axes[1, 1]
    for i, abl in enumerate(ablations):
        path = Path(run_dir) / abl / "metrics.jsonl"
        if not path.exists():
            continue
        entries = load_metrics(str(path))
        steps = [e["step"] for e in entries if "z_std_mean" in e]
        z_stds = [e["z_std_mean"] for e in entries if "z_std_mean" in e]
        if steps:
            ax.plot(steps, z_stds, color=colors[i], label=abl, alpha=0.7)
    ax.set_xlabel("Step")
    ax.set_ylabel("z Std (mean across dims)")
    ax.set_title("Belief Coordinate Variance")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 6. Rollout + CF loss components
    ax = axes[1, 2]
    for i, abl in enumerate(ablations):
        path = Path(run_dir) / abl / "metrics.jsonl"
        if not path.exists():
            continue
        entries = load_metrics(str(path))
        steps = [e["step"] for e in entries if "rollout_smooth" in e]
        rollout = [e["rollout_smooth"] for e in entries if "rollout_smooth" in e]
        if steps:
            ax.plot(steps, rollout, color=colors[i], label=f"{abl} rollout", alpha=0.7)
        steps_cf = [e["step"] for e in entries if "cf_loss" in e and e.get("cf_loss", 0) > 0]
        cf_loss = [e["cf_loss"] for e in entries if "cf_loss" in e and e.get("cf_loss", 0) > 0]
        if steps_cf:
            ax.plot(steps_cf, cf_loss, color=colors[i], linestyle="--",
                    label=f"{abl} CF", alpha=0.5)
    ax.set_xlabel("Step")
    ax.set_ylabel("Loss Component")
    ax.set_title("BPC Loss Components")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    if output_path is None:
        output_path = str(Path(run_dir) / "training_curves.png")
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved training curves to {output_path}")


def plot_z_per_dim(
    run_dir: str,
    ablation: str = "A2",
    output_path: str = None,
):
    """Plot z variance per dimension over training."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    path = Path(run_dir) / ablation / "metrics.jsonl"
    if not path.exists():
        print(f"No metrics for {ablation}")
        return

    entries = load_metrics(str(path))
    z_entries = [e for e in entries if "z_std_per_dim" in e]

    if not z_entries:
        print(f"No z_std_per_dim data for {ablation}")
        return

    steps = [e["step"] for e in z_entries]
    z_data = np.array([e["z_std_per_dim"] for e in z_entries])  # [num_steps, r]

    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(
        z_data.T,
        aspect="auto",
        cmap="viridis",
        extent=[steps[0], steps[-1], z_data.shape[1], 0],
    )
    ax.set_xlabel("Training Step")
    ax.set_ylabel("PCA Dimension")
    ax.set_title(f"z Variance per Dimension ({ablation})")
    plt.colorbar(im, label="Std")

    plt.tight_layout()
    if output_path is None:
        output_path = str(Path(run_dir) / f"z_per_dim_{ablation}.png")
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved z per-dim plot to {output_path}")


def generate_all_plots(run_dir: str, ablations: List[str] = None):
    """Generate all diagnostic plots."""
    if ablations is None:
        ablations = [f"A{i}" for i in range(8)]
        # Filter to existing
        ablations = [a for a in ablations if (Path(run_dir) / a / "metrics.jsonl").exists()]

    if not ablations:
        print("No ablation results found")
        return

    plot_training_curves(run_dir, ablations)
    for abl in ablations:
        plot_z_per_dim(run_dir, abl)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", type=str, default="runs/bpc")
    parser.add_argument("--ablations", nargs="+", default=None)
    args = parser.parse_args()

    generate_all_plots(args.run_dir, args.ablations)
