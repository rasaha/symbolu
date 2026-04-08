"""
Phase Coherence Loss and Semantic Entropy Monitoring.

This module provides training-time regularization and monitoring for Phase stability:

1. PhaseCoherenceLoss: Encourages smooth Phase evolution
   - Penalizes jitter (too different between steps)
   - Penalizes collapse (too similar between steps)

2. SemanticEntropyMonitor: Tracks entropy evolution during diffusion
   - Expected: high entropy early, decreasing towards clean
   - Alerts if entropy increases in late steps

These are TRAINING-ONLY tools that do not affect inference creativity.

Reference: Appendix I of PHASE_QUAD_IMAGE_GENERATOR_DESIGN.md
"""

from typing import Dict, List, Tuple, Optional
from collections import deque

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


class PhaseCoherenceLoss(nn.Module):
    """
    Phase coherence regularization for stable Phase evolution.

    Encourages Phase state to change smoothly across diffusion steps:
    - Too different (sim < target_low): Phase is jittering
    - Too similar (sim > target_high): Phase is collapsing

    The loss uses a bounded penalty that allows Phase to evolve naturally
    within a target similarity range without over-constraining creativity.

    Args:
        target_low: Minimum acceptable similarity (default 0.8).
            Below this, Phase is changing too fast (jittering).
        target_high: Maximum acceptable similarity (default 0.95).
            Above this, Phase is not evolving (collapsing).
        reduction: How to reduce the loss ('mean', 'sum', 'none').
    """

    def __init__(
        self,
        target_low: float = 0.8,
        target_high: float = 0.95,
        reduction: str = 'mean',
    ):
        super().__init__()
        self.target_low = target_low
        self.target_high = target_high
        self.reduction = reduction

        # Validation
        assert 0 <= target_low < target_high <= 1, \
            f"Invalid target range: [{target_low}, {target_high}]"

    def forward(
        self,
        phase_t: Tensor,
        phase_t_delta: Tensor,
    ) -> Tensor:
        """
        Compute Phase coherence loss.

        Args:
            phase_t: Phase state at step t [B, N, D] or [B, D].
            phase_t_delta: Phase state at step t+Δ [B, N, D] or [B, D].

        Returns:
            loss: Scalar loss if reduction='mean' or 'sum', else [B, N].
        """
        # Ensure same shape
        assert phase_t.shape == phase_t_delta.shape, \
            f"Shape mismatch: {phase_t.shape} vs {phase_t_delta.shape}"

        # Cosine similarity between states
        sim = F.cosine_similarity(phase_t, phase_t_delta, dim=-1)  # [B, N] or [B]

        # Bounded penalty
        loss_low = F.relu(self.target_low - sim)   # Penalize jitter
        loss_high = F.relu(sim - self.target_high) # Penalize collapse

        loss = loss_low + loss_high

        # Reduction
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        else:
            return loss

    def forward_with_stats(
        self,
        phase_t: Tensor,
        phase_t_delta: Tensor,
    ) -> Tuple[Tensor, Dict[str, float]]:
        """
        Compute loss with diagnostic statistics.

        Returns:
            loss: The coherence loss.
            stats: Dictionary with similarity statistics.
        """
        sim = F.cosine_similarity(phase_t, phase_t_delta, dim=-1)

        loss_low = F.relu(self.target_low - sim)
        loss_high = F.relu(sim - self.target_high)
        loss = (loss_low + loss_high).mean()

        with torch.no_grad():
            stats = {
                "phase_coherence/similarity_mean": sim.mean().item(),
                "phase_coherence/similarity_std": sim.std().item(),
                "phase_coherence/similarity_min": sim.min().item(),
                "phase_coherence/similarity_max": sim.max().item(),
                "phase_coherence/jitter_ratio": (sim < self.target_low).float().mean().item(),
                "phase_coherence/collapse_ratio": (sim > self.target_high).float().mean().item(),
                "phase_coherence/loss": loss.item(),
            }

        return loss, stats


