"""
CognadeVisionBlock: Complete Phase-Quad vision block combining all components.

This is the main building block of the Phase-Quad Image Generator,
combining LocalMixer, PhaseIntegrator2D, QuadRetriever2D, and GateMixer.

Flow:
    1. x_local = LocalMixer(x)
    2. S = PhaseIntegrator2D(x_local)
    3. proposals, scores = QuadRetriever2D(x_local, S)
    4. x_out = GateMixer(x, proposals, scores)
    5. x_out = x_out + FFN(LN(x_out))
"""

from typing import Optional

import torch
import torch.nn as nn
from torch import Tensor

from symbolu_extensions.vision.controls import (
    BlockControl,
    PhaseControl,
    QuadControl,
    GateControl,
    PatchMeta,
)
from symbolu_extensions.vision.local_mixer import LocalMixer
from symbolu_extensions.vision.phase_integrator import PhaseIntegrator2D
from symbolu_extensions.vision.quad_retriever import QuadRetriever2D
from symbolu_extensions.vision.gate_mixer import GateMixer


class CognadeVisionBlock(nn.Module):
    """
    Complete Phase-Quad vision block combining all components.

    Architecture:
    ```
    INPUT: x [B, N, D], t_embed [B, D], text_control

    (A) LOCAL PATH (cheap, O(N·W))
        x_local = LocalMixer(x)

    (B) PHASE INTEGRATOR (O(N), bi-axial)
        S = PhaseIntegrator2D(x_local)

    (C) QUAD RETRIEVER (O(N·K), sparse)
        proposals, scores = QuadRetriever2D(x_local, S, K=64)

    (D) GATE MIXER (Phase decides integration)
        x_out = GateMixer(x, proposals, scores, tau)

    (E) FFN
        x_out = x_out + FFN(LN(x_out))

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
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.topk = topk

        # Components
        self.local = LocalMixer(
            embed_dim,
            window_size,
            num_heads,
            use_cross_attn,
            text_dim,
            dropout,
        )
        self.phase2d = PhaseIntegrator2D(embed_dim, num_heads)
        self.quad = QuadRetriever2D(embed_dim, num_heads, topk)
        self.mixer = GateMixer(embed_dim, num_heads)

        # Pre-norm for FFN
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

        # Timestep modulation (AdaLN-style)
        # Produces scale and shift for the block
        self.time_mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 2),
            nn.SiLU(),
            nn.Linear(embed_dim * 2, embed_dim * 2),
        )

        # For ablation: replace Phase with mean pooling
        self._ablation_phase_disabled = False

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        time_embed: Tensor,
        text_cond: Optional[Tensor] = None,
        control: Optional[BlockControl] = None,
    ) -> Tensor:
        """
        Forward pass through Cognade vision block.

        Args:
            x: Input tokens [B, N, D].
            meta: PatchMeta with spatial info.
            time_embed: Timestep embedding [B, D].
            text_cond: Optional text embeddings [B, T, D_t].
            control: Optional BlockControl containing:
                - enable_quad: bool
                - enable_phase: bool
                - enable_local: bool
                - tau: temperature for gating
                - phase_control: PhaseControl
                - gate_control: GateControl

        Returns:
            x_out: [B, N, D] output tokens.
        """
        # Get control settings
        enable_quad = control.enable_quad if control else True
        enable_phase = control.enable_phase if control else True
        enable_local = control.enable_local if control else True
        tau = control.tau if control else 1.0

        # Timestep modulation (scale and shift)
        time_params = self.time_mlp(time_embed)
        scale, shift = time_params.chunk(2, dim=-1)
        scale = scale.unsqueeze(1)  # [B, 1, D]
        shift = shift.unsqueeze(1)  # [B, 1, D]

        # Apply timestep modulation
        x = x * (1 + scale) + shift

        # Local path (O(N·W))
        if enable_local:
            x_local = self.local(x, meta, text_cond)
            x = x + x_local
        else:
            # Skip local mixing (for ablation)
            pass

        # Phase path (O(N))
        if enable_phase:
            phase_control = control.get_phase_control() if control else None
            S = self.phase2d(x, meta, phase_control)
        else:
            # Ablation: Replace with mean pooling
            S = x.mean(dim=1, keepdim=True).expand_as(x)

        # Quad path (O(N·K))
        quad_control = QuadControl(enable_quad=enable_quad)
        proposals, scores = self.quad(x, S, meta, quad_control)

        # Gate mixer
        gate_control = GateControl(tau=tau)
        if control and control.gate_control:
            gate_control = control.get_gate_control()
        x = self.mixer(x, proposals, scores, gate_control)

        # FFN with pre-norm
        x = x + self.ffn(self.norm_ffn(x))

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

        # Gate metrics
        gate_metrics = self.mixer.get_instrumentation()
        for k, v in gate_metrics.items():
            diagnostics[f"gate/{k}"] = v

        return diagnostics


class CognadeVisionBlockStack(nn.Module):
    """
    Stack of CognadeVisionBlocks.

    Provides convenience methods for creating multiple blocks
    with shared or per-block configurations.

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
    ):
        super().__init__()

        self.num_blocks = num_blocks
        self.embed_dim = embed_dim

        self.blocks = nn.ModuleList([
            CognadeVisionBlock(
                embed_dim=embed_dim,
                num_heads=num_heads,
                topk=topk,
                window_size=window_size,
                ffn_ratio=ffn_ratio,
                dropout=dropout,
                use_cross_attn=use_cross_attn,
                text_dim=text_dim,
            )
            for _ in range(num_blocks)
        ])

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        time_embed: Tensor,
        text_cond: Optional[Tensor] = None,
        control: Optional[BlockControl] = None,
    ) -> Tensor:
        """
        Forward through all blocks.

        Args:
            x: Input tokens [B, N, D].
            meta: PatchMeta with spatial info.
            time_embed: Timestep embedding [B, D].
            text_cond: Optional text embeddings.
            control: Optional control (applied to all blocks).

        Returns:
            x: Output tokens [B, N, D].
        """
        for block in self.blocks:
            x = block(x, meta, time_embed, text_cond, control)
        return x

    def get_all_diagnostics(self) -> dict:
        """Get diagnostics from all blocks."""
        all_diagnostics = {}
        for i, block in enumerate(self.blocks):
            block_diag = block.get_diagnostics()
            for k, v in block_diag.items():
                all_diagnostics[f"block_{i}/{k}"] = v
        return all_diagnostics
