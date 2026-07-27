"""
student_gate.py — per-head write-gate activations driven from the frozen V2-S gate logit
(core.W_w), applied through SelectivePhaseV2's `gate_override` hook. The frozen v2-S source
is never modified; only how the logit is turned into B_t ∈ [0,1] varies.

Gate types (§ Sparse-gate controls):
    sigmoid       : B = σ(logit)
    sparse_budget : B = σ(logit) (sparsity comes from the write-budget loss in train.py)
    hard_st       : straight-through hard gate — forward 1[logit>0], backward σ'(logit)
    topk          : keep the top-k gates per (example, head) over the sequence, else 0
                    (straight-through); k = ceil(topk_frac · N)
"""
from __future__ import annotations

import math
import torch
import torch.nn as nn
from torch import Tensor


class FocusConditionedGate(nn.Module):
    """Focus-conditioned write gate (§4 pilot):

        B_t = σ( MLP([ h_t, f_t, h_t⊙f_t, |h_t − f_t| ]) )   per head

    where f_t is a CAUSAL focus summary produced after the header — here the representation
    at the cue position (position 0), frozen and broadcast forward. No future information, no
    oracle match bit, no target label. This lets the gate compare the current event to the
    distant focus cue, which a token-only gate cannot do. Emits a per-head logit; the actual
    B_t activation (sigmoid / hard / top-k) is applied by gate_from_logit downstream.
    """

    def __init__(self, embed_dim, num_heads, hidden=None):
        super().__init__()
        h = hidden or 2 * embed_dim
        self.net = nn.Sequential(nn.Linear(4 * embed_dim, h), nn.GELU(), nn.Linear(h, num_heads))
        for m in self.net:
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, std=0.02); nn.init.zeros_(m.bias)

    def logit(self, h: Tensor, focus_pos: int = 0, summary_override: Tensor = None) -> Tensor:
        """h:[B,N,D] → per-head gate logit [B,N,H]. f_t = h[:,focus_pos] broadcast (causal).
        summary_override: optional [B,D] replacement for f_t (for summary-shuffle / random
        controls); must not carry future/target information when used at eval."""
        if summary_override is None:
            f = h[:, focus_pos:focus_pos + 1].expand_as(h)     # [B,N,D] header/cue summary
        else:
            f = summary_override.unsqueeze(1).expand_as(h)
        feat = torch.cat([h, f, h * f, (h - f).abs()], dim=-1)
        return self.net(feat)


def gate_from_logit(logit: Tensor, kind: str = "sigmoid", topk_frac: float = 0.2) -> Tensor:
    """logit: [B,N,H] → B_t in [0,1], same shape. Causal (token-only)."""
    soft = torch.sigmoid(logit)
    if kind in ("sigmoid", "sparse_budget"):
        return soft
    if kind == "hard_st":
        hard = (logit > 0).float()
        return hard + (soft - soft.detach())         # straight-through
    if kind == "topk":
        B, N, H = logit.shape
        k = max(1, math.ceil(topk_frac * N))
        # top-k over the sequence dim per (example, head)
        thresh = torch.topk(logit, k, dim=1).values[:, -1:, :]   # [B,1,H] k-th largest
        mask = (logit >= thresh).float()
        return mask + (soft - soft.detach())          # straight-through, gated by top-k mask
    raise ValueError(f"unknown gate kind {kind}")
