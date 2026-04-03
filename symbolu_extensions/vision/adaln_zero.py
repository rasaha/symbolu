"""
AdaLN-Zero: Adaptive Layer Normalization with Zero-Init Gate.

DiT-style conditioning for diffusion transformers that provides:
- Pre-layer norm modulation (shift, scale)
- Post-residual gate (starts at 0, learns to enable)

Reference: Peebles & Xie, "Scalable Diffusion Models with Transformers" (DiT)
"""

from typing import Tuple

import torch
import torch.nn as nn
from torch import Tensor


class AdaLNZero(nn.Module):
    """
    Adaptive Layer Normalization with Zero-Init Gate (DiT-style).

    This module implements the key conditioning mechanism from DiT:
    1. Layer normalization without learned affine parameters
    2. Shift and scale computed from conditioning signal
    3. Separate gates for attention and FFN residual paths
    4. Zero-initialization for stable training start

    The zero-init ensures that at initialization:
    - gate_attn ≈ 0 → attention path is "turned off"
    - gate_ffn ≈ 0 → FFN path is "turned off"

    This allows gradients to flow cleanly through skip connections
    and lets the model gradually learn to "turn on" each path.

    Args:
        embed_dim: Model dimension D.
        cond_dim: Conditioning dimension (typically same as embed_dim).
        num_modulation_params: Number of modulation parameters to output.
            Default is 6 for: shift_attn, scale_attn, gate_attn, shift_ffn, scale_ffn, gate_ffn
    """

    def __init__(
        self,
        embed_dim: int,
        cond_dim: int,
        num_modulation_params: int = 6,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.cond_dim = cond_dim
        self.num_params = num_modulation_params

        # Layer norm without learned affine (shift/scale come from conditioning)
        self.norm = nn.LayerNorm(embed_dim, elementwise_affine=False)

        # MLP to compute modulation parameters from conditioning
        self.adaLN_mlp = nn.Sequential(
            nn.SiLU(),
            nn.Linear(cond_dim, num_modulation_params * embed_dim),
        )

        # Zero-init the final linear layer for stable training
        # This ensures gates start at 0
        nn.init.zeros_(self.adaLN_mlp[-1].weight)
        nn.init.zeros_(self.adaLN_mlp[-1].bias)

    def forward(
        self,
        x: Tensor,
        cond: Tensor,
    ) -> Tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        """
        Compute modulation parameters and normalized input.

        Args:
            x: Input tensor [B, N, D]
            cond: Conditioning tensor [B, D] (e.g., timestep embedding)

        Returns:
            Tuple of (x_norm, shift_attn, scale_attn, gate_attn, shift_ffn, scale_ffn, gate_ffn):
            - x_norm: Normalized input [B, N, D]
            - shift_attn: Shift for pre-attention norm [B, 1, D]
            - scale_attn: Scale for pre-attention norm [B, 1, D]
            - gate_attn: Gate for attention residual [B, 1, D]
            - shift_ffn: Shift for pre-FFN norm [B, 1, D]
            - scale_ffn: Scale for pre-FFN norm [B, 1, D]
            - gate_ffn: Gate for FFN residual [B, 1, D]
        """
        # Compute modulation parameters
        params = self.adaLN_mlp(cond)  # [B, 6*D]

        # Split into 6 components
        (
            shift_attn, scale_attn, gate_attn,
            shift_ffn, scale_ffn, gate_ffn
        ) = params.chunk(self.num_params, dim=-1)

        # Add broadcast dimension for sequence
        shift_attn = shift_attn.unsqueeze(1)  # [B, 1, D]
        scale_attn = scale_attn.unsqueeze(1)
        gate_attn = gate_attn.unsqueeze(1)
        shift_ffn = shift_ffn.unsqueeze(1)
        scale_ffn = scale_ffn.unsqueeze(1)
        gate_ffn = gate_ffn.unsqueeze(1)

        # Normalize input
        x_norm = self.norm(x)

        return x_norm, shift_attn, scale_attn, gate_attn, shift_ffn, scale_ffn, gate_ffn

    def modulate(
        self,
        x: Tensor,
        shift: Tensor,
        scale: Tensor,
    ) -> Tensor:
        """
        Apply shift and scale modulation to normalized input.

        Args:
            x: Normalized input [B, N, D]
            shift: Shift tensor [B, 1, D]
            scale: Scale tensor [B, 1, D]

        Returns:
            Modulated tensor [B, N, D]
        """
        return x * (1 + scale) + shift


class AdaLNZeroSimple(nn.Module):
    """
    Simplified AdaLN-Zero with single gate.

    Outputs 3 parameters: shift, scale, gate
    Useful for simpler blocks that don't need separate attention/FFN gating.

    Args:
        embed_dim: Model dimension D.
        cond_dim: Conditioning dimension.
    """

    def __init__(self, embed_dim: int, cond_dim: int):
        super().__init__()

        self.norm = nn.LayerNorm(embed_dim, elementwise_affine=False)

        self.adaLN_mlp = nn.Sequential(
            nn.SiLU(),
            nn.Linear(cond_dim, 3 * embed_dim),
        )

        # Zero-init
        nn.init.zeros_(self.adaLN_mlp[-1].weight)
        nn.init.zeros_(self.adaLN_mlp[-1].bias)

    def forward(
        self,
        x: Tensor,
        cond: Tensor,
    ) -> Tuple[Tensor, Tensor, Tensor, Tensor]:
        """
        Compute modulation parameters.

        Args:
            x: Input tensor [B, N, D]
            cond: Conditioning tensor [B, D]

        Returns:
            Tuple of (x_norm, shift, scale, gate)
        """
        params = self.adaLN_mlp(cond)
        shift, scale, gate = params.chunk(3, dim=-1)

        x_norm = self.norm(x)

        return (
            x_norm,
            shift.unsqueeze(1),
            scale.unsqueeze(1),
            gate.unsqueeze(1),
        )


class FinalLayer(nn.Module):
    """
    Final layer with AdaLN-Zero modulation for output projection.

    Typical usage at the end of a DiT model before unpatchifying.

    Args:
        embed_dim: Model dimension D.
        patch_size: Patch size for computing output dimension.
        out_channels: Output channels (e.g., VAE latent channels).
    """

    def __init__(
        self,
        embed_dim: int,
        patch_size: int,
        out_channels: int,
    ):
        super().__init__()

        self.norm = nn.LayerNorm(embed_dim, elementwise_affine=False)

        self.adaLN_mlp = nn.Sequential(
            nn.SiLU(),
            nn.Linear(embed_dim, 2 * embed_dim),
        )

        self.linear = nn.Linear(
            embed_dim,
            patch_size * patch_size * out_channels,
        )

        # Zero-init
        nn.init.zeros_(self.adaLN_mlp[-1].weight)
        nn.init.zeros_(self.adaLN_mlp[-1].bias)
        nn.init.zeros_(self.linear.weight)
        nn.init.zeros_(self.linear.bias)

    def forward(self, x: Tensor, cond: Tensor) -> Tensor:
        """
        Final layer forward pass.

        Args:
            x: Input tensor [B, N, D]
            cond: Conditioning tensor [B, D]

        Returns:
            Output tensor [B, N, patch_size^2 * out_channels]
        """
        params = self.adaLN_mlp(cond)
        shift, scale = params.chunk(2, dim=-1)

        x = self.norm(x)
        x = x * (1 + scale.unsqueeze(1)) + shift.unsqueeze(1)
        x = self.linear(x)

        return x
