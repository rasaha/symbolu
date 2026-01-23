"""
PhaseQuadVideoGenerator: Full Phase-Quad Video Generator model.

This model extends the image generator with temporal phase integration
for video generation. Uses PhaseIntegrator3D for spatiotemporal coherence.

Architecture:
    1. ENCODE: VideoVAE.encode(video) → z₀, then PatchEmbed3D → x
    2. DIFFUSION: Forward through CognadeVideo3DBlocks with timestep conditioning
    3. DECODE: Unpatchify3D → VideoVAE.decode → video
"""

from typing import Optional, Tuple, Dict, List

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.vision.video.config import PhaseQuadVideoConfig, BCVFVideoConfig
from symbolu.vision.video.bcvf_video import BCVFVideoQuadWeighter
from symbolu.vision.phase_integrator_3d import PhaseIntegrator3D, VideoMeta
from symbolu.vision.controls import (
    BlockControl,
    GeneratorControl,
    PhaseControl,
    QuadControl,
)
from symbolu.vision.quad_retriever import QuadRetriever
from symbolu.vision.gate_mixer import GateMixer


class PatchEmbed3D(nn.Module):
    """
    3D Patch embedding for video.

    Converts video latents [B, C, T, H, W] to patch embeddings [B, N, D]
    where N = T * H_p * W_p.

    Args:
        in_channels: Number of latent channels (e.g., 16 for CogVideoX).
        patch_size: Spatial patch size.
        temporal_patch_size: Temporal patch size (usually 1).
        embed_dim: Output embedding dimension.
    """

    def __init__(
        self,
        in_channels: int = 16,
        patch_size: int = 2,
        temporal_patch_size: int = 1,
        embed_dim: int = 768,
    ):
        super().__init__()

        self.in_channels = in_channels
        self.patch_size = patch_size
        self.temporal_patch_size = temporal_patch_size
        self.embed_dim = embed_dim

        # 3D convolution for patch embedding
        self.proj = nn.Conv3d(
            in_channels,
            embed_dim,
            kernel_size=(temporal_patch_size, patch_size, patch_size),
            stride=(temporal_patch_size, patch_size, patch_size),
        )
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x: Tensor) -> Tuple[Tensor, VideoMeta]:
        """
        Embed video latents into patches.

        Args:
            x: Video latent [B, C, T, H, W].

        Returns:
            patches: [B, N, D] where N = T' * H_p * W_p.
            meta: VideoMeta with grid dimensions.
        """
        B, C, T, H, W = x.shape

        # Project to patches: [B, C, T, H, W] -> [B, D, T', H_p, W_p]
        x = self.proj(x)

        # Get patch grid dimensions
        _, D, T_p, H_p, W_p = x.shape

        # Flatten: [B, D, T', H_p, W_p] -> [B, N, D]
        x = x.permute(0, 2, 3, 4, 1).reshape(B, -1, D)

        # Normalize
        x = self.norm(x)

        # Create metadata
        meta = VideoMeta(
            T=T_p,
            H_p=H_p,
            W_p=W_p,
            patch_size=self.patch_size,
            temporal_patch_size=self.temporal_patch_size,
            in_channels=self.in_channels,
        )
        meta = meta.to(x.device)

        return x, meta

    def unpatchify(self, x: Tensor, meta: VideoMeta) -> Tensor:
        """
        Convert patches back to video latent format.

        Args:
            x: Patches [B, N, D_out] where D_out = C * p_t * p * p.
            meta: VideoMeta with grid dimensions.

        Returns:
            video: [B, C, T, H, W] video latent.
        """
        B, N, D_out = x.shape
        T, H_p, W_p = meta.T, meta.H_p, meta.W_p
        p = self.patch_size
        p_t = self.temporal_patch_size
        C = self.in_channels

        # Reshape: [B, N, C*p_t*p*p] -> [B, T, H_p, W_p, C, p_t, p, p]
        x = x.view(B, T, H_p, W_p, C, p_t, p, p)

        # Rearrange: [B, T, H_p, W_p, C, p_t, p, p] -> [B, C, T*p_t, H_p*p, W_p*p]
        x = x.permute(0, 4, 1, 5, 2, 6, 3, 7)  # [B, C, T, p_t, H_p, p, W_p, p]
        x = x.reshape(B, C, T * p_t, H_p * p, W_p * p)

        return x


