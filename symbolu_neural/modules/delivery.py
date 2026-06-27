"""EQ-J1/J2 — Delivery Harmonization head.

Selects one of three tonal modes (Sweet Resonance, Inverse Jolt, Symbolic
Metaphor) via Gumbel-softmax at train time (argmax at eval), and emits a style
embedding that conditions generation. This is a controllable-generation head;
its training signal is human preference / style supervision.

- Q1 differentiable?  Yes via Gumbel-softmax (argmax at inference).
- Q2 grads flow?      Through the relaxed sample.
- Q3 reformulation:   EQ-J1 argmax Phi -> Gumbel-softmax over 3 modes; EQ-J2 clip
                      -> differentiable clamp.
- Q4 role:            New capability (style/tone control head).
- Q5 joint?           Yes.
- Q7 aux loss:        DHA preference/style loss (CE or pairwise ranking).
- Q8 failure mode:    reward sparsity; style<->content entanglement; mode collapse;
                      "changes style but not task quality" is a kill criterion.
"""
from __future__ import annotations

from typing import Dict, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..config import N_MODE


class DeliveryHarmonizationHead(nn.Module):
    def __init__(self, d_model: int, gumbel_temp: float = 1.0):
        super().__init__()
        self.temp = gumbel_temp
        # Phi mode-scorer over [pooled state, H_D,H_G,H_K, readiness]
        self.phi = nn.Linear(d_model + 4, N_MODE)
        self.style_emb = nn.Parameter(torch.randn(N_MODE, d_model) * 0.02)

    def forward(
        self, pooled: torch.Tensor, ctrl_feats: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """pooled:[B,d], ctrl_feats:[B,4] ([H_D,H_G,H_K,readiness]) ->
        (style:[B,d], info{mode_logits:[B,3], mode_w:[B,3]})."""
        logits = self.phi(torch.cat([pooled, ctrl_feats], dim=-1))   # EQ-J1
        if self.training:
            mode_w = F.gumbel_softmax(logits, tau=self.temp, hard=False)
        else:
            idx = logits.argmax(-1)
            mode_w = F.one_hot(idx, N_MODE).to(logits.dtype)
        style = mode_w @ self.style_emb                              # [B,d]
        return style, {"mode_logits": logits, "mode_w": mode_w}
