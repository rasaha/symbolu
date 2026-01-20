"""
LocalMixer: Local coherence via windowed attention or depthwise convolution.

Provides cheap O(N·W) local context where W is window size.
Optionally includes cross-attention to text tokens.
"""

from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from symbolu.vision.controls import PatchMeta


class LocalMixer(nn.Module):
    """
    Local coherence via windowed attention or depthwise convolution.

    Provides cheap O(N·W) local context where W is window size.
    Optionally includes cross-attention to text tokens.

    The local mixer handles fine-grained texture and local patterns,
    while Phase-Quad handles global semantic coherence.

    Args:
        embed_dim: Model dimension D.
        window_size: Local attention window W.
        num_heads: Number of attention heads.
        use_cross_attn: Include cross-attention to text.
        text_dim: Text embedding dimension (required if use_cross_attn).
        dropout: Dropout rate.
    """

    def __init__(
        self,
        embed_dim: int,
        window_size: int = 8,
        num_heads: int = 8,
        use_cross_attn: bool = False,
        text_dim: Optional[int] = None,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.window_size = window_size
        self.num_heads = num_heads
        self.use_cross_attn = use_cross_attn

        # Local self-attention
        self.local_attn = nn.MultiheadAttention(
            embed_dim, num_heads, batch_first=True, dropout=dropout
        )
        self.norm1 = nn.LayerNorm(embed_dim)

        # Optional cross-attention to text
        if use_cross_attn:
            if text_dim is None:
                raise ValueError("text_dim required when use_cross_attn=True")
            self.cross_attn = nn.MultiheadAttention(
                embed_dim,
                num_heads,
                batch_first=True,
                kdim=text_dim,
                vdim=text_dim,
                dropout=dropout,
            )
            self.norm2 = nn.LayerNorm(embed_dim)
            self.text_proj = nn.Linear(text_dim, embed_dim) if text_dim != embed_dim else nn.Identity()
        else:
            self.cross_attn = None
            self.norm2 = None
            self.text_proj = None

        # Dropout
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        text_cond: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Apply local mixing.

        Args:
            x: Input tokens [B, N, D].
            meta: PatchMeta with grid dimensions.
            text_cond: Optional text embeddings [B, T, D_t].

        Returns:
            x_local: [B, N, D] locally mixed tokens.
        """
        B, N, D = x.shape

        # Windowed self-attention
        # Reshape to 2D grid, apply window attention, reshape back
        x_grid = x.view(B, meta.H_p, meta.W_p, D)
        x_windowed, num_windows = self._window_partition(x_grid, self.window_size)
        # x_windowed: [B * num_windows, window_size * window_size, D]

        # Apply self-attention within windows
        x_norm = self.norm1(x_windowed)
        x_attn, _ = self.local_attn(x_norm, x_norm, x_norm)
        x_windowed = x_windowed + self.dropout(x_attn)

        # Reverse windowing
        x_local = self._window_reverse(x_windowed, meta.H_p, meta.W_p, num_windows)
        x_local = x_local.view(B, N, D)

        # Optional cross-attention to text
        if self.use_cross_attn and text_cond is not None and self.cross_attn is not None:
            x_norm = self.norm2(x_local)
            # Project text if needed
            text_proj = self.text_proj(text_cond) if self.text_proj is not None else text_cond
            x_cross, _ = self.cross_attn(x_norm, text_cond, text_cond)
            x_local = x_local + self.dropout(x_cross)

        return x_local

    def _window_partition(
        self,
        x: Tensor,
        window_size: int,
    ) -> Tuple[Tensor, Tuple[int, int]]:
        """
        Partition input into non-overlapping windows.

        Args:
            x: Input tensor [B, H, W, D].
            window_size: Size of each window.

        Returns:
            windows: [B * num_windows, window_size * window_size, D].
            num_windows: Tuple (num_h, num_w) of window counts.
        """
        B, H, W, D = x.shape

        # Pad if necessary
        pad_h = (window_size - H % window_size) % window_size
        pad_w = (window_size - W % window_size) % window_size

        if pad_h > 0 or pad_w > 0:
            x = F.pad(x, (0, 0, 0, pad_w, 0, pad_h))
            H, W = H + pad_h, W + pad_w

        # Calculate number of windows
        num_h = H // window_size
        num_w = W // window_size

        # Reshape: [B, H, W, D] -> [B, num_h, ws, num_w, ws, D]
        x = x.view(B, num_h, window_size, num_w, window_size, D)

        # Permute: [B, num_h, num_w, ws, ws, D]
        x = x.permute(0, 1, 3, 2, 4, 5).contiguous()

        # Flatten windows: [B * num_h * num_w, ws * ws, D]
        windows = x.view(B * num_h * num_w, window_size * window_size, D)

        return windows, (num_h, num_w)

    def _window_reverse(
        self,
        windows: Tensor,
        H_orig: int,
        W_orig: int,
        num_windows: Tuple[int, int],
    ) -> Tensor:
        """
        Reverse window partition.

        Args:
            windows: [B * num_windows, ws * ws, D].
            H_orig: Original height (before padding).
            W_orig: Original width (before padding).
            num_windows: Tuple (num_h, num_w).

        Returns:
            x: [B, H_orig, W_orig, D].
        """
        num_h, num_w = num_windows
        ws = int((windows.shape[1]) ** 0.5)
        B = windows.shape[0] // (num_h * num_w)
        D = windows.shape[-1]

        # Reshape: [B * num_h * num_w, ws * ws, D] -> [B, num_h, num_w, ws, ws, D]
        x = windows.view(B, num_h, num_w, ws, ws, D)

        # Permute: [B, num_h, ws, num_w, ws, D]
        x = x.permute(0, 1, 3, 2, 4, 5).contiguous()

        # Merge: [B, H, W, D]
        H = num_h * ws
        W = num_w * ws
        x = x.view(B, H, W, D)

        # Remove padding
        if H > H_orig or W > W_orig:
            x = x[:, :H_orig, :W_orig, :]

        return x


class ConvLocalMixer(nn.Module):
    """
    Alternative local mixer using depthwise convolution.

    Faster than windowed attention but less expressive.
    Good for ablation studies.

    Args:
        embed_dim: Model dimension D.
        kernel_size: Convolution kernel size.
        use_cross_attn: Include cross-attention to text.
        text_dim: Text embedding dimension.
    """

    def __init__(
        self,
        embed_dim: int,
        kernel_size: int = 7,
        use_cross_attn: bool = False,
        text_dim: Optional[int] = None,
        num_heads: int = 8,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.kernel_size = kernel_size
        self.use_cross_attn = use_cross_attn

        # Depthwise convolution
        self.dwconv = nn.Conv2d(
            embed_dim,
            embed_dim,
            kernel_size=kernel_size,
            padding=kernel_size // 2,
            groups=embed_dim,
        )
        self.norm1 = nn.LayerNorm(embed_dim)

        # Pointwise convolution (1x1)
        self.pwconv = nn.Conv2d(embed_dim, embed_dim, kernel_size=1)

        # Optional cross-attention to text
        if use_cross_attn:
            if text_dim is None:
                raise ValueError("text_dim required when use_cross_attn=True")
            self.cross_attn = nn.MultiheadAttention(
                embed_dim,
                num_heads,
                batch_first=True,
                kdim=text_dim,
                vdim=text_dim,
            )
            self.norm2 = nn.LayerNorm(embed_dim)
        else:
            self.cross_attn = None
            self.norm2 = None

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        text_cond: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Apply convolution-based local mixing.

        Args:
            x: Input tokens [B, N, D].
            meta: PatchMeta with grid dimensions.
            text_cond: Optional text embeddings [B, T, D_t].

        Returns:
            x_local: [B, N, D] locally mixed tokens.
        """
        B, N, D = x.shape

        # Reshape to 2D: [B, N, D] -> [B, H, W, D] -> [B, D, H, W]
        x_2d = x.view(B, meta.H_p, meta.W_p, D).permute(0, 3, 1, 2)

        # Apply depthwise + pointwise conv
        x_conv = self.dwconv(x_2d)
        x_conv = self.pwconv(x_conv)

        # Reshape back: [B, D, H, W] -> [B, H, W, D] -> [B, N, D]
        x_local = x_conv.permute(0, 2, 3, 1).view(B, N, D)

        # Residual + norm
        x_local = self.norm1(x + x_local)

        # Optional cross-attention
        if self.use_cross_attn and text_cond is not None and self.cross_attn is not None:
            x_norm = self.norm2(x_local)
            x_cross, _ = self.cross_attn(x_norm, text_cond, text_cond)
            x_local = x_local + x_cross

        return x_local
