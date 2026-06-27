"""Capacity-/FLOP-matched controls for the active Symbol-U mechanisms.

These exist to answer the adversarial question: does a Symbol-U mechanism learn
something a plain Transformer cannot reproduce with the SAME compute budget?

- RecurrentPlainRefine controls Recursive Refinement: a SHARED plain causal block
  applied `steps` times (recurrent depth) with NO entropy signal, NO halting, NO
  gated-delta accumulation. Same params (one block) and same FLOPs (steps
  applications) as CausalEntropyRefinement — the only thing removed is the
  Symbol-U gating machinery. This is the tightest possible control for refinement.

- PointwiseMemoryControl controls Deferred-Insight Memory: a pointwise residual
  FFN with params ≈ memory's value projection (d^2) and matched FLOPs, but NO
  cross-time mixing. Isolates whether memory's causal prefix-summary beats plain
  pointwise capacity.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .backbone import CausalBlock


class RecurrentPlainRefine(nn.Module):
    def __init__(self, d: int, n_heads: int, d_ff: int, steps: int = 3):
        super().__init__()
        self.steps = steps
        self.block = CausalBlock(d, n_heads, d_ff)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        for _ in range(self.steps):
            h = self.block(h)                              # plain recurrent depth
        return h


class PointwiseMemoryControl(nn.Module):
    def __init__(self, d: int, hidden: int = None):
        super().__init__()
        hidden = hidden or max(1, d // 2)                  # 2*d*hidden ≈ d^2 params
        self.w1 = nn.Linear(d, hidden)
        self.w2 = nn.Linear(hidden, d)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        return h + self.w2(F.gelu(self.w1(h)))             # pointwise, no time mixing
