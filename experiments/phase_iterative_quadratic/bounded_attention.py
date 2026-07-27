"""
bounded_attention.py — BoundedRoutedSoftmaxAttention (§4).

Exact softmax attention from each query over ONLY its bounded allowed set (local window ∪
routed global events ∪ prior-hop state), gathered as ≤ (W+K+P) keys. Identical math to the
reference but never forms a [B,H,N,N] tensor — cost is O(B·Lq·M·dh). Shares the parameter
structure (Wq,Wk,Wv,Wo) with the reference so correctness can be checked by copying weights.
The Phase router controls only WHICH global events are in the routed set; it never touches
Wq/Wk/Wv, logits, temperature, or token/positional identities.
"""
from __future__ import annotations

import math
import torch
import torch.nn as nn
from torch import Tensor

from .routing_mask import build_allowed


class BoundedRoutedSoftmaxAttention(nn.Module):
    def __init__(self, embed_dim, num_heads):
        super().__init__()
        self.D, self.H, self.dh = embed_dim, num_heads, embed_dim // num_heads
        self.Wq = nn.Linear(embed_dim, embed_dim, bias=False)
        self.Wk = nn.Linear(embed_dim, embed_dim, bias=False)
        self.Wv = nn.Linear(embed_dim, embed_dim, bias=False)
        self.Wo = nn.Linear(embed_dim, embed_dim, bias=False)

    def forward(self, x_q: Tensor, x_kv: Tensor, query_pos: Tensor, routed_idx: Tensor,
                W: int, valid_len: Tensor, prior_idx: Tensor = None) -> Tensor:
        """x_q:[B,Lq,D]; x_kv:[B,N,D]; returns [B,Lq,D]. Bounded: only ≤W+K+P keys per query."""
        B, Lq, _ = x_q.shape
        N = x_kv.shape[1]
        gather, valid = build_allowed(query_pos, routed_idx, W, valid_len, prior_idx, Lkv=N)
        M = gather.shape[-1]
        q = self.Wq(x_q).view(B, Lq, self.H, self.dh)                       # [B,Lq,H,dh]
        kv = x_kv
        gidx = gather.reshape(B, Lq * M, 1).expand(B, Lq * M, self.D)
        k_g = self.Wk(kv).gather(1, gidx).view(B, Lq, M, self.H, self.dh)   # [B,Lq,M,H,dh]
        v_g = self.Wv(kv).gather(1, gidx).view(B, Lq, M, self.H, self.dh)
        scores = torch.einsum("blhd,blmhd->blhm", q, k_g) / math.sqrt(self.dh)   # [B,Lq,H,M]
        vm = valid.unsqueeze(2)                                             # [B,Lq,1,M]
        scores = scores.masked_fill(~vm, float("-inf"))
        none = (~vm).all(dim=-1, keepdim=True)
        scores = scores.masked_fill(none, 0.0)
        w = torch.softmax(scores, dim=-1).masked_fill(none, 0.0)            # [B,Lq,H,M]
        out = torch.einsum("blhm,blmhd->blhd", w, v_g).reshape(B, Lq, self.D)
        return self.Wo(out)

    @torch.no_grad()
    def diagnostics(self, x_q, x_kv, query_pos, routed_idx, W, valid_len, required_idx=None, prior_idx=None):
        """Attention mass / entropy / mass on required evidence (§11), bounded."""
        B, Lq, _ = x_q.shape; N = x_kv.shape[1]
        gather, valid = build_allowed(query_pos, routed_idx, W, valid_len, prior_idx, Lkv=N)
        M = gather.shape[-1]
        q = self.Wq(x_q).view(B, Lq, self.H, self.dh)
        gidx = gather.reshape(B, Lq * M, 1).expand(B, Lq * M, self.D)
        k_g = self.Wk(x_kv).gather(1, gidx).view(B, Lq, M, self.H, self.dh)
        scores = torch.einsum("blhd,blmhd->blhm", q, k_g) / math.sqrt(self.dh)
        scores = scores.masked_fill(~valid.unsqueeze(2), float("-inf"))
        w = torch.softmax(scores, dim=-1).nan_to_num(0.0).mean(2)          # [B,Lq,M] mean over heads
        ent = -(w.clamp_min(1e-9) * w.clamp_min(1e-9).log()).sum(-1).mean().item()
        req_mass = 0.0
        if required_idx is not None:
            hit = (gather == required_idx.view(B, 1, 1)) & valid
            req_mass = (w * hit.float()).sum(-1).mean().item()
        return {"entropy": ent, "required_evidence_mass": req_mass, "keys_per_query": int(valid.sum(-1).float().mean().item())}
