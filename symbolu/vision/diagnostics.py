"""
Diagnostic metrics for Phase-Quad Image Generator.

These metrics are NON-NEGOTIABLE per design specification.
They must be tracked every N steps and logged to tensorboard/wandb.
"""

from dataclasses import dataclass
from typing import Dict, Optional

import torch
import torch.nn.functional as F
from torch import Tensor


@dataclass
class QuadUtilizationMetrics:
    """
    Metrics to prove Quad is doing useful work.

    Must be tracked every N steps and logged to tensorboard/wandb.

    Attributes:
        gate_entropy: Entropy of gate weights - should not collapse to uniform.
        active_selection_rate: Fraction of tokens where max(gate_weight) > 0.5.
        gate_saturation_rate: Fraction of tokens where max(gate_weight) > 0.9
            (saturation warning).
        score_mean: Mean of top-k scores.
        score_std: Standard deviation of top-k scores.
        score_min: Minimum score in top-k.
        score_max: Maximum score in top-k.
    """
    gate_entropy: float
    active_selection_rate: float
    gate_saturation_rate: float
    score_mean: float
    score_std: float
    score_min: float
    score_max: float

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for logging."""
        return {
            "quad/gate_entropy": self.gate_entropy,
            "quad/active_selection_rate": self.active_selection_rate,
            "quad/gate_saturation_rate": self.gate_saturation_rate,
            "quad/score_mean": self.score_mean,
            "quad/score_std": self.score_std,
            "quad/score_min": self.score_min,
            "quad/score_max": self.score_max,
        }

    def is_healthy(self) -> bool:
        """Check if metrics indicate healthy Quad operation."""
        # Gate entropy should not be too low (collapsed) or too high (uniform)
        entropy_ok = 0.5 < self.gate_entropy < 4.0

        # Should have some active selection
        selection_ok = self.active_selection_rate > 0.1

        # Saturation should not be too high
        saturation_ok = self.gate_saturation_rate < 0.8

        return entropy_ok and selection_ok and saturation_ok


@dataclass
class PhaseHealthMetrics:
    """
    Metrics for phase stability monitoring.

    Alerts:
    - amplitude_saturation > 0.95: a_k saturating
    - state_drift_ratio > 0.5: state changing too fast
    - row_col_divergence > 0.3: scans producing inconsistent states

    Attributes:
        amplitude_mean: Mean amplitude across all positions.
        amplitude_std: Standard deviation of amplitude.
        amplitude_saturation: Fraction where a_k > 0.95.
        state_drift_ratio: Change magnitude over window.
        state_norm: Norm of the state.
        row_col_similarity: Cosine similarity between row and column states.
    """
    amplitude_mean: float
    amplitude_std: float
    amplitude_saturation: float
    state_drift_ratio: float
    state_norm: float
    row_col_similarity: float

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for logging."""
        return {
            "phase/amplitude_mean": self.amplitude_mean,
            "phase/amplitude_std": self.amplitude_std,
            "phase/amplitude_saturation": self.amplitude_saturation,
            "phase/state_drift_ratio": self.state_drift_ratio,
            "phase/state_norm": self.state_norm,
            "phase/row_col_similarity": self.row_col_similarity,
        }

    def get_alerts(self) -> list:
        """Get list of alert messages if metrics are problematic."""
        alerts = []

        if self.amplitude_saturation > 0.95:
            alerts.append(
                f"ALERT: Amplitude saturation ({self.amplitude_saturation:.2%}) > 95%"
            )

        if self.state_drift_ratio > 0.5:
            alerts.append(
                f"ALERT: State drift ratio ({self.state_drift_ratio:.2f}) > 0.5"
            )

        if self.row_col_similarity < 0.7:
            alerts.append(
                f"ALERT: Row-col divergence (similarity={self.row_col_similarity:.2f}) < 0.7"
            )

        return alerts

    def is_healthy(self) -> bool:
        """Check if metrics indicate healthy Phase operation."""
        return len(self.get_alerts()) == 0


def compute_quad_utilization(
    gate_weights: Tensor,
    scores: Tensor,
) -> QuadUtilizationMetrics:
    """
    Compute Quad utilization metrics.

    Args:
        gate_weights: [B, N, K] normalized gate weights.
        scores: [B, N, K] raw retrieval scores.

    Returns:
        QuadUtilizationMetrics with computed values.
    """
    with torch.no_grad():
        # Gate entropy
        entropy = -(gate_weights * (gate_weights + 1e-8).log()).sum(dim=-1)
        gate_entropy = entropy.mean().item()

        # Active selection
        max_gate = gate_weights.max(dim=-1)[0]
        active_selection_rate = (max_gate > 0.5).float().mean().item()
        gate_saturation_rate = (max_gate > 0.9).float().mean().item()

        # Score distribution
        return QuadUtilizationMetrics(
            gate_entropy=gate_entropy,
            active_selection_rate=active_selection_rate,
            gate_saturation_rate=gate_saturation_rate,
            score_mean=scores.mean().item(),
            score_std=scores.std().item(),
            score_min=scores.min().item(),
            score_max=scores.max().item(),
        )


