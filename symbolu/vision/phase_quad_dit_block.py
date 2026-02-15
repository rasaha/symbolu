"""
PhaseQuadDiTBlock: Phase-Quad block with DiT-style architectural improvements.

This module implements the improved Phase-Quad block that addresses core
architectural limitations identified in the baseline:

1. AdaLN-Zero conditioning (DiT-style) - Proper timestep adaptation
2. Timestep-dependent Phase strength - Prevent noise contamination
3. Cross-attention to proposals - Rich proposal interaction

Reference: Appendix H of PHASE_QUAD_IMAGE_GENERATOR_DESIGN.md
"""

from typing import Optional

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.vision.adaln_zero import AdaLNZero, FinalLayer
from symbolu.vision.alternative_attention import (
    AlternativeAttentionToProposals,
    PhaseQuadAttentionVariant,
)
from symbolu.vision.attention_normalizations import AttentionNormType
from symbolu.vision.cross_attention_proposals import CrossAttentionToProposals
from symbolu.vision.bcvf_weighter import BCVFQuadWeighter, HybridBCVFCrossAttention
from symbolu.vision.config import AlternativeAttentionConfig
from symbolu.vision.controls import (
    BlockControl,
    PhaseControl,
    QuadControl,
    PatchMeta,
)
from symbolu.vision.local_mixer import LocalMixer
from symbolu.vision.phase_integrator import PhaseIntegrator2D
from symbolu.vision.quad_retriever import QuadRetriever2D


def compute_phase_strength(
    timestep: Tensor,
    t_max: int = 1000,
    min_strength: float = 0.1,
    max_strength: float = 1.0,
) -> Tensor:
    """
    Compute timestep-dependent Phase integration strength.

    At high noise levels (early diffusion steps), Phase integration on
    noise creates meaningless "authority" that interferes with learning.
    This function scales Phase contribution based on timestep:

    - Early steps (high t, noisy): Low strength (min_strength)
    - Late steps (low t, clean): High strength (max_strength)

    Args:
        timestep: Timestep values [B] or [B, 1]
        t_max: Maximum timestep value
        min_strength: Minimum Phase strength (at t=t_max)
        max_strength: Maximum Phase strength (at t=0)

    Returns:
        strength: Phase strength [B, 1] in range [min_strength, max_strength]
    """
    # Ensure correct shape
    if timestep.dim() == 1:
        timestep = timestep.unsqueeze(-1)

    # Normalize to [0, 1] where 0 = clean (t=0), 1 = noisy (t=t_max)
    t_normalized = timestep.float() / t_max

    # Linear interpolation: max at t=0, min at t=t_max
    strength = max_strength - (max_strength - min_strength) * t_normalized

    return strength


