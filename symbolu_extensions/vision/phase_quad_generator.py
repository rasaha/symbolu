"""
PhaseQuadImageGenerator: Full Phase-Quad Image Generator model.

This is the main model class that combines all components into a
complete latent diffusion image generator.

Architecture:
    1. ENCODE: VAE.encode(image) → z₀, then PatchEmbed2D → x
    2. DIFFUSION: Forward through CognadeVisionBlocks with timestep conditioning
    3. DECODE: Unpatchify → VAE.decode → image
"""

from typing import Optional, Dict, Tuple, Any

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.vision.config import PhaseQuadVisionConfig
from symbolu.vision.controls import (
    BlockControl,
    GeneratorControl,
    PatchMeta,
)
from symbolu.vision.patch_embed import PatchEmbed2D, TimestepEmbedding, TextProjection
from symbolu.vision.cognade_vision_block import CognadeVisionBlock
from symbolu.vision.phase_quad_dit_block import PhaseQuadDiTBlock
from symbolu.vision.diagnostics import (
    ModelDiagnostics,
    BlockDiagnostics,
    QuadUtilizationMetrics,
    PhaseHealthMetrics,
    compute_ghost_metrics,
)


class PhaseQuadImageGenerator(nn.Module):
    """
    Complete Phase-Quad Image Generator.

    This model implements a latent diffusion transformer using the
    Phase-Quad architecture for O(N) + O(N·K) efficient processing.

    Key Features:
    - O(N) phase accumulation with bi-axial scans
    - O(N·K) sparse global retrieval via TopK proposals
    - No-write contract enforcement
    - Comprehensive diagnostics for monitoring

    Args:
        config: PhaseQuadVisionConfig with all hyperparameters.
    """

    def __init__(self, config: PhaseQuadVisionConfig):
        super().__init__()

        # Validate config
        config.validate()

        self.config = config
        self.embed_dim = config.embed_dim
        self.num_heads = config.num_heads
        self.num_blocks = config.num_blocks

        # Patch embedding
        self.patch_embed = PatchEmbed2D(
            in_channels=config.vae.in_channels,
            patch_size=config.patch_size,
            embed_dim=config.embed_dim,
            use_2d_rope=config.block.quad.use_2d_rope,
        )

        # Timestep embedding
        self.time_embed = TimestepEmbedding(config.embed_dim)

        # Text projection (if using cross-attention)
        if config.block.local.use_cross_attn:
            self.text_proj = TextProjection(
                config.text_encoder.embed_dim,
                config.embed_dim,
            )
        else:
            self.text_proj = None

        # Main transformer blocks
        # NOTE: text_dim is embed_dim because text is projected by self.text_proj
        # before passing to blocks (from text_encoder.embed_dim to embed_dim)
        self.use_dit_style = config.block.dit_style.enabled

        if self.use_dit_style:
            # Use improved DiT-style blocks (Appendix H + I improvements)
            self.blocks = nn.ModuleList([
                PhaseQuadDiTBlock(
                    embed_dim=config.embed_dim,
                    num_heads=config.num_heads,
                    topk=config.topk,
                    window_size=config.block.local.window_size,
                    ffn_ratio=config.block.ffn_ratio,
                    dropout=config.block.dropout,
                    use_cross_attn=config.block.local.use_cross_attn,
                    text_dim=config.embed_dim if config.block.local.use_cross_attn else None,
                    t_max=config.training.diffusion.num_train_timesteps,
                    phase_min_strength=config.block.dit_style.phase_min_strength,
                    phase_max_strength=config.block.dit_style.phase_max_strength,
                    # BCVF configuration (Appendix I)
                    use_bcvf=config.block.bcvf.enabled,
                    bcvf_lambda_f=config.block.bcvf.lambda_f,
                    bcvf_lambda_b=config.block.bcvf.lambda_b,
                    bcvf_lambda_c=config.block.bcvf.lambda_c,
                    bcvf_beta=config.block.bcvf.beta,
                )
                for _ in range(config.num_blocks)
            ])
        else:
            # Use baseline blocks (original architecture)
            self.blocks = nn.ModuleList([
                CognadeVisionBlock(
                    embed_dim=config.embed_dim,
                    num_heads=config.num_heads,
                    topk=config.topk,
                    window_size=config.block.local.window_size,
                    ffn_ratio=config.block.ffn_ratio,
                    dropout=config.block.dropout,
                    use_cross_attn=config.block.local.use_cross_attn,
                    text_dim=config.embed_dim if config.block.local.use_cross_attn else None,
                )
                for _ in range(config.num_blocks)
            ])

        # Final layer norm
        self.final_norm = nn.LayerNorm(config.embed_dim)

        # Output projection (noise prediction head)
        self.out_proj = nn.Linear(
            config.embed_dim,
            config.vae.in_channels * config.patch_size * config.patch_size,
        )

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize weights using standard practices."""
        # Initialize linear layers
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.LayerNorm):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

        # Zero-init output projection for residual-friendly start
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
            z_t: Noisy latent [B, C, H, W] at timestep t.
            timestep: Diffusion timestep [B] or [B, 1].
            text_cond: Text conditioning [B, T, D_text] from text encoder.
            control: Optional GeneratorControl for ablation/inference control.

        Returns:
            noise_pred: Predicted noise [B, C, H, W] same shape as z_t.
        """
        B, C, H, W = z_t.shape

        # Patchify
        x, meta = self.patch_embed(z_t)  # [B, N, D], PatchMeta

        # Timestep embedding
        t_emb = self.time_embed(timestep)  # [B, D]

        # Project text if provided
        if text_cond is not None and self.text_proj is not None:
            text_cond = self.text_proj(text_cond)  # [B, T, D]

        # Forward through blocks
        for i, block in enumerate(self.blocks):
            # Get per-block control if specified
            block_control = None
            if control is not None:
                block_control = control.get_block_control(i)

            # DiT-style blocks need the raw timestep for phase strength calculation
            if self.use_dit_style:
                x = block(x, meta, t_emb, text_cond, timestep, block_control)
            else:
                x = block(x, meta, t_emb, text_cond, block_control)

        # Final norm
        x = self.final_norm(x)

        # Project to output
        x = self.out_proj(x)  # [B, N, C * P * P]

        # Unpatchify
        noise_pred = self.patch_embed.unpatchify(x, meta)  # [B, C, H, W]

        return noise_pred

    def forward_with_diagnostics(
        self,
        z_t: Tensor,
        timestep: Tensor,
        text_cond: Optional[Tensor] = None,
        control: Optional[GeneratorControl] = None,
    ) -> Tuple[Tensor, ModelDiagnostics]:
        """
        Forward pass with full diagnostics.

        Use this for training monitoring and debugging.
        Slower than regular forward due to metric computation.

        Args:
            z_t: Noisy latent [B, C, H, W].
            timestep: Diffusion timestep [B].
            text_cond: Text conditioning [B, T, D_text].
            control: Optional GeneratorControl.

        Returns:
            noise_pred: Predicted noise [B, C, H, W].
            diagnostics: ModelDiagnostics with all metrics.
        """
        B, C, H, W = z_t.shape

        # Patchify
        x, meta = self.patch_embed(z_t)

        # Timestep embedding
        t_emb = self.time_embed(timestep)

        # Project text
        if text_cond is not None and self.text_proj is not None:
            text_cond = self.text_proj(text_cond)

        # Collect diagnostics per block
        block_diagnostics = []

        # Forward through blocks with diagnostic collection
        for i, block in enumerate(self.blocks):
            block_control = None
            if control is not None:
                block_control = control.get_block_control(i)

            # DiT-style blocks need the raw timestep for phase strength calculation
            if self.use_dit_style:
                x = block(x, meta, t_emb, text_cond, timestep, block_control)
            else:
                x = block(x, meta, t_emb, text_cond, block_control)

            # Collect block diagnostics
            block_diag = block.get_diagnostics()

            # Extract quad metrics - compute derived values where possible
            score_mean = block_diag.get("quad/score_mean", 0.0)
            score_std = block_diag.get("quad/score_std", 0.0)
            # Estimate score range from mean and std (assuming roughly normal)
            score_min = max(0.0, score_mean - 3 * score_std) if score_std > 0 else score_mean
            score_max = min(1.0, score_mean + 3 * score_std) if score_std > 0 else score_mean
            # Estimate active selection rate from gate entropy (higher entropy = more distributed selection)
            gate_entropy = block_diag.get("gate/gate_entropy", 0.0)
            active_selection_rate = min(1.0, gate_entropy / 2.0) if gate_entropy > 0 else 0.5

            quad_metrics = QuadUtilizationMetrics(
                gate_entropy=gate_entropy,
                active_selection_rate=active_selection_rate,
                gate_saturation_rate=block_diag.get("gate/gate_saturation", 0.0),
                score_mean=score_mean,
                score_std=score_std,
                score_min=score_min,
                score_max=score_max,
            )

            # Extract phase metrics - compute derived values where possible
            row_amp_mean = block_diag.get("phase/row_amplitude_mean", 0.0)
            row_amp_std = block_diag.get("phase/row_amplitude_std", 0.0)
            col_amp_mean = block_diag.get("phase/col_amplitude_mean", 0.0)
            col_amp_std = block_diag.get("phase/col_amplitude_std", 0.0)
            # Compute average amplitude metrics
            amplitude_mean = (row_amp_mean + col_amp_mean) / 2.0
            amplitude_std = (row_amp_std + col_amp_std) / 2.0
            # Compute row/col similarity (1.0 = perfect match)
            row_col_similarity = 1.0 - abs(row_amp_mean - col_amp_mean) / (max(row_amp_mean, col_amp_mean) + 1e-8)
            # Estimate saturation (clamped to reasonable range)
            amplitude_saturation = min(1.0, amplitude_mean) if amplitude_mean > 0 else 0.0

            phase_metrics = PhaseHealthMetrics(
                amplitude_mean=amplitude_mean,
                amplitude_std=amplitude_std,
                amplitude_saturation=amplitude_saturation,
                state_drift_ratio=0.0,  # Would require tracking over time
                state_norm=amplitude_mean,  # Use amplitude as proxy
                row_col_similarity=row_col_similarity,
            )

            ghost_metrics = compute_ghost_metrics(x)

            block_diagnostics.append(BlockDiagnostics(
                block_idx=i,
                quad_metrics=quad_metrics,
                phase_metrics=phase_metrics,
                ghost_metrics=ghost_metrics,
            ))

        # Final norm and output
        x = self.final_norm(x)
        x = self.out_proj(x)
        noise_pred = self.patch_embed.unpatchify(x, meta)

        # Global metrics
        global_metrics = {
            "output_norm": noise_pred.norm().item(),
            "output_std": noise_pred.std().item(),
        }

        diagnostics = ModelDiagnostics(
            blocks=block_diagnostics,
            global_metrics=global_metrics,
        )

        return noise_pred, diagnostics

    def get_num_params(self, non_embedding: bool = True) -> int:
        """
        Get number of parameters.

        Args:
            non_embedding: If True, exclude embedding parameters.

        Returns:
            Number of parameters.
        """
        n_params = sum(p.numel() for p in self.parameters())
        if non_embedding:
            n_params -= self.patch_embed.proj.weight.numel()
        return n_params

    @classmethod
    def from_config(cls, config: PhaseQuadVisionConfig) -> "PhaseQuadImageGenerator":
        """Create model from config."""
        return cls(config)

    @classmethod
    def tiny(cls) -> "PhaseQuadImageGenerator":
        """Create tiny model for testing."""
        return cls(PhaseQuadVisionConfig.tiny())

    @classmethod
    def small(cls) -> "PhaseQuadImageGenerator":
        """Create small model for development."""
        return cls(PhaseQuadVisionConfig.small())

    @classmethod
    def base(cls) -> "PhaseQuadImageGenerator":
        """Create base model (recommended for PoC)."""
        return cls(PhaseQuadVisionConfig.base())

    @classmethod
    def large(cls) -> "PhaseQuadImageGenerator":
        """Create large model for full-scale experiments."""
        return cls(PhaseQuadVisionConfig.large())


