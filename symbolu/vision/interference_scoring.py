"""
Interference-Aware Proposal Scoring for Phase-Quad.

This module provides optional proposal-proposal compatibility scoring
that boosts mutually consistent proposals and downweights conflicting ones.

Key design principles:
- Applied AFTER BCVF filtering (not before)
- Operates only on K proposals (K ≤ 64), NOT on N tokens
- Lightweight O(K²) compute per position
- Optional creative mode enhancement, not core dependency

When to use:
- Multi-object composition
- Style blending
- Scene coherence
- Video temporal consistency

When NOT needed:
- Single-object images
- Pure reconstruction
- Deterministic enterprise tasks
- Early training stages

Reference: Designed as a "creative amplifier" layer per architectural guidance.
"""

from typing import Optional, Dict, Tuple
from dataclasses import dataclass

import torch
import torch.nn as nn
from torch import Tensor


@dataclass
class InterferenceConfig:
    """
    Configuration for interference-aware scoring.

    Attributes:
        enabled: Whether interference scoring is active.
        lambda_interference: Strength of interference modifier (0.03-0.08 recommended).
        min_multiplier: Minimum score multiplier (prevents collapse).
        max_multiplier: Maximum score multiplier (prevents runaway).
        timestep_threshold: Only apply at timesteps below this (0.0-1.0, lower = later/cleaner).
        warmup_steps: Steps before interference is fully enabled.
        max_k: Maximum K to apply interference (skip if K > this).
    """
    enabled: bool = False
    lambda_interference: float = 0.05
    min_multiplier: float = 0.8
    max_multiplier: float = 1.2
    timestep_threshold: float = 0.4  # Only apply in last 40% of denoising
    warmup_steps: int = 0  # Steps before full strength
    max_k: int = 64


def interference_rescore(
    proposals: Tensor,
    scores: Tensor,
    lam: float = 0.05,
    min_mult: float = 0.8,
    max_mult: float = 1.2,
    eps: float = 1e-6,
) -> Tuple[Tensor, Dict[str, float]]:
    """
    Apply interference-aware rescoring to proposals.

    Computes pairwise compatibility between proposals and uses it to
    boost mutually consistent proposals while downweighting outliers.

    Args:
        proposals: TopK proposals [B, N, K, D].
        scores: Current scores [B, N, K] (post-BCVF).
        lam: Interference strength (0.03-0.08 recommended).
        min_mult: Minimum multiplier clamp.
        max_mult: Maximum multiplier clamp.
        eps: Numerical stability epsilon.

    Returns:
        rescored: Modified scores [B, N, K].
        stats: Diagnostic statistics.
    """
    B, N, K, D = proposals.shape

    # Normalize proposals for cosine similarity
    p_norm = proposals / (proposals.norm(dim=-1, keepdim=True) + eps)  # [B, N, K, D]

    # Compute pairwise similarity between proposals at each position
    # sim[b, n, k, q] = cosine_similarity(proposal_k, proposal_q)
    sim = torch.einsum("bnkd,bnqd->bnkq", p_norm, p_norm)  # [B, N, K, K]

    # Zero out diagonal (self-similarity doesn't count)
    eye = torch.eye(K, device=sim.device, dtype=sim.dtype)
    sim = sim - eye.unsqueeze(0).unsqueeze(0)  # [B, N, K, K]

    # Compatibility score: average similarity with other proposals
    # High compat = proposal is consistent with many others
    # Low compat = proposal is an outlier
    compat = sim.mean(dim=-1)  # [B, N, K]

    # Compute multiplier with clamping for stability
    multiplier = (1.0 + lam * compat).clamp(min_mult, max_mult)

    # Apply to scores
    rescored = scores * multiplier

    # Compute diagnostics
    with torch.no_grad():
        stats = {
            "interference/compat_mean": compat.mean().item(),
            "interference/compat_std": compat.std().item(),
            "interference/compat_min": compat.min().item(),
            "interference/compat_max": compat.max().item(),
            "interference/multiplier_mean": multiplier.mean().item(),
            "interference/multiplier_std": multiplier.std().item(),
            "interference/score_change_pct": ((rescored - scores).abs() / (scores.abs() + eps)).mean().item() * 100,
        }

    return rescored, stats


