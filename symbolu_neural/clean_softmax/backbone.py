"""A clean, standard softmax decoder-only Transformer LM.

Deliberately vanilla and self-contained: token embedding + learned positional
encoding + causal masked scaled-dot-product self-attention + SwiGLU FFN + RMSNorm
+ residuals + weight-tied vocab head. NO phase attention, NO Sovereign State,
NO JEPA, NO CSR/phase rotation. This is the uncontaminated baseline the Symbol-U
modules attach to.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


class RMSNorm(nn.Module):
    def __init__(self, d: int, eps: float = 1e-5):
        super().__init__()
        self.eps = eps
        self.g = nn.Parameter(torch.ones(d))

    def forward(self, x):
        return self.g * x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)


class CausalSelfAttention(nn.Module):
    def __init__(self, d: int, n_heads: int, dropout: float = 0.0):
        super().__init__()
        assert d % n_heads == 0
        self.h = n_heads
        self.dk = d // n_heads
        self.qkv = nn.Linear(d, 3 * d, bias=False)
        self.proj = nn.Linear(d, d, bias=False)
        self.drop = dropout

    def forward(self, x):
        B, L, d = x.shape
        q, k, v = self.qkv(x).split(d, dim=2)
        q = q.view(B, L, self.h, self.dk).transpose(1, 2)
        k = k.view(B, L, self.h, self.dk).transpose(1, 2)
        v = v.view(B, L, self.h, self.dk).transpose(1, 2)
        o = F.scaled_dot_product_attention(           # standard softmax attention
            q, k, v, is_causal=True,
            dropout_p=self.drop if self.training else 0.0)
        o = o.transpose(1, 2).contiguous().view(B, L, d)
        return self.proj(o)


class SwiGLU(nn.Module):
    def __init__(self, d: int, d_ff: int):
        super().__init__()
        self.w1 = nn.Linear(d, d_ff, bias=False)
        self.w2 = nn.Linear(d, d_ff, bias=False)
        self.wo = nn.Linear(d_ff, d, bias=False)

    def forward(self, x):
        return self.wo(F.silu(self.w1(x)) * self.w2(x))


class CausalBlock(nn.Module):
    """Pre-norm causal transformer block. Reused by backbone and (causally) by
    the entropy-gated refinement core so refinement never leaks future tokens."""

    def __init__(self, d: int, n_heads: int, d_ff: int, dropout: float = 0.0):
        super().__init__()
        self.n1 = RMSNorm(d)
        self.attn = CausalSelfAttention(d, n_heads, dropout)
        self.n2 = RMSNorm(d)
        self.ff = SwiGLU(d, d_ff)

    def forward(self, x):
        x = x + self.attn(self.n1(x))
        x = x + self.ff(self.n2(x))
        return x


@dataclass
class BackboneConfig:
    vocab_size: int = 256
    d_model: int = 128
    n_layers: int = 3
    n_heads: int = 4
    d_ff: int = 512
    max_seq: int = 256
    dropout: float = 0.0


class SoftmaxTransformerLM(nn.Module):
    def __init__(self, cfg: BackboneConfig):
        super().__init__()
        self.cfg = cfg
        self.tok = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.pos = nn.Embedding(cfg.max_seq, cfg.d_model)
        self.blocks = nn.ModuleList(
            CausalBlock(cfg.d_model, cfg.n_heads, cfg.d_ff, cfg.dropout)
            for _ in range(cfg.n_layers))
        self.norm = RMSNorm(cfg.d_model)
        self.head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        self.head.weight = self.tok.weight                 # weight tying
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, std=0.02)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, std=0.02)

    def hidden(self, ids: torch.Tensor) -> torch.Tensor:
        B, L = ids.shape
        pos = torch.arange(L, device=ids.device).unsqueeze(0)
        x = self.tok(ids) + self.pos(pos)
        for blk in self.blocks:
            x = blk(x)
        return self.norm(x)                                # [B,L,d]

    def logits(self, h: torch.Tensor) -> torch.Tensor:
        return self.head(h)

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        return self.logits(self.hidden(ids))
