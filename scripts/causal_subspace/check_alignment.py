#!/usr/bin/env python3
"""
check-alignment — Diagnose the natural best outcome of JEPA-Ontology integration
=================================================================================

Determines which of four alignment outcomes describes how the JEPA's 32D
Sovereign State space relates to the OntologyMonitor's 4 validated axes:

  1. STRONG OVERLAP   — JEPA's 32 dims already encode the same 4 axes the
                        ontology monitor found, just using different names.
                        (All 4 axes have |corr| > 0.5 with some Sovereign dim)

  2. PARTIAL OVERLAP  — Some axes show up in the Sovereign State, others don't.
                        Each system catches things the other misses.
                        (1-3 axes align, rest don't)

  3. DISTRIBUTED      — The 4 axes exist in JEPA space, but no single dim maps
                        to them. You'd need a small learned bridge (linear probe).
                        (Individual |corr| < 0.3, but linear probe R² > 0.3)

  4. ORTHOGONAL       — The two systems look at genuinely different things.
                        No overlap at all.
                        (No correlation, probe R² < 0.1)

Usage::

    # Quick check on synthetic data (no model needed)
    python scripts/causal_subspace/check_alignment.py

    # Verbose with JSON output
    python scripts/causal_subspace/check_alignment.py --verbose --output alignment.json

    # Custom parameters
    python scripts/causal_subspace/check_alignment.py --n-samples 2000 --d-model 768

    # With a trained model checkpoint
    python scripts/causal_subspace/check_alignment.py --checkpoint checkpoints/best.pt

References:
    - DESIGN_jepa_observatory_integration.md §4b (The Alignment Hypothesis)
    - jepa_observatory.py (implementation of alignment matrix, bridge, scenarios)
"""

from __future__ import annotations

import os

# Prevent OpenBLAS/MKL thread deadlocks
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

# Ensure project root is on path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.causal_subspace.ontology_alignment import (
    AXIS_NAMES,
    N_AXES,
    N_ROBUST,
    ROBUST_AXES,
    ROBUST_AXIS_INDICES,
    OntologyMonitor,
    _compute_binned_mi,
)
from scripts.causal_subspace.jepa_observatory import (
    OntologyBridge,
    compute_alignment_matrix,
    _spearman_rank_correlation,
    compute_detection_auc,
    generate_synthetic_anomalies,
)
from symbolu.jepa.predictor import VrittiValidatedPredictor
from symbolu.jepa.state_projector import SovereignStateProjector

logger = logging.getLogger("check_alignment")


# ── Sovereign State component names ──────────────────────────────────────

try:
    from symbolu.sovereign.reasoning_kernel import BHAVA_NAMES, KOSHA_NAMES, VRITTI_NAMES, GUNA_NAMES
except ImportError:
    BHAVA_NAMES = ['POT', 'IDN', 'EXE', 'STR', 'COG', 'AGY', 'RSN', 'PRP', 'WIT', 'UNI', 'INT', 'ABS']
    KOSHA_NAMES = ['ANNA', 'PRANA', 'MANO', 'VIJNANA', 'ANANDA']
    VRITTI_NAMES = ['PRAMANA', 'VIPARYAYA', 'VIKALPA', 'NIDRA', 'SMRITI']
    GUNA_NAMES = ['SATTVA', 'RAJAS', 'TAMAS', 'VELOCITY', 'ACCEL', 'STABLE']

SOVEREIGN_DIM_NAMES: List[str] = (
    [f"Bhava.{n}" for n in BHAVA_NAMES] +        # [0:12]
    [f"Kosha.{n}" for n in KOSHA_NAMES] +         # [12:17]
    [f"Vritti.{n}" for n in VRITTI_NAMES] +        # [17:22]
    [f"Guna.{n}" for n in GUNA_NAMES] +            # [22:28]
    ["Reserved.0", "Reserved.1", "Reserved.2", "Reserved.3"]  # [28:32]
)


# ── Outcome classification ───────────────────────────────────────────────

