"""
reference_attention.py — explicit, correct multi-head scaled dot-product attention.

Ground truth for the bounded implementation. Standard exact softmax (no linear approximation):
    Q=XWq, K=XWk, V=XWv ; scores=QKᵀ/√dh + mask ; w=softmax(scores) ; out=wV.
Builds the full [B,H,Lq,Lkv] scores matrix — used ONLY as a small-sequence reference, never in
the bounded path.
"""
from __future__ import annotations

import math
import torch
import torch.nn as nn
from torch import Tensor


class ReferenceSoftmaxAttention(nn.Module):
    def __init__(self, embed_dim, num_heads):
        super().__init__()
        self.D, self.H = embed_dim, num_heads
        self.dh = embed_dim // num_heads
        self.Wq = nn.Linear(embed_dim, embed_dim, bias=False)
        self.Wk = nn.Linear(embed_dim, embed_dim, bias=False)
        self.Wv = nn.Linear(embed_dim, embed_dim, bias=False)
        self.Wo = nn.Linear(embed_dim, embed_dim, bias=False)

    def _split(self, x):
        B, L, _ = x.shape
        return x.view(B, L, self.H, self.dh).transpose(1, 2)          # [B,H,L,dh]

    def forward(self, x_q: Tensor, x_kv: Tensor, allow_mask: Tensor) -> Tensor:
        """x_q:[B,Lq,D]; x_kv:[B,Lkv,D]; allow_mask:[B,Lq,Lkv] bool (True = allowed)."""
        q, k, v = self._split(self.Wq(x_q)), self._split(self.Wk(x_kv)), self._split(self.Wv(x_kv))
        scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.dh)       # [B,H,Lq,Lkv]
        m = allow_mask.unsqueeze(1)                                   # [B,1,Lq,Lkv]
        scores = scores.masked_fill(~m, float("-inf"))
        # rows with no allowed key → uniform-zero output (avoid nan)
        none = (~m).all(dim=-1, keepdim=True)
        scores = scores.masked_fill(none, 0.0)
        w = torch.softmax(scores, dim=-1)
        w = w.masked_fill(none, 0.0)
        out = w @ v                                                  # [B,H,Lq,dh]
        out = out.transpose(1, 2).reshape(x_q.shape[0], x_q.shape[1], self.D)
        return self.Wo(out)

    @torch.no_grad()
    def attn_weights(self, x_q, x_kv, allow_mask):
        q, k = self._split(self.Wq(x_q)), self._split(self.Wk(x_kv))
        scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.dh)
        scores = scores.masked_fill(~allow_mask.unsqueeze(1), float("-inf"))
        return torch.softmax(scores, dim=-1)                         # [B,H,Lq,Lkv]
