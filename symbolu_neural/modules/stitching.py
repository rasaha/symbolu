"""EQ-D1..D4 — Soft stitching / differentiable selection.

The only genuinely hard discrete module. MVP uses a relaxed soft-top-k
(temperature softmax over candidate relevance) so gradients flow; the research
upgrade is differentiable top-k via perturbed optimizers / Sinkhorn ordering,
annealed to hard selection at inference (REINFORCE is the score-function fallback).

- Q1 differentiable?  Hard argmax -> Yes via relaxation.
- Q2 grads flow?      Through the soft selection weights (variance is the cost).
- Q3 reformulation:   EQ-D1 rel in log-space (product-of-powers); EQ-D2 indicators
                      -> soft agreement p_i . p_j; EQ-D4 argmax-subset -> soft top-k.
- Q4 role:            Replaces decoding-time selection/reranking.
- Q5 joint?           Partial (soft<->hard train/test gap).
- Q7 aux loss:        task reward (if REINFORCE) + optional diversity target.
- Q8 failure mode:    gradient variance; soft/hard mismatch; needs a candidate
                      source (off by default in the MVP — see config.enable_stitching).
"""
from __future__ import annotations

from typing import Dict, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class SoftStitchingSelector(nn.Module):
    def __init__(self, d_model: int, topk: int = 4, temp: float = 1.0):
        super().__init__()
        self.topk = topk
        self.temp = temp
        # EQ-D1 relevance: log-space sum of weighted log-factors
        self.rel_head = nn.Linear(d_model, 1)
        self.theta = nn.Parameter(torch.ones(1))   # exponent on the learned factor

    def forward(
        self, cand: torch.Tensor, cand_aspect: torch.Tensor = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """cand:[B,K,d] (candidate reps), cand_aspect:[B,K,10] optional ->
        (stitched:[B,d], info{sel_w:[B,K], redundancy:[B]})."""
        B, K, d = cand.shape
        log_rel = self.theta * self.rel_head(cand).squeeze(-1)        # EQ-D1 [B,K]
        sel_w = F.softmax(log_rel / self.temp, dim=-1)               # soft top-k proxy
        # EQ-D2 soft redundancy via aspect-distribution agreement (no hard indicator)
        if cand_aspect is not None:
            pa = cand_aspect.exp() if cand_aspect.lt(0).any() else cand_aspect
            agree = torch.einsum("bik,bjk->bij", pa, pa)            # [B,K,K]
            eye = torch.eye(K, device=cand.device).bool()
            redundancy = agree.masked_fill(eye, 0.0).mean(dim=(1, 2))
        else:
            redundancy = cand.new_zeros(B)
        stitched = (sel_w.unsqueeze(-1) * cand).sum(dim=1)           # [B,d]
        return stitched, {"sel_w": sel_w, "redundancy": redundancy,
                          "log_rel": log_rel}