class TemporalPhaseCoherenceLoss(nn.Module):
    """
    Extended Phase coherence that considers multiple timesteps.

    Maintains a buffer of recent Phase states and computes
    coherence across a sliding window.

    Args:
        target_low: Minimum acceptable similarity.
        target_high: Maximum acceptable similarity.
        window_size: Number of recent states to consider.
        decay: Exponential decay for older states' contribution.
    """

    def __init__(
        self,
        target_low: float = 0.8,
        target_high: float = 0.95,
        window_size: int = 5,
        decay: float = 0.9,
    ):
        super().__init__()
        self.base_loss = PhaseCoherenceLoss(target_low, target_high)
        self.window_size = window_size
        self.decay = decay

        # Buffer for recent states (not a parameter)
        self.register_buffer('_dummy', torch.empty(0))  # For device tracking
        self._state_buffer: deque = deque(maxlen=window_size)

    def forward(self, phase_state: Tensor) -> Tensor:
        """
        Compute temporal coherence loss.

        Args:
            phase_state: Current Phase state [B, N, D].

        Returns:
            loss: Aggregated coherence loss across window.
        """
        if len(self._state_buffer) == 0:
            self._state_buffer.append(phase_state.detach())
            return torch.tensor(0.0, device=phase_state.device)

        # Compute weighted loss against all states in buffer
        total_loss = torch.tensor(0.0, device=phase_state.device)
        total_weight = 0.0

        for i, past_state in enumerate(reversed(list(self._state_buffer))):
            weight = self.decay ** i
            loss = self.base_loss(phase_state, past_state)
            total_loss = total_loss + weight * loss
            total_weight += weight

        # Update buffer
        self._state_buffer.append(phase_state.detach())

        return total_loss / total_weight if total_weight > 0 else total_loss

    def reset(self):
        """Clear the state buffer."""
        self._state_buffer.clear()


def compute_semantic_entropy(x: Tensor, normalize: bool = True) -> float:
    """
    Compute semantic entropy of representation.

    Uses eigenvalue decomposition of the covariance matrix
    to estimate the "spread" of the representation space.

    Higher entropy = more diverse/spread representation
    Lower entropy = more concentrated/collapsed representation

    Args:
        x: Representation tensor [B, N, D] or [B, D].
        normalize: Whether to L2-normalize before computing.

    Returns:
        entropy: Scalar entropy value.
    """
    # Flatten to [*, D]
    if x.dim() == 3:
        x_flat = x.view(-1, x.size(-1))
    else:
        x_flat = x

    if normalize:
        x_flat = F.normalize(x_flat, dim=-1)

    # Compute covariance
    x_centered = x_flat - x_flat.mean(dim=0, keepdim=True)
    cov = x_centered.T @ x_centered / x_centered.size(0)

    # Entropy from eigenvalues
    try:
        eigenvalues = torch.linalg.eigvalsh(cov)
        eigenvalues = eigenvalues.clamp(min=1e-8)
        probs = eigenvalues / eigenvalues.sum()
        entropy = -(probs * torch.log(probs)).sum().item()
    except RuntimeError:
        # Fallback if eigendecomposition fails
        entropy = float('nan')

    return entropy


