"""
multiscale_phase.py — variant builders for the Phase v2 study.

Variants (each streaming, causal, bounded-state, O(N), no N×N):
    V1     : frozen Phase v1 baseline (dense, no decay, no gate) — wraps the frozen
             symbolu.lightweight_phase.LightweightPhaseAttention UNMODIFIED.
    V2-S   : selective-write, single persistent bank (γ=1), learned gate.
    V2-SD  : selective-write + learned bounded decay (single bank).
    V2-M   : selective-write, multi-timescale banks (γ = 0.5/0.9/0.99/1.0).

V1 is preserved as the canonical negative baseline and is never modified here.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor

from .config import PhaseV2Config, cfg_v2s, cfg_v2sd, cfg_v2m
from .selective_phase import SelectivePhaseV2, PhaseV2State


class V1Baseline(nn.Module):
    """Adapter around the FROZEN v1 Phase so the study can call all variants uniformly.
    Imports and uses symbolu.lightweight_phase unmodified."""

    def __init__(self, embed_dim=96, num_heads=4):
        super().__init__()
        from symbolu.lightweight_phase.config import PhaseConfig
        from symbolu.lightweight_phase.phase_core import LightweightPhaseAttention
        self.core = LightweightPhaseAttention(PhaseConfig(embed_dim=embed_dim, num_heads=num_heads))
        self.embed_dim, self.num_heads = embed_dim, num_heads
        self.head_dim = embed_dim // num_heads
        self.num_banks = 1
        self.variant = "V1"

    def forward(self, x, *, return_state=False, return_diagnostics=False, **kw):
        return self.core(x, return_state=return_state, return_diagnostics=return_diagnostics)

    def readout(self, x):
        """g = phase(x) - x  (the v1 global-state readout used in the diagnostics)."""
        return self.core(x) - x

    def state_bytes(self, B=1):
        return B * self.num_heads * self.head_dim * (8 + 4)


class PhaseV2Variant(nn.Module):
    """Wraps SelectivePhaseV2 and exposes .readout(x) = phasev2(x) - x for the probe."""

    def __init__(self, cfg: PhaseV2Config, variant: str):
        super().__init__()
        self.core = SelectivePhaseV2(cfg)
        self.cfg = cfg
        self.variant = variant
        self.embed_dim, self.num_heads = cfg.embed_dim, cfg.num_heads
        self.head_dim, self.num_banks = cfg.head_dim, cfg.num_banks

    def forward(self, x, *, return_state=False, return_diagnostics=False, gate_override=None):
        return self.core(x, return_state=return_state, return_diagnostics=return_diagnostics,
                         gate_override=gate_override)

    def readout(self, x, gate_override=None):
        out = self.core(x, gate_override=gate_override)
        return out - x

    def write_rate(self, x):
        d = self.core(x, return_diagnostics=True).diagnostics
        return d["write_rate_mean"].item(), d["write_rate_per_pos"]

    def state_bytes(self, B=1):
        return self.core.state_bytes(B)


def build_variant(name: str, embed_dim=96, num_heads=4, **kw) -> nn.Module:
    if name == "V1":
        return V1Baseline(embed_dim, num_heads)
    if name == "V2-S":
        return PhaseV2Variant(cfg_v2s(embed_dim, num_heads, **kw), "V2-S")
    if name == "V2-SD":
        return PhaseV2Variant(cfg_v2sd(embed_dim, num_heads, **kw), "V2-SD")
    if name == "V2-M":
        return PhaseV2Variant(cfg_v2m(embed_dim, num_heads, **kw), "V2-M")
    raise ValueError(f"unknown variant {name}")


VARIANTS = ("V1", "V2-S", "V2-SD", "V2-M")