class PhaseQuadDiTBlock(nn.Module):
    """
    Phase-Quad block with DiT-style improvements.

    Key enhancements over CognadeVisionBlock:

    1. **AdaLN-Zero conditioning**: DiT-style modulation with zero-init gates
       - Enables proper timestep-dependent behavior
       - Separate gates for attention and FFN paths
       - Stable training via zero-initialization

    2. **Timestep-dependent Phase strength**: Scales Phase contribution
       - Low strength at high noise (prevents noise contamination)
       - High strength at low noise (reinforces semantic structure)

    3. **Cross-attention to proposals**: Replaces simple weighted sum
       - Rich interaction between position and proposals
       - Learned query/key/value projections
       - Retrieval scores as attention bias

    Architecture:
        ```
        INPUT: x [B, N, D], t_emb [B, D], text_cond

        (A) AdaLN-Zero: Compute modulation parameters from timestep

        (B) LOCAL PATH: Windowed attention with text cross-attention
            x = x + gate_attn * LocalMixer(modulate(x))

        (C) PHASE INTEGRATOR: Bi-axial phase accumulation
            S = PhaseIntegrator2D(x) * phase_strength(timestep)

        (D) QUAD RETRIEVER: TopK proposal retrieval
            proposals, scores = QuadRetriever2D(x, S)

        (E) CROSS-ATTENTION: Position attends to proposals
            x = x + gate_attn * CrossAttn(x, proposals, scores)

        (F) FFN: With AdaLN-Zero gating
            x = x + gate_ffn * FFN(modulate(x))

        OUTPUT: x_out [B, N, D]
        ```

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        topk: Number of Quad proposals K.
        window_size: Local attention window size.
        ffn_ratio: FFN hidden dimension ratio.
        dropout: Dropout rate.
        use_cross_attn: Include cross-attention to text in LocalMixer.
        text_dim: Text embedding dimension.
        t_max: Maximum diffusion timestep (for phase strength calculation).
        phase_min_strength: Minimum Phase strength at t=t_max.
        phase_max_strength: Maximum Phase strength at t=0.
    """

    def __init__(
        self,
        embed_dim: int = 768,
        num_heads: int = 12,
        topk: int = 64,
        window_size: int = 8,
        ffn_ratio: float = 4.0,
        dropout: float = 0.1,
        use_cross_attn: bool = True,
        text_dim: Optional[int] = None,
        t_max: int = 1000,
        phase_min_strength: float = 0.1,
        phase_max_strength: float = 1.0,
        # BCVF configuration (Appendix I)
        use_bcvf: bool = True,
        bcvf_lambda_f: float = 1.0,
        bcvf_lambda_b: float = 1.0,
        bcvf_lambda_c: float = 0.5,
        bcvf_beta: float = 2.0,
        # Alternative attention normalization
        alt_attention: Optional[AlternativeAttentionConfig] = None,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.topk = topk
        self.t_max = t_max
        self.phase_min_strength = phase_min_strength
        self.phase_max_strength = phase_max_strength
        self.use_bcvf = use_bcvf
        self.use_alt_attention = alt_attention is not None and alt_attention.enabled

        # AdaLN-Zero conditioning
        self.adaln = AdaLNZero(embed_dim, embed_dim)

        # Local mixer (windowed attention + optional text cross-attention)
        self.local = LocalMixer(
            embed_dim,
            window_size,
            num_heads,
            use_cross_attn,
            text_dim,
            dropout,
        )

        # Phase integrator (bi-axial)
        self.phase2d = PhaseIntegrator2D(embed_dim, num_heads)

        # Quad retriever
        self.quad = QuadRetriever2D(embed_dim, num_heads, topk)

        # Proposal integration: select based on configuration
        self._build_proposal_mixer(
            embed_dim, num_heads, dropout, use_bcvf,
            bcvf_lambda_f, bcvf_lambda_b, bcvf_lambda_c, bcvf_beta,
            alt_attention,
        )

        # Alt attention module (set by _build_proposal_mixer, used in forward)
        # Declared here for type clarity; actual instance created above.
        if not hasattr(self, "alt_proposal_mixer"):
            self.alt_proposal_mixer = None

        # Layer norms for pre-normalization
        self.norm_local = nn.LayerNorm(embed_dim)
        self.norm_cross = nn.LayerNorm(embed_dim)
        self.norm_ffn = nn.LayerNorm(embed_dim)

        # FFN
        ffn_hidden = int(embed_dim * ffn_ratio)
        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, ffn_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ffn_hidden, embed_dim),
            nn.Dropout(dropout),
        )

        # Zero-init output projections for residual-friendly start
        self._zero_init_outputs()

    def _build_proposal_mixer(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float,
        use_bcvf: bool,
        bcvf_lambda_f: float,
        bcvf_lambda_b: float,
        bcvf_lambda_c: float,
        bcvf_beta: float,
        alt_attention: Optional[AlternativeAttentionConfig],
    ):
        """
        Build the proposal integration module based on configuration.

        Priority order:
        1. Alternative attention (if alt_attention.enabled):
           - With BCVF: PhaseQuadAttentionVariant (BCVF + entmax hybrid)
           - Without BCVF: AlternativeAttentionToProposals (pure entmax)
        2. BCVF hybrid (if use_bcvf): HybridBCVFCrossAttention (original)
        3. Pure softmax cross-attention: CrossAttentionToProposals (original)
        """
        bcvf_config = {
            "lambda_f": bcvf_lambda_f,
            "lambda_b": bcvf_lambda_b,
            "lambda_c": bcvf_lambda_c,
            "beta": bcvf_beta,
        }

        if self.use_alt_attention and alt_attention is not None:
            # Resolve norm type string -> enum
            norm_type = AttentionNormType(alt_attention.norm_type)

            if alt_attention.mix_with_bcvf and use_bcvf:
                # BCVF + alternative attention hybrid (recommended)
                self.proposal_mixer = None
                self.cross_attn_proposals = None
                self.alt_proposal_mixer = PhaseQuadAttentionVariant(
                    embed_dim=embed_dim,
                    num_heads=num_heads,
                    norm_type=norm_type,
                    entmax_alpha=alt_attention.entmax_alpha,
                    bcvf_config=bcvf_config,
                    mix_ratio=alt_attention.bcvf_mix_ratio,
                    temperature_init=alt_attention.logit_temperature_init,
                    learn_temperature=alt_attention.learn_temperature,
                    top_m=alt_attention.top_m,
                )
            else:
                # Pure alternative attention (no BCVF)
                self.proposal_mixer = None
                self.cross_attn_proposals = None
                self.alt_proposal_mixer = AlternativeAttentionToProposals(
                    embed_dim=embed_dim,
                    num_heads=num_heads,
                    dropout=dropout,
                    norm_type=norm_type,
                    entmax_alpha=alt_attention.entmax_alpha,
                    score_bias_scale=alt_attention.score_bias_scale,
                    temperature_init=alt_attention.logit_temperature_init,
                    learn_temperature=alt_attention.learn_temperature,
                    top_m=alt_attention.top_m,
                )
        elif use_bcvf:
            # Original: BCVF + softmax cross-attention hybrid (Appendix I)
            self.proposal_mixer = HybridBCVFCrossAttention(
                embed_dim=embed_dim,
                num_heads=num_heads,
                bcvf_config=bcvf_config,
            )
            self.cross_attn_proposals = None
            self.alt_proposal_mixer = None
        else:
            # Original: Pure softmax cross-attention (Appendix H)
            self.proposal_mixer = None
            self.cross_attn_proposals = CrossAttentionToProposals(
                embed_dim, num_heads, dropout, use_score_bias=True
            )
            self.alt_proposal_mixer = None

    def _zero_init_outputs(self):
        """Zero-initialize output projections for stable training."""
        # FFN last linear
        if hasattr(self.ffn[-2], 'weight'):
            nn.init.zeros_(self.ffn[-2].weight)
            nn.init.zeros_(self.ffn[-2].bias)

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        time_embed: Tensor,
        text_cond: Optional[Tensor] = None,
        timestep: Optional[Tensor] = None,
        control: Optional[BlockControl] = None,
    ) -> Tensor:
        """
        Forward pass with DiT-style conditioning.

        Args:
            x: Input tokens [B, N, D]
            meta: PatchMeta with spatial info
            time_embed: Timestep embedding [B, D]
            text_cond: Optional text embeddings [B, T, D_t]
            timestep: Raw timestep values [B] for phase strength calculation.
                      If None, uses maximum phase strength (assumes clean input).
            control: Optional BlockControl for ablation testing

        Returns:
            x_out: [B, N, D] output tokens
        """
        # Get control settings
        enable_quad = control.enable_quad if control else True
        enable_phase = control.enable_phase if control else True
        enable_local = control.enable_local if control else True

        # AdaLN-Zero: compute all modulation parameters
        (
            x_norm, shift_attn, scale_attn, gate_attn,
            shift_ffn, scale_ffn, gate_ffn
        ) = self.adaln(x, time_embed)

        # Local path with modulation and gating
        if enable_local:
            x_local_in = self.adaln.modulate(
                self.norm_local(x), shift_attn, scale_attn
            )
            x_local = self.local(x_local_in, meta, text_cond)
            x = x + gate_attn * x_local

        # Phase path with timestep-dependent strength
        if enable_phase:
            phase_control = control.get_phase_control() if control else None
            S = self.phase2d(x, meta, phase_control)

            # Scale Phase contribution based on timestep
            if timestep is not None:
                phase_strength = compute_phase_strength(
                    timestep, self.t_max,
                    self.phase_min_strength, self.phase_max_strength
                )
                # Expand for broadcasting with state tensor
                while phase_strength.dim() < S.dim():
                    phase_strength = phase_strength.unsqueeze(-1)
                S = S * phase_strength
        else:
            # Ablation: Replace with mean pooling
            S = x.mean(dim=1, keepdim=True).expand_as(x)

        # Quad retrieval
        quad_control = QuadControl(enable_quad=enable_quad)
        proposals, scores = self.quad(x, S, meta, quad_control)

        # Proposal integration: alternative attention, BCVF hybrid, or pure cross-attention
        x_cross_in = self.adaln.modulate(
            self.norm_cross(x), shift_attn, scale_attn
        )

        if self.use_alt_attention and self.alt_proposal_mixer is not None:
            # Alternative attention normalization (entmax/sparsemax/kernel)
            if isinstance(self.alt_proposal_mixer, PhaseQuadAttentionVariant):
                # BCVF + alternative attention hybrid
                x_cross = self.alt_proposal_mixer(x_cross_in, proposals, scores, S)
            else:
                # Pure alternative attention
                x_cross = self.alt_proposal_mixer(x_cross_in, proposals, scores)
        elif self.use_bcvf and self.proposal_mixer is not None:
            # Original: Hybrid BCVF + softmax Cross-attention (Appendix I)
            x_cross = self.proposal_mixer(x_cross_in, proposals, scores, S)
        else:
            # Original: Pure softmax cross-attention (Appendix H)
            x_cross = self.cross_attn_proposals(x_cross_in, proposals, scores)

        x = x + gate_attn * x_cross

        # FFN with modulation and gating
        x_ffn_in = self.adaln.modulate(
            self.norm_ffn(x), shift_ffn, scale_ffn
        )
        x = x + gate_ffn * self.ffn(x_ffn_in)

        return x

    def get_diagnostics(self) -> dict:
        """Get diagnostic metrics from all components."""
        diagnostics = {}

        # Phase health
        phase_metrics = self.phase2d.get_health_metrics()
        for k, v in phase_metrics.items():
            diagnostics[f"phase/{k}"] = v

        # Quad metrics
        quad_metrics = self.quad.get_instrumentation()
        for k, v in quad_metrics.items():
            diagnostics[f"quad/{k}"] = v

        # Alternative attention metrics (sparsity, BCVF, mix ratio)
        if self.use_alt_attention and self.alt_proposal_mixer is not None:
            if hasattr(self.alt_proposal_mixer, "get_diagnostics"):
                alt_metrics = self.alt_proposal_mixer.get_diagnostics()
                for k, v in alt_metrics.items():
                    diagnostics[f"alt_attn/{k}"] = v
            elif hasattr(self.alt_proposal_mixer, "get_sparsity_metrics"):
                sp_metrics = self.alt_proposal_mixer.get_sparsity_metrics()
                for k, v in sp_metrics.items():
                    diagnostics[f"alt_attn/{k}"] = v
        # BCVF metrics (original path)
        elif self.use_bcvf and self.proposal_mixer is not None:
            bcvf_metrics = self.proposal_mixer.bcvf.get_instrumentation()
            for k, v in bcvf_metrics.items():
                diagnostics[k] = v

        return diagnostics


