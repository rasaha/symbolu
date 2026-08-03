# Incubated from: symbolu/lightweight_phase/binding_slots.py
# Source commit: 8b4ec6e71666282384a4e23f78c724f8df4ba767
# Source blob: 6ee03c133b61bca2b089e787f06c00a99d007bc1
# Extraction status: SEMANTIC_EXTRACTION
#   - The class/dataclass bodies below are BYTE-IDENTICAL to the source.
#   - The ONLY delta is the import path on the `register_shape` line:
#       source:  from .invariants import register_shape
#       here:    from ..instrumentation.invariants import register_shape
#     (the vendored invariants.py is byte-identical to the source).
#   This is the clean lightweight implementation with source/version/supersession/eviction —
#   the metadata-extended variant targeted for the NOT-YET-DEMONSTRATED relational capabilities.
# Packaging status: NOT_PACKAGED
# Runtime status: RESOURCE_BLOCKED in this environment (PyTorch not installed). Its discrete
#   metadata semantics (supersession, source, eviction) are reproduced and tested by
#   ../binding_slots/slot_reference.py (stdlib); the torch module is the parity target.
"""
binding_slots.py — Stage 8 bounded binding slots (streaming, memory-efficient).

Design goals (frozen structure + complexity; the training validation ladder is
a separate, deferred stage):

  * Bounded slot count M. Persistent state is O(M·D), independent of N.
  * Per-token compute O(M·D); total O(N·M·D). NEVER materializes [B, N, N],
    [B, H, N, N], or the full-sequence [B, N, M, D].
  * Streaming read-then-write per token so causal reads never require storing a
    per-position slot snapshot.

Slot fields (minimal first implementation — entity↔value and entity↔source):
    slot_keys     [B, M, Ds]   content-addressable entity key
    slot_values   [B, M, Dv]   bound value
    slot_source   [B, M]        source identifier (int)
    slot_version  [B, M]        version counter (int)
    slot_usage    [B, M]        recency/usage score for eviction
    slot_active   [B, M]        1 = active, 0 = free/superseded

Operations: content-based matching, bounded Top-K read, collision handling
(match → in-place supersede + version bump), eviction (LRU by usage) on
allocation, source attribution. Reads are differentiable (soft attention over
slots); discrete metadata (version/usage/source/active) is maintained under
no_grad for auditability and the semantic tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from ..instrumentation.invariants import register_shape


@dataclass
class BindingSlotState:
    keys: Tensor      # [B, M, Ds]  (differentiable content)
    values: Tensor    # [B, M, Dv]
    source: Tensor    # [B, M]  long
    version: Tensor   # [B, M]  long
    usage: Tensor     # [B, M]  float
    active: Tensor    # [B, M]  float (0/1)
    position: int = 0

    def numel(self) -> int:
        return sum(t.numel() for t in (self.keys, self.values, self.source,
                                       self.version, self.usage, self.active))

    def detach(self) -> "BindingSlotState":
        return BindingSlotState(
            keys=self.keys.detach(), values=self.values.detach(),
            source=self.source, version=self.version, usage=self.usage,
            active=self.active, position=self.position,
        )


class BoundedBindingSlots(nn.Module):
    """A bounded, content-addressable slot memory integrated as an additive path."""

    def __init__(self, embed_dim: int, num_slots: int, slot_key_dim: Optional[int] = None,
                 top_k: int = 4, match_threshold: float = 0.5,
                 write_decay: float = 0.9, layernorm_eps: float = 1e-5):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_slots = num_slots
        self.Ds = slot_key_dim or embed_dim
        self.Dv = embed_dim
        self.top_k = min(top_k, num_slots)
        self.match_threshold = match_threshold
        self.write_decay = write_decay

        self.norm = nn.LayerNorm(embed_dim, eps=layernorm_eps)
        self.to_query = nn.Linear(embed_dim, self.Ds, bias=False)   # read address
        self.to_wkey = nn.Linear(embed_dim, self.Ds, bias=False)    # write key
        self.to_wval = nn.Linear(embed_dim, self.Dv, bias=False)    # write value
        self.to_gate = nn.Linear(embed_dim, 1)                      # write strength
        self.read_out = nn.Linear(self.Dv, embed_dim, bias=False)
        for lin in (self.to_query, self.to_wkey, self.to_wval, self.read_out):
            nn.init.normal_(lin.weight, std=0.02)
        nn.init.normal_(self.to_gate.weight, std=0.02)
        nn.init.constant_(self.to_gate.bias, -1.0)  # start with gentle writes

    def init_state(self, B: int, device, dtype=torch.float32) -> BindingSlotState:
        M = self.num_slots
        return BindingSlotState(
            keys=torch.zeros(B, M, self.Ds, device=device, dtype=dtype),
            values=torch.zeros(B, M, self.Dv, device=device, dtype=dtype),
            source=torch.full((B, M), -1, device=device, dtype=torch.long),
            version=torch.zeros(B, M, device=device, dtype=torch.long),
            usage=torch.zeros(B, M, device=device, dtype=dtype),
            active=torch.zeros(B, M, device=device, dtype=dtype),
            position=0,
        )

    # ------------------------------------------------------------------
    def _read(self, q: Tensor, state: BindingSlotState) -> Tensor:
        """Top-K soft read from current slots. q:[B,Ds] → readout:[B,D]. O(M·D)."""
        B, M = state.active.shape
        register_shape("slot_scores", (B, M), n_seq_axes=0)  # M is fixed, not N
        # cosine-ish score, masked by active
        scores = torch.einsum("bd,bmd->bm", q, state.keys) / (self.Ds ** 0.5)
        scores = scores.masked_fill(state.active < 0.5, float("-inf"))
        k = min(self.top_k, M)
        topv, topi = scores.topk(k, dim=-1)                      # [B,k]
        # handle all-inactive rows (‑inf) → zero readout
        finite = torch.isfinite(topv)
        attn = torch.softmax(topv.masked_fill(~finite, float("-inf")), dim=-1)
        attn = torch.where(finite.any(dim=-1, keepdim=True), attn, torch.zeros_like(attn))
        vals = torch.gather(state.values, 1, topi.unsqueeze(-1).expand(-1, -1, self.Dv))
        readout = torch.einsum("bk,bkd->bd", attn, vals)         # [B,Dv]
        return self.read_out(readout)

    # ------------------------------------------------------------------
    @torch.no_grad()
    def _address_write(self, wkey: Tensor, state: BindingSlotState) -> Tensor:
        """Choose a slot per batch element: matched slot (collision) or evicted LRU.

        Returns integer slot index [B]. Metadata-only (no grad).
        """
        B, M = state.active.shape
        sim = F.cosine_similarity(wkey.unsqueeze(1), state.keys, dim=-1)  # [B,M]
        sim = sim.masked_fill(state.active < 0.5, -2.0)
        best_sim, best_idx = sim.max(dim=-1)                              # [B]
        matched = best_sim >= self.match_threshold

        # allocation target: a free slot if any, else LRU (min usage) active slot
        free = state.active < 0.5
        has_free = free.any(dim=-1)
        free_idx = torch.argmax(free.float(), dim=-1)                    # first free
        lru_idx = torch.argmin(state.usage + (state.active < 0.5).float() * 1e9, dim=-1)
        alloc_idx = torch.where(has_free, free_idx, lru_idx)

        return torch.where(matched, best_idx, alloc_idx)

    # ------------------------------------------------------------------
    def _write(self, wkey: Tensor, wval: Tensor, gate: Tensor, source_id: Tensor,
               state: BindingSlotState) -> BindingSlotState:
        """Write into the addressed slot. Differentiable in keys/values via gate.

        wkey:[B,Ds] wval:[B,Dv] gate:[B,1] source_id:[B]. O(M·D).
        """
        B, M = state.active.shape
        idx = self._address_write(wkey, state)                           # [B]
        onehot = F.one_hot(idx, M).to(wkey.dtype)                        # [B,M]
        g = gate.unsqueeze(-1) * onehot.unsqueeze(-1)                    # [B,M,1] write mask

        # matched vs fresh (for version/supersession bookkeeping)
        with torch.no_grad():
            prev_active = state.active.gather(1, idx.unsqueeze(1)).squeeze(1)  # [B]

        new_keys = state.keys * (1 - g) + g * wkey.unsqueeze(1)
        new_values = state.values * (1 - g) + g * wval.unsqueeze(1)

        with torch.no_grad():
            m = onehot > 0.5
            new_active = state.active.clone(); new_active[m] = 1.0
            new_version = state.version.clone()
            new_version[m] = new_version[m] + 1          # version bump / supersession
            new_source = state.source.clone()
            new_source[m] = source_id.to(new_source.dtype)
            new_usage = state.usage * 0.999
            new_usage[m] = new_usage[m] + 1.0            # recency bump

        return BindingSlotState(
            keys=new_keys, values=new_values, source=new_source,
            version=new_version, usage=new_usage, active=new_active,
            position=state.position + 1,
        )

    # ------------------------------------------------------------------
    def forward(self, x: Tensor, *, state: Optional[BindingSlotState] = None,
                source_ids: Optional[Tensor] = None, return_state: bool = False):
        """Streaming read-then-write over the sequence. Returns readouts [B,N,D].

        Peak extra memory is O(M·D) for the carried state plus O(N·D) for the
        stacked outputs — never O(N·M·D).
        """
        B, N, D = x.shape
        if state is None:
            state = self.init_state(B, x.device, x.dtype)
        xn = self.norm(x)
        q_all = self.to_query(xn)      # [B,N,Ds] — projections are position-wise, cheap
        wk_all = self.to_wkey(xn)
        wv_all = self.to_wval(xn)
        gate_all = torch.sigmoid(self.to_gate(xn)) * self.write_decay  # [B,N,1]

        outs: List[Tensor] = []
        for t in range(N):
            readout = self._read(q_all[:, t], state)                  # read current slots
            outs.append(readout)
            src = (source_ids[:, t] if source_ids is not None
                   else torch.full((B,), state.position, device=x.device, dtype=torch.long))
            state = self._write(wk_all[:, t], wv_all[:, t], gate_all[:, t], src, state)

        readouts = torch.stack(outs, dim=1)                           # [B,N,D]
        if return_state:
            return readouts, state
        return readouts