class TimestepEmbedding(nn.Module):
    """Sinusoidal timestep embedding."""

    def __init__(self, embed_dim: int):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 4),
            nn.SiLU(),
            nn.Linear(embed_dim * 4, embed_dim),
        )
        self.embed_dim = embed_dim

    def forward(self, t: Tensor) -> Tensor:
        """
        Embed timesteps.

        Args:
            t: Timesteps [B] as integers or floats.

        Returns:
            embeddings: [B, D].
        """
        # Sinusoidal embedding
        half_dim = self.embed_dim // 2
        emb = torch.log(torch.tensor(10000.0)) / (half_dim - 1)
        emb = torch.exp(-emb * torch.arange(half_dim, device=t.device))
        emb = t.unsqueeze(1) * emb.unsqueeze(0)
        emb = torch.cat([torch.sin(emb), torch.cos(emb)], dim=-1)

        return self.mlp(emb)


class TextProjection(nn.Module):
    """Project text embeddings to model dimension."""

    def __init__(self, text_dim: int, embed_dim: int):
        super().__init__()
        self.proj = nn.Linear(text_dim, embed_dim)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x: Tensor) -> Tensor:
        return self.norm(self.proj(x))


class LocalMixer3D(nn.Module):
    """
    3D Local attention mixer with spatiotemporal windows.

    Uses windowed attention in 3D for efficient local processing.
    """

    def __init__(
        self,
        embed_dim: int = 768,
        num_heads: int = 12,
        window_size: int = 8,
        temporal_window: int = 4,
        dropout: float = 0.1,
        use_cross_attn: bool = True,
        text_dim: Optional[int] = None,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.window_size = window_size
        self.temporal_window = temporal_window

        # Self-attention (simplified: use full attention on flattened sequence)
        self.self_attn = nn.MultiheadAttention(
            embed_dim, num_heads, batch_first=True, dropout=dropout
        )
        self.norm1 = nn.LayerNorm(embed_dim)

        # Cross-attention
        if use_cross_attn and text_dim is not None:
            self.cross_attn = nn.MultiheadAttention(
                embed_dim, num_heads, batch_first=True,
                kdim=text_dim, vdim=text_dim, dropout=dropout
            )
            self.norm2 = nn.LayerNorm(embed_dim)
        else:
            self.cross_attn = None
            self.norm2 = None

    def forward(
        self,
        x: Tensor,
        meta: VideoMeta,
        text_cond: Optional[Tensor] = None,
    ) -> Tensor:
        """Forward pass with local 3D attention."""
        # Simplified: use chunked attention or full attention
        # For production: implement proper 3D windowed attention
        x_norm = self.norm1(x)
        x_attn, _ = self.self_attn(x_norm, x_norm, x_norm)
        x = x + x_attn

        if self.cross_attn is not None and text_cond is not None:
            x_norm = self.norm2(x)
            x_cross, _ = self.cross_attn(x_norm, text_cond, text_cond)
            x = x + x_cross

        return x


class CognadeVideo3DBlock(nn.Module):
    """
    Phase-Quad Vision Block adapted for video (3D).

    Same structure as CognadeVisionBlock but uses:
    - PhaseIntegrator3D instead of PhaseIntegrator2D
    - LocalMixer3D instead of LocalMixer
    - VideoMeta instead of PatchMeta
    - BCVFVideoQuadWeighter for temporal consistency (optional)
    """

    def __init__(
        self,
        embed_dim: int = 768,
        num_heads: int = 12,
        topk: int = 64,
        window_size: int = 8,
        temporal_window: int = 4,
        ffn_ratio: float = 4.0,
        dropout: float = 0.1,
        use_cross_attn: bool = True,
        text_dim: Optional[int] = None,
        bcvf_config: Optional[BCVFVideoConfig] = None,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.topk = topk
        self.use_bcvf = bcvf_config is not None and bcvf_config.enabled

        # Components
        self.local_mixer = LocalMixer3D(
            embed_dim=embed_dim,
            num_heads=num_heads,
            window_size=window_size,
            temporal_window=temporal_window,
            dropout=dropout,
            use_cross_attn=use_cross_attn,
            text_dim=text_dim,
        )

        self.phase_integrator = PhaseIntegrator3D(
            embed_dim=embed_dim,
            num_heads=num_heads,
        )

        self.quad_retriever = QuadRetriever(
            embed_dim=embed_dim,
            num_heads=num_heads,
            topk=topk,
        )

        self.gate_mixer = GateMixer(
            embed_dim=embed_dim,
            num_heads=num_heads,
        )

        # BCVF weighter for temporal consistency
        if self.use_bcvf:
            self.bcvf_weighter = BCVFVideoQuadWeighter(
                lambda_f=bcvf_config.lambda_f,
                lambda_b=bcvf_config.lambda_b,
                lambda_c=bcvf_config.lambda_c,
                lambda_t=bcvf_config.lambda_t,
                beta=bcvf_config.beta,
                detach_prev=bcvf_config.detach_prev,
            )
        else:
            self.bcvf_weighter = None

        # FFN
        self.norm = nn.LayerNorm(embed_dim)
        ffn_hidden = int(embed_dim * ffn_ratio)
        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, ffn_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ffn_hidden, embed_dim),
            nn.Dropout(dropout),
        )

        # Timestep modulation
        self.time_mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 2),
            nn.SiLU(),
            nn.Linear(embed_dim * 2, embed_dim * 2),
        )

    def forward(
        self,
        x: Tensor,
        meta: VideoMeta,
        time_embed: Tensor,
        text_cond: Optional[Tensor] = None,
        control: Optional[BlockControl] = None,
        prev_state: Optional[Tensor] = None,
    ) -> Tuple[Tensor, Optional[Tensor]]:
        """
        Forward pass through video block.

        Args:
            x: Input [B, N, D] where N = T * H_p * W_p.
            meta: VideoMeta with dimensions.
            time_embed: Timestep embedding [B, D].
            text_cond: Text conditioning [B, L, D].
            control: Optional BlockControl.
            prev_state: Previous frame's output [B, H_p*W_p, D] for BCVF temporal.

        Returns:
            x: Output [B, N, D].
            new_prev_state: Output from last frame [B, H_p*W_p, D] for next block.
        """
        B, N, D = x.shape
        T = meta.T
        N_spatial = meta.H_p * meta.W_p  # Spatial positions per frame

        # Get controls
        phase_control = control.get_phase_control() if control else PhaseControl()
        gate_control = control.get_gate_control() if control else None
        quad_control = control.get_quad_control() if control else QuadControl()

        # Timestep modulation
        time_params = self.time_mlp(time_embed)
        scale, shift = time_params.chunk(2, dim=-1)
        x = x * (1 + scale.unsqueeze(1)) + shift.unsqueeze(1)

        # Local mixing (with text cross-attention)
        x_local = self.local_mixer(x, meta, text_cond)

        # Phase integration (3D)
        phase_state = self.phase_integrator(x_local, meta, phase_control)

        # Quad retrieval - get both proposals and scores
        score_noise_std = quad_control.score_noise_std if quad_control else 0.0
        proposals, proposal_scores = self.quad_retriever(
            x_local, phase_state,
            score_noise_std=score_noise_std,
        )  # proposals: [B, N, K, D], scores: [B, N, K]

        # Apply BCVF temporal weighting if enabled
        new_prev_state = None
        if self.use_bcvf and self.bcvf_weighter is not None:
            K = proposals.shape[2]

            # Reshape to [B, T, N_spatial, K, D] for BCVF video
            proposals_3d = proposals.view(B, T, N_spatial, K, D)
            scores_3d = proposal_scores.view(B, T, N_spatial, K)
            phase_state_3d = phase_state.view(B, T, N_spatial, D)

            # Apply BCVF with temporal consistency
            weighted = self.bcvf_weighter(
                proposals_3d,
                scores_3d,
                phase_state_3d,
                prev_state,
            )  # [B, T, N_spatial, D]

            # Reshape back to [B, N, D]
            x = x_local + weighted.view(B, N, D)

            # Track prev_state for next block (last frame's output)
            new_prev_state = weighted[:, -1, :, :]  # [B, N_spatial, D]
        else:
            # Standard gate mixing (no BCVF)
            tau = gate_control.tau if gate_control else 1.0
            x = self.gate_mixer(x_local, proposals, phase_state, tau=tau)

        # FFN
        x = x + self.ffn(self.norm(x))

        return x, new_prev_state


