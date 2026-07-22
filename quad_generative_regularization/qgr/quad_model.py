"""Authentic Quad-scoring CPU transformer for the Quad generative regularization study.

The model reproduces the *phase-free separable core* of the canonical Quad scorer
`BindingCacheQuadQuery` (symbolu/phase_transformer.py:3507), as documented in
QUAD_TRACEABILITY.md.  Per implementation-spec sections 2 and 3, there is NO separate
phase / state / synchronization / Kuramoto mechanism anywhere in this module: Quad
queries its own hidden states (memory_state := hidden states), which is exactly the
mathematically separable subset of the authentic Quad score identified in the
Phase-0 compatibility gate.

The authentic Quad generative score per head is

    S^Q_{i,j} = ( W_q . LN_q(h_i) ) . ( W_k . LN_m(h_j) ) / sqrt(d_h)          (causal: j <= i)

and the ordinary forward path is softmax(S^Q) @ V, matching the canonical spec
Section 4 (steps 1-8) in dense (Top-K = N) mode.

The score tensor S^Q is exposed for the *training-only* auxiliary loss.  Exposing it
adds no operation to the deployed forward path (it is already computed), so a model
trained with lambda=0 is bit-identical to the task-only baseline (Arm A == Arm D0).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


@dataclass
class QuadConfig:
    """Configuration for the Quad-scoring transformer. All dimensions configurable."""

    vocab_size: int = 64
    hidden_size: int = 96
    num_layers: int = 2
    num_heads: int = 4
    ff_size: int = 384
    context_length: int = 64
    dropout: float = 0.0
    # Which block's Quad score S^Q is exposed for the auxiliary loss (default: last).
    aux_layer: int = -1
    # Padding token id (position 0 reserved). Embedding uses padding_idx.
    pad_id: int = 0

    def resolved_aux_layer(self) -> int:
        return self.aux_layer if self.aux_layer >= 0 else self.num_layers + self.aux_layer


class QuadAttention(nn.Module):
    """Authentic Quad generative scorer (phase-free reduction, memory_state := hidden states).

    Faithful to BindingCacheQuadQuery: query is projected from the (LayerNorm'd) input,
    keys/values from the (LayerNorm'd) memory tensor; here memory == the same hidden
    states, which is the separable phase-independent core (QUAD_TRACEABILITY.md sec 3).
    Dense mode (Top-K = N) is used so the score is the exact softmax attention score.
    """

    def __init__(self, hidden_size: int, num_heads: int, dropout: float = 0.0):
        super().__init__()
        if hidden_size % num_heads != 0:
            raise ValueError(
                f"hidden_size ({hidden_size}) must be divisible by num_heads ({num_heads})"
            )
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.head_dim = hidden_size // num_heads
        self.scale = self.head_dim ** -0.5

        # Query from input; Key/Value from memory (== hidden states here). bias=False
        # exactly as in the canonical BindingCacheQuadQuery.
        self.W_q = nn.Linear(hidden_size, hidden_size, bias=False)
        self.W_k = nn.Linear(hidden_size, hidden_size, bias=False)
        self.W_v = nn.Linear(hidden_size, hidden_size, bias=False)
        self.out_proj = nn.Linear(hidden_size, hidden_size, bias=False)

        self.norm_q = nn.LayerNorm(hidden_size)
        self.norm_m = nn.LayerNorm(hidden_size)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: Tensor,
        memory: Optional[Tensor] = None,
        causal: bool = True,
    ) -> Tuple[Tensor, Tensor]:
        """Return (output [B,N,D], quad_score S^Q [B,H,N,N] causal-masked, pre-softmax)."""
        B, N, D = x.shape
        H, d_h = self.num_heads, self.head_dim
        m = x if memory is None else memory

        x_norm = self.norm_q(x)
        m_norm = self.norm_m(m)

        Q = self.W_q(x_norm).view(B, N, H, d_h).transpose(1, 2)   # [B,H,N,d_h]
        K = self.W_k(m_norm).view(B, N, H, d_h).transpose(1, 2)   # [B,H,N,d_h]
        V = self.W_v(m_norm).view(B, N, H, d_h).transpose(1, 2)   # [B,H,N,d_h]

        # Authentic Quad score: scaled dot product, per head.
        scores = torch.matmul(Q, K.transpose(-2, -1)) * self.scale  # [B,H,N,N]

        if causal:
            mask = torch.triu(
                torch.ones(N, N, device=x.device, dtype=torch.bool), diagonal=1
            )
            scores = scores.masked_fill(mask, float("-inf"))

        quad_score = scores  # S^Q_{i,j}: causal-masked, pre-softmax generative score.

        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)
        out = torch.matmul(attn, V)                                  # [B,H,N,d_h]
        out = out.transpose(1, 2).reshape(B, N, D)
        out = self.out_proj(out)
        return out, quad_score


class FeedForward(nn.Module):
    def __init__(self, hidden_size: int, ff_size: int, dropout: float = 0.0):
        super().__init__()
        self.norm = nn.LayerNorm(hidden_size)
        self.fc1 = nn.Linear(hidden_size, ff_size)
        self.fc2 = nn.Linear(ff_size, hidden_size)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: Tensor) -> Tensor:
        return self.fc2(self.drop(F.gelu(self.fc1(self.norm(x)))))


class QuadBlock(nn.Module):
    """Pre-norm residual block: Quad attention + feed-forward."""

    def __init__(self, cfg: QuadConfig):
        super().__init__()
        self.attn = QuadAttention(cfg.hidden_size, cfg.num_heads, cfg.dropout)
        self.ff = FeedForward(cfg.hidden_size, cfg.ff_size, cfg.dropout)

    def forward(self, x: Tensor, causal: bool = True) -> Tuple[Tensor, Tensor]:
        attn_out, quad_score = self.attn(x, causal=causal)
        x = x + attn_out
        x = x + self.ff(x)
        return x, quad_score


class QuadTransformer(nn.Module):
    """Small causal transformer whose attention IS the authentic Quad scorer.

    forward returns logits and (optionally) the exposed Quad score at the aux layer.
    The `expose_quad` flag only controls whether the already-computed score tensor is
    *returned*; it never changes the forward computation (see the A vs D0 equivalence
    test).  Hidden states at each layer input are also captured so Arm C can build a
    generic hidden-state relational signal from the SAME layer, without touching the
    Quad score.
    """

    def __init__(self, cfg: QuadConfig):
        super().__init__()
        self.cfg = cfg
        self.token_emb = nn.Embedding(cfg.vocab_size, cfg.hidden_size, padding_idx=cfg.pad_id)
        self.pos_emb = nn.Embedding(cfg.context_length, cfg.hidden_size)
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList([QuadBlock(cfg) for _ in range(cfg.num_layers)])
        self.norm_f = nn.LayerNorm(cfg.hidden_size)
        self.head = nn.Linear(cfg.hidden_size, cfg.vocab_size, bias=False)
        self._aux_layer = cfg.resolved_aux_layer()

    def forward(
        self,
        tokens: Tensor,
        expose_quad: bool = False,
        expose_hidden: bool = False,
    ) -> Dict[str, Tensor]:
        """tokens: [B,N] long. Returns dict with 'logits' and optionally 'quad_score'
        (S^Q at the aux layer, [B,H,N,N]) and 'aux_hidden' (input hidden states to the
        aux layer, [B,N,D]) for the Arm-C generic relational control."""
        B, N = tokens.shape
        pos = torch.arange(N, device=tokens.device).unsqueeze(0).expand(B, N)
        x = self.token_emb(tokens) + self.pos_emb(pos)
        x = self.drop(x)

        quad_score: Optional[Tensor] = None
        aux_hidden: Optional[Tensor] = None
        for li, block in enumerate(self.blocks):
            if li == self._aux_layer and expose_hidden:
                aux_hidden = x  # hidden state feeding the aux layer (generic relation source)
            x, score = block(x, causal=True)
            if li == self._aux_layer and expose_quad:
                quad_score = score

        logits = self.head(self.norm_f(x))
        out: Dict[str, Tensor] = {"logits": logits}
        if expose_quad:
            out["quad_score"] = quad_score
        if expose_hidden:
            out["aux_hidden"] = aux_hidden
        return out

    def num_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


class GenericRelationHead(nn.Module):
    """Arm-C control: an equal-capacity, OFF-PATH learned relation on hidden states.

    Structurally identical to the Quad scorer (LayerNorm + W_q/W_k + scaled dot product),
    but it does NOT participate in the model's forward path — it is a training-only readout
    of the aux-layer hidden states, discarded at inference.  This isolates the single
    scientific variable: Arm D supervises the model's own forward-path Quad score, whereas
    Arm C supervises an identical-form relation that the model never uses to compute its
    output.  Both start from a non-trivial (uniform-ish) init, so neither aux target is
    pre-satisfied — a fair generic relational control (spec sections 12, 14).
    """

    def __init__(self, hidden_size: int, num_heads: int):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = hidden_size // num_heads
        self.scale = self.head_dim ** -0.5
        self.norm_q = nn.LayerNorm(hidden_size)
        self.norm_k = nn.LayerNorm(hidden_size)
        self.W_q = nn.Linear(hidden_size, hidden_size, bias=False)
        self.W_k = nn.Linear(hidden_size, hidden_size, bias=False)

    def forward(self, h: Tensor) -> Tensor:
        """h: [B,N,D] -> generic relation score [B,H,N,N] (causal-masked, pre-softmax)."""
        B, N, D = h.shape
        H, d_h = self.num_heads, self.head_dim
        q = self.W_q(self.norm_q(h)).view(B, N, H, d_h).transpose(1, 2)
        k = self.W_k(self.norm_k(h)).view(B, N, H, d_h).transpose(1, 2)
        scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale
        mask = torch.triu(torch.ones(N, N, device=h.device, dtype=torch.bool), diagonal=1)
        return scores.masked_fill(mask, float("-inf"))


def build_model(cfg: QuadConfig, seed: int) -> QuadTransformer:
    """Deterministically construct a model with a fixed init seed (identical across arms).

    Uses PyTorch's default module initialization under a fixed global seed. This gives
    correct LayerNorm init (weight=1, bias=0) and Kaiming-uniform linear weights, and is
    fully reproducible: the same seed yields bit-identical parameters, so Arms A, C, and
    D start from the same initialization (spec section 14).
    """
    torch.manual_seed(seed)
    model = QuadTransformer(cfg)
    # padding_idx already zeros the pad embedding row; nothing else to override.
    return model
