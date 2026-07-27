"""
matcher_losses.py — objectives for the matcher gate (§ change loss to paired ranking).

Primary   : pairwise ranking on the match score s_t (s_relevant > s_distractor by a margin),
            aligned with AUROC — or an InfoNCE contrastive variant.
Secondary : event-vs-filler BCE on the event detector e_t (learnable per-token).
Alignment : pull the focus projection toward relevant-event projections, push from distractors.
Budget    : discourage dense writes.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor


def pairwise_rank(s: Tensor, rel_mask: Tensor, distr_mask: Tensor, margin: float = 0.5) -> Tensor:
    """s:[B,N]; masks:[B,N] bool. Per example, all (relevant, distractor) pairs hinge."""
    losses = []
    for b in range(s.shape[0]):
        pos, neg = s[b][rel_mask[b]], s[b][distr_mask[b]]
        if pos.numel() and neg.numel():
            losses.append(F.relu(margin - pos.unsqueeze(1) + neg.unsqueeze(0)).mean())
    return torch.stack(losses).mean() if losses else torch.zeros((), device=s.device)


def infonce(s: Tensor, rel_mask: Tensor, distr_mask: Tensor, tau: float = 0.5) -> Tensor:
    losses = []
    for b in range(s.shape[0]):
        pos, neg = s[b][rel_mask[b]], s[b][distr_mask[b]]
        if pos.numel() and neg.numel():
            denom = torch.logsumexp(torch.cat([pos, neg]) / tau, dim=0)
            losses.append(-(pos / tau - denom).mean())
    return torch.stack(losses).mean() if losses else torch.zeros((), device=s.device)


def event_vs_filler(e_logit: Tensor, event_mask: Tensor, filler_mask: Tensor) -> Tensor:
    """e_logit:[B,N,H]; supervise mean-over-heads event detector: 1 at events, 0 at filler."""
    e = torch.sigmoid(e_logit).mean(-1)
    m = event_mask | filler_mask
    if not m.any():
        return torch.zeros((), device=e_logit.device)
    tgt = event_mask.float()
    return F.binary_cross_entropy(e[m].clamp(1e-4, 1 - 1e-4), tgt[m])


def alignment(z_f: Tensor, z_h: Tensor, rel_mask: Tensor, distr_mask: Tensor, m: float = 0.2) -> Tensor:
    """z_f:[B,comp]; z_h:[B,N,comp]. Focus ↔ relevant aligned, focus ↔ distractor separated."""
    zf = z_f / (z_f.norm(dim=-1, keepdim=True) + 1e-6)
    zh = z_h / (z_h.norm(dim=-1, keepdim=True) + 1e-6)
    cos = (zh * zf.unsqueeze(1)).sum(-1)                         # [B,N]
    losses = []
    for b in range(z_f.shape[0]):
        pos, neg = cos[b][rel_mask[b]], cos[b][distr_mask[b]]
        if pos.numel():
            losses.append(1 - pos.mean())
        if neg.numel():
            losses.append(F.relu(neg.mean() - m))
    return torch.stack(losses).mean() if losses else torch.zeros((), device=z_f.device)
