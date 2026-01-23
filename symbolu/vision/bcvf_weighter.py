"""
BCVF (Bidirectional Consistency Verification) for Quad Proposals.

This module re-weights Quad proposals based on bidirectional consistency:
- Forward score (sf): How well a proposal fits local evidence
- Backward score (sb): How well a proposal aligns with Phase memory
- Consistency: Agreement between forward and backward scores

BCVF improves image quality by:
- Suppressing unstable textures
- Reducing flicker in video
- Improving global composition

Reference: Appendix I of PHASE_QUAD_IMAGE_GENERATOR_DESIGN.md
"""

from typing import Optional, Dict

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


class BCVFQuadWeighter(nn.Module):
    """
    Bidirectional Consistency Verification for Quad proposals.

    Re-weights proposals based on:
    - Forward score (sf): How well proposal fits local evidence (from Quad scores)
    - Backward score (sb): How well proposal aligns with Phase memory
    - Consistency: Agreement between forward and backward

    The BCVF Lagrangian penalizes:
    1. Low forward feasibility (proposal doesn't match context)
    2. Low backward alignment (proposal conflicts with Phase memory)
    3. Forward-backward disagreement (inconsistent proposal)

    Args:
        lambda_f: Forward feasibility weight (default 1.0).
        lambda_b: Backward alignment weight (default 1.0).
        lambda_c: Consistency penalty weight (default 0.5).
        beta: Sharpness of weighting (higher = sharper selection, default 2.0).
        normalize_phase: Whether to L2-normalize Phase state before similarity.
    """

    def __init__(
        self,
        lambda_f: float = 1.0,
        lambda_b: float = 1.0,
        lambda_c: float = 0.5,
        beta: float = 2.0,
        normalize_phase: bool = True,
    ):
        super().__init__()
        self.lambda_f = lambda_f
        self.lambda_b = lambda_b
        self.lambda_c = lambda_c
        self.beta = beta
        self.normalize_phase = normalize_phase

        # Instrumentation
        self._last_sf_mean = 0.0
        self._last_sb_mean = 0.0
        self._last_weight_entropy = 0.0

    def forward(
        self,
        proposals: Tensor,
        proposal_scores: Tensor,
        phase_state: Tensor,
    ) -> Tensor:
        """
        Compute BCVF-weighted proposals.

        Args:
            proposals: TopK retrieved proposals [B, N, K, D].
            proposal_scores: Raw retrieval scores [B, N, K].
            phase_state: Current Phase state [B, N, D].

        Returns:
            weighted_proposals: BCVF-weighted combination [B, N, D].
        """
        B, N, K, D = proposals.shape

        # Forward score: local evidence fit
        # Use sigmoid to bound in [0, 1]
        sf = torch.sigmoid(proposal_scores)  # [B, N, K]

        # Backward score: Phase memory alignment
        # Cosine similarity between proposals and Phase state
        if self.normalize_phase:
            phase_normalized = F.normalize(phase_state, dim=-1)
            proposals_normalized = F.normalize(proposals, dim=-1)
            sb = (proposals_normalized * phase_normalized.unsqueeze(2)).sum(dim=-1)
        else:
            sb = F.cosine_similarity(
                proposals,
                phase_state.unsqueeze(2),
                dim=-1
            )  # [B, N, K]

        # Bound sb to [0, 1] for consistent Lagrangian
        sb = (sb + 1) / 2  # Map from [-1, 1] to [0, 1]

        # BCVF Lagrangian (B1)
        L = (
            self.lambda_f * (1 - sf) ** 2 +
            self.lambda_b * (1 - sb) ** 2 +
            self.lambda_c * (sf - sb) ** 2
        )  # [B, N, K]

        # Consistency weights (B2 + B3)
        w = torch.exp(-self.beta * L)
        w = w / (w.sum(dim=-1, keepdim=True) + 1e-8)  # [B, N, K]

        # Weighted combination
        weighted = torch.sum(w.unsqueeze(-1) * proposals, dim=2)  # [B, N, D]

        # Update instrumentation
        with torch.no_grad():
            self._last_sf_mean = sf.mean().item()
            self._last_sb_mean = sb.mean().item()
            # Entropy of weights (higher = more uniform, lower = more peaked)
            self._last_weight_entropy = -(w * torch.log(w + 1e-8)).sum(dim=-1).mean().item()

        return weighted

    def forward_with_raw_weights(
        self,
        proposals: Tensor,
        proposal_scores: Tensor,
        phase_state: Tensor,
    ) -> tuple[Tensor, Tensor]:
        """
        Compute BCVF weights and return both weighted proposals and raw weights.

        Useful for combining with other weighting mechanisms.

        Args:
            proposals: TopK retrieved proposals [B, N, K, D].
            proposal_scores: Raw retrieval scores [B, N, K].
            phase_state: Current Phase state [B, N, D].

        Returns:
            weighted_proposals: BCVF-weighted combination [B, N, D].
            weights: Raw BCVF weights [B, N, K].
        """
        B, N, K, D = proposals.shape

        # Forward score
        sf = torch.sigmoid(proposal_scores)

        # Backward score
        if self.normalize_phase:
            phase_normalized = F.normalize(phase_state, dim=-1)
            proposals_normalized = F.normalize(proposals, dim=-1)
            sb = (proposals_normalized * phase_normalized.unsqueeze(2)).sum(dim=-1)
        else:
            sb = F.cosine_similarity(proposals, phase_state.unsqueeze(2), dim=-1)

        sb = (sb + 1) / 2

        # Lagrangian
        L = (
            self.lambda_f * (1 - sf) ** 2 +
            self.lambda_b * (1 - sb) ** 2 +
            self.lambda_c * (sf - sb) ** 2
        )

        # Weights
        w = torch.exp(-self.beta * L)
        w = w / (w.sum(dim=-1, keepdim=True) + 1e-8)

        # Weighted combination
        weighted = torch.sum(w.unsqueeze(-1) * proposals, dim=2)

        return weighted, w

    def get_instrumentation(self) -> Dict[str, float]:
        """Get diagnostic metrics from last forward pass."""
        return {
            "bcvf/sf_mean": self._last_sf_mean,
            "bcvf/sb_mean": self._last_sb_mean,
            "bcvf/weight_entropy": self._last_weight_entropy,
        }