def compute_phase_health(
    S_row: Tensor,
    S_col: Tensor,
    a_k: Tensor,
    window: int = 32,
) -> PhaseHealthMetrics:
    """
    Compute phase health metrics.

    Args:
        S_row: [B, N, D] row scan state.
        S_col: [B, N, D] column scan state.
        a_k: [B, N, H] amplitude values.
        window: Window size for drift computation.

    Returns:
        PhaseHealthMetrics with computed values.
    """
    with torch.no_grad():
        # Amplitude statistics
        amplitude_mean = a_k.mean().item()
        amplitude_std = a_k.std().item()
        amplitude_saturation = (a_k > 0.95).float().mean().item()

        # State drift
        B, N, D = S_row.shape
        if N > window:
            S_early = S_row[:, :window, :]
            S_late = S_row[:, -window:, :]
            drift = (S_late - S_early).norm(dim=-1).mean()
            state_norm = S_row.norm(dim=-1).mean()
            state_drift_ratio = (drift / (state_norm + 1e-8)).item()
        else:
            state_drift_ratio = 0.0
            state_norm = S_row.norm(dim=-1).mean().item()

        # Row-column coherence (cosine similarity)
        S_row_norm = F.normalize(S_row, dim=-1)
        S_col_norm = F.normalize(S_col, dim=-1)
        similarity = (S_row_norm * S_col_norm).sum(dim=-1).mean()
        row_col_similarity = similarity.item()

        return PhaseHealthMetrics(
            amplitude_mean=amplitude_mean,
            amplitude_std=amplitude_std,
            amplitude_saturation=amplitude_saturation,
            state_drift_ratio=state_drift_ratio,
            state_norm=state_norm if isinstance(state_norm, float) else state_norm.item(),
            row_col_similarity=row_col_similarity,
        )


def compute_ghost_metrics(
    S: Tensor,
    window: int = 32,
) -> Dict[str, float]:
    """
    Compute phase state stability metrics.

    DO NOT hardcode universal thresholds - these depend on:
    - Normalization scheme
    - Scan order
    - Whether state is per-head or aggregated
    - Diffusion timestep (early noisy vs late denoise)

    Instead, track trends and correlations.

    Args:
        S: [B, N, D] phase state.
        window: Window size for comparison.

    Returns:
        Dictionary of stability metrics.
    """
    with torch.no_grad():
        B, N, D = S.shape
        metrics = {}

        if N > window:
            S_early = S[:, :N // 2, :]
            S_late = S[:, N // 2:, :]

            # Directional stability (cosine similarity)
            S_early_norm = F.normalize(S_early, dim=-1)
            S_late_norm = F.normalize(S_late, dim=-1)
            # Compare same positions in early and late halves
            min_len = min(S_early_norm.shape[1], S_late_norm.shape[1])
            cos_sim = (
                S_early_norm[:, :min_len] * S_late_norm[:, :min_len]
            ).sum(dim=-1).mean()
            metrics["directional_stability"] = cos_sim.item()

            # Drift magnitude
            drift = (S_late[:, :min_len] - S_early[:, :min_len]).norm(dim=-1).mean()
            base_norm = S.norm(dim=-1).mean()
            metrics["drift_magnitude"] = (drift / (base_norm + 1e-8)).item()

            # Per-position variance (should not collapse to constant)
            var_per_pos = S.var(dim=0).mean()
            metrics["positional_variance"] = var_per_pos.item()

        return metrics


@dataclass
class BlockDiagnostics:
    """Aggregated diagnostics for a single block."""
    block_idx: int
    quad_metrics: QuadUtilizationMetrics
    phase_metrics: PhaseHealthMetrics
    ghost_metrics: Dict[str, float]

    def to_dict(self) -> Dict[str, float]:
        """Convert to flat dictionary for logging."""
        prefix = f"block_{self.block_idx}/"
        result = {}

        for k, v in self.quad_metrics.to_dict().items():
            result[f"{prefix}{k}"] = v

        for k, v in self.phase_metrics.to_dict().items():
            result[f"{prefix}{k}"] = v

        for k, v in self.ghost_metrics.items():
            result[f"{prefix}ghost/{k}"] = v

        return result


@dataclass
class ModelDiagnostics:
    """Aggregated diagnostics for the full model."""
    blocks: list  # List of BlockDiagnostics
    global_metrics: Dict[str, float]

    def to_dict(self) -> Dict[str, float]:
        """Convert to flat dictionary for logging."""
        result = dict(self.global_metrics)

        for block_diag in self.blocks:
            result.update(block_diag.to_dict())

        return result

    def get_all_alerts(self) -> list:
        """Get all alerts from all blocks."""
        alerts = []
        for block_diag in self.blocks:
            block_alerts = block_diag.phase_metrics.get_alerts()
            for alert in block_alerts:
                alerts.append(f"Block {block_diag.block_idx}: {alert}")
        return alerts
