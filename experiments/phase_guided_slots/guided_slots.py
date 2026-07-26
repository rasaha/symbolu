"""
guided_slots.py — Phase-guidable bounded slot memory (new module; frozen
BoundedBindingSlots is NOT modified).

The module is guidance-AGNOSTIC: it consumes per-token write gate, write key,
write value, and retention priority (computed by the model's guidance head), and
a read query at the answer position. Configs C and D therefore differ ONLY in
whether the guidance head/read query see Phase's global state g_t — a clean causal
isolation of Phase's contribution.

Contracts:
  * persistent state O(M*D); per-token compute O(M*D); total O(N*M*D).
  * NEVER materializes [B,N,M,D] or any [.,N,N]. Streaming write loop over N.
  * eviction under pressure keeps the highest-retention slots (retention priority
    is provided per write; can come from Phase in D or from local-only in C).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from symbolu.lightweight_phase.invariants import register_shape


@dataclass
class GuidedSlotState:
    keys: Tensor      # [B,M,Ds]
    values: Tensor    # [B,M,Dv]
    retain: Tensor    # [B,M] retention priority (higher = keep)
    usage: Tensor     # [B,M]
    active: Tensor    # [B,M]
    src: Tensor       # [B,M] long (source id written)

    def numel(self):
        return sum(t.numel() for t in (self.keys, self.values, self.retain,
                                       self.usage, self.active))


class GuidedBoundedSlots(nn.Module):
    def __init__(self, num_slots: int, key_dim: int, val_dim: int,
                 match_threshold: float = 0.6):
        super().__init__()
        self.M = num_slots
        self.Ds = key_dim
        self.Dv = val_dim
        self.match_threshold = match_threshold

    def init_state(self, B, device, dtype=torch.float32) -> GuidedSlotState:
        M = self.M
        return GuidedSlotState(
            keys=torch.zeros(B, M, self.Ds, device=device, dtype=dtype),
            values=torch.zeros(B, M, self.Dv, device=device, dtype=dtype),
            retain=torch.full((B, M), -1e4, device=device, dtype=dtype),
            usage=torch.zeros(B, M, device=device, dtype=dtype),
            active=torch.zeros(B, M, device=device, dtype=dtype),
            src=torch.full((B, M), -1, device=device, dtype=torch.long),
        )

    def write_stream(self, write_key: Tensor, write_val: Tensor, write_gate: Tensor,
                     retain: Tensor, src_ids: Tensor,
                     state: Optional[GuidedSlotState] = None) -> GuidedSlotState:
        """Stream writes over the sequence.

        write_key:[B,N,Ds] write_val:[B,N,Dv] write_gate:[B,N] retain:[B,N]
        src_ids:[B,N] long. Returns final GuidedSlotState. O(N*M*D), no [B,N,M,D].
        """
        B, N, _ = write_key.shape
        device = write_key.device
        if state is None:
            state = self.init_state(B, device, write_key.dtype)
        keys, values = state.keys, state.values
        retain_s, usage, active = state.retain, state.usage, state.active
        src = state.src
        register_shape("guided_slot_scores", (B, self.M), n_seq_axes=0)

        for t in range(N):
            g = write_gate[:, t]                    # [B] in [0,1]
            wk = write_key[:, t]                     # [B,Ds]
            wv = write_val[:, t]                     # [B,Dv]
            rt = retain[:, t]                        # [B]
            # match to existing active slot
            sim = F.cosine_similarity(wk.unsqueeze(1), keys, dim=-1)  # [B,M]
            sim = sim.masked_fill(active < 0.5, -2.0)
            best_sim, best_idx = sim.max(dim=-1)                       # [B]
            matched = best_sim >= self.match_threshold

            free = active < 0.5
            has_free = free.any(dim=-1)
            free_idx = torch.argmax(free.float(), dim=-1)
            # eviction target: lowest retention among active (Phase-guided in D)
            evict_idx = torch.argmin(retain_s + (active < 0.5) * 1e9, dim=-1)
            alloc_idx = torch.where(has_free, free_idx, evict_idx)
            idx = torch.where(matched, best_idx, alloc_idx)            # [B]

            # only write where gate is meaningfully open (soft, differentiable)
            gate = g.unsqueeze(-1)                                     # [B,1]
            onehot = F.one_hot(idx, self.M).to(wk.dtype)              # [B,M]
            m = (onehot * gate)                                        # [B,M] write mass
            m1 = m.unsqueeze(-1)                                       # [B,M,1]
            keys = keys * (1 - m1) + m1 * wk.unsqueeze(1)
            values = values * (1 - m1) + m1 * wv.unsqueeze(1)
            # retention/usage/active updated (detached bookkeeping w/ soft gate)
            retain_s = retain_s * (1 - m) + m * rt.unsqueeze(1)
            usage = usage * 0.999 + m
            active = torch.clamp(active + m, max=1.0)
            with torch.no_grad():
                hard = (gate.squeeze(-1) > 0.5)                        # [B]
                for b in range(B):
                    if hard[b]:
                        src[b, idx[b]] = src_ids[b, t]

        return GuidedSlotState(keys=keys, values=values, retain=retain_s,
                               usage=usage, active=active, src=src)

    def read_topk(self, read_query: Tensor, state: GuidedSlotState,
                  top_k: int) -> Tuple[Tensor, Tensor, Tensor]:
        """Bounded Top-K read. read_query:[B,Ds] → (slot_vals[B,K,Dv], idx[B,K], attn[B,K])."""
        B = read_query.shape[0]
        M = self.M
        scores = torch.einsum("bd,bmd->bm", read_query, state.keys) / (self.Ds ** 0.5)
        scores = scores.masked_fill(state.active < 0.5, float("-inf"))
        k = min(top_k, M)
        topv, topi = scores.topk(k, dim=-1)
        finite = torch.isfinite(topv)
        attn = torch.softmax(topv.masked_fill(~finite, float("-inf")), dim=-1)
        attn = torch.where(finite.any(-1, keepdim=True), attn, torch.zeros_like(attn))
        vals = torch.gather(state.values, 1, topi.unsqueeze(-1).expand(-1, -1, self.Dv))
        return vals, topi, attn
