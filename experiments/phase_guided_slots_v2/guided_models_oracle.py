"""
guided_models_oracle.py — arms over the ORACLE-addressed bounded memory.

Addressing/lookup are oracle (structurally correct); LEARNED: value encoding,
retention priority, write gate, and final value decode. Phase enters ONLY as a
retention-priority signal (the one place the redesign permits testing it):

    A         : local window only (no slots)
    C         : oracle slots; retention from local h only
    D         : oracle slots; retention from local h + Phase global state g
    D-no-guid : oracle slots; retention zeroed (Phase computed, not used)

Frozen LightweightPhaseAttention and LocalWindowAttention imported unmodified;
OracleSlots is a new experiment module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.lightweight_phase.config import PhaseConfig
from symbolu.lightweight_phase.phase_core import LightweightPhaseAttention
from symbolu.lightweight_phase.local_window import LocalWindowAttention
from experiments.phase_guided_slots_v2.oracle_slots import OracleSlots

ARMS = ("A", "C", "D", "D-no-guid")


@dataclass
class OCfg:
    vocab_size: int
    embed_dim: int = 96
    num_heads: int = 4
    local_window: int = 16
    num_slots: int = 8
    max_seq_len: int = 1400
    gate_bias_init: float = 0.0
    dropout: float = 0.0


def _flags(arm: str):
    # (use_phase, retain_from_phase)
    return {"A": (False, False), "C": (False, True),
            "D": (True, True), "D-no-guid": (True, False)}[arm]


class OracleSlotLM(nn.Module):
    def __init__(self, cfg: OCfg, arm: str):
        super().__init__()
        self.cfg = cfg
        self.arm = arm
        self.use_phase, self.retain_learned = _flags(arm)
        self.use_slots = arm != "A"
        D = cfg.embed_dim
        self.token_embed = nn.Embedding(cfg.vocab_size, D)
        self.pos_embed = nn.Embedding(cfg.max_seq_len, D)
        self.local = LocalWindowAttention(D, cfg.num_heads, cfg.local_window, dropout=cfg.dropout)
        if self.use_phase:
            self.phase = LightweightPhaseAttention(PhaseConfig(embed_dim=D, num_heads=cfg.num_heads))
        self.g_write = nn.Linear(2 * D, 1)      # write gate (fire at fact anchors)
        self.g_retain = nn.Linear(2 * D, 1)     # retention priority
        self.w_val = nn.Linear(D, D, bias=False)  # LEARNED value encoding
        if self.use_slots:
            self.slots = OracleSlots(cfg.num_slots, D)
        self.readout = nn.Sequential(nn.Linear(D + D + D, 2 * D), nn.GELU(), nn.Linear(2 * D, D))
        self.norm_f = nn.LayerNorm(D)
        self.lm_head = nn.Linear(D, cfg.vocab_size, bias=False)  # LEARNED decode
        self.write_head_out = None
        for m in (self.g_write, self.g_retain):
            nn.init.normal_(m.weight, std=0.02); nn.init.zeros_(m.bias)
        nn.init.normal_(self.token_embed.weight, std=0.02)
        nn.init.normal_(self.pos_embed.weight, std=0.02)
        nn.init.normal_(self.lm_head.weight, std=0.02)
        with torch.no_grad():
            self.g_write.bias.fill_(cfg.gate_bias_init)

    def num_parameters(self):
        return sum(p.numel() for p in {id(p): p for p in self.parameters()}.values())

    def encode(self, input_ids: Tensor):
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).clamp(max=self.cfg.max_seq_len - 1)
        x = self.token_embed(input_ids) + self.pos_embed(pos).unsqueeze(0)
        h = self.local(x, return_residual_add=True)
        g = (self.phase(h) - h) if self.use_phase else torch.zeros_like(h)
        return h, g

    def guidance(self, h, g):
        hg = torch.cat([h, g], dim=-1)
        r_write = torch.sigmoid(self.g_write(hg)).squeeze(-1)
        p_retain = self.g_retain(hg).squeeze(-1)
        if not self.retain_learned:               # D-no-guid: neutral retention
            p_retain = torch.zeros_like(p_retain)
        return r_write, p_retain

    def forward(self, input_ids: Tensor, answer_pos: Tensor,
                entity_at_pos: Optional[Tensor] = None, query_entity: Optional[Tensor] = None,
                write_labels: Optional[Tensor] = None) -> Dict[str, Tensor]:
        B, N = input_ids.shape
        ar = torch.arange(B, device=input_ids.device)
        h, g = self.encode(input_ids)
        r_write, p_retain = self.guidance(h, g)
        self.write_head_out = r_write
        hA = h[ar, answer_pos]; gA = g[ar, answer_pos]

        if not self.use_slots:
            feat = self.readout(torch.cat([hA, gA, torch.zeros_like(hA)], dim=-1))
            return {"answer_logits": self.lm_head(self.norm_f(feat)), "r_write": r_write}

        # Writes only ever happen at fact anchors (entity_at_pos >= 0); compress the
        # sequence to those positions so the streaming write loop runs O(#facts) instead
        # of O(N). Identical result: non-anchor tokens never write (entity < 0).
        values = self.w_val(h)
        e_c, v_c, g_c, r_c = _compress_to_anchors(entity_at_pos, values, r_write, p_retain)
        state = self.slots.write_stream(e_c, v_c, g_c, r_c, target_entity=query_entity)
        val, found = self.slots.read(query_entity, state)
        feat = self.readout(torch.cat([hA, gA, val], dim=-1))
        return {"answer_logits": self.lm_head(self.norm_f(feat)), "r_write": r_write,
                "found": found, "state": state}


def _compress_to_anchors(entity_at_pos, values, gate, retain):
    """Keep only fact-anchor positions (entity_at_pos >= 0), preserving order, padded
    with entity=-1 (a no-write). Compresses the write stream from N to #facts."""
    B, N = entity_at_pos.shape
    mask = entity_at_pos >= 0                         # [B,N]
    counts = mask.sum(dim=1)                          # [B]
    Amax = int(counts.max().item()) if counts.numel() else 0
    if Amax == 0:
        Amax = 1
    # anchors first (stable), then non-anchors as padding
    order = torch.argsort(mask.to(torch.int64), dim=1, descending=True, stable=True)
    sel = order[:, :Amax]                             # [B,Amax] source positions
    ar = torch.arange(B, device=entity_at_pos.device).unsqueeze(1)
    e_c = entity_at_pos[ar, sel]
    v_c = values[ar, sel]
    g_c = gate[ar, sel]
    r_c = retain[ar, sel]
    # positions beyond each row's anchor count are padding → mark as no-write
    col = torch.arange(Amax, device=entity_at_pos.device).unsqueeze(0)
    pad = col >= counts.unsqueeze(1)
    e_c = e_c.masked_fill(pad, -1)
    return e_c, v_c, g_c, r_c


def build_oracle(cfg: OCfg, arm: str, seed: int) -> OracleSlotLM:
    torch.manual_seed(seed)
    return OracleSlotLM(cfg, arm)