class StandardAttentionBlock(nn.Module):
    """
    Standard attention block for baseline comparison.

    Same model size but uses O(N²) full attention instead of Phase-Quad.
    Used for fair comparison against the Phase-Quad architecture.

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        ffn_ratio: FFN hidden dimension ratio.
        dropout: Dropout rate.
        use_cross_attn: Include cross-attention to text.
        text_dim: Text embedding dimension.
    """

    def __init__(
        self,
        embed_dim: int = 768,
        num_heads: int = 12,
        ffn_ratio: float = 4.0,
        dropout: float = 0.1,
        use_cross_attn: bool = True,
        text_dim: Optional[int] = None,
    ):
        super().__init__()

        self.embed_dim = embed_dim

        # Self-attention
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

        # FFN
        self.norm3 = nn.LayerNorm(embed_dim)
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
        meta: PatchMeta,
        time_embed: Tensor,
        text_cond: Optional[Tensor] = None,
        control: Optional[BlockControl] = None,
    ) -> Tensor:
        """Forward pass."""
        # Timestep modulation
        time_params = self.time_mlp(time_embed)
        scale, shift = time_params.chunk(2, dim=-1)
        x = x * (1 + scale.unsqueeze(1)) + shift.unsqueeze(1)

        # Self-attention
        x_norm = self.norm1(x)
        x_attn, _ = self.self_attn(x_norm, x_norm, x_norm)
        x = x + x_attn

        # Cross-attention
        if self.cross_attn is not None and text_cond is not None:
            x_norm = self.norm2(x)
            x_cross, _ = self.cross_attn(x_norm, text_cond, text_cond)
            x = x + x_cross

        # FFN
        x = x + self.ffn(self.norm3(x))

        return x


