"""
Alternative attention modules for Phase-Quad architecture.

Drop-in replacements for CrossAttentionToProposals that use different
attention normalizations (sparsemax, entmax, kernel attention) instead
of standard softmax.

Each module preserves the same interface:
    forward(x, proposals, scores) -> Tensor [B, N, D]

This enables controlled A/B experiments within the Phase-Quad block
by swapping only the proposal integration path.

Integration points in Phase-Quad:
1. CrossAttentionToProposals (primary): Softmax over K proposals
2. LocalMixer (secondary): Uses nn.MultiheadAttention (separate concern)
3. BCVF weighter: Uses exp(-beta*L) normalization (keeps its own)

The alternative normalizations here target integration point 1,
where sparsity directly improves TopK proposal selection quality.
"""

from typing import Optional, Dict, Literal
import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from symbolu.vision.attention_normalizations import (
    AttentionNormType,
    sparsemax,
    entmax,
    entmax15,
    KernelAttention,
    attention_sparsity_metrics,
    logit_sharpness_metrics,
)


class AlternativeAttentionToProposals(nn.Module):
    """
    Cross-attention from query positions to Quad proposals with
    configurable attention normalization.

    Drop-in replacement for CrossAttentionToProposals that supports
    softmax, sparsemax, entmax(alpha), and kernel attention.

    For Phase-Quad, the recommended configuration is entmax(1.3) because:
    - Moderate sparsity aligns with TopK proposal selection
    - Smoother gradients than entmax(1.5) or sparsemax
    - Compatible with BCVF consistency filtering
    - Reduces noise from irrelevant proposals while keeping gradient signal strong

    Architecture:
        Query: Current position representation [B, N, D]
        Key/Value: Retrieved proposals [B, N, K, D]
        Bias: Retrieval scores (soft guidance from Quad)
        Normalization: Configurable (softmax | sparsemax | entmax | kernel)

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        dropout: Attention dropout rate.
        use_score_bias: Whether to add retrieval scores as attention bias.
        norm_type: Attention normalization type.
        entmax_alpha: Alpha parameter for entmax (only used if norm_type is entmax).
        score_bias_scale: Scale factor for retrieval score bias (default 0.5).
        temperature_init: Initial logit temperature value (default 1.0).
        learn_temperature: If True, temperature is a learned parameter (default True).
    """

    # Clamp bounds for temperature to prevent degenerate regimes:
    #   < 0.05 -> near-argmax (gradient vanishes)
    #   > 10.0 -> near-uniform (no selectivity)
    TEMPERATURE_MIN = 0.05
    TEMPERATURE_MAX = 10.0

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.0,
        use_score_bias: bool = True,
        norm_type: AttentionNormType = AttentionNormType.ENTMAX_ALPHA,
        entmax_alpha: float = 1.3,
        score_bias_scale: float = 0.5,
        temperature_init: float = 1.0,
        learn_temperature: bool = True,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.use_score_bias = use_score_bias
        self.norm_type = norm_type
        self.entmax_alpha = entmax_alpha
        self.score_bias_scale = score_bias_scale

        assert embed_dim % num_heads == 0, (
            f"embed_dim {embed_dim} not divisible by num_heads {num_heads}"
        )

        self.scale = self.head_dim ** -0.5

        # Projections
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Logit temperature: controls "pressure" on entmax/sparsemax.
        # Stored in log-space so exp() is always positive.
        # Clamped to [TEMPERATURE_MIN, TEMPERATURE_MAX] in forward.
        log_temp = torch.tensor(math.log(temperature_init))
        if learn_temperature:
            self.log_temperature = nn.Parameter(log_temp)
        else:
            self.register_buffer("log_temperature", log_temp)

        # Dropout
        self.attn_dropout = nn.Dropout(dropout)

        # Kernel attention module (only for kernel types)
        self._kernel_attn = None
        if norm_type in (AttentionNormType.KERNEL_ELU, AttentionNormType.KERNEL_RBF):
            feature_map = "elu" if norm_type == AttentionNormType.KERNEL_ELU else "rbf"
            self._kernel_attn = KernelAttention(
                feature_map=feature_map,
                head_dim=self.head_dim,
            )

        # Zero-init output projection for residual-friendly start
        nn.init.zeros_(self.out_proj.weight)
        nn.init.zeros_(self.out_proj.bias)

        # Instrumentation
        self._last_sparsity_metrics: Dict[str, float] = {}
        self._last_logit_metrics: Dict[str, float] = {}

    def _normalize_scores(self, attn: Tensor) -> Tensor:
        """
        Apply the configured attention normalization.

        Args:
            attn: Raw attention scores [B, N, H, 1, K].

        Returns:
            Normalized attention weights [B, N, H, 1, K].
        """
        if self.norm_type == AttentionNormType.SOFTMAX:
            return F.softmax(attn, dim=-1)
        elif self.norm_type == AttentionNormType.SPARSEMAX:
            return sparsemax(attn, dim=-1)
        elif self.norm_type == AttentionNormType.ENTMAX15:
            return entmax15(attn, dim=-1)
        elif self.norm_type == AttentionNormType.ENTMAX_ALPHA:
            return entmax(attn, alpha=self.entmax_alpha, dim=-1)
        else:
            # Kernel attention handled separately in forward()
            raise ValueError(
                f"Normalization {self.norm_type} should not reach _normalize_scores"
            )

    def forward(
        self,
        x: Tensor,
        proposals: Tensor,
        scores: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Cross-attention from positions to their proposals.

        Args:
            x: Current representation [B, N, D].
            proposals: TopK retrieved proposals [B, N, K, D].
            scores: Optional retrieval scores for bias [B, N, K].

        Returns:
            out: Cross-attended output [B, N, D].
        """
        B, N, D = x.shape
        K = proposals.size(2)
        H = self.num_heads
        D_h = self.head_dim

        # Project queries from current position
        q = self.q_proj(x).view(B, N, H, D_h)

        # Project keys and values from proposals
        proposals_flat = proposals.view(B * N, K, D)
        k = self.k_proj(proposals_flat).view(B, N, K, H, D_h)
        v = self.v_proj(proposals_flat).view(B, N, K, H, D_h)

        # Handle kernel attention separately (no explicit score computation)
        if self._kernel_attn is not None:
            return self._forward_kernel(q, k, v, B, N, K, H, D_h, D, scores)

        # Standard score-based attention with alternative normalization
        # q: [B, N, H, D_h] -> [B, N, H, 1, D_h]
        # k: [B, N, K, H, D_h] -> [B, N, H, K, D_h]
        q = q.unsqueeze(3)
        k = k.permute(0, 1, 3, 2, 4)
        v = v.permute(0, 1, 3, 2, 4)

        # Compute attention scores
        attn = (q @ k.transpose(-2, -1)) * self.scale  # [B, N, H, 1, K]

        # Add retrieval score bias if provided
        if self.use_score_bias and scores is not None:
            score_bias = scores.unsqueeze(2).unsqueeze(3)  # [B, N, 1, 1, K]
            attn = attn + score_bias * self.score_bias_scale

        # Apply temperature: controls logit sharpness ("pressure") before
        # entmax/sparsemax normalization. Without this, Q/K weight drift
        # during training changes effective sparsity unpredictably.
        temperature = self.log_temperature.exp()
        temperature = torch.clamp(
            temperature, self.TEMPERATURE_MIN, self.TEMPERATURE_MAX
        )
        attn = attn / temperature

        # Track logit sharpness BEFORE normalization
        with torch.no_grad():
            self._last_logit_metrics = logit_sharpness_metrics(attn, dim=-1)
            self._last_logit_metrics["temperature"] = temperature.item()

        # Apply configured normalization
        attn_weights = self._normalize_scores(attn)

        # Track sparsity metrics AFTER normalization
        with torch.no_grad():
            self._last_sparsity_metrics = attention_sparsity_metrics(
                attn_weights.squeeze(3), dim=-1
            )

        attn_weights = self.attn_dropout(attn_weights)

        # Weighted combination
        out = attn_weights @ v  # [B, N, H, 1, D_h]
        out = out.squeeze(3).reshape(B, N, D)

        # Output projection
        out = self.out_proj(out)
        return out

    def _forward_kernel(
        self,
        q: Tensor,
        k: Tensor,
        v: Tensor,
        B: int,
        N: int,
        K: int,
        H: int,
        D_h: int,
        D: int,
        scores: Optional[Tensor],
    ) -> Tensor:
        """
        Forward pass using kernel (linear) attention.

        For kernel attention over K proposals per position, we reshape
        to standard attention format and use the kernel attention module.

        Args:
            q: [B, N, H, D_h]
            k: [B, N, K, H, D_h]
            v: [B, N, K, H, D_h]
            scores: Optional retrieval scores [B, N, K].
        """
        # Reshape for kernel attention: treat each position independently
        # q: [B, N, H, D_h] -> [B*N, H, 1, D_h]
        q = q.reshape(B * N, H, 1, D_h)

        # k, v: [B, N, K, H, D_h] -> [B*N, H, K, D_h]
        k = k.permute(0, 1, 3, 2, 4).reshape(B * N, H, K, D_h)
        v = v.permute(0, 1, 3, 2, 4).reshape(B * N, H, K, D_h)

        # Apply kernel attention
        out = self._kernel_attn(q, k, v)  # [B*N, H, 1, D_h]

        # Reshape back
        out = out.squeeze(2).reshape(B, N, D)

        # Track approximate sparsity
        with torch.no_grad():
            self._last_sparsity_metrics = {
                "sparsity": 0.0,  # Kernel attention has no exact zeros
                "entropy": float("nan"),
                "normalized_entropy": float("nan"),
                "top1_mass": float("nan"),
                "top5_mass": float("nan"),
                "gini": float("nan"),
            }

        return self.out_proj(out)

    def get_sparsity_metrics(self) -> Dict[str, float]:
        """Get sparsity and logit sharpness diagnostics from the last forward pass."""
        metrics = {
            f"attn/{k}": v for k, v in self._last_sparsity_metrics.items()
        }
        for k, v in self._last_logit_metrics.items():
            metrics[f"attn/{k}"] = v
        return metrics


class PhaseQuadAttentionVariant(nn.Module):
    """
    Complete Phase-Quad proposal integration with alternative attention.

    Combines BCVF consistency filtering with alternative attention
    normalization. This is the recommended integration pattern:

    1. BCVF filters proposals for consistency (unchanged)
    2. Alternative attention provides sparse/controlled weighting
    3. Learned mixing ratio between BCVF and attention paths

    This replaces HybridBCVFCrossAttention when using alternative
    attention normalizations.

    Args:
        embed_dim: Model dimension.
        num_heads: Number of attention heads.
        norm_type: Attention normalization type.
        entmax_alpha: Alpha for entmax (if applicable).
        bcvf_config: BCVF configuration dict.
        mix_ratio: Initial BCVF vs attention mix (0=pure attn, 1=pure BCVF).
        temperature_init: Initial logit temperature (default 1.0).
        learn_temperature: Whether temperature is trainable (default True).
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        norm_type: AttentionNormType = AttentionNormType.ENTMAX_ALPHA,
        entmax_alpha: float = 1.3,
        bcvf_config: Optional[Dict] = None,
        mix_ratio: float = 0.5,
        temperature_init: float = 1.0,
        learn_temperature: bool = True,
    ):
        super().__init__()

        from symbolu.vision.bcvf_weighter import BCVFQuadWeighter

        bcvf_config = bcvf_config or {}
        self.bcvf = BCVFQuadWeighter(**bcvf_config)

        self.alt_attn = AlternativeAttentionToProposals(
            embed_dim=embed_dim,
            num_heads=num_heads,
            norm_type=norm_type,
            entmax_alpha=entmax_alpha,
            temperature_init=temperature_init,
            learn_temperature=learn_temperature,
        )

        self.mix_ratio = nn.Parameter(torch.tensor(mix_ratio))
        self.norm_type = norm_type

    def forward(
        self,
        x: Tensor,
        proposals: Tensor,
        proposal_scores: Tensor,
        phase_state: Tensor,
    ) -> Tensor:
        """
        Hybrid BCVF + alternative attention proposal integration.

        Args:
            x: Current representation [B, N, D].
            proposals: TopK proposals [B, N, K, D].
            proposal_scores: Retrieval scores [B, N, K].
            phase_state: Phase state [B, N, D].

        Returns:
            output: Integrated proposals [B, N, D].
        """
        # BCVF path (consistency filtering)
        bcvf_out = self.bcvf(proposals, proposal_scores, phase_state)

        # Alternative attention path
        attn_out = self.alt_attn(x, proposals, proposal_scores)

        # Mix
        ratio = torch.sigmoid(self.mix_ratio)
        return ratio * bcvf_out + (1 - ratio) * attn_out

    def get_diagnostics(self) -> Dict[str, float]:
        """Get combined diagnostics."""
        diagnostics = {}

        # BCVF metrics
        bcvf_metrics = self.bcvf.get_instrumentation()
        diagnostics.update(bcvf_metrics)

        # Attention sparsity metrics
        attn_metrics = self.alt_attn.get_sparsity_metrics()
        diagnostics.update(attn_metrics)

        # Mix ratio
        with torch.no_grad():
            diagnostics["mix_ratio"] = torch.sigmoid(self.mix_ratio).item()
            diagnostics["norm_type"] = self.norm_type.value

        return diagnostics
