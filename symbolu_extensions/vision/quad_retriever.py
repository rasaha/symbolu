"""
QuadRetriever2D: Sparse global retrieval from phase state via TopK proposals.

This module implements the Quad Retriever that queries the Phase state
to retrieve TopK proposals. Unlike full attention, this achieves O(N·K)
complexity for sparse global retrieval.

Key properties:
- Returns raw proposals WITHOUT softmax mixing
- Phase (via GateMixer) decides integration
- Uses STANDARD 2D RoPE (phase-modulated RoPE is deferred)
"""

from typing import Tuple, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from symbolu_extensions.vision.controls import QuadControl, PatchMeta
from symbolu_extensions.vision.rope_2d import RotaryPositionEmbedding2D, apply_2d_rope


class QuadRetriever2D(nn.Module):
    """
    Sparse global retrieval from phase state via TopK proposals.

    Extends BindingCacheQuadQuery for 2D with standard 2D RoPE.

    IMPORTANT: Uses STANDARD 2D RoPE for geometric awareness.
    Phase-modulated RoPE is explicitly NOT implemented (high coupling risk).

    Returns raw proposals WITHOUT softmax mixing.
    Phase (via GateMixer) decides integration.

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        topk: Number of proposals K to retrieve per position.
        use_2d_rope: Use standard 2D RoPE (recommended).
        chunk_size: Chunk size for memory-efficient retrieval (0 = no chunking).
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        topk: int = 64,
        use_2d_rope: bool = True,
        chunk_size: int = 0,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.topk = topk
        self.scale = self.head_dim ** -0.5
        self.chunk_size = chunk_size

        if embed_dim % num_heads != 0:
            raise ValueError(
                f"embed_dim ({embed_dim}) must be divisible by "
                f"num_heads ({num_heads})"
            )

        # Projections
        self.W_q = nn.Linear(embed_dim, embed_dim)
        self.W_k = nn.Linear(embed_dim, embed_dim)
        self.W_v = nn.Linear(embed_dim, embed_dim)

        # Layer norms
        self.norm_q = nn.LayerNorm(embed_dim)
        self.norm_s = nn.LayerNorm(embed_dim)

        # 2D RoPE (standard, not phase-modulated)
        self.use_2d_rope = use_2d_rope
        if use_2d_rope:
            self.rope = RotaryPositionEmbedding2D(self.head_dim)

        # Instrumentation
        self.register_buffer("_last_score_entropy", torch.tensor(0.0))
        self.register_buffer("_last_score_mean", torch.tensor(0.0))
        self.register_buffer("_last_score_std", torch.tensor(0.0))

    def forward(
        self,
        x: Tensor,
        S: Tensor,
        meta: PatchMeta,
        control: Optional[QuadControl] = None,
    ) -> Tuple[Tensor, Tensor]:
        """
        Retrieve TopK proposals from phase state.

        Args:
            x: Current tokens [B, N, D] - source for queries.
            S: Phase state [B, N, D] - from PhaseIntegrator2D.
            meta: PatchMeta with coords for 2D RoPE.
            control: Optional QuadControl containing:
                - enable_quad: bool (if False, return zeros)

        Returns:
            proposals: [B, N, K, D] - K proposals per position.
            scores: [B, N, K] - retrieval scores (raw, pre-sigmoid).
        """
        if control is not None and not control.enable_quad:
            B, N, D = x.shape
            K = self.topk
            return (
                torch.zeros(B, N, K, D, device=x.device, dtype=x.dtype),
                torch.zeros(B, N, K, device=x.device, dtype=x.dtype),
            )

        # Get score noise from control
        score_noise_std = 0.0
        if control is not None:
            score_noise_std = control.score_noise_std

        # Use chunked retrieval for large N
        if self.chunk_size > 0 and x.shape[1] > self.chunk_size:
            return self.forward_chunked(x, S, meta, self.chunk_size, score_noise_std)

        return self._forward_full(x, S, meta, score_noise_std)

    def _forward_full(
        self,
        x: Tensor,
        S: Tensor,
        meta: PatchMeta,
        score_noise_std: float = 0.0,
    ) -> Tuple[Tensor, Tensor]:
        """Full (non-chunked) forward pass."""
        B, N, D = x.shape
        H = self.num_heads
        D_h = self.head_dim
        K = min(self.topk, N)

        # Normalize
        x_norm = self.norm_q(x)
        S_norm = self.norm_s(S)

        # Project
        Q = self.W_q(x_norm).view(B, N, H, D_h)
        Keys = self.W_k(S_norm).view(B, N, H, D_h)
        V = self.W_v(S_norm).view(B, N, H, D_h)

        # Apply 2D RoPE (standard, geometry only)
        if self.use_2d_rope:
            coords = meta.coords.to(x.device)
            Q, Keys = apply_2d_rope(Q, Keys, coords, self.rope)

        # Transpose for attention: [B, N, H, D_h] -> [B, H, N, D_h]
        Q = Q.transpose(1, 2)
        Keys = Keys.transpose(1, 2)
        V = V.transpose(1, 2)

        # Compute scores: [B, H, N, N]
        scores = torch.matmul(Q, Keys.transpose(-2, -1)) * self.scale

        # Add score noise for creativity (if enabled)
        # Higher noise -> more surprising proposals enter TopK
        if score_noise_std > 0.0 and self.training is False:
            noise = torch.randn_like(scores) * score_noise_std
            scores = scores + noise

        # TopK selection - NO SOFTMAX
        top_scores, top_indices = scores.topk(K, dim=-1)  # [B, H, N, K]

        # Gather values using advanced indexing
        # V: [B, H, N, D_h]
        # top_indices: [B, H, N, K]
        # We need: top_V[b, h, n, k, :] = V[b, h, top_indices[b, h, n, k], :]

        # Expand indices for gathering
        # top_indices: [B, H, N, K] -> [B, H, N, K, 1] -> [B, H, N, K, D_h]
        top_indices_exp = top_indices.unsqueeze(-1).expand(-1, -1, -1, -1, D_h)

        # Expand V for gathering
        # V: [B, H, N, D_h] -> [B, H, 1, N, D_h] -> [B, H, N, N, D_h]
        V_exp = V.unsqueeze(2).expand(-1, -1, N, -1, -1)

        # Gather
        top_V = torch.gather(V_exp, 3, top_indices_exp)  # [B, H, N, K, D_h]

        # Reshape outputs
        # top_V: [B, H, N, K, D_h] -> [B, N, K, H, D_h] -> [B, N, K, D]
        proposals = top_V.permute(0, 2, 3, 1, 4).reshape(B, N, K, D)

        # Average scores across heads: [B, H, N, K] -> [B, N, K]
        proposal_scores = top_scores.permute(0, 2, 3, 1).mean(dim=-1)

        # Track diagnostics
        with torch.no_grad():
            probs = torch.softmax(proposal_scores, dim=-1)
            entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
            self._last_score_entropy = entropy
            self._last_score_mean = proposal_scores.mean()
            self._last_score_std = proposal_scores.std()

        return proposals, proposal_scores

    def forward_chunked(
        self,
        x: Tensor,
        S: Tensor,
        meta: PatchMeta,
        chunk_size: int = 1024,
        score_noise_std: float = 0.0,
    ) -> Tuple[Tensor, Tensor]:
        """
        Chunked Quad retrieval for large token counts.

        Per design doc E.2.3:
        - Chunk queries (not keys/values)
        - Keep Phase state global
        - Quad retrieves per chunk
        - Integrate chunk-local proposals

        Memory: O(chunk_size × K × D) instead of O(N × K × D)

        Args:
            x: Current tokens [B, N, D].
            S: Phase state [B, N, D].
            meta: PatchMeta with coords.
            chunk_size: Number of query positions per chunk.
            score_noise_std: Noise to add to scores for creativity.

        Returns:
            proposals: [B, N, K, D] - K proposals per position.
            scores: [B, N, K] - retrieval scores.
        """
        B, N, D = x.shape
        H = self.num_heads
        D_h = self.head_dim
        K = min(self.topk, N)

        # Normalize (full)
        x_norm = self.norm_q(x)
        S_norm = self.norm_s(S)

        # Project keys and values once (full)
        Keys = self.W_k(S_norm).view(B, N, H, D_h)
        V = self.W_v(S_norm).view(B, N, H, D_h)

        # Apply RoPE to keys
        if self.use_2d_rope:
            coords = meta.coords.to(x.device)
            Keys = self.rope(Keys, coords)

        # Transpose for attention
        Keys = Keys.transpose(1, 2)  # [B, H, N, D_h]
        V = V.transpose(1, 2)        # [B, H, N, D_h]

        # Initialize outputs
        all_proposals = []
        all_scores = []

        # Process in chunks
        for start in range(0, N, chunk_size):
            end = min(start + chunk_size, N)
            chunk_len = end - start

            # Get query chunk
            x_chunk = x_norm[:, start:end, :]
            Q_chunk = self.W_q(x_chunk).view(B, chunk_len, H, D_h)

            # Apply RoPE to queries
            if self.use_2d_rope:
                coords_chunk = coords[start:end]
                Q_chunk = self.rope(Q_chunk, coords_chunk)

            Q_chunk = Q_chunk.transpose(1, 2)  # [B, H, chunk_len, D_h]

            # Compute scores for this chunk
            scores_chunk = torch.matmul(Q_chunk, Keys.transpose(-2, -1)) * self.scale
            # [B, H, chunk_len, N]

            # Add score noise for creativity (if enabled)
            if score_noise_std > 0.0 and self.training is False:
                noise = torch.randn_like(scores_chunk) * score_noise_std
                scores_chunk = scores_chunk + noise

            # TopK selection
            top_scores, top_indices = scores_chunk.topk(K, dim=-1)
            # [B, H, chunk_len, K]

            # Gather values
            top_indices_exp = top_indices.unsqueeze(-1).expand(-1, -1, -1, -1, D_h)
            V_exp = V.unsqueeze(2).expand(-1, -1, chunk_len, -1, -1)
            top_V = torch.gather(V_exp, 3, top_indices_exp)
            # [B, H, chunk_len, K, D_h]

            # Reshape
            proposals_chunk = top_V.permute(0, 2, 3, 1, 4).reshape(B, chunk_len, K, D)
            scores_chunk = top_scores.permute(0, 2, 3, 1).mean(dim=-1)

            all_proposals.append(proposals_chunk)
            all_scores.append(scores_chunk)

        # Concatenate chunks
        proposals = torch.cat(all_proposals, dim=1)
        scores = torch.cat(all_scores, dim=1)

        return proposals, scores

    def get_instrumentation(self) -> dict:
        """Get diagnostic metrics."""
        return {
            "score_entropy": self._last_score_entropy.item(),
            "score_mean": self._last_score_mean.item(),
            "score_std": self._last_score_std.item(),
        }


class QuadRetriever(nn.Module):
    """
    Simple QuadRetriever without 2D RoPE (for video/3D use cases).

    This is a simplified version of QuadRetriever2D that doesn't require
    positional metadata. Useful for video generation where 3D positions
    are handled differently.

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        topk: Number of proposals K to retrieve per position.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        topk: int = 64,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.topk = topk
        self.scale = self.head_dim ** -0.5

        if embed_dim % num_heads != 0:
            raise ValueError(
                f"embed_dim ({embed_dim}) must be divisible by "
                f"num_heads ({num_heads})"
            )

        # Projections
        self.W_q = nn.Linear(embed_dim, embed_dim)
        self.W_k = nn.Linear(embed_dim, embed_dim)
        self.W_v = nn.Linear(embed_dim, embed_dim)

        # Layer norms
        self.norm_q = nn.LayerNorm(embed_dim)
        self.norm_s = nn.LayerNorm(embed_dim)

        # Instrumentation
        self.register_buffer("_last_score_entropy", torch.tensor(0.0))
        self.register_buffer("_last_score_mean", torch.tensor(0.0))
        self.register_buffer("_last_score_std", torch.tensor(0.0))

    def forward(
        self,
        x: Tensor,
        S: Tensor,
        score_noise_std: float = 0.0,
    ) -> Tuple[Tensor, Tensor]:
        """
        Retrieve TopK proposals from phase state.

        Args:
            x: Current tokens [B, N, D] - source for queries.
            S: Phase state [B, N, D] - from PhaseIntegrator.
            score_noise_std: Noise to add to scores for creativity.

        Returns:
            proposals: [B, N, K, D] - K proposals per position.
            scores: [B, N, K] - retrieval scores (raw, pre-sigmoid).
        """
        B, N, D = x.shape
        H = self.num_heads
        D_h = self.head_dim
        K = min(self.topk, N)

        # Normalize
        x_norm = self.norm_q(x)
        S_norm = self.norm_s(S)

        # Project
        Q = self.W_q(x_norm).view(B, N, H, D_h)
        Keys = self.W_k(S_norm).view(B, N, H, D_h)
        V = self.W_v(S_norm).view(B, N, H, D_h)

        # Transpose for attention: [B, N, H, D_h] -> [B, H, N, D_h]
        Q = Q.transpose(1, 2)
        Keys = Keys.transpose(1, 2)
        V = V.transpose(1, 2)

        # Compute scores: [B, H, N, N]
        scores = torch.matmul(Q, Keys.transpose(-2, -1)) * self.scale

        # Add score noise for creativity (if enabled)
        if score_noise_std > 0.0 and self.training is False:
            noise = torch.randn_like(scores) * score_noise_std
            scores = scores + noise

        # TopK selection - NO SOFTMAX
        top_scores, top_indices = scores.topk(K, dim=-1)  # [B, H, N, K]

        # Gather values
        top_indices_exp = top_indices.unsqueeze(-1).expand(-1, -1, -1, -1, D_h)
        V_exp = V.unsqueeze(2).expand(-1, -1, N, -1, -1)
        top_V = torch.gather(V_exp, 3, top_indices_exp)  # [B, H, N, K, D_h]

        # Reshape outputs
        proposals = top_V.permute(0, 2, 3, 1, 4).reshape(B, N, K, D)

        # Average scores across heads: [B, H, N, K] -> [B, N, K]
        proposal_scores = top_scores.permute(0, 2, 3, 1).mean(dim=-1)

        # Track diagnostics
        with torch.no_grad():
            probs = torch.softmax(proposal_scores, dim=-1)
            entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
            self._last_score_entropy = entropy
            self._last_score_mean = proposal_scores.mean()
            self._last_score_std = proposal_scores.std()

        return proposals, proposal_scores

    def get_instrumentation(self) -> dict:
        """Get diagnostic metrics."""
        return {
            "score_entropy": self._last_score_entropy.item(),
            "score_mean": self._last_score_mean.item(),
            "score_std": self._last_score_std.item(),
        }
