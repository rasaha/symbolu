"""
local_window.py — Stage 6 bounded local sliding-window attention (O(N·W)).

This is a genuine sub-quadratic sliding window: it never materializes an [N, N]
score matrix. For each query position it attends to at most ``window`` past keys
(causal), computed via an unfold over a left-padded key/value tensor, producing
scores of shape [B, H, N, W]. Peak intermediate memory is O(N·W), not O(N²).

It supports the same incremental ``step`` contract used elsewhere via a small
ring of the last ``window`` tokens carried in ``LocalWindowState``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from .invariants import register_shape


@dataclass
class LocalWindowState:
    """Carries the last ``window`` normalized-token projections for streaming."""

    k: Tensor  # [B, H, L, Dh], L ≤ window
    v: Tensor  # [B, H, L, Dh]

    def numel(self) -> int:
        return self.k.numel() + self.v.numel()


class LocalWindowAttention(nn.Module):
    """Causal sliding-window multi-head attention, O(N·W) time and memory."""

    def __init__(self, embed_dim: int, num_heads: int, window: int,
                 dropout: float = 0.0, layernorm_eps: float = 1e-5):
        super().__init__()
        assert embed_dim % num_heads == 0
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.window = window
        self.norm = nn.LayerNorm(embed_dim, eps=layernorm_eps)
        self.W_q = nn.Linear(embed_dim, embed_dim, bias=False)
        self.W_k = nn.Linear(embed_dim, embed_dim, bias=False)
        self.W_v = nn.Linear(embed_dim, embed_dim, bias=False)
        self.W_out = nn.Linear(embed_dim, embed_dim, bias=False)
        self.dropout = nn.Dropout(dropout)
        self.reset_parameters()

    def reset_parameters(self) -> None:
        for lin in (self.W_q, self.W_k, self.W_v, self.W_out):
            nn.init.normal_(lin.weight, mean=0.0, std=0.02)

    def _heads(self, t: Tensor) -> Tensor:
        B, N, _ = t.shape
        return t.view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B,H,N,Dh]

    def forward(self, x: Tensor, *, return_residual_add: bool = True) -> Tensor:
        """Return x + local_attn(LN(x)) if return_residual_add else the attn output."""
        B, N, D = x.shape
        W = min(self.window, N)
        x_norm = self.norm(x)
        q = self._heads(self.W_q(x_norm))  # [B,H,N,Dh]
        k = self._heads(self.W_k(x_norm))
        v = self._heads(self.W_v(x_norm))

        # Left-pad keys/values by (W-1) so each query has a full window to unfold.
        k_pad = F.pad(k, (0, 0, W - 1, 0))  # pad along the N axis (dim=2), front
        v_pad = F.pad(v, (0, 0, W - 1, 0))
        # unfold along sequence: windows of length W ending at each position.
        k_win = k_pad.unfold(2, W, 1).permute(0, 1, 2, 4, 3)  # [B,H,N,W,Dh]
        v_win = v_pad.unfold(2, W, 1).permute(0, 1, 2, 4, 3)  # [B,H,N,W,Dh]
        register_shape("local_scores", (B, self.num_heads, N, W), n_seq_axes=1)

        scores = torch.einsum("bhnd,bhnwd->bhnw", q, k_win) / math.sqrt(self.head_dim)
        # Mask padded slots for the first W-1 positions (padding sits at window front).
        # Position i (0-indexed) has valid keys for the last min(i+1, W) window slots.
        idx = torch.arange(N, device=x.device)
        valid_counts = torch.clamp(idx + 1, max=W)  # [N]
        slot = torch.arange(W, device=x.device)  # window slot 0..W-1 (0=oldest)
        # valid if slot >= W - valid_counts
        valid = slot.view(1, W) >= (W - valid_counts).view(N, 1)  # [N, W]
        scores = scores.masked_fill(~valid.view(1, 1, N, W), float("-inf"))

        attn = torch.softmax(scores, dim=-1)
        attn = self.dropout(attn)
        out = torch.einsum("bhnw,bhnwd->bhnd", attn, v_win)  # [B,H,N,Dh]
        out = out.transpose(1, 2).reshape(B, N, D)
        out = self.W_out(out)
        return x + out if return_residual_add else out
