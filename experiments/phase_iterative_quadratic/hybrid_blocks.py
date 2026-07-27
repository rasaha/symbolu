"""
hybrid_blocks.py — P (frozen Phase feature) + Q (bounded softmax) building blocks.

PhaseFeature wraps the FROZEN V2-S recurrence (γ=1, ω=0, one bank, existing readout) and
exposes its per-position readout as a bounded O(N) causal feature. Phase parameters are frozen
(requires_grad=False); Phase only informs routing/features, never Q/K/V or logits.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.phase_v2_experimental.config import cfg_v2s
from symbolu.phase_v2_experimental.selective_phase import SelectivePhaseV2


class PhaseFeature(nn.Module):
    def __init__(self, embed_dim, num_heads):
        super().__init__()
        self.core = SelectivePhaseV2(cfg_v2s(embed_dim, num_heads))     # γ=1 persistent bank
        for p in self.core.parameters():
            p.requires_grad_(False)
        self.proj = nn.Linear(embed_dim, embed_dim)                     # trainable adapter

    @torch.no_grad()
    def _readout(self, x):
        return self.core(x) - x                                        # frozen V2-S readout [B,N,D]

    def forward(self, x: Tensor, zero=False, shuffle=False) -> Tensor:
        r = self._readout(x)
        if zero:
            r = torch.zeros_like(r)
        elif shuffle:
            r = r[torch.randperm(r.shape[0], device=r.device)]
        return self.proj(r)
