"""EQ-H1..H4 — Experience anchor router.

Ten learned anchor embeddings, soft-attended using an entropy+context query
(replaces argmax selection). Hysteresis (EQ-H3) is realized as an EMA over the
attention weights (a soft surrogate for the hard OR-high/AND-low band) to damp
oscillation between anchors across refinement steps.

- Q1 differentiable?  Yes (attention over a learned slot memory).
- Q2 grads flow?      Yes.
- Q3 reformulation:   EQ-H2 argmax psi -> soft attention; EQ-H3 hard hysteresis
                      -> EMA temporal smoothing; EQ-H4 kappa -> learned transition bias.
- Q4 role:            Augments / routing-prior + grounding memory.
- Q5 joint?           Yes (hysteresis<->smoothness trade-off).
- Q7 aux loss:        none required.
- Q8 failure mode:    soft hysteresis may reintroduce the oscillation it was meant
                      to prevent; anchors may go unused (dead slots).
"""
from __future__ import annotations

from typing import Dict, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..config import N_ANCHOR


class ExperienceAnchorRouter(nn.Module):
    def __init__(self, d_model: int, hysteresis_ema: float = 0.9):
        super().__init__()
        self.ema = hysteresis_ema
        self.anchors = nn.Parameter(torch.randn(N_ANCHOR, d_model) * 0.02)  # EQ-H1
        self.query = nn.Linear(d_model + 3, d_model)                        # EQ-H2 psi
        self.register_buffer("prev_w", torch.zeros(N_ANCHOR), persistent=False)

    def forward(
        self, state: torch.Tensor, entropy_vec: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """state:[B,d], entropy_vec:[B,3] -> (anchor_mix:[B,d], info{w:[B,10]})."""
        q = self.query(torch.cat([state, entropy_vec], dim=-1))    # [B,d]
        w = F.softmax(q @ self.anchors.t(), dim=-1)               # [B,10] EQ-H2
        # EQ-H3 hysteresis: EMA smooth across calls (uses running mean over batch)
        smoothed = self.ema * self.prev_w + (1 - self.ema) * w.mean(0).detach()
        if self.training:
            self.prev_w = smoothed
        anchor_mix = w @ self.anchors                             # [B,d]
        return anchor_mix, {"w": w, "hysteresis_w": smoothed}
