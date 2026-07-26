"""
guided_models.py — two-stage Phase-guided-slot LM (arms A/C/D + ablations).

Stage 1 (Phase relevance pass): frozen Phase produces a global state g_t; a
guidance head maps [h_t; g_t] → (r_write, k_guide, p_retain).
Stage 2 (bounded relational memory): a guided slot memory writes selected evidence
(gate r_write, key = local ⊕ k_guide, retention p_retain, capacity-pressured
eviction keeps high-retention slots), then a bounded Top-K read + relational
readout answers the query.

Arms differ ONLY in whether the guidance head / read query see Phase's g_t:
    A            : local only (no slots)                     — baseline
    C            : local + slots, guidance from h only (g=0) — unguided slots
    D            : local + slots, guidance from [h; g]       — Phase-guided
    D-no-guid    : Phase computed but guidance zeroed        — isolates the signal
    D-random     : guidance replaced by random of same scale — control
    D-write-only : Phase guidance on writes only
    D-query-only : Phase guidance on reads only

Frozen LightweightPhaseAttention / LocalWindowAttention used unmodified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from symbolu.lightweight_phase.config import PhaseConfig
from symbolu.lightweight_phase.phase_core import LightweightPhaseAttention
from symbolu.lightweight_phase.local_window import LocalWindowAttention
from .guided_slots import GuidedBoundedSlots

ARMS = ("A", "C", "D", "D-no-guid", "D-random", "D-write-only", "D-query-only")


@dataclass
class GCfg:
    vocab_size: int
    embed_dim: int = 96
    num_heads: int = 4
    local_window: int = 16
    num_slots: int = 8
    slot_key_dim: int = 48
    top_k: int = 4
    max_seq_len: int = 512
    dropout: float = 0.0


def _arm_flags(arm: str):
    # (use_phase, guide_write, guide_read, guide_mode)
    return {
        "A": (False, False, False, "none"),
        "C": (False, True, True, "learned"),   # slots with local-only guidance
        "D": (True, True, True, "learned"),
        "D-no-guid": (True, False, False, "none"),
        "D-random": (True, True, True, "random"),
        "D-write-only": (True, True, False, "learned"),
        "D-query-only": (True, False, True, "learned"),
    }[arm]


class GuidedSlotLM(nn.Module):
    def __init__(self, cfg: GCfg, arm: str):
        super().__init__()
        self.cfg = cfg
        self.arm = arm
        self.use_phase, self.guide_write, self.guide_read, self.guide_mode = _arm_flags(arm)
        self.use_slots = arm != "A"
        D = cfg.embed_dim
        self.token_embed = nn.Embedding(cfg.vocab_size, D)
        self.pos_embed = nn.Embedding(cfg.max_seq_len, D)
        self.local = LocalWindowAttention(D, cfg.num_heads, cfg.local_window, dropout=cfg.dropout)
        if self.use_phase:
            self.phase = LightweightPhaseAttention(PhaseConfig(embed_dim=D, num_heads=cfg.num_heads))
        # guidance head input dim: [h; g] (g zeros when no phase)
        self.g_write = nn.Linear(2 * D, 1)
        self.g_kguide = nn.Linear(2 * D, cfg.slot_key_dim)
        self.g_retain = nn.Linear(2 * D, 1)
        # slot projections
        self.k_local = nn.Linear(D, cfg.slot_key_dim, bias=False)
        self.w_val = nn.Linear(D, D, bias=False)
        self.q_read = nn.Linear(D, cfg.slot_key_dim, bias=False)
        self.q_read_g = nn.Linear(D, cfg.slot_key_dim, bias=False)
        if self.use_slots:
            self.slots = GuidedBoundedSlots(cfg.num_slots, cfg.slot_key_dim, D)
        # relational readout
        self.readout = nn.Sequential(
            nn.Linear(D + D + D, 2 * D), nn.GELU(), nn.Linear(2 * D, D))
        self.norm_f = nn.LayerNorm(D)
        self.lm_head = nn.Linear(D, cfg.vocab_size, bias=False)
        self.write_head_out = None
        for m in (self.g_write, self.g_kguide, self.g_retain):
            nn.init.normal_(m.weight, std=0.02); nn.init.zeros_(m.bias)
        nn.init.normal_(self.token_embed.weight, std=0.02)
        nn.init.normal_(self.pos_embed.weight, std=0.02)
        nn.init.normal_(self.lm_head.weight, std=0.02)

    def num_parameters(self):
        return sum(p.numel() for p in {id(p): p for p in self.parameters()}.values())

    def encode(self, input_ids: Tensor):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).clamp(max=self.cfg.max_seq_len - 1)
        x = self.token_embed(input_ids) + self.pos_embed(pos).unsqueeze(0)
        h = self.local(x, return_residual_add=True)     # local representation
        if self.use_phase:
            g = self.phase(h) - h                        # Phase global-state readout
        else:
            g = torch.zeros_like(h)
        return h, g

    def guidance(self, h: Tensor, g: Tensor):
        hg = torch.cat([h, g], dim=-1)
        r_write = torch.sigmoid(self.g_write(hg)).squeeze(-1)    # [B,N]
        k_guide = self.g_kguide(hg)                               # [B,N,Ds]
        p_retain = self.g_retain(hg).squeeze(-1)                  # [B,N]
        if self.guide_mode == "none":
            r_write = torch.full_like(r_write, 0.5)
            k_guide = torch.zeros_like(k_guide)
            p_retain = torch.zeros_like(p_retain)
        elif self.guide_mode == "random":
            r_write = torch.rand_like(r_write)
            k_guide = torch.randn_like(k_guide) * 0.1
            p_retain = torch.randn_like(p_retain)
        return r_write, k_guide, p_retain

    def forward(self, input_ids: Tensor, answer_pos: Tensor,
                write_labels: Optional[Tensor] = None) -> Dict[str, Tensor]:
        B, N = input_ids.shape
        h, g = self.encode(input_ids)
        ar = torch.arange(B, device=input_ids.device)
        r_write, k_guide, p_retain = self.guidance(h, g)
        self.write_head_out = r_write  # for write-F1 metric

        if not self.use_slots:
            # A: answer from local rep at <A> only (no memory)
            hA = h[ar, answer_pos]
            gA = g[ar, answer_pos]
            comb = torch.zeros_like(hA)
            feat = self.readout(torch.cat([hA, gA, comb], dim=-1))
            logits = self.lm_head(self.norm_f(feat))
            return {"answer_logits": logits, "r_write": r_write}

        # Stage 2 writes (streaming)
        write_key = self.k_local(h)
        if self.guide_write:
            write_key = write_key + k_guide
        write_val = self.w_val(h)
        write_gate = r_write
        retain = p_retain if self.guide_write else torch.zeros_like(p_retain)
        state = self.slots.write_stream(write_key, write_val, write_gate, retain, input_ids)

        # Read at answer position
        hA = h[ar, answer_pos]; gA = g[ar, answer_pos]
        read_query = self.q_read(hA)
        if self.guide_read:
            read_query = read_query + self.q_read_g(gA)
        vals, idx, attn = self.slots.read_topk(read_query, state, self.cfg.top_k)
        combined = torch.einsum("bk,bkd->bd", attn, vals)         # bounded relational combine
        feat = self.readout(torch.cat([hA, gA, combined], dim=-1))
        logits = self.lm_head(self.norm_f(feat))
        return {"answer_logits": logits, "r_write": r_write,
                "slot_idx": idx, "slot_attn": attn, "state": state}


def build(cfg: GCfg, arm: str, seed: int) -> GuidedSlotLM:
    torch.manual_seed(seed)
    return GuidedSlotLM(cfg, arm)
