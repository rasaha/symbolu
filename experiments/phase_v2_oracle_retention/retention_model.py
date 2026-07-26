"""
retention_model.py — oracle-addressed bounded memory where ONLY the retention/eviction
priority may use the Phase v2-S focus signal. Identity allocation, query lookup, value
encoding, slot value, and the answer decoder are IDENTICAL across arms (oracle,
unchanged). Frozen Phase v1 is untouched; Phase v2-S is the experimental module.

Retention interface (§7):  r_final = r_local(h) + λ · normalize(r_phase([h; g_v2]))
with λ ∈ [0, λ_max] (init 0). Eviction = argmin(r_final) over active slots (oracle,
discrete at eval). Arms differ ONLY in the retention signal:
    C-oracle    : r_final = r_local
    D-v2        : r_final = r_local + λ·norm(r_phase from Phase v2-S state)
    D-zero      : r_final = r_local + λ·0            (Phase computed, zeroed)
    D-random    : r_final = r_local + λ·randn        (scale-matched)
    D-shuffled  : r_final = r_local + λ·norm(r_phase) shuffled across the batch
    D-v1        : r_final = r_local + λ·norm(r_phase from FROZEN Phase v1)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.lightweight_phase.local_window import LocalWindowAttention
from symbolu.phase_v2_experimental.config import cfg_v2s
from symbolu.phase_v2_experimental.multiscale_phase import PhaseV2Variant, V1Baseline
from experiments.phase_guided_slots_v2.oracle_slots import OracleSlots

ARMS = ("C-oracle", "D-v2", "D-zero", "D-random", "D-shuffled", "D-v1")


@dataclass
class OCfg:
    vocab_size: int
    embed_dim: int = 96
    num_heads: int = 4
    local_window: int = 16   # must cover a full record so the value is in-window; the
                             # distant focus header stays OUTSIDE (records arrive far past it)
    num_slots: int = 8
    lambda_max: float = 0.25
    lambda_fixed: Optional[float] = None   # if None, learn λ (bounded); else fix it
    gate_bias_init: float = 0.0


def _uses_phase(arm):
    return arm in ("D-v2", "D-zero", "D-random", "D-shuffled", "D-v1")


class RetentionModel(nn.Module):
    def __init__(self, cfg: OCfg, arm: str):
        super().__init__()
        self.cfg = cfg
        self.arm = arm
        self.use_phase = _uses_phase(arm)
        D = cfg.embed_dim
        self.token_embed = nn.Embedding(cfg.vocab_size, D)
        self.pos_embed = nn.Embedding(8192, D)
        self.local = LocalWindowAttention(D, cfg.num_heads, cfg.local_window)
        if self.use_phase:
            if arm == "D-v1":
                self.phase = V1Baseline(D, cfg.num_heads)
            else:
                self.phase = PhaseV2Variant(cfg_v2s(D, cfg.num_heads), "V2-S")
        # retention heads
        self.r_local = nn.Linear(D, 1)
        self.r_phase = nn.Linear(2 * D, 1)
        # write gate + value + read + decode (identical across arms)
        self.g_write = nn.Linear(D, 1)
        self.w_val = nn.Linear(D, D, bias=False)
        self.slots = OracleSlots(cfg.num_slots, D)
        self.readout = nn.Sequential(nn.Linear(D + D, 2 * D), nn.GELU(), nn.Linear(2 * D, D))
        self.norm_f = nn.LayerNorm(D)
        self.lm_head = nn.Linear(D, cfg.vocab_size, bias=False)
        # bounded λ (init 0): λ = λ_max·sigmoid(θ), θ0 → σ≈0
        if cfg.lambda_fixed is None:
            self.lambda_theta = nn.Parameter(torch.tensor(-6.0))
        else:
            self.register_parameter("lambda_theta", None)
        for m in (self.r_local, self.r_phase, self.g_write):
            nn.init.normal_(m.weight, std=0.02); nn.init.zeros_(m.bias)
        nn.init.normal_(self.token_embed.weight, std=0.02)
        nn.init.normal_(self.pos_embed.weight, std=0.02)
        nn.init.normal_(self.lm_head.weight, std=0.02)
        with torch.no_grad():
            self.g_write.bias.fill_(cfg.gate_bias_init)

    def lam(self):
        if self.cfg.lambda_fixed is not None:
            return self.cfg.lambda_fixed
        return self.cfg.lambda_max * torch.sigmoid(self.lambda_theta)

    def encode(self, ids, gate_override=None):
        N = ids.shape[1]
        pos = torch.arange(N, device=ids.device).clamp(max=8191)
        x = self.token_embed(ids) + self.pos_embed(pos).unsqueeze(0)
        h = self.local(x, return_residual_add=True)
        if self.use_phase:
            if self.arm == "D-v1":
                g = self.phase.readout(h)
            else:
                g = self.phase.readout(h, gate_override=gate_override)
        else:
            g = torch.zeros_like(h)
        return h, g

    def retention(self, h, g):
        r_local = self.r_local(h).squeeze(-1)                       # [B,N]
        if not self.use_phase:
            return r_local, r_local, torch.zeros_like(r_local)
        rp_raw = self.r_phase(torch.cat([h, g], dim=-1)).squeeze(-1)  # [B,N]
        # normalize the phase score (per example, zero-mean unit-std) — §7
        rp = (rp_raw - rp_raw.mean(dim=1, keepdim=True)) / (rp_raw.std(dim=1, keepdim=True) + 1e-5)
        if self.arm == "D-zero":
            contrib = torch.zeros_like(rp)
        elif self.arm == "D-random":
            contrib = torch.randn_like(rp)
        elif self.arm == "D-shuffled":
            contrib = rp[torch.randperm(rp.shape[0])]
        else:                                                        # D-v2, D-v1
            contrib = rp
        lam = self.lam()
        r_final = r_local + lam * contrib
        return r_final, r_local, rp

    def forward(self, ids, answer_pos, entity_at_pos, query_entity,
                gate_override=None) -> Dict[str, Tensor]:
        B, N = ids.shape
        ar = torch.arange(B, device=ids.device)
        h, g = self.encode(ids, gate_override=gate_override)
        r_final, r_local, r_phase = self.retention(h, g)
        gate = torch.sigmoid(self.g_write(h)).squeeze(-1)           # [B,N]
        value = self.w_val(h)
        state = self.slots.write_stream(entity_at_pos, value, gate, r_final,
                                        target_entity=query_entity)
        val, found = self.slots.read(query_entity, state)
        hA = h[ar, answer_pos]
        feat = self.readout(torch.cat([hA, val], dim=-1))           # NO phase in decode
        logits = self.lm_head(self.norm_f(feat))
        return {"answer_logits": logits, "found": found, "state": state,
                "r_final": r_final, "r_local": r_local, "r_phase": r_phase,
                "gate": gate, "g_phase": g}

    def gate_values(self, ids):
        """Cheap per-token Phase write gate [B,N,H] for supervision (v2 arms)."""
        if not self.use_phase or self.arm == "D-v1":
            return None
        N = ids.shape[1]
        pos = torch.arange(N, device=ids.device).clamp(max=8191)
        x = self.token_embed(ids) + self.pos_embed(pos).unsqueeze(0)
        h = self.local(x, return_residual_add=True)
        return self.phase.gate_values(h)

    def state_bytes(self, B=1):
        sb = self.slots.M * self.cfg.embed_dim * 4 * B      # oracle slot values (float32)
        if self.use_phase and self.arm != "D-v1":
            sb += self.phase.state_bytes(B)
        return sb
