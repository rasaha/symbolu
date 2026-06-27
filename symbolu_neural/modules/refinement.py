"""EQ-F1..F4/F6 — Entropy-gated recurrent refinement core.

This is the most novel and most fragile module: an adaptive-depth recurrent
refinement of the sequence state, gated by entropy, with a soft mode router
(symbolic vs anchor). MVP uses ACT-style halting (Graves 2016) over a shared
transformer-encoder block; the research upgrade is a Deep Equilibrium (implicit
diff) formulation with a certified-contraction energy.

- Q1 differentiable?  Via ACT relaxation (yes) / DEQ implicit diff (research).
- Q2 grads flow?      Yes (unrolled BPTT here; truncation bias is the cost).
- Q3 reformulation:   EQ-F1 f -> shared recurrent block; EQ-F3 barrier energy
                      tau/H REMOVED (diverges as H->0) -> replaced by ACT ponder
                      cost; EQ-F4 hard stop -> halting probabilities; EQ-F6 hard
                      switch -> soft router (softmax over modes).
- Q4 role:            New capability (recurrent depth + routing).
- Q5 joint?           Yes.
- Q7 aux loss:        stability/convergence loss (ponder cost + final-step delta).
- Q8 failure mode:    no fixed-point guarantee; unrolling is memory-heavy; the
                      original tau/H energy is ill-posed (see SPEC R-1) and is
                      intentionally NOT reproduced here.
"""
from __future__ import annotations

from typing import Dict, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class EntropyGatedRefinementCore(nn.Module):
    def __init__(self, d_model: int, max_steps: int = 4, halt_eps: float = 0.01,
                 n_router_modes: int = 2, nhead: int = 4):
        super().__init__()
        self.max_steps = max_steps
        self.halt_eps = halt_eps
        # shared recurrent block (EQ-F1 f); two mode-specific transforms (EQ-F6)
        self.block = nn.TransformerEncoderLayer(
            d_model, nhead=nhead, dim_feedforward=4 * d_model, batch_first=True
        )
        self.mode_transforms = nn.ModuleList(
            nn.Linear(d_model, d_model) for _ in range(n_router_modes)
        )
        # router uses entropy(3) + pooled state; halting unit per ACT
        self.router = nn.Linear(d_model + 3, n_router_modes)
        self.halt = nn.Linear(d_model, 1)

    def forward(
        self, x: torch.Tensor, entropy_vec: torch.Tensor,
        mask: torch.Tensor = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """x:[B,n,d], entropy_vec:[B,3] -> (refined:[B,n,d], info)."""
        B, n, d = x.shape
        kpm = None if mask is None else (mask == 0)
        halting_acc = x.new_zeros(B, n)
        out = x.new_zeros(B, n, d)
        remainders = x.new_zeros(B, n)
        n_updates = x.new_zeros(B, n)
        state = x
        last_delta = x.new_zeros(())
        for step in range(self.max_steps):
            prev = state
            pooled = state.mean(dim=1)                                  # [B,d]
            mode_logits = self.router(torch.cat([pooled, entropy_vec], -1))
            mode_w = F.softmax(mode_logits, dim=-1)                     # [B,M]
            mixed = sum(mode_w[:, i].view(B, 1, 1) * t(state)
                        for i, t in enumerate(self.mode_transforms))
            state = self.block(state + mixed, src_key_padding_mask=kpm) # EQ-F1
            p_halt = torch.sigmoid(self.halt(state)).squeeze(-1)        # [B,n]
            still = (halting_acc < 1.0 - self.halt_eps).float()
            new_halted = ((halting_acc + p_halt * still) >= 1.0 - self.halt_eps).float()
            contrib = torch.where(new_halted.bool(),
                                  1.0 - halting_acc, p_halt) * still
            out = out + contrib.unsqueeze(-1) * state                   # ACT weighting
            halting_acc = halting_acc + contrib
            n_updates = n_updates + still
            remainders = remainders + (1.0 - halting_acc) * (1.0 - still)
            last_delta = (state - prev).pow(2).mean()                   # EQ-F4 proxy
        ponder = (n_updates + remainders).mean()
        info = {"ponder_cost": ponder, "final_delta": last_delta,
                "mode_w": mode_w}
        return out, info