class StandardAttentionGenerator(nn.Module):
    """
    Standard attention baseline generator for fair comparison.

    Same architecture as PhaseQuadImageGenerator but uses O(N²) attention.

    Args:
        config: PhaseQuadVisionConfig.
    """

    def __init__(self, config: PhaseQuadVisionConfig):
        super().__init__()

        self.config = config

        # Same patch embedding
        self.patch_embed = PatchEmbed2D(
            in_channels=config.vae.in_channels,
            patch_size=config.patch_size,
            embed_dim=config.embed_dim,
        )

        # Timestep embedding
        self.time_embed = TimestepEmbedding(config.embed_dim)

        # Text projection
        if config.block.local.use_cross_attn:
            self.text_proj = TextProjection(
                config.text_encoder.embed_dim,
                config.embed_dim,
            )
        else:
            self.text_proj = None

        # Standard attention blocks
        self.blocks = nn.ModuleList([
            StandardAttentionBlock(
                embed_dim=config.embed_dim,
                num_heads=config.num_heads,
                ffn_ratio=config.block.ffn_ratio,
                dropout=config.block.dropout,
                use_cross_attn=config.block.local.use_cross_attn,
                text_dim=config.text_encoder.embed_dim if config.block.local.use_cross_attn else None,
            )
            for _ in range(config.num_blocks)
        ])

        # Final layers
        self.final_norm = nn.LayerNorm(config.embed_dim)
        self.out_proj = nn.Linear(
            config.embed_dim,
            config.vae.in_channels * config.patch_size * config.patch_size,
        )

    def forward(
        self,
        z_t: Tensor,
        timestep: Tensor,
        text_cond: Optional[Tensor] = None,
        control: Optional[GeneratorControl] = None,
    ) -> Tensor:
        """Forward pass."""
        x, meta = self.patch_embed(z_t)
        t_emb = self.time_embed(timestep)

        if text_cond is not None and self.text_proj is not None:
            text_cond = self.text_proj(text_cond)

        for block in self.blocks:
            x = block(x, meta, t_emb, text_cond)

        x = self.final_norm(x)
        x = self.out_proj(x)
        noise_pred = self.patch_embed.unpatchify(x, meta)

        return noise_pred
