#!/usr/bin/env python3
"""
Fusion Mapper Heatmap Generator
================================

Generates 2D heatmaps showing mapper-combined influence for FusionEngine
across the entropy-tension space.

The FusionEngine blends outputs from multiple mappers:
- HRM (High-Resolution Mapper): Provides detail-oriented, abstract insights
- LCM (Low-Context Mapper): Provides grounding, concrete facts
- LAM (Long-Arc Mapper): Provides long-arc, emotional context

Influence coloring (continuous blend):
- Blue channel: HRM influence (detail)
- Green channel: LCM influence (grounding)
- Red channel: LAM influence (long-arc)

The resulting color shows the balance of influences:
- Pure Blue: HRM-dominated (abstract reasoning)
- Pure Green: LCM-dominated (factual grounding)
- Pure Red: LAM-dominated (emotional/therapeutic)
- Cyan: HRM + LCM blend
- Magenta: HRM + LAM blend
- Yellow: LCM + LAM blend
- White: All three balanced
- Dark: Low activation

Generates heatmaps for 5 key domains:
- task, generic, therapy, identity, spiritual

Usage:
    python -m symbolu.tools.heatmaps.fusion_mapper_heatmap

Output:
    symbolu/symbolu/tools/heatmaps/output/fusion_heatmap_<domain>.png
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

# FusionEngine default channel weights
DEFAULT_WEIGHTS = {
    "hrm": 0.4,  # α - High-Reasoning weight
    "lcm": 0.3,  # β - Linguistic Coherence weight
    "lam": 0.3,  # LAM weight for long-arc
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def compute_mapper_strengths(
    tier: Tier,
    entropy: float,
    tension: float,
    domain: str,
) -> Tuple[float, float, float]:
    """
    Compute mapper activation strengths for FusionEngine.

    Instead of binary activation, we compute continuous strengths [0, 1]
    based on how far beyond thresholds the values are.

    Args:
        tier: Routing tier (LOWER/UPPER/HYBRID)
        entropy: Normalized entropy [0, 1]
        tension: Long-arc tension [0, 1]
        domain: Domain classification

    Returns:
        Tuple of (hrm_strength, lcm_strength, lam_strength)
    """
    # HRM strength: (tier != LOWER) and entropy > 0.40
    # Strength increases linearly from 0.40 to 1.0
    if tier != Tier.LOWER and entropy > HRM_ENTROPY_THRESHOLD:
        hrm_strength = min(1.0, (entropy - HRM_ENTROPY_THRESHOLD) / (1.0 - HRM_ENTROPY_THRESHOLD))
    else:
        # Small base strength if tier is not LOWER (can still contribute)
        hrm_strength = 0.1 if tier != Tier.LOWER else 0.0

    # LCM strength: (tier == LOWER) and entropy > 0.50
    # Strength increases linearly from 0.50 to 1.0
    if tier == Tier.LOWER and entropy > LCM_ENTROPY_THRESHOLD:
        lcm_strength = min(1.0, (entropy - LCM_ENTROPY_THRESHOLD) / (1.0 - LCM_ENTROPY_THRESHOLD))
    else:
        # Small base strength if tier is LOWER (can still contribute)
        lcm_strength = 0.1 if tier == Tier.LOWER else 0.0

    # LAM strength: tension > 0.50 OR (domain in LAM_DOMAINS and entropy > 0.60)
    lam_strength = 0.0

    # Tension-based LAM
    if tension > LAM_TENSION_THRESHOLD:
        lam_strength = max(lam_strength, (tension - LAM_TENSION_THRESHOLD) / (1.0 - LAM_TENSION_THRESHOLD))

    # Domain-based LAM
    if domain in LAM_DOMAINS and entropy > LAM_DOMAIN_ENTROPY_THRESHOLD:
        domain_lam = (entropy - LAM_DOMAIN_ENTROPY_THRESHOLD) / (1.0 - LAM_DOMAIN_ENTROPY_THRESHOLD)
        lam_strength = max(lam_strength, domain_lam)

    # LAM domains get a base boost
    if domain in LAM_DOMAINS:
        lam_strength = max(lam_strength, 0.2)

    return (hrm_strength, lcm_strength, lam_strength)


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


def compute_fusion_influence(
    hrm_strength: float,
    lcm_strength: float,
    lam_strength: float,
) -> Tuple[float, float, float]:
    """
    Compute weighted fusion influence for RGB coloring.

    Uses FusionEngine channel weights to determine final influence.

    Args:
        hrm_strength: HRM activation strength [0, 1]
        lcm_strength: LCM activation strength [0, 1]
        lam_strength: LAM activation strength [0, 1]

    Returns:
        Tuple of (r, g, b) values [0, 1] for coloring
    """
    # Apply channel weights
    hrm_influence = hrm_strength * DEFAULT_WEIGHTS["hrm"]
    lcm_influence = lcm_strength * DEFAULT_WEIGHTS["lcm"]
    lam_influence = lam_strength * DEFAULT_WEIGHTS["lam"]

    # Normalize to total influence
    total = hrm_influence + lcm_influence + lam_influence
    if total > 0:
        # Scale to preserve intensity
        scale = min(1.0, total / 0.4)  # 0.4 is max single channel

        # Map to RGB:
        # Red = LAM (long-arc, emotional)
        # Green = LCM (grounding, concrete)
        # Blue = HRM (detail, abstract)
        r = (lam_influence / total) * scale
        g = (lcm_influence / total) * scale
        b = (hrm_influence / total) * scale

        # Ensure minimum visibility
        min_value = 0.15
        r = max(min_value, r)
        g = max(min_value, g)
        b = max(min_value, b)
    else:
        # No influence - dark gray
        r, g, b = 0.2, 0.2, 0.2

    return (r, g, b)


def generate_heatmap_data(domain: str) -> np.ndarray:
    """
    Generate heatmap data for a specific domain.

    Creates a GRID_SIZE x GRID_SIZE array of RGB colors representing
    fusion influence across entropy-tension space.

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

            # Compute mapper strengths
            hrm_strength, lcm_strength, lam_strength = compute_mapper_strengths(
                tier=tier,
                entropy=entropy,
                tension=tension,
                domain=domain,
            )

            # Compute fusion influence colors
            r, g, b = compute_fusion_influence(hrm_strength, lcm_strength, lam_strength)

            # Note: tension is Y-axis (row), entropy is X-axis (column)
            # We flip Y so tension=0 is at bottom
            rgb_data[GRID_SIZE - 1 - i, j] = [r, g, b]

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
    # HRM threshold (vertical at entropy=0.40)
    ax.axvline(x=HRM_ENTROPY_THRESHOLD, color='white', linestyle='--', alpha=0.7, linewidth=1)
    ax.text(HRM_ENTROPY_THRESHOLD + 0.02, 0.95, 'HRM', color='white', fontsize=8,
            bbox=dict(boxstyle='round', facecolor='blue', alpha=0.5))

    # LCM threshold (vertical at entropy=0.50)
    ax.axvline(x=LCM_ENTROPY_THRESHOLD, color='white', linestyle='--', alpha=0.7, linewidth=1)
    ax.text(LCM_ENTROPY_THRESHOLD + 0.02, 0.85, 'LCM', color='white', fontsize=8,
            bbox=dict(boxstyle='round', facecolor='green', alpha=0.5))

    # LAM tension threshold (horizontal at tension=0.50)
    ax.axhline(y=LAM_TENSION_THRESHOLD, color='white', linestyle='--', alpha=0.7, linewidth=1)
    ax.text(0.02, LAM_TENSION_THRESHOLD + 0.02, 'LAM tension', color='white', fontsize=8,
            bbox=dict(boxstyle='round', facecolor='red', alpha=0.5))

    # LAM domain entropy threshold (if applicable)
    if domain in LAM_DOMAINS:
        ax.axvline(x=LAM_DOMAIN_ENTROPY_THRESHOLD, color='yellow', linestyle=':', alpha=0.7, linewidth=1)
        ax.text(LAM_DOMAIN_ENTROPY_THRESHOLD + 0.02, 0.75, 'LAM domain', color='yellow', fontsize=8)

    # Labels and title
    ax.set_xlabel('Normalized Entropy', fontsize=12)
    ax.set_ylabel('Long-Arc Tension', fontsize=12)
    ax.set_title(f'FusionEngine Mapper Influence - Domain: {domain.upper()}', fontsize=14)

    # Add legend explaining color channels
    legend_text = (
        "Color Channels:\n"
        "  Red = LAM (long-arc)\n"
        "  Green = LCM (grounding)\n"
        "  Blue = HRM (detail)"
    )
    ax.text(0.02, 0.02, legend_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='bottom',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Add influence legend
    legend_elements = [
        plt.Rectangle((0,0), 1, 1, facecolor='red', label='LAM dominant'),
        plt.Rectangle((0,0), 1, 1, facecolor='green', label='LCM dominant'),
        plt.Rectangle((0,0), 1, 1, facecolor='blue', label='HRM dominant'),
        plt.Rectangle((0,0), 1, 1, facecolor='magenta', label='HRM + LAM'),
        plt.Rectangle((0,0), 1, 1, facecolor='cyan', label='HRM + LCM'),
        plt.Rectangle((0,0), 1, 1, facecolor='yellow', label='LCM + LAM'),
        plt.Rectangle((0,0), 1, 1, facecolor='white', label='Balanced'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

    # Save figure
    output_path = OUTPUT_DIR / f"fusion_heatmap_{domain}.png"
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
        print(f"Generating fusion heatmap for domain: {domain}...")
        path = generate_heatmap(domain)
        paths.append(path)
        print(f"  Saved to: {path}")

    return paths


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point for fusion mapper heatmap generation."""
    print("=" * 60)
    print("FusionEngine Mapper Heatmap Generator")
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