class SemanticEntropyMonitor:
    """
    Monitor semantic entropy evolution during diffusion.

    Expected behavior:
    - Early steps (noisy): High entropy
    - Late steps (clean): Lower entropy (but not collapsed)

    Alert conditions:
    - Entropy increases significantly in late steps
    - Entropy drops too fast (potential mode collapse)

    Args:
        alert_threshold: Threshold for entropy increase alert.
        collapse_threshold: Threshold for detecting collapse.
        history_size: Maximum history size to maintain.
    """

    def __init__(
        self,
        alert_threshold: float = 0.1,
        collapse_threshold: float = 0.3,
        history_size: int = 1000,
    ):
        self.alert_threshold = alert_threshold
        self.collapse_threshold = collapse_threshold
        self.history: List[Tuple[int, float]] = []
        self.history_size = history_size

    def update(self, x: Tensor, timestep: int) -> Dict[str, any]:
        """
        Update entropy tracking with new state.

        Args:
            x: Current representation [B, N, D].
            timestep: Current diffusion timestep.

        Returns:
            metrics: Dictionary with entropy and alert status.
        """
        entropy = compute_semantic_entropy(x)
        self.history.append((timestep, entropy))

        # Trim history if needed
        if len(self.history) > self.history_size:
            self.history = self.history[-self.history_size:]

        metrics = {
            "entropy": entropy,
            "timestep": timestep,
            "alert": False,
            "alert_reason": None,
        }

        # Check for anomalies
        if len(self.history) >= 2:
            prev_t, prev_e = self.history[-2]

            # Alert: entropy increasing in late steps (should decrease)
            if timestep < prev_t and entropy > prev_e + self.alert_threshold:
                metrics["alert"] = True
                metrics["alert_reason"] = "entropy_increase"
                metrics["entropy_delta"] = entropy - prev_e

            # Alert: entropy dropping too fast (potential collapse)
            elif prev_e - entropy > self.collapse_threshold:
                metrics["alert"] = True
                metrics["alert_reason"] = "potential_collapse"
                metrics["entropy_delta"] = prev_e - entropy

        return metrics

    def get_trajectory(self) -> List[Tuple[int, float]]:
        """Get full entropy trajectory."""
        return list(self.history)

    def get_summary(self) -> Dict[str, float]:
        """Get summary statistics of entropy trajectory."""
        if not self.history:
            return {}

        entropies = [e for _, e in self.history]
        timesteps = [t for t, _ in self.history]

        return {
            "entropy_mean": sum(entropies) / len(entropies),
            "entropy_min": min(entropies),
            "entropy_max": max(entropies),
            "entropy_std": (sum((e - sum(entropies)/len(entropies))**2 for e in entropies) / len(entropies)) ** 0.5,
            "timestep_range": (min(timesteps), max(timesteps)),
            "num_samples": len(self.history),
        }

    def reset(self):
        """Clear history."""
        self.history = []


class CombinedStabilityLoss(nn.Module):
    """
    Combined stability loss for training.

    Aggregates multiple stability objectives:
    - Phase coherence
    - Optional entropy regularization

    Args:
        phase_coherence_weight: Weight for Phase coherence loss.
        phase_config: Config dict for PhaseCoherenceLoss.
        use_entropy_reg: Whether to add entropy regularization.
        entropy_weight: Weight for entropy regularization.
    """

    def __init__(
        self,
        phase_coherence_weight: float = 0.01,
        phase_config: Optional[Dict] = None,
        use_entropy_reg: bool = False,
        entropy_weight: float = 0.001,
    ):
        super().__init__()

        phase_config = phase_config or {}
        self.phase_coherence = PhaseCoherenceLoss(**phase_config)
        self.phase_weight = phase_coherence_weight

        self.use_entropy_reg = use_entropy_reg
        self.entropy_weight = entropy_weight

        # Monitor for logging
        self.entropy_monitor = SemanticEntropyMonitor()

    def forward(
        self,
        phase_t: Tensor,
        phase_t_prev: Tensor,
        x: Optional[Tensor] = None,
        timestep: Optional[int] = None,
    ) -> Tuple[Tensor, Dict[str, float]]:
        """
        Compute combined stability loss.

        Args:
            phase_t: Current Phase state.
            phase_t_prev: Previous Phase state.
            x: Optional representation for entropy monitoring.
            timestep: Optional timestep for entropy tracking.

        Returns:
            loss: Combined stability loss.
            stats: Dictionary of diagnostic statistics.
        """
        stats = {}

        # Phase coherence
        coherence_loss, coherence_stats = self.phase_coherence.forward_with_stats(
            phase_t, phase_t_prev
        )
        stats.update(coherence_stats)

        total_loss = self.phase_weight * coherence_loss

        # Entropy monitoring (optional)
        if x is not None and timestep is not None:
            entropy_metrics = self.entropy_monitor.update(x, timestep)
            stats.update({f"entropy/{k}": v for k, v in entropy_metrics.items()})

            # Optional entropy regularization
            if self.use_entropy_reg:
                # Penalize very low entropy (collapse)
                entropy = entropy_metrics["entropy"]
                if entropy < 1.0:  # Threshold for "too low"
                    entropy_penalty = (1.0 - entropy) ** 2
                    total_loss = total_loss + self.entropy_weight * entropy_penalty
                    stats["entropy/regularization_penalty"] = entropy_penalty

        stats["stability/total_loss"] = total_loss.item() if torch.is_tensor(total_loss) else total_loss

        return total_loss, stats
