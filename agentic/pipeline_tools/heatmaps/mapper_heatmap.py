#!/usr/bin/env python3
"""
Mapper Heatmap Generator
========================

Developer tool for visualizing HRM/LCM/LAM activation zones across
the normalized_entropy × long_arc_tension parameter space.

Usage:
    python symbolu/tools/heatmaps/mapper_heatmap.py

Output:
    Saves heatmap images to symbolu/tools/heatmaps/output/

Canonical Mapper Rules v2.0:
- HRM: (tier != LOWER) and (normalized_entropy > 0.40)
- LCM: (tier == LOWER) and (normalized_entropy > 0.50)
- LAM: long_arc_tension > 0.50 OR temporal_patterns_detected
       OR (domain in ["therapy", "identity", "spiritual"] and normalized_entropy > 0.60)

The heatmaps provide a visual reference for understanding activation boundaries
and can be used for documentation, debugging, and design discussions.
"""

import os
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from typing import Tuple, List


# Canonical thresholds (frozen in v2.0 specification)
HRM_ENTROPY_THRESHOLD = 0.40
LCM_ENTROPY_THRESHOLD = 0.50
LAM_TENSION_THRESHOLD = 0.50
LAM_DOMAIN_ENTROPY_THRESHOLD = 0.60
LAM_DOMAINS = ["therapy", "identity", "spiritual"]


class Tier:
    """Tier enumeration for typing."""
    LOWER = "lower"
    UPPER = "upper"
    HYBRID = "hybrid"


def compute_mapper_for_point(
    tier: str,
    domain: str,
    entropy: float,
    tension: float,
) -> str:
    """
    Compute which mapper(s) are active for given parameters.

    Returns a string label representing the active mapper state:
    - "none" — No mappers active
    - "hrm" — HRM only
    - "lcm" — LCM only
    - "lam" — LAM only
    - "hrm+lam" — HRM and LAM (common for UPPER tier + high entropy + deep domain/tension)
    - "lcm+lam" — LCM and LAM (rare: LOWER tier + medium entropy + high tension)

    Args:
        tier: Tier classification (lower/upper/hybrid)
        domain: Domain classification
        entropy: Normalized entropy [0, 1]
        tension: Long-arc tension [0, 1]

    Returns:
        String label for mapper state
    """
    # Temporal patterns detection (not yet implemented)
    temporal_patterns_detected = False

    # Apply canonical formulas
    use_hrm = (tier != Tier.LOWER) and (entropy > HRM_ENTROPY_THRESHOLD)
    use_lcm = (tier == Tier.LOWER) and (entropy > LCM_ENTROPY_THRESHOLD)
    use_lam = (
        tension > LAM_TENSION_THRESHOLD
        or temporal_patterns_detected
        or (domain in LAM_DOMAINS and entropy > LAM_DOMAIN_ENTROPY_THRESHOLD)
    )

    # Encode mapper state as string
    if use_hrm and use_lam:
        return "hrm+lam"
    elif use_lcm and use_lam:
        return "lcm+lam"
    elif use_hrm:
        return "hrm"
    elif use_lcm:
        return "lcm"
    elif use_lam:
        return "lam"
    else:
        return "none"