class InterferenceScorer(nn.Module):
    """
    Module wrapper for interference-aware proposal scoring.

    Provides:
    - Configurable lambda with warmup
    - Timestep-conditional application
    - Diagnostic tracking
    - Clean integration with BCVF

    Example:
        >>> scorer = InterferenceScorer(config)
        >>> rescored, stats = scorer(proposals, scores, timestep=200, step=10000)
    """

    def __init__(self, config: Optional[InterferenceConfig] = None):
        super().__init__()
        self.config = config or InterferenceConfig()

        # Track diagnostics
        self._last_stats: Dict[str, float] = {}
        self._applications_count = 0
        self._skip_count = 0

    def get_effective_lambda(self, step: int) -> float:
        """
        Get effective lambda considering warmup schedule.

        Args:
            step: Current training step.

        Returns:
            Effective lambda value (0 to config.lambda_interference).
        """
        if not self.config.enabled:
            return 0.0

        if self.config.warmup_steps <= 0:
            return self.config.lambda_interference

        # Linear warmup
        progress = min(step / self.config.warmup_steps, 1.0)
        return self.config.lambda_interference * progress

    def should_apply(
        self,
        timestep: int,
        max_timestep: int = 1000,
        k: int = 64,
    ) -> bool:
        """
        Determine if interference should be applied at this timestep.

        Args:
            timestep: Current diffusion timestep (higher = noisier).
            max_timestep: Maximum timestep value.
            k: Number of proposals.

        Returns:
            True if interference should be applied.
        """
        if not self.config.enabled:
            return False

        # Skip if K is too large
        if k > self.config.max_k:
            return False

        # Only apply at low-noise timesteps (late in denoising)
        timestep_ratio = timestep / max_timestep
        return timestep_ratio < self.config.timestep_threshold

    def forward(
        self,
        proposals: Tensor,
        scores: Tensor,
        timestep: Optional[int] = None,
        max_timestep: int = 1000,
        step: int = 0,
    ) -> Tuple[Tensor, Dict[str, float]]:
        """
        Apply interference scoring if conditions are met.

        Args:
            proposals: TopK proposals [B, N, K, D].
            scores: Current scores [B, N, K].
            timestep: Current diffusion timestep (None = always apply if enabled).
            max_timestep: Maximum timestep for ratio calculation.
            step: Current training step (for warmup).

        Returns:
            scores: Possibly rescored [B, N, K].
            stats: Diagnostic statistics (empty if not applied).
        """
        K = proposals.shape[2]

        # Check if we should apply
        if timestep is not None:
            should_apply = self.should_apply(timestep, max_timestep, K)
        else:
            should_apply = self.config.enabled and K <= self.config.max_k

        if not should_apply:
            self._skip_count += 1
            return scores, {"interference/applied": 0.0}

        # Get effective lambda
        lam = self.get_effective_lambda(step)

        if lam <= 0:
            self._skip_count += 1
            return scores, {"interference/applied": 0.0}

        # Apply interference rescoring
        rescored, stats = interference_rescore(
            proposals,
            scores,
            lam=lam,
            min_mult=self.config.min_multiplier,
            max_mult=self.config.max_multiplier,
        )

        # Track application
        self._applications_count += 1
        stats["interference/applied"] = 1.0
        stats["interference/effective_lambda"] = lam
        self._last_stats = stats

        return rescored, stats

    def get_diagnostics(self) -> Dict[str, float]:
        """Get accumulated diagnostics."""
        total = self._applications_count + self._skip_count
        return {
            **self._last_stats,
            "interference/application_rate": self._applications_count / max(total, 1),
            "interference/total_applications": float(self._applications_count),
            "interference/total_skips": float(self._skip_count),
        }

    def reset_stats(self):
        """Reset diagnostic counters."""
        self._applications_count = 0
        self._skip_count = 0
        self._last_stats = {}


class InterferenceCurriculumScheduler:
    """
    Curriculum scheduler for interference training.

    Implements the recommended training curriculum:
    - Stage A (0-30%): Interference OFF
    - Stage B (30-60%): Soft introduction, lambda ramps up
    - Stage C (60-100%): Full creative mode

    Args:
        total_steps: Total training steps.
        stage_a_end: Fraction where Stage A ends (default 0.3).
        stage_b_end: Fraction where Stage B ends (default 0.6).
        lambda_max: Maximum lambda value (default 0.05).
        timestep_threshold_start: Starting timestep threshold (default 0.2).
        timestep_threshold_end: Ending timestep threshold (default 0.4).
    """

    def __init__(
        self,
        total_steps: int,
        stage_a_end: float = 0.3,
        stage_b_end: float = 0.6,
        lambda_max: float = 0.05,
        timestep_threshold_start: float = 0.2,
        timestep_threshold_end: float = 0.4,
    ):
        self.total_steps = total_steps
        self.stage_a_end = stage_a_end
        self.stage_b_end = stage_b_end
        self.lambda_max = lambda_max
        self.timestep_threshold_start = timestep_threshold_start
        self.timestep_threshold_end = timestep_threshold_end

    def get_config(self, step: int) -> InterferenceConfig:
        """
        Get interference config for current step.

        Args:
            step: Current training step.

        Returns:
            InterferenceConfig for this step.
        """
        progress = step / max(self.total_steps, 1)

        # Stage A: Interference OFF
        if progress < self.stage_a_end:
            return InterferenceConfig(enabled=False)

        # Stage B: Soft introduction
        if progress < self.stage_b_end:
            # Ramp lambda from 0 to lambda_max
            stage_progress = (progress - self.stage_a_end) / (self.stage_b_end - self.stage_a_end)
            current_lambda = self.lambda_max * stage_progress

            # Ramp timestep threshold
            current_threshold = (
                self.timestep_threshold_start +
                (self.timestep_threshold_end - self.timestep_threshold_start) * stage_progress
            )

            return InterferenceConfig(
                enabled=True,
                lambda_interference=current_lambda,
                timestep_threshold=current_threshold,
            )

        # Stage C: Full creative mode
        return InterferenceConfig(
            enabled=True,
            lambda_interference=self.lambda_max,
            timestep_threshold=self.timestep_threshold_end,
        )

    def get_stage(self, step: int) -> str:
        """Get current curriculum stage name."""
        progress = step / max(self.total_steps, 1)
        if progress < self.stage_a_end:
            return "A_baseline"
        elif progress < self.stage_b_end:
            return "B_soft_intro"
        else:
            return "C_full_creative"


def create_interference_scorer(
    enabled: bool = False,
    lambda_interference: float = 0.05,
    **kwargs,
) -> InterferenceScorer:
    """
    Factory function to create interference scorer.

    Args:
        enabled: Whether to enable interference.
        lambda_interference: Interference strength.
        **kwargs: Additional config options.

    Returns:
        Configured InterferenceScorer.
    """
    config = InterferenceConfig(
        enabled=enabled,
        lambda_interference=lambda_interference,
        **kwargs,
    )
    return InterferenceScorer(config)
