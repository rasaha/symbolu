"""EQ-A1 — Soft phoneme/syllable segmentation.

Differentiability review mapping
--------------------------------
- Q1 differentiable?      Partial -> made differentiable via learned strided
                          attention pooling (Charformer/GBST-style), no hard
                          boundary argmax.
- Q2 gradients flow?      Yes, through the soft pooling weights.
- Q3 reformulation:       Replace discrete boundary detection with a boundary
                          *scorer* + softmax-weighted block pooling at a fixed
                          stride. (DP/marginalized segmentation is the research
                          upgrade; this MVP uses fixed-stride soft pooling.)
- Q4 role:                Augments the tokenizer with a phonological pooling bias.
- Q5 joint-trainable?     Yes.
- Q6 tensors:             in  x:[B,L,d] (+mask:[B,L]) -> out u:[B,n,d], align:[B,n,L]
- Q7 aux losses:          none required (optional boundary supervision).
- Q8 failure mode:        fixed stride may not align to true syllables; n is a
                          heuristic; long-range syllable structure is ignored.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class SoftSyllableSegmenter(nn.Module):
    def __init__(self, d_model: int, stride: int = 2):
        super().__init__()
        self.stride = stride
        # per-position salience score used to soft-weight within each block
        self.boundary_scorer = nn.Linear(d_model, 1)
        self.proj = nn.Linear(d_model, d_model)

    def forward(
        self, x: torch.Tensor, mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """x:[B,L,d] -> (u:[B,n,d], align:[B,n,L]).  n = ceil(L/stride)."""
        B, L, d = x.shape
        s = self.stride
        n = math.ceil(L / s)
        pad = n * s - L
        if pad:
            x = F.pad(x, (0, 0, 0, pad))
            if mask is not None:
                mask = F.pad(mask, (0, pad), value=0)
        scores = self.boundary_scorer(x).squeeze(-1)        # [B, n*s]
        scores = scores.view(B, n, s)
        if mask is not None:
            m = mask.view(B, n, s)
            scores = scores.masked_fill(m == 0, float("-inf"))
        w = F.softmax(scores, dim=-1)                       # [B,n,s] within-block
        w = torch.nan_to_num(w)                             # all-masked block -> 0
        xb = x.view(B, n, s, d)
        u = self.proj((w.unsqueeze(-1) * xb).sum(dim=2))    # [B,n,d]
        # scatter within-block weights back to a full block-diagonal alignment [B,n,L]
        align = w.new_zeros(B, n, n * s)
        rows = torch.arange(n, device=x.device)
        for j in range(s):                                  # tiny loop over stride
            align[:, rows, rows * s + j] = w[:, :, j]
        return u, align[:, :, :L]
