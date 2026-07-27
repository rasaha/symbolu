"""
iterative_router.py — query-conditioned relevance routers (§3 step 2/7).

Given the CURRENT query q_h, score each candidate event and select the top-K global events to
enter the bounded attention set. The router changes its selection as q_h evolves across hops.
Router kinds: cond (MLP), cosine, bilinear. Interventions (oracle/random/shuffled/phase-zero)
are handled at the model level.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor


class LearnedRouter(nn.Module):
    def __init__(self, embed_dim, kind="cond", comp=48):
        super().__init__()
        self.kind = kind
        if kind == "cond":
            self.net = nn.Sequential(nn.Linear(4 * embed_dim, 2 * embed_dim), nn.GELU(),
                                     nn.Linear(2 * embed_dim, 1))
        else:
            self.Wq = nn.Linear(embed_dim, comp, bias=False)
            self.We = nn.Linear(embed_dim, comp, bias=False)
            self.ln_q = nn.LayerNorm(comp); self.ln_e = nn.LayerNorm(comp)
            if kind == "bilinear":
                self.M = nn.Parameter(torch.eye(comp) + 0.01 * torch.randn(comp, comp))
            self.tau = 0.1

    def score(self, q: Tensor, ereps: Tensor) -> Tensor:
        """q:[B,D]; ereps:[B,Ne,D] → scores:[B,Ne]."""
        B, Ne, D = ereps.shape
        if self.kind == "cond":
            qb = q.unsqueeze(1).expand(B, Ne, D)
            feat = torch.cat([qb, ereps, qb * ereps, (qb - ereps).abs()], dim=-1)
            return self.net(feat).squeeze(-1)
        zq = self.ln_q(self.Wq(q)); ze = self.ln_e(self.We(ereps))
        if self.kind == "cosine":
            zq = zq / (zq.norm(dim=-1, keepdim=True) + 1e-6)
            ze = ze / (ze.norm(dim=-1, keepdim=True) + 1e-6)
            return (ze * zq.unsqueeze(1)).sum(-1) / self.tau
        return torch.einsum("bc,bnc->bn", zq @ self.M, ze)           # bilinear