class PhaseQuadVideoGenerator(nn.Module):
    """
    Complete Phase-Quad Video Generator.

    Extends the image generator with temporal phase integration
    for coherent video generation.

    Args:
        config: PhaseQuadVideoConfig with all hyperparameters.
    """

    def __init__(self, config: PhaseQuadVideoConfig):
        super().__init__()

        # Validate config
        config.validate()

        self.config = config
        self.embed_dim = config.embed_dim
        self.num_heads = config.num_heads
        self.num_blocks = config.num_blocks

        # 3D patch embedding
        self.patch_embed = PatchEmbed3D(
            in_channels=config.vae.latent_channels,
            patch_size=config.patch_size,
            temporal_patch_size=config.temporal_patch_size,
            embed_dim=config.embed_dim,
        )

        # Timestep embedding
        self.time_embed = TimestepEmbedding(config.embed_dim)

        # Text projection
        self.text_proj = TextProjection(
            config.text_encoder.embed_dim,
            config.embed_dim,
        )

        # Main transformer blocks
        self.blocks = nn.ModuleList([
            CognadeVideo3DBlock(
                embed_dim=config.embed_dim,
                num_heads=config.num_heads,
                topk=config.topk,
                window_size=config.block.local.window_size,
                temporal_window=config.block.local.temporal_window,
                ffn_ratio=config.block.ffn_ratio,
                dropout=config.block.dropout,
                use_cross_attn=True,
                text_dim=config.embed_dim,
                bcvf_config=config.block.bcvf,
            )
            for _ in range(config.num_blocks)
        ])

        # Track BCVF metrics for instrumentation
        self._bcvf_metrics: Dict[str, float] = {}

        # Final layer norm
        self.final_norm = nn.LayerNorm(config.embed_dim)

        # Output projection (noise prediction head)
        out_channels = (
            config.vae.latent_channels
            * config.temporal_patch_size
            * config.patch_size
            * config.patch_size
        )
        self.out_proj = nn.Linear(config.embed_dim, out_channels)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize weights."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.LayerNorm):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

        # Zero-init output projection
        nn.init.zeros_(self.out_proj.weight)
        nn.init.zeros_(self.out_proj.bias)

    def forward(
        self,
        z_t: Tensor,
        timestep: Tensor,
        text_cond: Optional[Tensor] = None,
        control: Optional[GeneratorControl] = None,
    ) -> Tensor:
        """
        Forward pass for noise prediction.

        Args:
            z_t: Noisy video latent [B, C, T, H, W] at timestep t.
            timestep: Diffusion timestep [B].
            text_cond: Text conditioning [B, L, D_text].
            control: Optional GeneratorControl.

        Returns:
            noise_pred: Predicted noise [B, C, T, H, W].
        """
        B, C, T, H, W = z_t.shape

        # Patchify
        x, meta = self.patch_embed(z_t)  # [B, N, D], VideoMeta

        # Timestep embedding
        t_emb = self.time_embed(timestep)  # [B, D]

        # Project text
        if text_cond is not None:
            text_cond = self.text_proj(text_cond)  # [B, L, D]

        # Forward through blocks with BCVF prev_state tracking
        prev_states: List[Optional[Tensor]] = [None] * len(self.blocks)

        for i, block in enumerate(self.blocks):
            block_control = None
            if control is not None:
                block_control = control.get_block_control(i)

            x, new_prev_state = block(
                x, meta, t_emb, text_cond, block_control,
                prev_state=prev_states[i],
            )

            # Update prev_state for this block (for next forward pass)
            # Note: In training, we don't carry state across batches
            # This is mainly for temporal consistency within a single forward

        # Collect BCVF metrics from blocks
        self._bcvf_metrics = {}
        for i, block in enumerate(self.blocks):
            if block.use_bcvf and block.bcvf_weighter is not None:
                block_metrics = block.bcvf_weighter.get_instrumentation()
                for key, value in block_metrics.items():
                    self._bcvf_metrics[f"block_{i}/{key}"] = value

        # Final norm and output
        x = self.final_norm(x)
        x = self.out_proj(x)  # [B, N, C * p_t * p * p]

        # Unpatchify
        noise_pred = self.patch_embed.unpatchify(x, meta)  # [B, C, T, H, W]

        return noise_pred

    def get_num_params(self, non_embedding: bool = True) -> int:
        """Get number of parameters."""
        n_params = sum(p.numel() for p in self.parameters())
        if non_embedding:
            n_params -= self.patch_embed.proj.weight.numel()
        return n_params

    def get_bcvf_metrics(self) -> Dict[str, float]:
        """
        Get BCVF metrics from all blocks.

        Returns:
            Dictionary with BCVF metrics from each block.
        """
        return self._bcvf_metrics

    @classmethod
    def tiny(cls) -> "PhaseQuadVideoGenerator":
        """Create tiny model for testing."""
        return cls(PhaseQuadVideoConfig.tiny())

    @classmethod
    def small(cls) -> "PhaseQuadVideoGenerator":
        """Create small model for development."""
        return cls(PhaseQuadVideoConfig.small())

    @classmethod
    def base(cls) -> "PhaseQuadVideoGenerator":
        """Create base model for production."""
        return cls(PhaseQuadVideoConfig.base())
