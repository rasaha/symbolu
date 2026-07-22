"""Internal-channel definitions for USE (read-only).

A *channel* is an explicitly-defined internal pathway that yields one vector per token position.
USE maps each channel to a phase (see ``phases.py``). Channel sets support the required
ablations: head-wise, layer-wise, Quad-only, value-space, residual, and full-network.

Per-head Quad-retrieval outputs and value vectors are recomputed here read-only from the
captured residual stream entering a block and that block's frozen attention module, using the
model's own weights. This runs no model forward and changes nothing.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List

import torch
import torch.nn.functional as F

from . import _qgr_path  # noqa: F401


@torch.no_grad()
def _recompute_heads(h: torch.Tensor, attn) -> Dict[str, torch.Tensor]:
    """Recompute per-head Quad outputs, values, and attention from residual input h [B,N,D].

    Mirrors QuadAttention.forward exactly (including the bounded geometry) but returns the
    per-head tensors. Read-only: uses attn's frozen parameters, runs no module forward.
    """
    B, N, D = h.shape
    Hn, dh = attn.num_heads, attn.head_dim
    x_norm = attn.norm_q(h)
    m_norm = attn.norm_m(h)
    Q = attn.W_q(x_norm).view(B, N, Hn, dh).transpose(1, 2)   # [B,H,N,dh]
    K = attn.W_k(m_norm).view(B, N, Hn, dh).transpose(1, 2)
    V = attn.W_v(m_norm).view(B, N, Hn, dh).transpose(1, 2)
    if getattr(attn, "bounded", False):
        qn = Q / (Q.norm(dim=-1, keepdim=True) + attn.bound_eps)
        kn = K / (K.norm(dim=-1, keepdim=True) + attn.bound_eps)
        scores = attn.bound_alpha * torch.matmul(qn, kn.transpose(-2, -1))
    else:
        scores = torch.matmul(Q, K.transpose(-2, -1)) * attn.scale
    mask = torch.triu(torch.ones(N, N, dtype=torch.bool, device=h.device), diagonal=1)
    scores = scores.masked_fill(mask, float("-inf"))
    attn_probs = F.softmax(scores, dim=-1)
    per_head_out = torch.matmul(attn_probs, V)                # [B,H,N,dh]  (Quad retrieval output)
    return {"per_head_out": per_head_out, "value": V, "attn_probs": attn_probs}


@torch.no_grad()
def build_channels(rec: Dict, model, channel_set: str) -> "OrderedDict[str, torch.Tensor]":
    """Return an ordered dict {channel_name: [B,N,dim]} for the requested channel set."""
    L = rec["num_layers"]
    Hn = rec["num_heads"]
    heads = {li: _recompute_heads(rec["block_in"][li], model.blocks[li].attn) for li in range(L)}

    def quad_heads(layers):
        d = OrderedDict()
        for li in layers:
            for h in range(Hn):
                d[f"quad_L{li}_H{h}"] = heads[li]["per_head_out"][:, h]      # [B,N,dh]
        return d

    def value_heads(layers):
        d = OrderedDict()
        for li in layers:
            for h in range(Hn):
                d[f"val_L{li}_H{h}"] = heads[li]["value"][:, h]
        return d

    cs = channel_set
    if cs in ("quad_heads", "quad_only", "quad"):
        return quad_heads(range(L))
    if cs == "quad_heads_L0":
        return quad_heads([0])
    if cs == "quad_heads_L1":
        return quad_heads([L - 1])
    if cs == "value_heads":
        return value_heads(range(L))
    if cs == "layers":
        d = OrderedDict()
        d["emb"] = rec["block_in"][0]
        for li in range(L):
            d[f"block_out_L{li}"] = rec["block_out"][li]
        return d
    if cs == "attn_out":
        return OrderedDict((f"attn_out_L{li}", rec["attn_out"][li]) for li in range(L))
    if cs == "ff":
        return OrderedDict((f"ff_L{li}", rec["ff_out"][li]) for li in range(L))
    if cs == "residual":
        return OrderedDict((f"res_L{li}", rec["block_out"][li]) for li in range(L))
    if cs == "full":
        d = quad_heads(range(L))
        d["emb"] = rec["block_in"][0]
        for li in range(L):
            d[f"block_out_L{li}"] = rec["block_out"][li]
        return d
    if cs == "full_network":
        d = quad_heads(range(L))
        d.update(value_heads(range(L)))
        d["emb"] = rec["block_in"][0]
        for li in range(L):
            d[f"block_out_L{li}"] = rec["block_out"][li]
            d[f"ff_L{li}"] = rec["ff_out"][li]
        return d
    raise ValueError(f"unknown channel set {cs!r}")


CHANNEL_SETS = [
    "quad_heads", "quad_heads_L0", "quad_heads_L1", "value_heads",
    "layers", "attn_out", "ff", "residual", "full", "full_network",
]