class AdaptiveBCVFWeighter(nn.Module):
    """
    Adaptive BCVF with learned parameters.

    Extends BCVFQuadWeighter with learnable lambda and beta parameters
    that can adapt during training.

    Args:
        embed_dim: Model dimension for computing adaptive parameters.
        init_lambda_f: Initial forward weight.
        init_lambda_b: Initial backward weight.
        init_lambda_c: Initial consistency weight.
        init_beta: Initial sharpness.
    """

    def __init__(
        self,
        embed_dim: int,
        init_lambda_f: float = 1.0,
        init_lambda_b: float = 1.0,
        init_lambda_c: float = 0.5,
        init_beta: float = 2.0,
    ):
        super().__init__()

        # Learnable parameters (in log space for positivity)
        self.log_lambda_f = nn.Parameter(torch.tensor(init_lambda_f).log())
        self.log_lambda_b = nn.Parameter(torch.tensor(init_lambda_b).log())
        self.log_lambda_c = nn.Parameter(torch.tensor(init_lambda_c).log())
        self.log_beta = nn.Parameter(torch.tensor(init_beta).log())

        # Optional: condition parameters on timestep
        self.time_adapt = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.SiLU(),
            nn.Linear(64, 4),  # lambda_f, lambda_b, lambda_c, beta
        )

        # Initialize time adaptation to zero (start with base params)
        nn.init.zeros_(self.time_adapt[-1].weight)
        nn.init.zeros_(self.time_adapt[-1].bias)

    def forward(
        self,
        proposals: Tensor,
        proposal_scores: Tensor,
        phase_state: Tensor,
        time_embed: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Compute adaptively-weighted proposals.

        Args:
            proposals: TopK retrieved proposals [B, N, K, D].
            proposal_scores: Raw retrieval scores [B, N, K].
            phase_state: Current Phase state [B, N, D].
            time_embed: Optional timestep embedding [B, D] for adaptation.

        Returns:
            weighted_proposals: Weighted combination [B, N, D].
        """
        B, N, K, D = proposals.shape

        # Get base parameters
        lambda_f = self.log_lambda_f.exp()
        lambda_b = self.log_lambda_b.exp()
        lambda_c = self.log_lambda_c.exp()
        beta = self.log_beta.exp()

        # Optionally adapt based on timestep
        if time_embed is not None:
            deltas = self.time_adapt(time_embed)  # [B, 4]
            delta_f, delta_b, delta_c, delta_beta = deltas.unbind(dim=-1)
            lambda_f = lambda_f * (1 + delta_f).unsqueeze(-1).unsqueeze(-1)
            lambda_b = lambda_b * (1 + delta_b).unsqueeze(-1).unsqueeze(-1)
            lambda_c = lambda_c * (1 + delta_c).unsqueeze(-1).unsqueeze(-1)
            beta = beta * (1 + delta_beta).unsqueeze(-1).unsqueeze(-1)

        # Forward score
        sf = torch.sigmoid(proposal_scores)

        # Backward score
        phase_normalized = F.normalize(phase_state, dim=-1)
        proposals_normalized = F.normalize(proposals, dim=-1)
        sb = (proposals_normalized * phase_normalized.unsqueeze(2)).sum(dim=-1)
        sb = (sb + 1) / 2

        # Lagrangian with adaptive parameters
        L = (
            lambda_f * (1 - sf) ** 2 +
            lambda_b * (1 - sb) ** 2 +
            lambda_c * (sf - sb) ** 2
        )

        # Weights
        w = torch.exp(-beta * L)
        w = w / (w.sum(dim=-1, keepdim=True) + 1e-8)

        # Weighted combination
        return torch.sum(w.unsqueeze(-1) * proposals, dim=2)


class HybridBCVFCrossAttention(nn.Module):
    """
    Hybrid combining BCVF weighting with cross-attention.

    Uses BCVF weights as soft guidance for cross-attention,
    providing smooth transition between pure BCVF and pure cross-attention.

    Args:
        embed_dim: Model dimension.
        num_heads: Number of attention heads.
        bcvf_config: BCVF configuration dict.
        mix_ratio: Ratio of BCVF vs cross-attention (0 = pure cross-attn, 1 = pure BCVF).
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        bcvf_config: Optional[Dict] = None,
        mix_ratio: float = 0.5,
    ):
        super().__init__()

        from symbolu.vision.cross_attention_proposals import CrossAttentionToProposals

        bcvf_config = bcvf_config or {}
        self.bcvf = BCVFQuadWeighter(**bcvf_config)
        self.cross_attn = CrossAttentionToProposals(embed_dim, num_heads)

        # Learnable mixing ratio
        self.mix_ratio = nn.Parameter(torch.tensor(mix_ratio))

    def forward(
        self,
        x: Tensor,
        proposals: Tensor,
        proposal_scores: Tensor,
        phase_state: Tensor,
    ) -> Tensor:
        """
        Hybrid BCVF + cross-attention proposal integration.

        Args:
            x: Current representation [B, N, D].
            proposals: TopK proposals [B, N, K, D].
            proposal_scores: Retrieval scores [B, N, K].
            phase_state: Phase state [B, N, D].

        Returns:
            output: Integrated proposals [B, N, D].
        """
        # BCVF path
        bcvf_out = self.bcvf(proposals, proposal_scores, phase_state)

        # Cross-attention path (uses original scores as bias)
        cross_out = self.cross_attn(x, proposals, proposal_scores)

        # Mix
        ratio = torch.sigmoid(self.mix_ratio)
        return ratio * bcvf_out + (1 - ratio) * cross_out
