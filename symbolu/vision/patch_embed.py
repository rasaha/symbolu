"""
PatchEmbed2D: Patchify VAE latent into tokens with 2D position encoding.

This module handles the conversion of VAE latent tensors [B, C, H, W]
into patch token sequences [B, N, D] suitable for the Phase-Quad
transformer blocks.
"""

import math
from typing import Tuple, Optional, Callable

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from symbolu.vision.controls import PatchMeta


class PatchEmbed2D(nn.Module):
    """
    Patchify VAE latent into tokens with 2D position encoding.

    Converts a VAE latent tensor into a sequence of patch tokens,
    adding positional information that can be used by downstream
    components for 2D spatial operations.

    IMPORTANT: Uses STANDARD 2D RoPE or learned position embeddings.
    Phase-modulated RoPE is explicitly deferred (high coupling risk).

    Args:
        in_channels: Number of VAE latent channels (default: 4 for SDXL VAE).
        patch_size: Patch size in latent space (default: 2).
        embed_dim: Model dimension (default: 768).
        use_2d_rope: If True, rely on external 2D RoPE (no learned pos embed).
        use_learned_pos: If True, add learned position embeddings.
        max_h: Maximum height in patches (for learned pos embed).
        max_w: Maximum width in patches (for learned pos embed).
        bias: Whether to use bias in projection.
    """

    def __init__(
        self,
        in_channels: int = 4,
        patch_size: int = 2,
        embed_dim: int = 768,
        use_2d_rope: bool = True,
        use_learned_pos: bool = False,
        max_h: int = 128,
        max_w: int = 128,
        bias: bool = True,
    ):
        super().__init__()

        self.in_channels = in_channels
        self.patch_size = patch_size
        self.embed_dim = embed_dim
        self.use_2d_rope = use_2d_rope
        self.use_learned_pos = use_learned_pos

        # Patch projection (equivalent to Conv2d with kernel_size=patch_size, stride=patch_size)
        self.proj = nn.Conv2d(
            in_channels,
            embed_dim,
            kernel_size=patch_size,
            stride=patch_size,
            bias=bias,
        )

        # Layer norm for patch embeddings
        self.norm = nn.LayerNorm(embed_dim)

        # Optional learned position embeddings
        if use_learned_pos and not use_2d_rope:
            self.pos_embed = nn.Parameter(
                torch.zeros(1, max_h * max_w, embed_dim)
            )
            nn.init.trunc_normal_(self.pos_embed, std=0.02)
        else:
            self.pos_embed = None

        # For unpatchify
        self.unpatch_proj = nn.Linear(embed_dim, in_channels * patch_size * patch_size)

    def forward(self, z: Tensor) -> Tuple[Tensor, PatchMeta]:
        """
        Patchify latent tensor.

        Args:
            z: Latent tensor [B, C, H_img, W_img] from VAE encoder.

        Returns:
            x: Patch tokens [B, N, D] where N = (H_img/P) × (W_img/P).
            meta: PatchMeta containing grid dimensions and coordinates.

        Raises:
            ValueError: If spatial dimensions are not divisible by patch_size.
        """
        B, C, H_img, W_img = z.shape

        if H_img % self.patch_size != 0 or W_img % self.patch_size != 0:
            raise ValueError(
                f"Spatial dimensions ({H_img}, {W_img}) must be divisible "
                f"by patch_size ({self.patch_size})"
            )

        # Patchify via convolution
        # [B, C, H, W] -> [B, D, H_p, W_p]
        x = self.proj(z)

        # Get patch grid dimensions
        H_p, W_p = x.shape[2], x.shape[3]
        N = H_p * W_p

        # Flatten to sequence: [B, D, H_p, W_p] -> [B, D, N] -> [B, N, D]
        x = x.flatten(2).transpose(1, 2)

        # Apply layer norm
        x = self.norm(x)

        # Add learned position embeddings if enabled
        if self.pos_embed is not None:
            x = x + self.pos_embed[:, :N, :]

        # Create coordinate tensor for 2D RoPE
        # coords[i] = (row, col) for patch i in row-major order
        coords = self._create_coords(H_p, W_p, z.device)

        # Create metadata
        meta = PatchMeta(
            H_p=H_p,
            W_p=W_p,
            coords=coords,
            patch_size=self.patch_size,
            in_channels=self.in_channels,
        )

        return x, meta

    def _create_coords(self, H_p: int, W_p: int, device: torch.device) -> Tensor:
        """
        Create coordinate tensor for patches.

        Args:
            H_p: Number of patch rows.
            W_p: Number of patch columns.
            device: Device for tensor.

        Returns:
            coords: [N, 2] tensor where coords[i] = (row, col).
        """
        # Create row and column indices
        rows = torch.arange(H_p, device=device)
        cols = torch.arange(W_p, device=device)

        # Create meshgrid
        row_grid, col_grid = torch.meshgrid(rows, cols, indexing="ij")

        # Flatten and stack: [H_p, W_p] -> [N, 2]
        coords = torch.stack([row_grid.flatten(), col_grid.flatten()], dim=1)

        return coords

    def unpatchify(self, x: Tensor, meta: PatchMeta) -> Tensor:
        """
        Reverse patchification.

        Args:
            x: Patch tokens [B, N, D].
            meta: PatchMeta from forward pass.

        Returns:
            z: Latent tensor [B, C, H_img, W_img].
        """
        B, N, D = x.shape
        H_p, W_p = meta.H_p, meta.W_p
        P = self.patch_size
        C = meta.in_channels

        # Project back to patch space
        # [B, N, D] -> [B, N, C * P * P]
        x = self.unpatch_proj(x)

        # Reshape: [B, N, C * P * P] -> [B, H_p, W_p, C, P, P]
        x = x.view(B, H_p, W_p, C, P, P)

        # Rearrange: [B, H_p, W_p, C, P, P] -> [B, C, H_p, P, W_p, P]
        x = x.permute(0, 3, 1, 4, 2, 5)

        # Merge patches: [B, C, H_p, P, W_p, P] -> [B, C, H_img, W_img]
        H_img = H_p * P
        W_img = W_p * P
        x = x.reshape(B, C, H_img, W_img)

        return x


