"""
Visualization utilities for Spanda-Softmax Hybrid experiments.

Generates:
    1. Training curves (PPL over steps, per configuration)
    2. Anchor geometry plots (pairwise cosine histogram, t-SNE)
    3. Psi trajectory plots (norm over time, 2D PCA projection)
    4. Comparative results table
    5. Coherence metrics (emission vs backbone continuity)
"""

import os
import json
import math
import numpy as np
from typing import Dict, List, Optional


def _safe_import_matplotlib():
    """Import matplotlib with non-interactive backend."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def plot_training_curves(
    all_logs: Dict[str, List[Dict]],
    output_dir: str,
    metric: str = "perplexity",
    title: str = "Training Perplexity",
):
    """
    Plot training curves for multiple configurations.

    Args:
        all_logs: {config_name: [{"step": int, metric: float, ...}, ...]}.
        output_dir: Directory to save plots.
        metric: Which metric to plot.
        title: Plot title.
    """
    plt = _safe_import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 6))

    for name, logs in all_logs.items():
        steps = [l["step"] for l in logs if metric in l]
        values = [l[metric] for l in logs if metric in l]
        if steps:
            ax.plot(steps, values, label=name, linewidth=1.5)

    ax.set_xlabel("Step")
    ax.set_ylabel(metric.replace("_", " ").title())
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    if metric == "perplexity":
        ax.set_yscale("log")

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"training_{metric}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_anchor_cosine_histogram(
    cosine_values: np.ndarray,
    output_dir: str,
    config_name: str = "",
):
    """Plot histogram of pairwise anchor cosine similarities."""
    plt = _safe_import_matplotlib()
    fig, ax = plt.subplots(figsize=(8, 5))

    ax.hist(cosine_values, bins=50, density=True, alpha=0.7, color="steelblue")
    ax.axvline(x=cosine_values.mean(), color="red", linestyle="--",
               label=f"Mean={cosine_values.mean():.3f}")
    ax.set_xlabel("Cosine Similarity")
    ax.set_ylabel("Density")
    ax.set_title(f"Anchor Pairwise Cosine Distribution {config_name}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"anchor_cosine_hist_{config_name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_psi_trajectory(
    psi_norms: np.ndarray,
    output_dir: str,
    config_name: str = "",
    norm_clamp_c: Optional[float] = None,
):
    """
    Plot Psi norm trajectory over sequence positions.

    Args:
        psi_norms: [T] array of ||Psi_t|| values for one sequence.
        output_dir: Directory to save plot.
        config_name: Configuration label.
        norm_clamp_c: Norm clamp ceiling (plotted as horizontal line).
    """
    plt = _safe_import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 4))

    ax.plot(psi_norms, linewidth=1.0, color="steelblue", label="||Psi_t||")
    if norm_clamp_c is not None:
        ax.axhline(y=norm_clamp_c, color="red", linestyle="--",
                    alpha=0.5, label=f"Clamp ceiling c={norm_clamp_c:.1f}")
    ax.set_xlabel("Token Position")
    ax.set_ylabel("||Psi||")
    ax.set_title(f"Psi Norm Trajectory {config_name}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"psi_trajectory_{config_name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_continuity_comparison(
    all_logs: Dict[str, List[Dict]],
    output_dir: str,
):
    """Plot emission continuity vs backbone continuity over training."""
    plt = _safe_import_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for name, logs in all_logs.items():
        steps = [l["step"] for l in logs if "psi_continuity" in l]
        psi_cont = [l["psi_continuity"] for l in logs if "psi_continuity" in l]
        h_cont = [l["backbone_continuity"] for l in logs if "backbone_continuity" in l]

        if steps and psi_cont:
            axes[0].plot(steps, psi_cont, label=f"{name} (Psi)", linewidth=1.0)
        if steps and h_cont:
            axes[1].plot(steps, h_cont, label=f"{name} (h)", linewidth=1.0)

    axes[0].set_title("Emission Continuity: cos(Psi_t, Psi_{t+1})")
    axes[0].set_xlabel("Step")
    axes[0].set_ylabel("Mean Cosine Similarity")
    axes[0].legend(fontsize=7)
    axes[0].grid(True, alpha=0.3)

    axes[1].set_title("Backbone Continuity: cos(h_t, h_{t+1})")
    axes[1].set_xlabel("Step")
    axes[1].set_ylabel("Mean Cosine Similarity")
    axes[1].legend(fontsize=7)
    axes[1].grid(True, alpha=0.3)

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "continuity_comparison.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_tau_evolution(
    all_logs: Dict[str, List[Dict]],
    output_dir: str,
):
    """Plot temperature tau evolution over training."""
    plt = _safe_import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 5))

    for name, logs in all_logs.items():
        steps = [l["step"] for l in logs if "tau" in l]
        taus = [l["tau"] for l in logs if "tau" in l]
        if steps:
            ax.plot(steps, taus, label=name, linewidth=1.5)

    ax.set_xlabel("Step")
    ax.set_ylabel("Temperature (tau)")
    ax.set_title("Emission Temperature Evolution")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0.1, color="red", linestyle=":", alpha=0.3, label="Danger low")
    ax.axhline(y=100, color="red", linestyle=":", alpha=0.3, label="Danger high")

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "tau_evolution.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_psi_norms_over_training(
    all_logs: Dict[str, List[Dict]],
    output_dir: str,
):
    """Plot mean and max Psi norms over training."""
    plt = _safe_import_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for name, logs in all_logs.items():
        steps = [l["step"] for l in logs if "mean_psi_norm" in l]
        mean_norms = [l["mean_psi_norm"] for l in logs if "mean_psi_norm" in l]
        max_norms = [l["max_psi_norm"] for l in logs if "max_psi_norm" in l]

        if steps and mean_norms:
            axes[0].plot(steps, mean_norms, label=name, linewidth=1.0)
        if steps and max_norms:
            axes[1].plot(steps, max_norms, label=name, linewidth=1.0)

    axes[0].set_title("Mean ||Psi|| Over Training")
    axes[0].set_xlabel("Step")
    axes[0].set_ylabel("Mean ||Psi||")
    axes[0].legend(fontsize=7)
    axes[0].grid(True, alpha=0.3)

    axes[1].set_title("Max ||Psi|| Over Training")
    axes[1].set_xlabel("Step")
    axes[1].set_ylabel("Max ||Psi||")
    axes[1].legend(fontsize=7)
    axes[1].grid(True, alpha=0.3)

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "psi_norms_training.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def generate_results_table(
    results: Dict[str, Dict[str, float]],
    output_dir: str,
) -> str:
    """
    Generate a markdown results table.

    Args:
        results: {config_name: {metric: value}}.
        output_dir: Where to save table.

    Returns:
        Markdown table string.
    """
    if not results:
        return "No results available."

    # Collect all metric names
    all_metrics = set()
    for config_results in results.values():
        all_metrics.update(config_results.keys())
    metrics = sorted(all_metrics)

    # Build markdown table
    header = "| Configuration | " + " | ".join(metrics) + " |"
    separator = "|" + "---|" * (len(metrics) + 1)

    rows = []
    for config_name, config_results in results.items():
        values = []
        for m in metrics:
            v = config_results.get(m, "N/A")
            if isinstance(v, float):
                if v > 100:
                    values.append(f"{v:.1f}")
                elif v > 1:
                    values.append(f"{v:.3f}")
                else:
                    values.append(f"{v:.4f}")
            else:
                values.append(str(v))
        row = f"| {config_name} | " + " | ".join(values) + " |"
        rows.append(row)

    table = "\n".join([header, separator] + rows)

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "results_table.md")
    with open(path, "w") as f:
        f.write("# Spanda v0.4 Experiment Results\n\n")
        f.write(table)
        f.write("\n")

    return table


def generate_all_plots(
    all_logs: Dict[str, List[Dict]],
    final_results: Dict[str, Dict[str, float]],
    output_dir: str,
):
    """Generate all standard plots from experiment logs."""
    paths = []

    # Training curves
    paths.append(plot_training_curves(all_logs, output_dir, "perplexity", "Training Perplexity"))

    # Spanda-specific plots (only for configs that have Spanda metrics)
    spanda_logs = {
        k: v for k, v in all_logs.items()
        if any("tau" in entry for entry in v)
    }

    if spanda_logs:
        paths.append(plot_continuity_comparison(spanda_logs, output_dir))
        paths.append(plot_tau_evolution(spanda_logs, output_dir))
        paths.append(plot_psi_norms_over_training(spanda_logs, output_dir))

    # Results table
    table = generate_results_table(final_results, output_dir)

    return paths, table
