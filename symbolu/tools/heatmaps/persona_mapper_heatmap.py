#!/usr/bin/env python3
"""
Persona Mapper Heatmap Generator
=================================

Generates 2D heatmaps showing which mapper (HRM/LCM/LAM) shapes
the PersonaEngine's initial interpretation across the entropy-tension space.

Color scheme:
- Blue (HRM): High-Resolution Mapper dominates (abstract/symbolic)
- Green (LCM): Low-Context Mapper dominates (concrete/semantic)
- Red (LAM): Long-Arc Mapper dominates (emotional/therapeutic)
- Purple (HRM+LAM): Both HRM and LAM active
- Cyan (LCM+LAM): Both LCM and LAM active
- Gray (None): No mapper active
- Yellow (Multiple): Three or more mappers active

Generates heatmaps for 5 key domains:
- task, generic, therapy, identity, spiritual

Usage:
    python -m symbolu.tools.heatmaps.persona_mapper_heatmap

Output:
    symbolu/symbolu/tools/heatmaps/output/persona_heatmap_<domain>.png
"""

import math
import os
from pathlib import Path
from typing import Dict, Tuple, List

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

from symbolu.mechanical.pipeline.ttor.models import Tier


# =============================================================================
# CONSTANTS
# =============================================================================

OUTPUT_DIR = Path(__file__).parent / "output"

# Canonical mapper thresholds (frozen in v2.0)
HRM_ENTROPY_THRESHOLD = 0.40
LCM_ENTROPY_THRESHOLD = 0.50
LAM_TENSION_THRESHOLD = 0.50
LAM_DOMAIN_ENTROPY_THRESHOLD = 0.60
LAM_DOMAINS = ["therapy", "identity", "spiritual"]

# Domains to generate heatmaps for
TARGET_DOMAINS = ["task", "generic", "therapy", "identity", "spiritual"]

# Grid resolution
GRID_SIZE = 100  # 100x100 grid points