class TimestepEmbedding(nn.Module):
    """
    Sinusoidal timestep embedding for diffusion models.

    Converts integer timesteps into continuous embeddings suitable
    for conditioning the Phase-Quad transformer.

    Args:
        embed_dim: Output embedding dimension.
        max_timesteps: Maximum number of timesteps.
    """

    def __init__(
        self,
        embed_dim: int,
        max_timesteps: int = 1000,
        freq_scale: float = 1.0,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.max_timesteps = max_timesteps

        # MLP to project sinusoidal embedding
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 4),
            nn.SiLU(),
            nn.Linear(embed_dim * 4, embed_dim),
        )

        # Precompute frequencies
        half_dim = embed_dim // 2
        freq = torch.exp(
            -math.log(10000.0) * torch.arange(half_dim).float() / half_dim
        ) * freq_scale
        self.register_buffer("freq", freq)

    def forward(self, t: Tensor) -> Tensor:
        """
        Embed timesteps.

        Args:
            t: Timestep indices [B] or [B, 1].

        Returns:
            embed: Timestep embeddings [B, D].
        """
        if t.dim() == 2:
            t = t.squeeze(-1)

        # Compute sinusoidal embedding
        # t: [B] -> [B, 1]
        t = t.unsqueeze(-1).float()

        # [B, 1] * [half_dim] -> [B, half_dim]
        freqs = t * self.freq.unsqueeze(0)

        # Concatenate sin and cos: [B, D]
        embed = torch.cat([torch.sin(freqs), torch.cos(freqs)], dim=-1)

        # Project through MLP
        embed = self.mlp(embed)

        return embed


class TextProjection(nn.Module):
    """
    Project text embeddings to model dimension.

    Handles dimension mismatch between text encoder output and
    model embedding dimension.

    Args:
        text_dim: Input text embedding dimension.
        embed_dim: Model embedding dimension.
    """

    def __init__(self, text_dim: int, embed_dim: int):
        super().__init__()

        self.proj = nn.Linear(text_dim, embed_dim)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, text_embeds: Tensor) -> Tensor:
        """
        Project text embeddings.

        Args:
            text_embeds: [B, T, D_text] from text encoder.

        Returns:
            projected: [B, T, D] projected embeddings.
        """
        return self.norm(self.proj(text_embeds))
