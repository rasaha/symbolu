"""
BCVF (Bidirectional Consistency Verification) for Video.

Extends image BCVF with temporal consistency scoring to reduce
flicker, drift, and stutter across video frames.

Key addition: Temporal consistency score (st) measures alignment
between proposals and the previous frame's representation.

Reference: Appendix C of PHASE_QUAD_VIDEO_DESIGN.md
"""

from typing import Optional, Dict, Tuple
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


@dataclass
class BCVFVideoConfig:
    """BCVF configuration for video."""
    enabled: bool = True
    lambda_f: float = 1.0      # Forward feasibility weight
    lambda_b: float = 1.0      # Backward alignment weight
    lambda_c: float = 0.5      # Consistency penalty weight
    lambda_t: float = 0.75     # Temporal consistency weight (NEW)
    beta: float = 2.0          # Sharpness of weighting
    detach_prev: bool = True   # Detach prev_state for stability


class BCVFVideoQuadWeighter(nn.Module):
    """
    BCVF for video with temporal consistency scoring.

    Extends image BCVF to reduce flicker and drift across frames.

    Scores:
    - sf (forward): proposal fits local evidence
    - sb (backward): proposal aligns with Phase memory
    - st (temporal): proposal aligns with previous frame [NEW]

    Lagrangian:
        L = λf(1-sf)² + λb(1-sb)² + λc(sf-sb)² + λt(1-st)²

    Args:
        lambda_f: Forward feasibility weight.
        lambda_b: Backward alignment weight.
        lambda_c: Consistency penalty weight.
        lambda_t: Temporal consistency weight.
        beta: Sharpness of weighting (higher = sharper selection).
        detach_prev: Whether to detach prev_state (safer early in training).
        normalize: Whether to L2-normalize before similarity computation.
    """

    def __init__(
        self,
        lambda_f: float = 1.0,
        lambda_b: float = 1.0,
        lambda_c: float = 0.5,
        lambda_t: float = 0.75,
        beta: float = 2.0,
        detach_prev: bool = True,
        normalize: bool = True,
    ):
        super().__init__()
        self.lambda_f = lambda_f
        self.lambda_b = lambda_b
        self.lambda_c = lambda_c
        self.lambda_t = lambda_t
        self.beta = beta
        self.detach_prev = detach_prev
        self.normalize = normalize

        # Instrumentation for logging
        self._last_sf_mean = 0.0
        self._last_sb_mean = 0.0
        self._last_st_mean = 0.0
        self._last_weight_entropy = 0.0
        self._last_top1_weight = 0.0

    def forward(
        self,
        proposals: Tensor,
        proposal_scores: Tensor,
        phase_state: Tensor,
        prev_state: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Compute BCVF-weighted proposals with temporal consistency.

        Args:
            proposals: TopK retrieved proposals [B, T, N, K, D].
            proposal_scores: Raw retrieval scores [B, T, N, K].
            phase_state: Current Phase state [B, T, N, D].
            prev_state: Previous frame's output [B, N, D] or None for t=0.

        Returns:
            weighted: BCVF-weighted proposals [B, T, N, D].
        """
        B, T, N, K, D = proposals.shape

        # Forward score: local evidence fit
        sf = torch.sigmoid(proposal_scores)  # [B, T, N, K]

        # Backward score: Phase memory alignment
        if self.normalize:
            proposals_norm = F.normalize(proposals, dim=-1)
            phase_norm = F.normalize(phase_state, dim=-1)
            sb = (proposals_norm * phase_norm.unsqueeze(3)).sum(dim=-1)
        else:
            sb = F.cosine_similarity(
                proposals,
                phase_state.unsqueeze(3),
                dim=-1
            )  # [B, T, N, K]

        # Map sb from [-1, 1] to [0, 1]
        sb = (sb + 1) / 2

        # Process frame by frame for temporal consistency
        outputs = []
        current_prev = prev_state

        for t in range(T):
            # Temporal consistency score
            if t == 0 and current_prev is None:
                st_t = torch.zeros_like(sf[:, t])  # [B, N, K]
            else:
                if self.normalize:
                    prop_t_norm = F.normalize(proposals[:, t], dim=-1)
                    prev_norm = F.normalize(current_prev, dim=-1)
                    st_t = (prop_t_norm * prev_norm.unsqueeze(2)).sum(dim=-1)
                else:
                    st_t = F.cosine_similarity(
                        proposals[:, t],           # [B, N, K, D]
                        current_prev.unsqueeze(2), # [B, N, 1, D]
                        dim=-1
                    )  # [B, N, K]

                # Map st from [-1, 1] to [0, 1]
                st_t = (st_t + 1) / 2

            # BCVF Lagrangian with temporal term
            L = (
                self.lambda_f * (1 - sf[:, t])**2 +
                self.lambda_b * (1 - sb[:, t])**2 +
                self.lambda_c * (sf[:, t] - sb[:, t])**2 +
                self.lambda_t * (1 - st_t)**2
            )  # [B, N, K]

            # Weights
            w = torch.exp(-self.beta * L)
            w = w / (w.sum(dim=-1, keepdim=True) + 1e-8)  # [B, N, K]

            # Weighted combination
            weighted_t = torch.sum(
                w.unsqueeze(-1) * proposals[:, t],
                dim=2
            )  # [B, N, D]

            outputs.append(weighted_t)

            # Update prev_state for next frame
            if self.detach_prev:
                current_prev = weighted_t.detach()
            else:
                current_prev = weighted_t

        # Stack outputs
        output = torch.stack(outputs, dim=1)  # [B, T, N, D]

        # Update instrumentation (using last frame stats)
        with torch.no_grad():
            self._last_sf_mean = sf.mean().item()
            self._last_sb_mean = sb.mean().item()
            if T > 1:
                self._last_st_mean = st_t.mean().item()
            self._last_weight_entropy = -(w * torch.log(w + 1e-8)).sum(-1).mean().item()
            self._last_top1_weight = w.max(dim=-1)[0].mean().item()

        return output

    def forward_with_metrics(
        self,
        proposals: Tensor,
        proposal_scores: Tensor,
        phase_state: Tensor,
        prev_state: Optional[Tensor] = None,
    ) -> Tuple[Tensor, Dict[str, float]]:
        """
        Forward pass with detailed metrics for logging.

        Returns:
            output: Weighted proposals [B, T, N, D].
            metrics: Dictionary of BCVF metrics.
        """
        output = self.forward(proposals, proposal_scores, phase_state, prev_state)

        metrics = {
            "bcvf_video/sf_mean": self._last_sf_mean,
            "bcvf_video/sb_mean": self._last_sb_mean,
            "bcvf_video/st_mean": self._last_st_mean,
            "bcvf_video/weight_entropy": self._last_weight_entropy,
            "bcvf_video/top1_weight": self._last_top1_weight,
        }

        return output, metrics

    def get_instrumentation(self) -> Dict[str, float]:
        """Get diagnostic metrics from last forward pass."""
        return {
            "bcvf_video/sf_mean": self._last_sf_mean,
            "bcvf_video/sb_mean": self._last_sb_mean,
            "bcvf_video/st_mean": self._last_st_mean,
            "bcvf_video/weight_entropy": self._last_weight_entropy,
            "bcvf_video/top1_weight": self._last_top1_weight,
        }


class AdaptiveBCVFVideoWeighter(nn.Module):
    """
    Adaptive BCVF for video with learnable parameters.

    Lambda values adapt based on timestep embedding, allowing
    different temporal consistency strength at different diffusion steps.

    Args:
        embed_dim: Model dimension for adaptive projection.
        init_lambda_f: Initial forward weight.
        init_lambda_b: Initial backward weight.
        init_lambda_c: Initial consistency weight.
        init_lambda_t: Initial temporal weight.
        init_beta: Initial sharpness.
    """

    def __init__(
        self,
        embed_dim: int,
        init_lambda_f: float = 1.0,
        init_lambda_b: float = 1.0,
        init_lambda_c: float = 0.5,
        init_lambda_t: float = 0.75,
        init_beta: float = 2.0,
    ):
        super().__init__()

        # Base parameters (in log space for positivity)
        self.log_lambda_f = nn.Parameter(torch.tensor(init_lambda_f).log())
        self.log_lambda_b = nn.Parameter(torch.tensor(init_lambda_b).log())
        self.log_lambda_c = nn.Parameter(torch.tensor(init_lambda_c).log())
        self.log_lambda_t = nn.Parameter(torch.tensor(init_lambda_t).log())
        self.log_beta = nn.Parameter(torch.tensor(init_beta).log())

        # Adaptive modulation based on timestep
        self.time_adapt = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.SiLU(),
            nn.Linear(64, 5),  # lambda_f, lambda_b, lambda_c, lambda_t, beta
        )

        # Zero-init for stable start
        nn.init.zeros_(self.time_adapt[-1].weight)
        nn.init.zeros_(self.time_adapt[-1].bias)

    def forward(
        self,
        proposals: Tensor,
        proposal_scores: Tensor,
        phase_state: Tensor,
        prev_state: Optional[Tensor] = None,
        time_embed: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Compute adaptively-weighted video proposals.

        Args:
            proposals: [B, T, N, K, D]
            proposal_scores: [B, T, N, K]
            phase_state: [B, T, N, D]
            prev_state: [B, N, D] or None
            time_embed: [B, D] timestep embedding for adaptation

        Returns:
            weighted: [B, T, N, D]
        """
        B, T, N, K, D = proposals.shape

        # Get base parameters
        lambda_f = self.log_lambda_f.exp()
        lambda_b = self.log_lambda_b.exp()
        lambda_c = self.log_lambda_c.exp()
        lambda_t = self.log_lambda_t.exp()
        beta = self.log_beta.exp()

        # Adapt based on timestep
        if time_embed is not None:
            deltas = self.time_adapt(time_embed)  # [B, 5]
            delta_f, delta_b, delta_c, delta_t, delta_beta = deltas.unbind(dim=-1)
            lambda_f = lambda_f * (1 + delta_f).view(B, 1, 1)
            lambda_b = lambda_b * (1 + delta_b).view(B, 1, 1)
            lambda_c = lambda_c * (1 + delta_c).view(B, 1, 1)
            lambda_t = lambda_t * (1 + delta_t).view(B, 1, 1)
            beta = beta * (1 + delta_beta).view(B, 1, 1)

        # Compute scores
        sf = torch.sigmoid(proposal_scores)
        sb = F.cosine_similarity(proposals, phase_state.unsqueeze(3), dim=-1)
        sb = (sb + 1) / 2

        # Process frames
        outputs = []
        current_prev = prev_state

        for t in range(T):
            if t == 0 and current_prev is None:
                st_t = torch.zeros_like(sf[:, t])
            else:
                st_t = F.cosine_similarity(
                    proposals[:, t],
                    current_prev.unsqueeze(2),
                    dim=-1
                )
                st_t = (st_t + 1) / 2

            # Lagrangian with adaptive parameters
            if time_embed is not None:
                L = (
                    lambda_f * (1 - sf[:, t])**2 +
                    lambda_b * (1 - sb[:, t])**2 +
                    lambda_c * (sf[:, t] - sb[:, t])**2 +
                    lambda_t * (1 - st_t)**2
                )
                w = torch.exp(-beta * L)
            else:
                L = (
                    lambda_f * (1 - sf[:, t])**2 +
                    lambda_b * (1 - sb[:, t])**2 +
                    lambda_c * (sf[:, t] - sb[:, t])**2 +
                    lambda_t * (1 - st_t)**2
                )
                w = torch.exp(-beta * L)

            w = w / (w.sum(dim=-1, keepdim=True) + 1e-8)

            weighted_t = torch.sum(w.unsqueeze(-1) * proposals[:, t], dim=2)
            outputs.append(weighted_t)
            current_prev = weighted_t.detach()

        return torch.stack(outputs, dim=1)


def compute_video_bcvf_metrics(
    sf: Tensor,
    sb: Tensor,
    st: Tensor,
    weights: Tensor,
) -> Dict[str, float]:
    """
    Compute comprehensive BCVF metrics for logging.

    Args:
        sf: Forward scores [B, T, N, K]
        sb: Backward scores [B, T, N, K]
        st: Temporal scores [B, T, N, K]
        weights: BCVF weights [B, T, N, K]

    Returns:
        Dictionary of metrics.
    """
    return {
        # Score means
        "bcvf_video/sf_mean": sf.mean().item(),
        "bcvf_video/sb_mean": sb.mean().item(),
        "bcvf_video/st_mean": st.mean().item(),

        # Score standard deviations
        "bcvf_video/sf_std": sf.std().item(),
        "bcvf_video/sb_std": sb.std().item(),
        "bcvf_video/st_std": st.std().item(),

        # Weight distribution
        "bcvf_video/weight_entropy": -(weights * torch.log(weights + 1e-8)).sum(-1).mean().item(),
        "bcvf_video/top1_weight": weights.max(dim=-1)[0].mean().item(),
        "bcvf_video/top3_weight": weights.topk(3, dim=-1)[0].sum(dim=-1).mean().item(),

        # Temporal consistency indicators
        "bcvf_video/st_temporal_std": st.std(dim=1).mean().item(),  # Variation across time
    }
