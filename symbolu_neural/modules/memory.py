"""EQ-G1..G4 — Differentiable episodic memory (Deferred Insight Engine).

A key-value memory with content-based soft read and a readiness gate. The
triadic decision (defer / mirror-preview / full-surface) is a soft mixture for
training EXCEPT the harm branch, which is delegated to the hard safety boundary
(see modules/safety.py) and must NOT be softened at inference.

- Q1 differentiable?  Yes for read/write (NTM-style soft addressing).
- Q2 grads flow?      Through soft read; writes use straight-through on keys.
- Q3 reformulation:   EQ-G1 flags -> continuous slot states; EQ-G2 readiness
                      R>=tau -> sigmoid gate over [H_D,H_G,H_K,dt]; EQ-G3 phi gates
                      -> learned multiplicative gates; EQ-G4 branch -> soft mixture
                      (harm branch excluded, stays hard elsewhere).
- Q4 role:            New capability (episodic, readiness-gated recall).
- Q5 joint?           Yes.
- Q7 aux loss:        memory recall/helpfulness loss (needs a helpfulness signal).
- Q8 failure mode:    write/read collapse; recall that changes style but not task
                      quality (a kill criterion); harm-gating must remain hard.
"""
from __future__ import annotations

from typing import Dict, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class DeferredInsightMemory(nn.Module):
    def __init__(self, d_model: int, slots: int = 64, readiness_dim: int = 4):
        super().__init__()
        self.slots = slots
        self.key_proj = nn.Linear(d_model, d_model)
        self.val_proj = nn.Linear(d_model, d_model)
        self.query = nn.Linear(d_model, d_model)
        self.readiness = nn.Linear(readiness_dim, 1)         # EQ-G2 R
        self.write_gate = nn.Linear(d_model, 1)
        # persistent (non-parameter) memory buffers
        self.register_buffer("mem_k", torch.zeros(slots, d_model), persistent=False)
        self.register_buffer("mem_v", torch.zeros(slots, d_model), persistent=False)
        self.register_buffer("mem_age", torch.zeros(slots), persistent=False)
        self.register_buffer("ptr", torch.zeros(1, dtype=torch.long), persistent=False)

    @torch.no_grad()
    def write(self, state: torch.Tensor) -> None:
        """Round-robin write of a pooled state [B,d] (straight-through keys)."""
        k = self.key_proj(state).mean(0)
        v = self.val_proj(state).mean(0)
        i = int(self.ptr.item()) % self.slots
        self.mem_k[i] = k
        self.mem_v[i] = v
        self.mem_age.add_(1.0)
        self.mem_age[i] = 0.0
        self.ptr[0] = (i + 1) % self.slots

    def forward(
        self, state: torch.Tensor, readiness_feats: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """state:[B,d], readiness_feats:[B,readiness_dim] ([H_D,H_G,H_K,dt]) ->
        (recall:[B,d], info{readiness:[B,1], attn:[B,slots]})."""
        B, d = state.shape
        q = self.query(state)                                   # [B,d]
        attn = F.softmax(q @ self.mem_k.t(), dim=-1)            # [B,slots] read
        recall = attn @ self.mem_v                             # [B,d]
        R = torch.sigmoid(self.readiness(readiness_feats))     # [B,1] EQ-G2 gate
        gated = R * recall                                     # readiness-gated
        return gated, {"readiness": R, "attn": attn}
