"""
guided_models_v2.py — v2 arms with CLEAN content addressing.

Why a v2 model (the v1 GuidedSlotLM is unchanged and NOT modified): in v1 the write
KEY was `k_local(h) + k_guide`, and the guidance projection's bias grew to dominate,
collapsing every write key to a single direction (cosine → 1.0) so all facts merged
into ~2 slots — the common-mode-swamping pathology the v1 root-cause report
identified. That makes a bounded-memory PRESSURE test impossible.

v2 keeps the content write key PURE (`k_local(h)`) for all arms, so distinct facts
occupy distinct slots and real capacity pressure can form. Phase guidance enters only
through the channels the v1 report recommended — the write GATE, the RETENTION
priority, and a READ bonus — never the content key. Arms:

    A         : local window only (no slots)
    C         : slots; gate/retain/read from local h only (no Phase)
    D         : slots; gate/retain/read also see Phase global state g
    D-no-guid : D architecture, Phase guidance zeroed

Frozen LightweightPhaseAttention, LocalWindowAttention, and GuidedBoundedSlots are
imported unmodified.
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
from experiments.phase_guided_slots.guided_slots import GuidedBoundedSlots

ARMS = ("A", "C", "D", "D-no-guid")


@dataclass
class GCfg2:
    vocab_size: int
    embed_dim: int = 96
    num_heads: int = 4
    local_window: int = 16
    num_slots: int = 8
    slot_key_dim: int = 48
    top_k: int = 2
    max_seq_len: int = 1400
    match_threshold: float = 0.95
    gate_bias_init: float = -3.0
    dropout: float = 0.0


def _arm_flags(arm: str):
    # (use_phase, guide)  — guide gates/retention/read use Phase g when True
    return {
        "A": (False, False),
        "C": (False, True),        # slots with local-only guidance (no phase)
        "D": (True, True),
        "D-no-guid": (True, False),  # phase computed, guidance zeroed
    }[arm]


class GuidedSlotLMv2(nn.Module):
    def __init__(self, cfg: GCfg2, arm: str):
        super().__init__()
        self.cfg = cfg
        self.arm = arm
        self.use_phase, self.guide = _arm_flags(arm)
        self.use_slots = arm != "A"
        D = cfg.embed_dim
        self.token_embed = nn.Embedding(cfg.vocab_size, D)
        self.pos_embed = nn.Embedding(cfg.max_seq_len, D)
        self.local = LocalWindowAttention(D, cfg.num_heads, cfg.local_window, dropout=cfg.dropout)
        if self.use_phase:
            self.phase = LightweightPhaseAttention(PhaseConfig(embed_dim=D, num_heads=cfg.num_heads))
        # guidance MLPs take [h; g] (g zeros when no phase); drive gate / retention / read
        self.g_write = nn.Linear(2 * D, 1)
        self.g_retain = nn.Linear(2 * D, 1)
        self.g_readbonus = nn.Linear(D, cfg.slot_key_dim, bias=False)  # phase read bonus
        # PURE content projections (no guidance added → no key collapse)
        self.k_local = nn.Linear(D, cfg.slot_key_dim, bias=False)
        self.w_val = nn.Linear(D, D, bias=False)
        self.q_read = nn.Linear(D, cfg.slot_key_dim, bias=False)
        if self.use_slots:
            self.slots = GuidedBoundedSlots(cfg.num_slots, cfg.slot_key_dim, D,
                                            match_threshold=cfg.match_threshold)
        self.readout = nn.Sequential(nn.Linear(D + D + D, 2 * D), nn.GELU(), nn.Linear(2 * D, D))
        self.norm_f = nn.LayerNorm(D)
        self.lm_head = nn.Linear(D, cfg.vocab_size, bias=False)
        self.write_head_out = None
        for m in (self.g_write, self.g_retain):
            nn.init.normal_(m.weight, std=0.02); nn.init.zeros_(m.bias)
        nn.init.zeros_(self.g_readbonus.weight)
        nn.init.normal_(self.token_embed.weight, std=0.02)
        nn.init.normal_(self.pos_embed.weight, std=0.02)
        nn.init.normal_(self.lm_head.weight, std=0.02)
        with torch.no_grad():
            self.g_write.bias.fill_(cfg.gate_bias_init)   # start writing rarely

    def num_parameters(self):
        return sum(p.numel() for p in {id(p): p for p in self.parameters()}.values())

    def encode(self, input_ids: Tensor):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).clamp(max=self.cfg.max_seq_len - 1)
        x = self.token_embed(input_ids) + self.pos_embed(pos).unsqueeze(0)
        h = self.local(x, return_residual_add=True)
        g = (self.phase(h) - h) if self.use_phase else torch.zeros_like(h)
        return h, g

    def guidance(self, h: Tensor, g: Tensor):
        hg = torch.cat([h, g], dim=-1)
        r_write = torch.sigmoid(self.g_write(hg)).squeeze(-1)
        p_retain = self.g_retain(hg).squeeze(-1)
        if not self.guide:                       # D-no-guid: neutral gate/retention
            r_write = torch.sigmoid(self.g_write(torch.cat([h, torch.zeros_like(g)], -1))).squeeze(-1)
            p_retain = torch.zeros_like(p_retain)
        return r_write, p_retain

    def forward(self, input_ids: Tensor, answer_pos: Tensor,
                write_labels: Optional[Tensor] = None) -> Dict[str, Tensor]:
        B, N = input_ids.shape
        h, g = self.encode(input_ids)
        ar = torch.arange(B, device=input_ids.device)
        r_write, p_retain = self.guidance(h, g)
        self.write_head_out = r_write

        if not self.use_slots:
            hA = h[ar, answer_pos]; gA = g[ar, answer_pos]
            feat = self.readout(torch.cat([hA, gA, torch.zeros_like(hA)], dim=-1))
            return {"answer_logits": self.lm_head(self.norm_f(feat)), "r_write": r_write}

        write_key = self.k_local(h)              # PURE content key (no guidance bias)
        write_val = self.w_val(h)
        state = self.slots.write_stream(write_key, write_val, r_write, p_retain, input_ids)

        hA = h[ar, answer_pos]; gA = g[ar, answer_pos]
        read_query = self.q_read(hA)
        if self.use_phase and self.guide:
            read_query = read_query + self.g_readbonus(gA)   # phase read bonus (starts at 0)
        vals, idx, attn = self.slots.read_topk(read_query, state, self.cfg.top_k)
        combined = torch.einsum("bk,bkd->bd", attn, vals)
        feat = self.readout(torch.cat([hA, gA, combined], dim=-1))
        return {"answer_logits": self.lm_head(self.norm_f(feat)), "r_write": r_write,
                "write_key": write_key, "slot_idx": idx, "slot_attn": attn, "state": state}


def build_v2(cfg: GCfg2, arm: str, seed: int) -> GuidedSlotLMv2:
    torch.manual_seed(seed)
    return GuidedSlotLMv2(cfg, arm)