# Color mapping for mapper combinations
# (HRM, LCM, LAM) -> color
COLOR_MAP = {
    (False, False, False): "#808080",  # Gray - None active
    (True, False, False): "#4169E1",   # Blue - HRM only
    (False, True, False): "#228B22",   # Green - LCM only
    (False, False, True): "#DC143C",   # Red - LAM only
    (True, False, True): "#9370DB",    # Purple - HRM + LAM
    (False, True, True): "#00CED1",    # Cyan - LCM + LAM
    (True, True, False): "#FFD700",    # Gold - HRM + LCM (rare)
    (True, True, True): "#FF8C00",     # Orange - All three
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def compute_mappers_for_persona(
    tier: Tier,
    entropy: float,
    tension: float,
    domain: str,
) -> Tuple[bool, bool, bool]:
    """
    Compute mapper activation flags for PersonaEngine using canonical rules.

    This mirrors TTOR's canonical mapper rules v2.0.

    Args:
        tier: Routing tier (LOWER/UPPER/HYBRID)
        entropy: Normalized entropy [0, 1]
        tension: Long-arc tension [0, 1]
        domain: Domain classification

    Returns:
        Tuple of (use_hrm, use_lcm, use_lam)
    """
    # HRM: (tier != LOWER) and (entropy > 0.40)
    use_hrm = (tier != Tier.LOWER) and (entropy > HRM_ENTROPY_THRESHOLD)

    # LCM: (tier == LOWER) and (entropy > 0.50)
    use_lcm = (tier == Tier.LOWER) and (entropy > LCM_ENTROPY_THRESHOLD)

    # LAM: tension > 0.50 OR (domain in LAM_DOMAINS and entropy > 0.60)
    use_lam = (
        tension > LAM_TENSION_THRESHOLD
        or (domain in LAM_DOMAINS and entropy > LAM_DOMAIN_ENTROPY_THRESHOLD)
    )

    return (use_hrm, use_lcm, use_lam)


def determine_tier_from_entropy(entropy: float, domain: str) -> Tier:
    """
    Heuristic to determine likely tier based on entropy and domain.

    For heatmap purposes, we use a simplified tier selection:
    - Low entropy (< 0.4) + task domains → LOWER
    - High entropy (> 0.6) + reflective domains → UPPER
    - Otherwise → HYBRID
    """
    task_domains = ["task", "code", "math", "lookup"]
    reflective_domains = ["therapy", "philosophy", "spiritual", "identity"]

    if entropy < 0.4 and domain in task_domains:
        return Tier.LOWER
    elif entropy > 0.6 and domain in reflective_domains:
        return Tier.UPPER
    elif entropy < 0.35:
        return Tier.LOWER
    elif entropy > 0.65:
        return Tier.UPPER
    else:
        return Tier.HYBRID


def get_mapper_color(use_hrm: bool, use_lcm: bool, use_lam: bool) -> str:
    """Get color for mapper combination."""
    return COLOR_MAP.get((use_hrm, use_lcm, use_lam), "#808080")


def generate_heatmap_data(domain: str) -> np.ndarray:
    """
    Generate heatmap data for a specific domain.

    Creates a GRID_SIZE x GRID_SIZE array of RGB colors representing
    mapper activations across entropy-tension space.

    Args:
        domain: Domain to generate heatmap for

    Returns:
        RGB array of shape (GRID_SIZE, GRID_SIZE, 3)
    """
    entropy_values = np.linspace(0, 1, GRID_SIZE)
    tension_values = np.linspace(0, 1, GRID_SIZE)

    # Initialize RGB array
    rgb_data = np.zeros((GRID_SIZE, GRID_SIZE, 3))

    for i, tension in enumerate(tension_values):
        for j, entropy in enumerate(entropy_values):
            # Determine tier based on entropy and domain
            tier = determine_tier_from_entropy(entropy, domain)

            # Compute mapper flags
            use_hrm, use_lcm, use_lam = compute_mappers_for_persona(
                tier=tier,
                entropy=entropy,
                tension=tension,
                domain=domain,
            )

            # Get color
            color_hex = get_mapper_color(use_hrm, use_lcm, use_lam)
            rgb = mcolors.to_rgb(color_hex)

            # Note: tension is Y-axis (row), entropy is X-axis (column)
            # We flip Y so tension=0 is at bottom
            rgb_data[GRID_SIZE - 1 - i, j] = rgb

    return rgb_data


def generate_heatmap(domain: str) -> str:
    """
    Generate and save heatmap for a specific domain.

    Args:
        domain: Domain to generate heatmap for

    Returns:
        Path to saved image file
    """
    # Generate data
    rgb_data = generate_heatmap_data(domain)

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot heatmap
    ax.imshow(rgb_data, extent=[0, 1, 0, 1], aspect='auto', origin='lower')

    # Add threshold lines
    # HRM threshold (horizontal at entropy=0.40)
    ax.axvline(x=HRM_ENTROPY_THRESHOLD, color='blue', linestyle='--', alpha=0.5, linewidth=1)
    ax.text(HRM_ENTROPY_THRESHOLD + 0.02, 0.95, 'HRM threshold', color='blue', fontsize=8)

    # LCM threshold (horizontal at entropy=0.50)
    ax.axvline(x=LCM_ENTROPY_THRESHOLD, color='green', linestyle='--', alpha=0.5, linewidth=1)
    ax.text(LCM_ENTROPY_THRESHOLD + 0.02, 0.85, 'LCM threshold', color='green', fontsize=8)

    # LAM tension threshold (vertical at tension=0.50)
    ax.axhline(y=LAM_TENSION_THRESHOLD, color='red', linestyle='--', alpha=0.5, linewidth=1)
    ax.text(0.02, LAM_TENSION_THRESHOLD + 0.02, 'LAM tension', color='red', fontsize=8)

    # LAM domain entropy threshold (if applicable)
    if domain in LAM_DOMAINS:
        ax.axvline(x=LAM_DOMAIN_ENTROPY_THRESHOLD, color='darkred', linestyle=':', alpha=0.5, linewidth=1)
        ax.text(LAM_DOMAIN_ENTROPY_THRESHOLD + 0.02, 0.75, 'LAM domain', color='darkred', fontsize=8)

    # Labels and title
    ax.set_xlabel('Normalized Entropy', fontsize=12)
    ax.set_ylabel('Long-Arc Tension', fontsize=12)
    ax.set_title(f'PersonaEngine Mapper Activation - Domain: {domain.upper()}', fontsize=14)

    # Add legend
    legend_elements = [
        plt.Rectangle((0,0), 1, 1, facecolor='#4169E1', label='HRM (abstract)'),
        plt.Rectangle((0,0), 1, 1, facecolor='#228B22', label='LCM (concrete)'),
        plt.Rectangle((0,0), 1, 1, facecolor='#DC143C', label='LAM (emotional)'),
        plt.Rectangle((0,0), 1, 1, facecolor='#9370DB', label='HRM + LAM'),
        plt.Rectangle((0,0), 1, 1, facecolor='#00CED1', label='LCM + LAM'),
        plt.Rectangle((0,0), 1, 1, facecolor='#808080', label='None'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

    # Save figure
    output_path = OUTPUT_DIR / f"persona_heatmap_{domain}.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return str(output_path)


def generate_all_heatmaps() -> List[str]:
    """
    Generate heatmaps for all target domains.

    Returns:
        List of paths to saved image files
    """
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    paths = []
    for domain in TARGET_DOMAINS:
        print(f"Generating persona heatmap for domain: {domain}...")
        path = generate_heatmap(domain)
        paths.append(path)
        print(f"  Saved to: {path}")

    return paths


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point for persona mapper heatmap generation."""
    print("=" * 60)
    print("PersonaEngine Mapper Heatmap Generator")
    print("=" * 60)
    print()

    paths = generate_all_heatmaps()

    print()
    print(f"Generated {len(paths)} heatmaps:")
    for path in paths:
        print(f"  - {path}")
    print()
    print("Done!")


if __name__ == "__main__":
    main()
