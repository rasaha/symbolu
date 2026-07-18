"""EQ-A2/A3/A4/B2 + Guna/Kosha — typed latent-factor heads.

These are the heart of the architecture and the locus of the #1 research risk:
*identifiability / grounding*. As linear+softmax probes they are trivially
differentiable, but without supervision (the "syntable") or a strong prior the
5/10/3/5-way categoricals become arbitrary clusters, not Vritti/Guna/Kosha.
Entropy gradients cannot fix this (entropy is permutation-invariant).

Mapping (per head documented in its class):
- Q1 differentiable?  Yes (already the EQ-L4 softmax form).
- Q2 grads flow?      Yes.
- Q4 role:            Augments the backbone with typed latent heads.
- Q5 joint?           Yes.
- Q7 aux loss:        typed-supervision CE (REQUIRED for grounding); optional IB.
- Q8 failure mode:    uninterpretable clusters if unsupervised; head collapse.
"""
from __future__ import annotations

from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..config import N_VRITTI, N_ASPECT, N_GUNA, N_KOSHA


class _SoftmaxHead(nn.Module):
    """Generic linear -> log_softmax head. in:[...,d] -> logp:[...,C]."""

    def __init__(self, d_model: int, n_classes: int):
        super().__init__()
        self.lin = nn.Linear(d_model, n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.log_softmax(self.lin(x), dim=-1)


class VrittiHead(_SoftmaxHead):
    """EQ-A2. in u:[B,n,d] -> log p_v:[B,n,5]."""

    def __init__(self, d_model: int):
        super().__init__(d_model, N_VRITTI)


class AspectHead(_SoftmaxHead):
    """EQ-A3. in u:[B,n,d] -> log p_w_syl:[B,n,10]."""

    def __init__(self, d_model: int):
        super().__init__(d_model, N_ASPECT)


class AspectAggregator(nn.Module):
    """EQ-B2. Attention-pool per-syllable aspect logits to utterance level.

    in  p_w_syl_logp:[B,n,10], u:[B,n,d]  ->  log p_w:[B,10]
    The combiner is a learned attention over syllable slots (the patent leaves
    the aggregation rule unspecified; this is the candidate learned form).
    """

    def __init__(self, d_model: int):
        super().__init__()
        self.attn = nn.Linear(d_model, 1)

    def forward(self, p_w_syl_logp: torch.Tensor, u: torch.Tensor) -> torch.Tensor:
        a = F.softmax(self.attn(u).squeeze(-1), dim=-1)         # [B,n]
        p_w_syl = p_w_syl_logp.exp()
        p_w = (a.unsqueeze(-1) * p_w_syl).sum(dim=1)            # [B,10]
        return (p_w.clamp_min(1e-8)).log()


class GunaHead(_SoftmaxHead):
    """Guna distribution from a pooled utterance rep. in h:[B,d] -> log p_g:[B,3].

    Provenance of p_g is patent-unspecified (MRQ-7); here it is a learned head.
    """

    def __init__(self, d_model: int):
        super().__init__(d_model, N_GUNA)


class KoshaHead(_SoftmaxHead):
    """Kosha distribution. in h:[B,d] -> log p_k:[B,5]. (MRQ-7: learned head.)"""

    def __init__(self, d_model: int):
        super().__init__(d_model, N_KOSHA)


class ContextVrittiCoupling(nn.Module):
    """EQ-A4. s_C = sum_v p_v[v] * kappa(e_v, C).  Learned bilinear kappa.

    in  p_v:[B,n,5], context:[B,d]  ->  s_C:[B,n]
    """

    def __init__(self, d_model: int):
        super().__init__()
        self.vritti_emb = nn.Parameter(torch.randn(N_VRITTI, d_model) * 0.02)
        self.bilinear = nn.Bilinear(d_model, d_model, 1)

    def forward(self, p_v: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        B, n, _ = p_v.shape
        ctx = context.unsqueeze(1).expand(B, N_VRITTI, -1)            # [B,5,d]
        ev = self.vritti_emb.unsqueeze(0).expand(B, -1, -1)          # [B,5,d]
        kappa = self.bilinear(ev, ctx).squeeze(-1)                  # [B,5]
        s_c = torch.einsum("bnv,bv->bn", p_v, kappa)                # [B,n]
        return s_c