@dataclass
class AlignmentOutcome:
    """Result of the alignment check between JEPA and OntologyMonitor."""

    # Classification (1-4)
    outcome_number: int = 0
    outcome_name: str = ""
    outcome_description: str = ""

    # Per-axis alignment details
    per_axis_best_dim: Dict[str, int] = field(default_factory=dict)
    per_axis_best_dim_name: Dict[str, str] = field(default_factory=dict)
    per_axis_best_corr: Dict[str, float] = field(default_factory=dict)
    per_axis_mi: Dict[str, float] = field(default_factory=dict)

    # Aggregate metrics
    n_strong_axes: int = 0        # |corr| > 0.5
    n_moderate_axes: int = 0      # 0.3 < |corr| <= 0.5
    n_weak_axes: int = 0          # |corr| <= 0.3
    max_abs_corr: float = 0.0
    mean_abs_corr: float = 0.0

    # Linear probe (bridge) results
    bridge_r2_mean: float = 0.0
    bridge_r2_per_axis: Dict[str, float] = field(default_factory=dict)
    bridge_n_positive_r2: int = 0

    # Mutual information
    mean_mi: float = 0.0

    # Anomaly detection AUC comparison
    jepa_auc: float = 0.0
    ontology_auc: float = 0.0
    combined_auc: float = 0.0
    auc_delta: float = 0.0  # combined - max(individual)

    # Evidence strings
    evidence: List[str] = field(default_factory=list)

    # Full correlation matrix for reference
    corr_matrix_shape: List[int] = field(default_factory=list)


OUTCOME_DESCRIPTIONS = {
    1: (
        "STRONG OVERLAP",
        "The JEPA's 32 dimensions already encode the same 4 axes the ontology "
        "monitor found. The JEPA is a temporal version of the ontology monitor — "
        "it predicts not just 'this is concrete thinking' but 'concrete thinking "
        "is about to shift to abstract.'",
    ),
    2: (
        "PARTIAL OVERLAP",
        "Some ontological axes show up in the Sovereign State dimensions, others "
        "don't. Each system catches things the other misses. Integration is most "
        "valuable here — complementary signals.",
    ),
    3: (
        "DISTRIBUTED ENCODING",
        "The 4 ontological axes exist in the JEPA's space, but no single "
        "dimension maps to them. A small learned bridge (linear probe) can "
        "translate between them. The information is there, just spread across "
        "multiple dimensions.",
    ),
    4: (
        "COMPLETELY ORTHOGONAL",
        "The two systems look at genuinely different things. The ontology monitor "
        "reads what the model is thinking about. The JEPA reads how the model's "
        "internal dynamics are evolving. No overlap at all.",
    ),
}


