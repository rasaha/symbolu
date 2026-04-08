"""
CrossAttentionToProposals: Rich interaction between positions and Quad proposals.

Instead of simple weighted sum of proposals, this module uses cross-attention
to allow each position to attend to its retrieved proposals with learned
query/key/value projections.

This addresses a core limitation where proposals were just blended instead
of being transformed based on the query context.
"""

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


class CrossAttentionToProposals(nn.Module):
    """
    Cross-attention from query positions to Quad proposals.

    Each position attends to its K retrieved proposals using standard
    multi-head cross-attention. The retrieval scores from QuadRetriever
    are used as attention bias to maintain the Quad ranking while still
    allowing rich interaction.

    Architecture:
        - Query: Current position representation
        - Key/Value: Retrieved proposals
        - Bias: Retrieval scores (soft guidance from Quad)

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        dropout: Attention dropout rate.
        use_score_bias: Whether to add retrieval scores as attention bias.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.0,
        use_score_bias: bool = True,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.use_score_bias = use_score_bias

        assert embed_dim % num_heads == 0, f"embed_dim {embed_dim} not divisible by num_heads {num_heads}"

        self.scale = self.head_dim ** -0.5

        # Projections
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Dropout
        self.attn_dropout = nn.Dropout(dropout)

        # Initialize output projection to zero for residual-friendly start
        nn.init.zeros_(self.out_proj.weight)
        nn.init.zeros_(self.out_proj.bias)

    def forward(
        self,
        x: Tensor,
        proposals: Tensor,
        scores: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Cross-attention from positions to their proposals.

        Args:
            x: Current representation [B, N, D]
            proposals: TopK retrieved proposals [B, N, K, D]
            scores: Optional retrieval scores for bias [B, N, K]

        Returns:
            out: Cross-attended output [B, N, D]
        """
        B, N, D = x.shape
        K = proposals.size(2)
        H = self.num_heads
        D_h = self.head_dim

        # Project queries from current position
        q = self.q_proj(x)  # [B, N, D]
        q = q.view(B, N, H, D_h)  # [B, N, H, D_h]

        # Project keys and values from proposals
        # Flatten proposals for efficient projection
        proposals_flat = proposals.view(B * N, K, D)
        k = self.k_proj(proposals_flat)  # [B*N, K, D]
        v = self.v_proj(proposals_flat)  # [B*N, K, D]

        # Reshape for multi-head attention
        k = k.view(B, N, K, H, D_h)  # [B, N, K, H, D_h]
        v = v.view(B, N, K, H, D_h)  # [B, N, K, H, D_h]

        # Rearrange for attention computation
        # q: [B, N, H, D_h] -> [B, N, H, 1, D_h]
        # k: [B, N, K, H, D_h] -> [B, N, H, K, D_h]
        q = q.unsqueeze(3)  # [B, N, H, 1, D_h]
        k = k.permute(0, 1, 3, 2, 4)  # [B, N, H, K, D_h]
        v = v.permute(0, 1, 3, 2, 4)  # [B, N, H, K, D_h]

        # Compute attention scores
        attn = (q @ k.transpose(-2, -1)) * self.scale  # [B, N, H, 1, K]

        # Add retrieval score bias if provided
        if self.use_score_bias and scores is not None:
            # Normalize scores to reasonable range
            score_bias = scores.unsqueeze(2).unsqueeze(3)  # [B, N, 1, 1, K]
            # Scale bias to not overwhelm learned attention
            attn = attn + score_bias * 0.5

        # Softmax over proposals
        attn = F.softmax(attn, dim=-1)  # [B, N, H, 1, K]
        attn = self.attn_dropout(attn)

        # Weighted combination of values
        out = attn @ v  # [B, N, H, 1, D_h]
        out = out.squeeze(3)  # [B, N, H, D_h]

        # Merge heads
        out = out.reshape(B, N, D)  # [B, N, D]

        # Output projection
        out = self.out_proj(out)

        return out


class GatedCrossAttentionToProposals(nn.Module):
    """
    Cross-attention to proposals with learned gating.

    Extends CrossAttentionToProposals with a learned gate that controls
    how much of the cross-attended result is added to the residual stream.

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        dropout: Attention dropout rate.
        use_score_bias: Whether to add retrieval scores as attention bias.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.0,
        use_score_bias: bool = True,
    ):
        super().__init__()

        self.cross_attn = CrossAttentionToProposals(
            embed_dim, num_heads, dropout, use_score_bias
        )

        # Learned gate (scalar per position)
        self.gate_proj = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 4),
            nn.SiLU(),
            nn.Linear(embed_dim // 4, 1),
            nn.Sigmoid(),
        )

    def forward(
        self,
        x: Tensor,
        proposals: Tensor,
        scores: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Gated cross-attention.

        Args:
            x: Current representation [B, N, D]
            proposals: TopK retrieved proposals [B, N, K, D]
            scores: Optional retrieval scores [B, N, K]

        Returns:
            out: Gated cross-attended output [B, N, D]
        """
        # Compute cross-attention
        attn_out = self.cross_attn(x, proposals, scores)

        # Compute gate
        gate = self.gate_proj(x)  # [B, N, 1]

        # Gated output
        return gate * attn_out


class HybridProposalMixer(nn.Module):
    """
    Hybrid mixer combining cross-attention and weighted sum.

    Provides a smooth transition path from the original GateMixer approach
    to the new cross-attention approach via a learned mixing coefficient.

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        dropout: Attention dropout rate.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.0,
    ):
        super().__init__()

        # Cross-attention path
        self.cross_attn = CrossAttentionToProposals(
            embed_dim, num_heads, dropout
        )

        # Weighted sum path (original approach)
        self.value_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj_weighted = nn.Linear(embed_dim, embed_dim)

        # Mixing coefficient (learned)
        # Starts at 0.5 to give both paths equal weight initially
        self.mix_coef = nn.Parameter(torch.tensor(0.5))

    def forward(
        self,
        x: Tensor,
        proposals: Tensor,
        scores: Tensor,
    ) -> Tensor:
        """
        Hybrid mixing of proposals.

        Args:
            x: Current representation [B, N, D]
            proposals: TopK retrieved proposals [B, N, K, D]
            scores: Retrieval scores [B, N, K]

        Returns:
            out: Mixed output [B, N, D]
        """
        # Cross-attention path
        cross_out = self.cross_attn(x, proposals, scores)

        # Weighted sum path
        B, N, K, D = proposals.shape
        v = self.value_proj(proposals)  # [B, N, K, D]

        # Normalize scores for weighted sum
        weights = F.softmax(scores, dim=-1)  # [B, N, K]
        weights = weights.unsqueeze(-1)  # [B, N, K, 1]

        weighted_out = (weights * v).sum(dim=2)  # [B, N, D]
        weighted_out = self.out_proj_weighted(weighted_out)

        # Mix the two paths
        mix = torch.sigmoid(self.mix_coef)
        out = mix * cross_out + (1 - mix) * weighted_out

        return out