class PhaseQuadDiTBlockStack(nn.Module):
    """
    Stack of PhaseQuadDiTBlocks.

    Provides convenience for creating multiple blocks with shared configuration.

    Args:
        num_blocks: Number of blocks to stack.
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        topk: Number of Quad proposals K.
        window_size: Local attention window size.
        ffn_ratio: FFN hidden dimension ratio.
        dropout: Dropout rate.
        use_cross_attn: Include cross-attention to text.
        text_dim: Text embedding dimension.
        t_max: Maximum diffusion timestep.
        use_bcvf: Enable BCVF proposal weighting.
        bcvf_lambda_f: BCVF forward weight.
        bcvf_lambda_b: BCVF backward weight.
        bcvf_lambda_c: BCVF consistency weight.
        bcvf_beta: BCVF sharpness.
        alt_attention: Alternative attention config (entmax/sparsemax/kernel).
    """

    def __init__(
        self,
        num_blocks: int,
        embed_dim: int = 768,
        num_heads: int = 12,
        topk: int = 64,
        window_size: int = 8,
        ffn_ratio: float = 4.0,
        dropout: float = 0.1,
        use_cross_attn: bool = True,
        text_dim: Optional[int] = None,
        t_max: int = 1000,
        use_bcvf: bool = True,
        bcvf_lambda_f: float = 1.0,
        bcvf_lambda_b: float = 1.0,
        bcvf_lambda_c: float = 0.5,
        bcvf_beta: float = 2.0,
        alt_attention: Optional[AlternativeAttentionConfig] = None,
    ):
        super().__init__()

        self.num_blocks = num_blocks
        self.embed_dim = embed_dim

        self.blocks = nn.ModuleList([
            PhaseQuadDiTBlock(
                embed_dim=embed_dim,
                num_heads=num_heads,
                topk=topk,
                window_size=window_size,
                ffn_ratio=ffn_ratio,
                dropout=dropout,
                use_cross_attn=use_cross_attn,
                text_dim=text_dim,
                t_max=t_max,
                use_bcvf=use_bcvf,
                bcvf_lambda_f=bcvf_lambda_f,
                bcvf_lambda_b=bcvf_lambda_b,
                bcvf_lambda_c=bcvf_lambda_c,
                bcvf_beta=bcvf_beta,
                alt_attention=alt_attention,
            )
            for _ in range(num_blocks)
        ])

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        time_embed: Tensor,
        text_cond: Optional[Tensor] = None,
        timestep: Optional[Tensor] = None,
        control: Optional[BlockControl] = None,
    ) -> Tensor:
        """
        Forward through all blocks.

        Args:
            x: Input tokens [B, N, D]
            meta: PatchMeta with spatial info
            time_embed: Timestep embedding [B, D]
            text_cond: Optional text embeddings
            timestep: Raw timestep values [B]
            control: Optional control (applied to all blocks)

        Returns:
            x: Output tokens [B, N, D]
        """
        for block in self.blocks:
            x = block(x, meta, time_embed, text_cond, timestep, control)
        return x

    def get_all_diagnostics(self) -> dict:
        """Get diagnostics from all blocks."""
        all_diagnostics = {}
        for i, block in enumerate(self.blocks):
            block_diag = block.get_diagnostics()
            for k, v in block_diag.items():
                all_diagnostics[f"block_{i}/{k}"] = v
        return all_diagnostics