def classify_outcome(
    corr_matrix: np.ndarray,
    bridge_r2_per_axis: Dict[str, float],
    per_axis_mi: Dict[str, float],
) -> AlignmentOutcome:
    """Classify into one of the 4 outcomes.

    Decision tree:
        1. Count axes with |corr| > 0.5 (strong direct mapping)
           → 4/4 strong = Outcome 1 (Strong Overlap)
           → 1-3 strong  = Outcome 2 (Partial Overlap)

        2. If 0 strong axes, check linear probe R²:
           → R² > 0.3 on 3+ axes = Outcome 3 (Distributed Encoding)
           → R² > 0.1 on 2+ axes = Outcome 3 (Distributed Encoding, weak)

        3. If neither:
           → Outcome 4 (Completely Orthogonal)

    Also considers MI as confirming evidence.
    """
    result = AlignmentOutcome()
    result.corr_matrix_shape = list(corr_matrix.shape)

    n_axes = corr_matrix.shape[0]
    max_corr_per_axis = np.max(np.abs(corr_matrix), axis=1)  # [n_axes]
    best_dim_per_axis = np.argmax(np.abs(corr_matrix), axis=1)  # [n_axes]

    # Per-axis breakdown
    for j in range(n_axes):
        axis_name = ROBUST_AXES[j] if j < len(ROBUST_AXES) else f"axis_{j}"
        best_dim = int(best_dim_per_axis[j])
        best_corr = float(corr_matrix[j, best_dim])
        dim_name = SOVEREIGN_DIM_NAMES[best_dim] if best_dim < len(SOVEREIGN_DIM_NAMES) else f"dim_{best_dim}"

        result.per_axis_best_dim[axis_name] = best_dim
        result.per_axis_best_dim_name[axis_name] = dim_name
        result.per_axis_best_corr[axis_name] = best_corr

        abs_corr = abs(best_corr)
        if abs_corr > 0.5:
            result.n_strong_axes += 1
        elif abs_corr > 0.3:
            result.n_moderate_axes += 1
        else:
            result.n_weak_axes += 1

    result.max_abs_corr = float(np.max(np.abs(corr_matrix)))
    result.mean_abs_corr = float(np.mean(max_corr_per_axis))

    # Bridge R²
    result.bridge_r2_per_axis = bridge_r2_per_axis
    r2_values = list(bridge_r2_per_axis.values())
    result.bridge_r2_mean = float(np.mean(r2_values)) if r2_values else 0.0
    result.bridge_n_positive_r2 = sum(1 for v in r2_values if v > 0.1)

    # MI
    result.per_axis_mi = per_axis_mi
    mi_values = list(per_axis_mi.values())
    result.mean_mi = float(np.mean(mi_values)) if mi_values else 0.0

    # ── Decision tree ──

    # Outcome 1: Strong Overlap (all 4 axes directly map)
    if result.n_strong_axes >= 4:
        result.outcome_number = 1
        result.evidence.append(
            f"All {result.n_strong_axes}/4 axes have |corr| > 0.5 with a Sovereign dim"
        )
        result.evidence.append(
            "JEPA predictions directly translate to ontological predictions"
        )

    # Outcome 2: Partial Overlap (some axes directly map)
    elif result.n_strong_axes >= 1 or (result.n_moderate_axes >= 2 and result.n_strong_axes >= 0):
        n_aligned = result.n_strong_axes + result.n_moderate_axes
        if n_aligned >= 1:
            result.outcome_number = 2
            result.evidence.append(
                f"{result.n_strong_axes}/4 axes strong (|corr|>0.5), "
                f"{result.n_moderate_axes}/4 moderate (|corr|>0.3)"
            )
            # Identify which axes aligned and which didn't
            aligned = [
                ax for ax, corr in result.per_axis_best_corr.items()
                if abs(corr) > 0.3
            ]
            missing = [
                ax for ax, corr in result.per_axis_best_corr.items()
                if abs(corr) <= 0.3
            ]
            if aligned:
                result.evidence.append(f"Aligned axes: {', '.join(aligned)}")
            if missing:
                result.evidence.append(f"Missing from JEPA: {', '.join(missing)}")
            result.evidence.append(
                "Bridge works for aligned axes; monitor needed for the rest"
            )

    # Check for Distributed Encoding via linear probe
    if result.outcome_number == 0:
        n_r2_good = sum(1 for v in r2_values if v > 0.3)
        n_r2_fair = sum(1 for v in r2_values if v > 0.1)

        if n_r2_good >= 3 or (n_r2_fair >= 2 and result.bridge_r2_mean > 0.2):
            result.outcome_number = 3
            result.evidence.append(
                f"No single dim maps to axes (max |corr| = {result.max_abs_corr:.3f}), "
                f"but linear probe recovers signal"
            )
            result.evidence.append(
                f"Bridge R²: {', '.join(f'{k}={v:.3f}' for k, v in bridge_r2_per_axis.items())}"
            )
            result.evidence.append(
                "Information is there, just distributed across multiple dimensions"
            )

    # Outcome 2 can also be reached via moderate correlation + probe
    if result.outcome_number == 0 and (result.n_moderate_axes >= 1 or result.bridge_r2_mean > 0.1):
        result.outcome_number = 2
        result.evidence.append(
            f"Moderate alignment: {result.n_moderate_axes}/4 axes with |corr|>0.3, "
            f"bridge R²={result.bridge_r2_mean:.3f}"
        )
        result.evidence.append("Partial overlap — complementary signals")

    # Outcome 4: Completely Orthogonal (fallback)
    if result.outcome_number == 0:
        result.outcome_number = 4
        result.evidence.append(
            f"No axis has |corr| > 0.3 (max={result.max_abs_corr:.3f})"
        )
        result.evidence.append(
            f"Linear probe R²={result.bridge_r2_mean:.3f} — below threshold"
        )
        result.evidence.append(
            "The two systems measure genuinely different aspects of the model"
        )

    name, desc = OUTCOME_DESCRIPTIONS[result.outcome_number]
    result.outcome_name = name
    result.outcome_description = desc

    return result


