"""
Part 6 — Layer Trajectory Mapping
====================================

Plot the causal efficacy of the structural subspace across all layers.

For each layer L:
    1. Build the structural subspace basis U_k^L from that layer's hidden states.
    2. Run the MDL probe → compression ratio.
    3. Run causal interventions → success rate.

This produces a trajectory that reveals:
    - The **crystallization layer**: where the structural invariant first
      emerges (compression ratio spikes).
    - The **consumption layer**: where the invariant is consumed/dissolved
      by subsequent MLPs (compression ratio drops).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class LayerTrajectory:
    """Full trajectory of structural subspace strength across layers."""

    n_layers: int = 0
    label_name: str = ""

    # Per-layer metrics
    layers: List[int] = field(default_factory=list)
    mdl_compression: List[float] = field(default_factory=list)
    mdl_bits_per_label: List[float] = field(default_factory=list)
    causal_success_rate: List[float] = field(default_factory=list)
    causal_flip_rate: List[float] = field(default_factory=list)
    causal_fluency_rate: List[float] = field(default_factory=list)
    pca_cumvar_at_k: List[float] = field(default_factory=list)

    # Summary
    crystallization_layer: int = -1
    consumption_layer: int = -1
    peak_compression: float = 0.0
    peak_causal_success: float = 0.0


# ---------------------------------------------------------------------------
# Trajectory computation
# ---------------------------------------------------------------------------

def compute_layer_trajectory(
    hidden_states: Dict[int, np.ndarray],
    labels: np.ndarray,
    label_name: str,
    model=None,
    tokenizer=None,
    subspace_k: int = 16,
    mdl_cfg=None,
    intervention_cfg=None,
    run_interventions: bool = True,
    precomputed_mdl: Optional[Dict[int, "MDLProbeResult"]] = None,
) -> LayerTrajectory:
    """Compute the structural subspace trajectory across all layers.

    Parameters
    ----------
    hidden_states : dict[int, np.ndarray]
        Per-layer hidden states, each [N, d].
    labels : np.ndarray [N]
        Structural labels (integer).
    label_name : str
    model : nn.Module (optional, required for causal interventions)
    tokenizer : optional (required for causal interventions)
    subspace_k : int
        Subspace dimensionality.
    mdl_cfg : MDLProbeConfig (optional)
    intervention_cfg : InterventionConfig (optional)
    run_interventions : bool
        Whether to also run causal interventions per layer.
    precomputed_mdl : dict[int, MDLProbeResult] (optional)
        If provided, reuse these MDL results instead of recomputing.

    Returns
    -------
    LayerTrajectory
    """
    from scripts.causal_subspace.mdl_probing import MDLProbeConfig, MDLProbeResult, run_mdl_probe
    from scripts.causal_subspace.causal_intervention import (
        InterventionConfig,
        build_subspace_basis,
        run_causal_intervention,
    )
    from scripts.causal_subspace.disentanglement import compute_pca_baseline

    if mdl_cfg is None:
        mdl_cfg = MDLProbeConfig()
    if intervention_cfg is None:
        intervention_cfg = InterventionConfig()

    n_layers = len(hidden_states)
    trajectory = LayerTrajectory(n_layers=n_layers, label_name=label_name)

    logger.info(
        "Computing layer trajectory for '%s' across %d layers (k=%d)",
        label_name, n_layers, subspace_k,
    )

    for layer_idx in sorted(hidden_states.keys()):
        H = hidden_states[layer_idx]
        logger.info("--- Layer %d ---", layer_idx)

        trajectory.layers.append(layer_idx)

        # PCA cumulative variance at k
        _, cumvar, _ = compute_pca_baseline(H, subspace_k)
        trajectory.pca_cumvar_at_k.append(float(cumvar[-1]) if len(cumvar) > 0 else 0.0)

        # MDL probe — reuse precomputed results if available
        if precomputed_mdl is not None and layer_idx in precomputed_mdl:
            mdl_result = precomputed_mdl[layer_idx]
            logger.info("  Reusing precomputed MDL result for layer %d", layer_idx)
        else:
            mdl_result = run_mdl_probe(H, labels, layer_idx, label_name, mdl_cfg)
        trajectory.mdl_compression.append(mdl_result.compression_ratio)
        trajectory.mdl_bits_per_label.append(
            mdl_result.online_code_length / max(mdl_result.n_samples, 1)
        )

        # Causal intervention (optional, expensive)
        if run_interventions and model is not None and tokenizer is not None:
            U_k = build_subspace_basis(H, labels, subspace_k)
            intervention_result = run_causal_intervention(
                model, tokenizer, U_k, layer_idx, intervention_cfg,
            )
            trajectory.causal_success_rate.append(
                intervention_result.causal_success_rate
            )
            trajectory.causal_flip_rate.append(intervention_result.flip_rate)
            trajectory.causal_fluency_rate.append(intervention_result.fluency_rate)
        else:
            trajectory.causal_success_rate.append(0.0)
            trajectory.causal_flip_rate.append(0.0)
            trajectory.causal_fluency_rate.append(0.0)

    # Identify crystallization and consumption layers
    if trajectory.mdl_compression:
        peak_idx = int(np.argmax(trajectory.mdl_compression))
        trajectory.crystallization_layer = trajectory.layers[peak_idx]
        trajectory.peak_compression = trajectory.mdl_compression[peak_idx]

        # Consumption: first layer after peak where compression drops below
        # 80% of peak
        threshold = trajectory.peak_compression * 0.8
        for i in range(peak_idx + 1, len(trajectory.mdl_compression)):
            if trajectory.mdl_compression[i] < threshold:
                trajectory.consumption_layer = trajectory.layers[i]
                break

    if trajectory.causal_success_rate:
        trajectory.peak_causal_success = max(trajectory.causal_success_rate)

    logger.info(
        "Trajectory for '%s': crystallization=L%d (compression=%.2fx), "
        "consumption=L%d, peak_causal=%.1f%%",
        label_name,
        trajectory.crystallization_layer,
        trajectory.peak_compression,
        trajectory.consumption_layer,
        trajectory.peak_causal_success * 100,
    )

    return trajectory


# ---------------------------------------------------------------------------
# ASCII trajectory plot
# ---------------------------------------------------------------------------

def plot_trajectory_ascii(traj: LayerTrajectory) -> str:
    """Render the trajectory as an ASCII chart for console output."""
    lines = []
    lines.append(f"Layer Trajectory: {traj.label_name}")
    lines.append("=" * 70)

    if not traj.layers:
        lines.append("  (no data)")
        return "\n".join(lines)

    # Header
    lines.append(
        f"{'Layer':>6} | {'MDL Compr':>10} | {'bits/label':>10} | "
        f"{'Causal %':>9} | {'PCA cumvar':>10} | {'Vis':>20}"
    )
    lines.append("-" * 75)

    max_compression = max(traj.mdl_compression) if traj.mdl_compression else 1.0

    for i, layer in enumerate(traj.layers):
        comp = traj.mdl_compression[i] if i < len(traj.mdl_compression) else 0.0
        bpl = traj.mdl_bits_per_label[i] if i < len(traj.mdl_bits_per_label) else 0.0
        causal = traj.causal_success_rate[i] if i < len(traj.causal_success_rate) else 0.0
        cumvar = traj.pca_cumvar_at_k[i] if i < len(traj.pca_cumvar_at_k) else 0.0

        # ASCII bar
        bar_len = int(20 * comp / max(max_compression, 1e-10))
        bar = "█" * bar_len + "░" * (20 - bar_len)

        marker = ""
        if layer == traj.crystallization_layer:
            marker = " ← CRYSTALLIZATION"
        elif layer == traj.consumption_layer:
            marker = " ← CONSUMPTION"

        lines.append(
            f"  L{layer:>3} | {comp:>10.2f}x | {bpl:>10.3f} | "
            f"{causal * 100:>8.1f}% | {cumvar:>10.3f} | {bar}{marker}"
        )

    lines.append("-" * 75)
    lines.append(
        f"Crystallization: Layer {traj.crystallization_layer} "
        f"(compression = {traj.peak_compression:.2f}x)"
    )
    lines.append(
        f"Consumption:     Layer {traj.consumption_layer}"
    )
    lines.append(
        f"Peak causal:     {traj.peak_causal_success * 100:.1f}%"
    )

    return "\n".join(lines)
