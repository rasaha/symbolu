"""
2D Rotary Position Embedding for Phase-Quad Image Generator.

This implements STANDARD 2D RoPE for geometric awareness in the
QuadRetriever. Phase-modulated RoPE is explicitly NOT implemented
per design specification (high coupling risk).

The 2D RoPE applies separate rotary embeddings for x and y coordinates,
allowing the model to encode 2D spatial relationships.
"""

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
from torch import Tensor


class RotaryPositionEmbedding2D(nn.Module):
    """
    Standard 2D Rotary Position Embedding.

    Applies separate rotary embeddings for row (y) and column (x)
    coordinates. The head dimension is split in half: first half
    encodes x position, second half encodes y position.

    IMPORTANT: This is STANDARD 2D RoPE. Phase-modulated RoPE is
    explicitly deferred per design specification (Section 3.6).

    Args:
        dim: Head dimension (must be divisible by 4).
        max_seq_len: Maximum sequence length per dimension.
        base: Base for exponential frequency computation.
    """

    def __init__(
        self,
        dim: int,
        max_seq_len: int = 256,
        base: float = 10000.0,
    ):
        super().__init__()

        if dim % 4 != 0:
            raise ValueError(
                f"dim must be divisible by 4 for 2D RoPE, got {dim}. "
                "Half the dimensions encode x, half encode y, and each "
                "uses sin/cos pairs."
            )

        self.dim = dim
        self.max_seq_len = max_seq_len
        self.base = base

        # Each spatial dimension gets half the head dimension
        self.dim_per_axis = dim // 2

        # Compute inverse frequencies
        # Shape: [dim_per_axis // 2]
        inv_freq = 1.0 / (
            base ** (torch.arange(0, self.dim_per_axis, 2).float() / self.dim_per_axis)
        )
        self.register_buffer("inv_freq", inv_freq)

        # Cache for position encodings
        self._cached_freqs_x: Optional[Tensor] = None
        self._cached_freqs_y: Optional[Tensor] = None
        self._cached_max: int = 0

    def _compute_freqs(self, max_pos: int, device: torch.device) -> Tuple[Tensor, Tensor]:
        """
        Compute frequency tensors for positions 0 to max_pos-1.

        Returns:
            freqs_x: [max_pos, dim_per_axis // 2]
            freqs_y: [max_pos, dim_per_axis // 2]
        """
        if self._cached_max >= max_pos and self._cached_freqs_x is not None:
            return (
                self._cached_freqs_x[:max_pos].to(device),
                self._cached_freqs_y[:max_pos].to(device),
            )

        # Position indices
        pos = torch.arange(max_pos, device=device, dtype=self.inv_freq.dtype)

        # Outer product: [max_pos, dim_per_axis // 2]
        freqs = torch.outer(pos, self.inv_freq.to(device))

        # Cache (same frequencies for x and y, applied to different positions)
        self._cached_freqs_x = freqs
        self._cached_freqs_y = freqs
        self._cached_max = max_pos

        return freqs, freqs

    def forward(
        self,
        x: Tensor,
        coords: Tensor,
    ) -> Tensor:
        """
        Apply 2D rotary position embedding.

        Args:
            x: Input tensor [B, N, H, D_h] or [B, H, N, D_h].
            coords: Position coordinates [N, 2] where coords[i] = (row, col).

        Returns:
            x_rotated: Input with rotary embedding applied, same shape as x.
        """
        # Handle both [B, N, H, D_h] and [B, H, N, D_h] formats
        if x.dim() == 4:
            # Determine format by checking which dimension matches H
            # Assume D_h is smallest, H is second smallest
            shape = x.shape
            if shape[2] < shape[1]:
                # Format: [B, N, H, D_h]
                is_n_h_format = True
            else:
                # Format: [B, H, N, D_h]
                is_n_h_format = False
        else:
            raise ValueError(f"Expected 4D tensor, got {x.dim()}D")

        if is_n_h_format:
            B, N, H, D_h = x.shape
        else:
            B, H, N, D_h = x.shape
            x = x.transpose(1, 2)  # [B, N, H, D_h]

        if D_h != self.dim:
            raise ValueError(f"Expected head dim {self.dim}, got {D_h}")

        # Get coordinates
        row_coords = coords[:, 0]  # [N]
        col_coords = coords[:, 1]  # [N]

        # Get max position for frequency computation
        max_pos = max(row_coords.max().item(), col_coords.max().item()) + 1
        max_pos = max(max_pos, 1)  # Ensure at least 1

        # Compute frequencies
        freqs_x, freqs_y = self._compute_freqs(int(max_pos), x.device)

        # Get frequencies for each position
        # freqs_row: [N, dim_per_axis // 2]
        freqs_row = freqs_y[row_coords.long()]
        freqs_col = freqs_x[col_coords.long()]

        # Split x into x-part and y-part
        # x: [B, N, H, D_h] -> x_col, x_row: [B, N, H, D_h // 2]
        x_col, x_row = x.chunk(2, dim=-1)

        # Apply rotary embedding to each part
        x_col_rotated = self._apply_rotary(x_col, freqs_col)
        x_row_rotated = self._apply_rotary(x_row, freqs_row)

        # Concatenate
        x_out = torch.cat([x_col_rotated, x_row_rotated], dim=-1)

        # Restore original format if needed
        if not is_n_h_format:
            x_out = x_out.transpose(1, 2)  # [B, H, N, D_h]

        return x_out

    def _apply_rotary(self, x: Tensor, freqs: Tensor) -> Tensor:
        """
        Apply rotary embedding to a tensor.

        Args:
            x: [B, N, H, D] where D = dim_per_axis
            freqs: [N, D // 2]

        Returns:
            x_rotated: Same shape as x
        """
        B, N, H, D = x.shape

        # Split into pairs for rotation
        x1 = x[..., : D // 2]  # [B, N, H, D // 2]
        x2 = x[..., D // 2 :]  # [B, N, H, D // 2]

        # Expand freqs for batch and head dims
        # [N, D // 2] -> [1, N, 1, D // 2]
        freqs = freqs.unsqueeze(0).unsqueeze(2)

        # Compute sin and cos
        cos = torch.cos(freqs)
        sin = torch.sin(freqs)

        # Apply rotation
        x1_rot = x1 * cos - x2 * sin
        x2_rot = x1 * sin + x2 * cos

        return torch.cat([x1_rot, x2_rot], dim=-1)


def apply_2d_rope(
    q: Tensor,
    k: Tensor,
    coords: Tensor,
    rope: RotaryPositionEmbedding2D,
) -> Tuple[Tensor, Tensor]:
    """
    Apply 2D RoPE to query and key tensors.

    Args:
        q: Query tensor [B, N, H, D_h] or [B, H, N, D_h].
        k: Key tensor [B, N, H, D_h] or [B, H, N, D_h].
        coords: Position coordinates [N, 2].
        rope: RotaryPositionEmbedding2D instance.

    Returns:
        q_rot, k_rot: Rotated query and key tensors.
    """
    q_rot = rope(q, coords)
    k_rot = rope(k, coords)
    return q_rot, k_rot
