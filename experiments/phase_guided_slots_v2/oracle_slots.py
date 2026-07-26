"""
oracle_slots.py — bounded slot memory with ORACLE composite-identity addressing.

Rationale (per the redesign directive): neural identity-key learning is a *separate*
unresolved problem — trained content keys either collapse (all facts → one slot) or
learn a query-independent shortcut, so the previous key-diversity/curriculum sweeps
could not isolate the capacity question. This module makes record ALLOCATION and
query LOOKUP structurally correct using oracle entity ids, while everything that the
research question actually concerns stays LEARNED:

    LEARNED   : value encoding, retention priority, eviction (by learned retention),
                final value decoding.
    ORACLE    : which slot a record goes to and which slot a query reads:
                  same identity   → same slot   (supersession, in place)
                  new identity     → free slot, else evict lowest-retention slot
                  query identity   → the slot holding that identity (or nothing)

Consequence (the clean baseline this is meant to produce):
    target survives (not evicted)  → its value is retrievable → accuracy high
    target evicted                 → read returns nothing      → accuracy ≈ chance
    overall accuracy ≈ target survival rate.

Addressing/eviction are discrete index ops (no grad); the VALUE path is fully
differentiable via the soft gated blend, so value-encode/decode and retention still
train end to end. This is NOT the frozen BoundedBindingSlots (untouched) — it is a
new experiment module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import torch
import torch.nn as nn
from torch import Tensor


@dataclass
class OracleSlotState:
    entity: Tensor   # [B,M] long   oracle identity in each slot (-1 empty)
    value: Tensor    # [B,M,Dv]     learned bound value (differentiable)
    retain: Tensor   # [B,M]        learned retention priority (higher = keep)
    active: Tensor   # [B,M]        1 active / 0 empty
    # instrumentation counters (no grad)
    n_alloc: Tensor  # [B]
    n_evict: Tensor  # [B]
    n_super: Tensor  # [B]  (supersession in-place updates)
    target_evicted: Tensor  # [B]  target ever evicted


class OracleSlots(nn.Module):
    def __init__(self, num_slots: int, val_dim: int):
        super().__init__()
        self.M = num_slots
        self.Dv = val_dim

    def init_state(self, B, device, dtype=torch.float32) -> OracleSlotState:
        M = self.M
        return OracleSlotState(
            entity=torch.full((B, M), -1, device=device, dtype=torch.long),
            value=torch.zeros(B, M, self.Dv, device=device, dtype=dtype),
            retain=torch.full((B, M), -1e4, device=device, dtype=dtype),
            active=torch.zeros(B, M, device=device, dtype=dtype),
            n_alloc=torch.zeros(B, device=device), n_evict=torch.zeros(B, device=device),
            n_super=torch.zeros(B, device=device),
            target_evicted=torch.zeros(B, device=device),
        )

    def write_stream(self, entity_ids: Tensor, values: Tensor, gate: Tensor,
                     retain: Tensor, target_entity: Optional[Tensor] = None) -> OracleSlotState:
        """entity_ids:[B,N] long (-1 where not a write anchor). values:[B,N,Dv].
        gate:[B,N] in [0,1]. retain:[B,N]. Streams writes with oracle addressing."""
        B, N, Dv = values.shape
        device = values.device
        st = self.init_state(B, device, values.dtype)
        entity, value, ret, active = st.entity, st.value, st.retain, st.active
        M = self.M
        ar = torch.arange(B, device=device)
        for t in range(N):
            e = entity_ids[:, t]                          # [B]
            g = gate[:, t]                                # [B]
            val = values[:, t]                            # [B,Dv]
            rt = retain[:, t]                             # [B]
            hard = (g > 0.5) & (e >= 0)                   # [B] real write

            with torch.no_grad():
                match = (entity == e.unsqueeze(1)) & (active > 0.5)   # [B,M]
                has_match = match.any(dim=1)
                match_idx = torch.argmax(match.float(), dim=1)
                free = active < 0.5
                has_free = free.any(dim=1)
                free_idx = torch.argmax(free.float(), dim=1)
                evict_idx = torch.argmin(ret + (active < 0.5).float() * 1e9, dim=1)
                alloc_idx = torch.where(has_free, free_idx, evict_idx)
                idx = torch.where(has_match, match_idx, alloc_idx)     # [B]
                # counters
                do = hard
                st.n_super += (do & has_match).float()
                st.n_alloc += (do & ~has_match & has_free).float()
                ev = do & ~has_match & ~has_free
                st.n_evict += ev.float()
                if target_entity is not None:
                    evicted_ent = entity.gather(1, idx.unsqueeze(1)).squeeze(1)
                    st.target_evicted += (ev & (evicted_ent == target_entity)).float()

            # differentiable gated value/retention write into the chosen slot
            onehot = torch.zeros(B, M, device=device, dtype=values.dtype)
            onehot[ar, idx] = 1.0
            m = onehot * (g * hard.float()).unsqueeze(-1)     # write mass [B,M]
            m1 = m.unsqueeze(-1)
            value = value * (1 - m1) + m1 * val.unsqueeze(1)
            ret = ret * (1 - m) + m * rt.unsqueeze(1)

            with torch.no_grad():
                wsel = hard
                if wsel.any():
                    bidx = ar[wsel]; sidx = idx[wsel]
                    entity[bidx, sidx] = e[wsel]
                    active[bidx, sidx] = 1.0

        return OracleSlotState(entity=entity, value=value, retain=ret, active=active,
                               n_alloc=st.n_alloc, n_evict=st.n_evict, n_super=st.n_super,
                               target_evicted=st.target_evicted)

    def read(self, query_entity: Tensor, state: OracleSlotState) -> Tuple[Tensor, Tensor]:
        """Oracle lookup: return (value[B,Dv], found[B]) for the slot holding
        `query_entity`. If absent (evicted/never written) → zeros and found=0."""
        B = query_entity.shape[0]
        device = query_entity.device
        match = (state.entity == query_entity.unsqueeze(1)) & (state.active > 0.5)  # [B,M]
        found = match.any(dim=1)
        idx = torch.argmax(match.float(), dim=1)                                     # [B]
        val = state.value.gather(1, idx.view(B, 1, 1).expand(-1, -1, self.Dv)).squeeze(1)
        val = torch.where(found.unsqueeze(-1), val, torch.zeros_like(val))
        return val, found
