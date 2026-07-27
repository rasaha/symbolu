"""
routing_mask.py — build the bounded attention set A_t (§5) without a full N×N tensor.

    A_t = LocalWindow(t, W) ∪ RoutedEvents(q_h, K) ∪ PriorHopState

Produces, per query, a bounded list of allowed key indices (≤ W+K+|prior|) with a validity
mask, plus (for the reference only) the equivalent boolean [B,Lq,Lkv] mask. Enforces causal
masking (idx ≤ query position), padding (idx < valid length), deterministic routed ordering,
and deduplication (a token that is both local and routed is counted once).
"""
from __future__ import annotations

import torch
from torch import Tensor


def build_allowed(query_pos: Tensor, routed_idx: Tensor, W: int, valid_len: Tensor,
                  prior_idx: Tensor = None, Lkv: int = None):
    """
    query_pos:[B,Lq] absolute key-position of each query; routed_idx:[B,K] global routed key
    indices (−1 = none); valid_len:[B] number of real (non-pad) keys; prior_idx:[B,P] or None.
    Returns gather_idx:[B,Lq,M] (clamped to valid, dupes/invalid point at 0) and
    valid_mask:[B,Lq,M] bool.
    """
    B, Lq = query_pos.shape
    dev = query_pos.device
    K = routed_idx.shape[1]
    P = 0 if prior_idx is None else prior_idx.shape[1]
    # local window indices [t-W+1 .. t]
    off = torch.arange(W, device=dev)                                # 0..W-1
    local = query_pos.unsqueeze(-1) - (W - 1) + off                  # [B,Lq,W]
    routed = routed_idx.unsqueeze(1).expand(B, Lq, K)                # [B,Lq,K]
    cand = torch.cat([local, routed], dim=-1)                        # [B,Lq,W+K]
    if P:
        cand = torch.cat([cand, prior_idx.unsqueeze(1).expand(B, Lq, P)], dim=-1)
    M = cand.shape[-1]
    # validity: non-negative, causal (≤ query_pos), within valid_len, (routed −1 filtered)
    valid = (cand >= 0) & (cand <= query_pos.unsqueeze(-1)) & (cand < valid_len.view(B, 1, 1))
    # deduplicate: keep first occurrence along M
    dup = torch.zeros_like(valid)
    for m in range(1, M):
        same = (cand[..., m:m + 1] == cand[..., :m]) & valid[..., m:m + 1] & valid[..., :m]
        dup[..., m] = same.any(dim=-1)
    valid = valid & ~dup
    gather = cand.clamp(min=0)
    if Lkv is not None:
        gather = gather.clamp(max=Lkv - 1)
    gather = torch.where(valid, gather, torch.zeros_like(gather))
    return gather, valid


def full_mask(gather_idx: Tensor, valid_mask: Tensor, Lkv: int) -> Tensor:
    """Equivalent boolean [B,Lq,Lkv] allow-mask (for the reference implementation)."""
    B, Lq, M = gather_idx.shape
    mask = torch.zeros(B, Lq, Lkv, dtype=torch.bool, device=gather_idx.device)
    idx = torch.where(valid_mask, gather_idx, torch.full_like(gather_idx, Lkv))  # invalid → OOB bucket
    idx = idx.clamp(max=Lkv)
    ext = torch.zeros(B, Lq, Lkv + 1, dtype=torch.bool, device=gather_idx.device)
    ext.scatter_(2, idx, True)
    return ext[:, :, :Lkv]