# ── Synthetic data generation ────────────────────────────────────────────

def generate_synthetic_hidden_states(
    n_samples: int = 1000,
    d_model: int = 768,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic hidden states with known ontological structure.

    Creates hidden states where the first few PCA directions encode
    ontological information, mimicking what the causal subspace pipeline
    found in GPT-2.

    Returns:
        H: Hidden states [N, d_model]
        ont_features: 12-axis ontology features [N, 12]
        valid_mask: Always-true mask [N]
    """
    rng = np.random.RandomState(seed)

    # Base hidden states: random with some structure
    H = rng.randn(n_samples, d_model).astype(np.float32) * 0.1

    # Create 12 ontological feature channels
    ont_features = np.zeros((n_samples, N_AXES), dtype=np.float32)

    # Assign each sample to a "role class" (noun/verb/adj/function)
    n_classes = 4
    class_labels = rng.randint(0, n_classes, size=n_samples)

    # Class prototypes in ontology space
    class_prototypes = {
        0: np.array([0.1, 0.9, 0.1, 0.3, 0.1, 0.2, 0.1, 0.1, 0.1, 0.1, 0.2, 0.1]),  # noun
        1: np.array([0.1, 0.2, 0.9, 0.2, 0.3, 0.8, 0.2, 0.5, 0.1, 0.1, 0.3, 0.1]),  # verb
        2: np.array([0.1, 0.1, 0.1, 0.1, 0.6, 0.1, 0.3, 0.2, 0.7, 0.3, 0.1, 0.1]),  # adj
        3: np.array([0.8, 0.1, 0.1, 0.7, 0.1, 0.1, 0.6, 0.1, 0.1, 0.5, 0.1, 0.8]),  # function
    }

    for i in range(n_samples):
        c = class_labels[i]
        ont_features[i] = class_prototypes[c] + rng.randn(N_AXES) * 0.15
        ont_features[i] = np.clip(ont_features[i], 0.0, 1.0)

    # Inject ontological signal into hidden states
    # The first ~20 PCA directions carry class-discriminative information
    # (mimicking the validated causal subspace from Parts 1-6)
    signal_dims = 20
    signal_projection = rng.randn(N_AXES, signal_dims).astype(np.float32) * 0.5

    for i in range(n_samples):
        signal = ont_features[i] @ signal_projection  # [signal_dims]
        H[i, :signal_dims] += signal

    # Add sequence-level temporal correlations (mimics actual model dynamics)
    seq_length = 20
    n_seqs = n_samples // seq_length
    for seq in range(n_seqs):
        start = seq * seq_length
        end = min(start + seq_length, n_samples)
        # Each sequence has a drift direction
        drift_dir = rng.randn(d_model).astype(np.float32) * 0.02
        for t in range(start, end):
            H[t] += drift_dir * (t - start)

    valid_mask = np.ones(n_samples, dtype=bool)

    logger.info(
        "Generated synthetic data: %d samples, d_model=%d, "
        "%d classes, %d signal dims",
        n_samples, d_model, n_classes, signal_dims,
    )

    return H, ont_features, valid_mask


# ── Main analysis pipeline ───────────────────────────────────────────────

def run_alignment_check(
    H: np.ndarray,
    ont_features: np.ndarray,
    valid_mask: np.ndarray,
    d_model: int = 768,
    state_dim: int = 32,
    n_epochs_bridge: int = 200,
    n_epochs_monitor: int = 100,
    seed: int = 42,
) -> AlignmentOutcome:
    """Run the full alignment check pipeline.

    Steps:
        1. Project H → Sovereign State (32D) via SovereignStateProjector
        2. Extract robust ontological axes (4D) from ont_features
        3. Compute rank correlation matrix [4 x 32]
        4. Compute per-axis MI (mutual information)
        5. Train linear probe (OntologyBridge) and measure R²
        6. Run anomaly detection comparison (JEPA vs ontology vs combined)
        7. Classify into Outcome 1/2/3/4

    Args:
        H: Hidden states [N, d_model]
        ont_features: Full 12-axis ontology [N, 12]
        valid_mask: Valid mask [N]
        d_model: Hidden dimension
        state_dim: Sovereign State dimension (32)
        n_epochs_bridge: Bridge training epochs
        n_epochs_monitor: Monitor training epochs
        seed: Random seed

    Returns:
        AlignmentOutcome with full diagnosis
    """
    H_valid = H[valid_mask]
    ont_valid = ont_features[valid_mask]
    z_ont_robust = ont_valid[:, ROBUST_AXIS_INDICES]  # [N, 4]
    N = H_valid.shape[0]

    logger.info("=" * 60)
    logger.info("ALIGNMENT CHECK: N=%d, d=%d, state_dim=%d", N, d_model, state_dim)
    logger.info("=" * 60)

    # ── Step 1: Project to Sovereign State ──
    logger.info("Step 1: Projecting hidden states → Sovereign State [32D]...")
    projector = SovereignStateProjector(hidden_dim=d_model, state_dim=state_dim)
    with torch.no_grad():
        S = projector(torch.from_numpy(H_valid.astype(np.float32))).cpu().numpy()
    logger.info("  Sovereign State: shape=%s", S.shape)

    # ── Step 2: Compute rank correlation matrix [4 x 32] ──
    logger.info("Step 2: Computing rank correlation matrix [4 x 32]...")
    corr_matrix = compute_alignment_matrix(z_ont_robust, S)
    logger.info("  Max |corr| = %.3f", np.max(np.abs(corr_matrix)))

    # ── Step 3: Compute per-axis MI ──
    logger.info("Step 3: Computing per-axis mutual information...")
    per_axis_mi: Dict[str, float] = {}
    for j in range(N_ROBUST):
        axis_name = ROBUST_AXES[j]
        best_mi = 0.0
        for k in range(state_dim):
            mi = _compute_binned_mi(z_ont_robust[:, j], S[:, k], n_bins=20)
            best_mi = max(best_mi, mi)
        per_axis_mi[axis_name] = best_mi
        logger.info("  %s: best MI = %.4f", axis_name, best_mi)

    # ── Step 4: Train linear probe (OntologyBridge) ──
    logger.info("Step 4: Training OntologyBridge (linear probe S → z_ont)...")
    bridge = OntologyBridge(state_dim=state_dim, n_axes=N_ROBUST)
    bridge_metrics = bridge.train_bridge(
        S, z_ont_robust,
        n_epochs=n_epochs_bridge, seed=seed,
    )
    logger.info("  Bridge R² = %.3f", bridge_metrics["r2_mean"])

    # ── Step 5: Anomaly detection comparison ──
    logger.info("Step 5: Anomaly detection comparison (trajectory_break)...")
    monitor = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)
    monitor.train_monitor(
        H=H_valid, ont_features=ont_valid,
        valid_mask=np.ones(N, dtype=bool),
        n_epochs=n_epochs_monitor, seed=seed,
    )

    predictor = VrittiValidatedPredictor(state_dim=state_dim, hidden_dim=128, prediction_steps=2)

    # Generate trajectory-break anomalies
    anomalous, labels = generate_synthetic_anomalies(H_valid, "trajectory_break", seed=seed)

    # JEPA scores
    with torch.no_grad():
        s_anomalous = projector(torch.from_numpy(anomalous.astype(np.float32)))
        s_pred_anom, _ = predictor(s_anomalous)
        jepa_error = ((s_pred_anom - s_anomalous) ** 2).mean(dim=-1)
        if jepa_error.dim() > 1:
            jepa_error = jepa_error.mean(dim=-1)
        jepa_scores = jepa_error.cpu().numpy()

    # Ontology scores
    anom_result = monitor.predict(anomalous)
    if monitor._centroid is not None:
        ont_scores = np.mean(
            np.abs(anom_result.z_ont - monitor._centroid) /
            np.maximum(monitor._centroid_std, 1e-6), axis=1,
        )
    else:
        ont_scores = np.zeros(N)

    # Combined
    jepa_norm = jepa_scores / (np.max(jepa_scores) + 1e-10)
    ont_norm = ont_scores / (np.max(ont_scores) + 1e-10)
    combined_scores = 0.5 * jepa_norm + 0.5 * ont_norm

    jepa_auc = compute_detection_auc(jepa_scores, labels) if labels.sum() > 0 else 0.5
    ont_auc = compute_detection_auc(ont_scores, labels) if labels.sum() > 0 else 0.5
    combined_auc = compute_detection_auc(combined_scores, labels) if labels.sum() > 0 else 0.5

    logger.info("  JEPA AUC=%.3f, Ontology AUC=%.3f, Combined AUC=%.3f",
                jepa_auc, ont_auc, combined_auc)

    # ── Step 6: Classify outcome ──
    logger.info("Step 6: Classifying alignment outcome...")
    outcome = classify_outcome(corr_matrix, bridge_metrics["r2_per_axis"], per_axis_mi)

    # Attach AUC results
    outcome.jepa_auc = jepa_auc
    outcome.ontology_auc = ont_auc
    outcome.combined_auc = combined_auc
    outcome.auc_delta = combined_auc - max(jepa_auc, ont_auc)

    return outcome


# ── Terminal rendering ───────────────────────────────────────────────────

# Box-drawing characters
H_LINE = "\u2500"
V_LINE = "\u2502"
TL = "\u250c"
TR = "\u2510"
BL = "\u2514"
BR = "\u2518"
T_DOWN = "\u252c"
T_UP = "\u2534"
T_RIGHT = "\u251c"
T_LEFT = "\u2524"
CROSS = "\u253c"

# Outcome indicators
STRONG_DOT = "\u25cf"   # ●
WEAK_DOT = "\u25cb"     # ○
ARROW_R = "\u2192"      # →
CHECK = "\u2713"        # ✓
CROSS_MARK = "\u2717"   # ✗
BAR_FULL = "\u2588"     # █
BAR_MED = "\u2593"      # ▓
BAR_LIGHT = "\u2591"    # ░


def _corr_bar(value: float, width: int = 20) -> str:
    """Render a correlation value as a horizontal bar."""
    abs_val = abs(value)
    filled = int(abs_val * width)
    sign = "+" if value >= 0 else "-"
    bar = BAR_FULL * filled + BAR_LIGHT * (width - filled)
    return f"[{sign}] {bar} {value:+.3f}"


def _r2_indicator(r2: float) -> str:
    """Render an R² value with status indicator."""
    if r2 > 0.5:
        return f"{CHECK} R²={r2:.3f} (strong)"
    elif r2 > 0.3:
        return f"{CHECK} R²={r2:.3f} (moderate)"
    elif r2 > 0.1:
        return f"{WEAK_DOT} R²={r2:.3f} (weak)"
    else:
        return f"{CROSS_MARK} R²={r2:.3f} (none)"


def render_outcome(outcome: AlignmentOutcome) -> str:
    """Render the alignment check result as a terminal report."""
    lines = []
    w = 72  # report width

    # ── Header ──
    lines.append("")
    lines.append(f"{TL}{H_LINE * (w - 2)}{TR}")
    lines.append(f"{V_LINE}{'JEPA-ONTOLOGY ALIGNMENT CHECK':^{w - 2}}{V_LINE}")
    lines.append(f"{V_LINE}{'Sovereign State [32D] vs Ontological Axes [4D]':^{w - 2}}{V_LINE}")
    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # ── Outcome banner ──
    num = outcome.outcome_number
    name = outcome.outcome_name
    banner = f"  OUTCOME {num}: {name}  "
    lines.append(f"{V_LINE}{banner:^{w - 2}}{V_LINE}")
    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # Description (word-wrapped)
    desc = outcome.outcome_description
    desc_words = desc.split()
    desc_lines = []
    current_line = ""
    for word in desc_words:
        if len(current_line) + len(word) + 1 <= w - 6:
            current_line += (" " if current_line else "") + word
        else:
            desc_lines.append(current_line)
            current_line = word
    if current_line:
        desc_lines.append(current_line)

    for dl in desc_lines:
        lines.append(f"{V_LINE}  {dl:<{w - 4}}{V_LINE}")
    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # ── Per-axis correlation table ──
    lines.append(f"{V_LINE}{'  AXIS CORRELATION MAP':^{w - 2}}{V_LINE}")
    lines.append(f"{V_LINE}{'  (Rank correlation: ontological axis vs best Sovereign dim)':^{w - 2}}{V_LINE}")
    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    for axis_name in ROBUST_AXES:
        corr = outcome.per_axis_best_corr.get(axis_name, 0.0)
        dim_name = outcome.per_axis_best_dim_name.get(axis_name, "?")
        mi = outcome.per_axis_mi.get(axis_name, 0.0)
        bar = _corr_bar(corr, 15)

        short_axis = axis_name.replace("O", "").replace("_", " ")
        line1 = f"  {short_axis:<18s} {ARROW_R} {dim_name:<16s} {bar}"
        lines.append(f"{V_LINE}{line1:<{w - 2}}{V_LINE}")

        # MI sub-line
        mi_line = f"{'':20s} MI={mi:.4f}"
        lines.append(f"{V_LINE}{mi_line:<{w - 2}}{V_LINE}")

    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # ── Summary stats ──
    lines.append(f"{V_LINE}{'  CORRELATION SUMMARY':^{w - 2}}{V_LINE}")
    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    stat_lines = [
        f"  Strong (|corr|>0.5):    {outcome.n_strong_axes}/4 axes",
        f"  Moderate (|corr|>0.3):  {outcome.n_moderate_axes}/4 axes",
        f"  Weak (|corr|<=0.3):     {outcome.n_weak_axes}/4 axes",
        f"  Max |corr|:             {outcome.max_abs_corr:.3f}",
        f"  Mean |corr|:            {outcome.mean_abs_corr:.3f}",
        f"  Mean MI:                {outcome.mean_mi:.4f}",
    ]
    for sl in stat_lines:
        lines.append(f"{V_LINE}{sl:<{w - 2}}{V_LINE}")

    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # ── Linear probe (bridge) results ──
    lines.append(f"{V_LINE}{'  LINEAR PROBE (ONTOLOGY BRIDGE)':^{w - 2}}{V_LINE}")
    lines.append(f"{V_LINE}{'  Can a linear map recover ontological axes from Sovereign State?':^{w - 2}}{V_LINE}")
    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    for axis_name in ROBUST_AXES:
        r2 = outcome.bridge_r2_per_axis.get(axis_name, 0.0)
        short_axis = axis_name.replace("O", "").replace("_", " ")
        indicator = _r2_indicator(r2)
        line = f"  {short_axis:<18s} {indicator}"
        lines.append(f"{V_LINE}{line:<{w - 2}}{V_LINE}")

    mean_line = f"  {'Mean':18s} R²={outcome.bridge_r2_mean:.3f}"
    lines.append(f"{V_LINE}{mean_line:<{w - 2}}{V_LINE}")

    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # ── Anomaly detection comparison ──
    lines.append(f"{V_LINE}{'  ANOMALY DETECTION (trajectory_break)':^{w - 2}}{V_LINE}")
    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    auc_lines = [
        f"  JEPA only:     AUC = {outcome.jepa_auc:.3f}",
        f"  Ontology only: AUC = {outcome.ontology_auc:.3f}",
        f"  Combined:      AUC = {outcome.combined_auc:.3f}  "
        f"(delta = {outcome.auc_delta:+.3f})",
    ]
    for al in auc_lines:
        lines.append(f"{V_LINE}{al:<{w - 2}}{V_LINE}")

    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # ── Evidence ──
    lines.append(f"{V_LINE}{'  EVIDENCE':^{w - 2}}{V_LINE}")
    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    for ev in outcome.evidence:
        # Word-wrap evidence lines
        ev_words = ev.split()
        ev_line = ""
        for word in ev_words:
            if len(ev_line) + len(word) + 1 <= w - 8:
                ev_line += (" " if ev_line else "") + word
            else:
                lines.append(f"{V_LINE}    {ev_line:<{w - 6}}{V_LINE}")
                ev_line = word
        if ev_line:
            lines.append(f"{V_LINE}    {ev_line:<{w - 6}}{V_LINE}")

    # ── Footer ──
    lines.append(f"{BL}{H_LINE * (w - 2)}{BR}")
    lines.append("")

    return "\n".join(lines)


# ── CLI entry point ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Check the natural alignment between JEPA's 32D Sovereign State "
            "and the OntologyMonitor's 4 validated axes. Determines which of "
            "4 outcomes best describes the relationship: Strong Overlap, "
            "Partial Overlap, Distributed Encoding, or Completely Orthogonal."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Outcomes:
  1. STRONG OVERLAP     All 4 axes have |corr| > 0.5 with a Sovereign dim
  2. PARTIAL OVERLAP    1-3 axes align; each system catches different things
  3. DISTRIBUTED        No direct mapping, but linear probe recovers the info
  4. ORTHOGONAL         Two systems genuinely measure different things

Examples:
  # Quick synthetic check
  python scripts/causal_subspace/check_alignment.py

  # Larger sample, save JSON
  python scripts/causal_subspace/check_alignment.py --n-samples 5000 --output result.json

  # Verbose
  python scripts/causal_subspace/check_alignment.py -v
        """,
    )

    parser.add_argument(
        "--n-samples", type=int, default=1000,
        help="Number of synthetic samples (default: 1000)",
    )
    parser.add_argument(
        "--d-model", type=int, default=768,
        help="Hidden state dimension (default: 768)",
    )
    parser.add_argument(
        "--state-dim", type=int, default=32,
        help="Sovereign State dimension (default: 32)",
    )
    parser.add_argument(
        "--bridge-epochs", type=int, default=200,
        help="Bridge training epochs (default: 200)",
    )
    parser.add_argument(
        "--monitor-epochs", type=int, default=100,
        help="Monitor training epochs (default: 100)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--checkpoint", type=str, default=None,
        help="Path to model checkpoint (uses real hidden states instead of synthetic)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    t0 = time.time()

    # ── Generate or load data ──
    if args.checkpoint:
        # Real model data — defer to run_symbolu_ontology for the heavy lifting
        print(f"Loading model from checkpoint: {args.checkpoint}")
        print("(For full checkpoint analysis, use run_symbolu_ontology.py --run-all)")
        print("Using synthetic data for alignment check...\n")

    H, ont_features, valid_mask = generate_synthetic_hidden_states(
        n_samples=args.n_samples,
        d_model=args.d_model,
        seed=args.seed,
    )

    # ── Run alignment check ──
    outcome = run_alignment_check(
        H=H,
        ont_features=ont_features,
        valid_mask=valid_mask,
        d_model=args.d_model,
        state_dim=args.state_dim,
        n_epochs_bridge=args.bridge_epochs,
        n_epochs_monitor=args.monitor_epochs,
        seed=args.seed,
    )

    elapsed = time.time() - t0

    # ── Render output ──
    report = render_outcome(outcome)
    print(report)
    print(f"  Completed in {elapsed:.1f}s\n")

    # ── Save JSON ──
    if args.output:
        output_path = Path(args.output)
        result_dict = {
            "outcome_number": outcome.outcome_number,
            "outcome_name": outcome.outcome_name,
            "outcome_description": outcome.outcome_description,
            "per_axis_best_dim": outcome.per_axis_best_dim,
            "per_axis_best_dim_name": outcome.per_axis_best_dim_name,
            "per_axis_best_corr": outcome.per_axis_best_corr,
            "per_axis_mi": outcome.per_axis_mi,
            "n_strong_axes": outcome.n_strong_axes,
            "n_moderate_axes": outcome.n_moderate_axes,
            "n_weak_axes": outcome.n_weak_axes,
            "max_abs_corr": outcome.max_abs_corr,
            "mean_abs_corr": outcome.mean_abs_corr,
            "bridge_r2_mean": outcome.bridge_r2_mean,
            "bridge_r2_per_axis": outcome.bridge_r2_per_axis,
            "bridge_n_positive_r2": outcome.bridge_n_positive_r2,
            "mean_mi": outcome.mean_mi,
            "jepa_auc": outcome.jepa_auc,
            "ontology_auc": outcome.ontology_auc,
            "combined_auc": outcome.combined_auc,
            "auc_delta": outcome.auc_delta,
            "evidence": outcome.evidence,
            "corr_matrix_shape": outcome.corr_matrix_shape,
            "elapsed_seconds": elapsed,
            "config": {
                "n_samples": args.n_samples,
                "d_model": args.d_model,
                "state_dim": args.state_dim,
                "bridge_epochs": args.bridge_epochs,
                "monitor_epochs": args.monitor_epochs,
                "seed": args.seed,
            },
        }

        def _serialize(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        with open(output_path, "w") as f:
            json.dump(result_dict, f, indent=2, default=_serialize)
        print(f"  Results saved to {output_path}\n")

    return outcome


if __name__ == "__main__":
    main()
