"""
matcher_gate.py — explicit focus↔event matcher gates (§ improved conditioned gate).

Recurrence is UNCHANGED (S_t = S_{t-1}+B_t(k⊙v), γ=1, ω=0). Only the gate that produces B_t
changes: instead of a generic concat-MLP inferring relational equality implicitly, we give the
gate an explicit learned similarity between the stored focus summary f_t and the current event
h_t, and split event-detection from relevance-matching (two-stage):

    z_f = LN(W_f f_t),  z_h = LN(W_h h_t)                 (shared comparison space)
    cosine  : s_t = (z_f·z_h) / (‖z_f‖‖z_h‖ · τ)
    bilinear: s_t = z_fᵀ M z_h                            (learns which focus dims ↔ event dims)
    e_t = σ(W_e h_t)         (is this an event worth considering?)
    r_t = σ(a·s_t + b)       (does it match the remembered focus?)
    B_t = e_t · r_t          per head (r_t broadcast over heads)

f_t is the causal header-captured focus summary (rep at the cue position) — not the mixed
recurrent state — so it hasn't absorbed later distractor content. No oracle match bit, no
future query, no target label at inference. `match_score` exposes s_t for the ranking loss and
for relevant-vs-distractor AUROC.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor


class MatcherGate(nn.Module):
    def __init__(self, embed_dim, num_heads, kind="bilinear", comp_dim=64, tau=0.1):
        super().__init__()
        self.kind = kind
        self.tau = tau
        self.W_f = nn.Linear(embed_dim, comp_dim, bias=False)
        self.W_h = nn.Linear(embed_dim, comp_dim, bias=False)
        self.ln_f = nn.LayerNorm(comp_dim)
        self.ln_h = nn.LayerNorm(comp_dim)
        self.W_e = nn.Linear(embed_dim, num_heads)          # event detector (per head)
        self.a = nn.Parameter(torch.tensor(4.0))            # relevance scale
        self.b = nn.Parameter(torch.tensor(0.0))            # relevance bias
        if kind == "bilinear":
            self.M = nn.Parameter(torch.eye(comp_dim) + 0.01 * torch.randn(comp_dim, comp_dim))
        for lin in (self.W_f, self.W_h):
            nn.init.normal_(lin.weight, std=0.02)
        nn.init.normal_(self.W_e.weight, std=0.02); nn.init.zeros_(self.W_e.bias)

    def _project(self, h, focus_pos=0, summary_override=None):
        f = summary_override if summary_override is not None else h[:, focus_pos]   # [B,D]
        z_f = self.ln_f(self.W_f(f))                        # [B,comp]
        z_h = self.ln_h(self.W_h(h))                        # [B,N,comp]
        return z_f, z_h

    def match_score(self, h, focus_pos=0, summary_override=None) -> Tensor:
        """Relevance score s_t, shape [B,N]."""
        z_f, z_h = self._project(h, focus_pos, summary_override)
        if self.kind == "cosine":
            zf = z_f / (z_f.norm(dim=-1, keepdim=True) + 1e-6)
            zh = z_h / (z_h.norm(dim=-1, keepdim=True) + 1e-6)
            return (zh * zf.unsqueeze(1)).sum(-1) / self.tau
        # bilinear: s = z_f^T M z_h
        zfM = z_f @ self.M                                  # [B,comp]
        return torch.einsum("bc,bnc->bn", zfM, z_h)

    def logit(self, h, focus_pos=0, summary_override=None) -> Tensor:
        """Per-head gate logit for B_t = e_t·r_t, returned as a logit so gate_from_logit can
        apply sigmoid/hard/top-k uniformly. logit = log(e·r/(1-e·r)) is avoided; instead we
        return a logit whose sigmoid equals e_t·r_t via log-odds of the product is nontrivial,
        so we expose B directly through gate_prob and a matched logit."""
        s = self.match_score(h, focus_pos, summary_override)            # [B,N]
        r = torch.sigmoid(self.a * s + self.b).unsqueeze(-1)            # [B,N,1]
        e = torch.sigmoid(self.W_e(h))                                  # [B,N,H]
        B = (e * r).clamp(1e-5, 1 - 1e-5)                               # [B,N,H]
        return torch.log(B / (1 - B))                                   # logit with σ(logit)=B

    def event_logit(self, h) -> Tensor:
        return self.W_e(h)                                              # [B,N,H]