def plot_heatmap_for_profile(
    tier: str,
    domain: str,
    resolution: int = 50,
    output_dir: str = "symbolu/tools/heatmaps/output",
) -> None:
    """
    Generate and save a heatmap for a given tier + domain profile.

    Args:
        tier: Tier classification (lower/upper/hybrid)
        domain: Domain classification
        resolution: Grid resolution (NxN grid)
        output_dir: Directory to save output images
    """
    # Create meshgrid for entropy and tension
    entropy_vals = np.linspace(0, 1, resolution)
    tension_vals = np.linspace(0, 1, resolution)
    E, T = np.meshgrid(entropy_vals, tension_vals)

    # Compute mapper state for each grid point
    # We'll encode states as integers for color mapping
    state_map = {
        "none": 0,
        "lcm": 1,
        "hrm": 2,
        "lam": 3,
        "lcm+lam": 4,
        "hrm+lam": 5,
    }

    Z = np.zeros_like(E, dtype=int)
    for i in range(resolution):
        for j in range(resolution):
            state = compute_mapper_for_point(
                tier=tier,
                domain=domain,
                entropy=E[i, j],
                tension=T[i, j],
            )
            Z[i, j] = state_map.get(state, 0)

    # Define colormap
    colors = [
        "#f0f0f0",  # 0: none (light gray)
        "#4a90e2",  # 1: lcm (blue)
        "#e24a4a",  # 2: hrm (red)
        "#50c878",  # 3: lam (green)
        "#9b59b6",  # 4: lcm+lam (purple)
        "#ff8c00",  # 5: hrm+lam (orange)
    ]
    cmap = ListedColormap(colors)

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot heatmap
    im = ax.imshow(
        Z,
        extent=[0, 1, 0, 1],
        origin="lower",
        aspect="auto",
        cmap=cmap,
        vmin=0,
        vmax=5,
        interpolation="nearest",
    )

    # Add canonical threshold lines
    # HRM threshold (vertical line at entropy = 0.40)
    if tier != Tier.LOWER:
        ax.axvline(x=HRM_ENTROPY_THRESHOLD, color="darkred", linestyle="--", linewidth=1.5, alpha=0.7, label="HRM threshold (0.40)")

    # LCM threshold (vertical line at entropy = 0.50)
    if tier == Tier.LOWER:
        ax.axvline(x=LCM_ENTROPY_THRESHOLD, color="darkblue", linestyle="--", linewidth=1.5, alpha=0.7, label="LCM threshold (0.50)")

    # LAM tension threshold (horizontal line at tension = 0.50)
    ax.axhline(y=LAM_TENSION_THRESHOLD, color="darkgreen", linestyle="--", linewidth=1.5, alpha=0.7, label="LAM tension threshold (0.50)")

    # LAM domain threshold (vertical line at entropy = 0.60) - only for deep domains
    if domain in LAM_DOMAINS:
        ax.axvline(x=LAM_DOMAIN_ENTROPY_THRESHOLD, color="darkgreen", linestyle=":", linewidth=1.5, alpha=0.7, label=f"LAM domain threshold (0.60)")

    # Labels and title
    ax.set_xlabel("Normalized Entropy", fontsize=12)
    ax.set_ylabel("Long-Arc Tension", fontsize=12)
    ax.set_title(f"Mapper Activation Zones: {tier.upper()} tier, {domain} domain", fontsize=14, fontweight="bold")

    # Legend
    ax.legend(loc="upper left", fontsize=9)

    # Colorbar with labels
    cbar = plt.colorbar(im, ax=ax, ticks=[0, 1, 2, 3, 4, 5])
    cbar.ax.set_yticklabels(["none", "lcm", "hrm", "lam", "lcm+lam", "hrm+lam"])
    cbar.set_label("Mapper State", fontsize=11)

    # Grid
    ax.grid(True, linestyle=":", alpha=0.3)

    # Save figure
    os.makedirs(output_dir, exist_ok=True)
    filename = f"heatmap_{tier}_{domain}.png"
    filepath = os.path.join(output_dir, filename)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"✓ Generated: {filepath}")


def generate_all_heatmaps(output_dir: str = "symbolu/tools/heatmaps/output") -> None:
    """
    Generate heatmaps for all key tier + domain profiles.

    Profiles:
    - LOWER + generic
    - LOWER + task
    - UPPER + therapy
    - UPPER + identity
    - UPPER + spiritual
    - UPPER + generic (for comparison)
    - HYBRID + generic (for comparison)
    """
    profiles = [
        (Tier.LOWER, "generic"),
        (Tier.LOWER, "task"),
        (Tier.UPPER, "therapy"),
        (Tier.UPPER, "identity"),
        (Tier.UPPER, "spiritual"),
        (Tier.UPPER, "generic"),
        (Tier.HYBRID, "generic"),
    ]

    print("Generating Mapper Activation Heatmaps")
    print("=" * 50)

    for tier, domain in profiles:
        print(f"Generating heatmap: {tier.upper()} tier, {domain} domain...")
        plot_heatmap_for_profile(tier, domain, resolution=100, output_dir=output_dir)

    print("=" * 50)
    print(f"All heatmaps saved to: {output_dir}")


def main():
    """Main entry point for heatmap generation."""
    import sys

    # Parse command-line arguments (optional)
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = "symbolu/tools/heatmaps/output"

    # Generate all heatmaps
    generate_all_heatmaps(output_dir=output_dir)

    print("\n✓ Heatmap generation complete!")
    print(f"\nView heatmaps at: {output_dir}/heatmap_*.png")


if __name__ == "__main__":
    main()
