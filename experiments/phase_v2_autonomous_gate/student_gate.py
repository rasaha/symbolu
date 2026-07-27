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
from torch import Tensor


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
