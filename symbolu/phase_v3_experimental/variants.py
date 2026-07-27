"""
variants.py — uniform variant builders for the Phase v3 study (§7).

    V1      : frozen Phase v1 (dense, no decay, no gate) — wraps symbolu.lightweight_phase
              UNMODIFIED via the v2 adapter (which itself never modifies v1).
    V2-S    : completed selective-write persistent baseline — wraps the UNMODIFIED
              symbolu.phase_v2_experimental.SelectivePhaseV2 (γ=1, learned scalar gate).
    V3-B    : Phase v3, input-dependent write only.
    V3-AB   : Phase v3, input-dependent retention + write.
    V3-ABC  : Phase v3, input-dependent retention + write + read (primary variant).

All variants expose the same probe surface via `.features(x)` returning
{state, raw_readout, selective_readout, fused}. V1 and V2-S are never modified here;
any v3 failure leaves them byte-identical.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor

from .config import (cfg_v3b, cfg_v3ab, cfg_v3abc,
                     cfg_cell_B, cfg_cell_Bgamma, cfg_cell_Bomega, cfg_cell_AB)
from .selective_complex_phase import SelectiveComplexPhaseV3

VARIANTS = ("V1", "V2-S", "V3-B", "V3-AB", "V3-ABC")
V3_VARIANTS = ("V3-B", "V3-AB", "V3-ABC")
# 2×2 transition-ablation cells (selective write held ON; isolate γ_t vs ω_t)
CELLS = ("T-B", "T-Bgamma", "T-Bomega", "T-AB")
_CELL_CFG = {"T-B": cfg_cell_B, "T-Bgamma": cfg_cell_Bgamma,
             "T-Bomega": cfg_cell_Bomega, "T-AB": cfg_cell_AB}


class V3Variant(nn.Module):
    def __init__(self, cfg, name: str):
        super().__init__()
        self.core = SelectiveComplexPhaseV3(cfg)
        self.cfg = cfg
        self.variant = name
        self.embed_dim, self.num_heads = cfg.embed_dim, cfg.num_heads
        self.head_dim = cfg.head_dim

    def forward(self, x, **kw):
        return self.core(x, **kw)

    def features(self, x, overrides=None):
        return self.core(x, return_features=True, overrides=overrides).features

    def diagnostics(self, x, overrides=None):
        return self.core(x, return_diagnostics=True, overrides=overrides).diagnostics

    def readout(self, x):
        return self.core(x) - x

    def state_bytes(self, B=1):
        return self.core.state_bytes(B)


class V1Adapter(nn.Module):
    """Frozen Phase v1, exposed with the v3 probe surface. Uses the v2 V1Baseline
    adapter, which wraps symbolu.lightweight_phase unmodified."""

    def __init__(self, embed_dim=96, num_heads=4):
        super().__init__()
        from symbolu.phase_v2_experimental.multiscale_phase import V1Baseline
        self.core = V1Baseline(embed_dim, num_heads)
        self.variant = "V1"
        self.embed_dim, self.num_heads = embed_dim, num_heads
        self.head_dim = embed_dim // num_heads

    def forward(self, x, **kw):
        return self.core(x)

    def features(self, x, overrides=None):
        g = self.core.readout(x)                       # v1 global readout g = phase(x) - x
        return {"state": g, "raw_readout": g, "selective_readout": g, "fused": x + g}

    def state_bytes(self, B=1):
        return self.core.state_bytes(B)


class V2SAdapter(nn.Module):
    """Completed Phase v2-S, exposed with the v3 probe surface. Wraps the UNMODIFIED
    symbolu.phase_v2_experimental selective-write core (γ=1, learned scalar gate)."""

    def __init__(self, embed_dim=96, num_heads=4):
        super().__init__()
        from symbolu.phase_v2_experimental.config import cfg_v2s
        from symbolu.phase_v2_experimental.selective_phase import SelectivePhaseV2
        self.core = SelectivePhaseV2(cfg_v2s(embed_dim, num_heads))
        self.variant = "V2-S"
        self.embed_dim, self.num_heads = embed_dim, num_heads
        self.head_dim = embed_dim // num_heads

    def forward(self, x, **kw):
        return self.core(x)

    def features(self, x, overrides=None):
        # replicate the v2 readout path to expose comparable probe features
        core = self.core
        xn = core.norm(x)
        phi_q, a_q, phi_k, a_k, v = core._project(xn)
        w = core._gate(xn).unsqueeze(-1)
        from symbolu.phase_v2_experimental.selective_phase import _scan
        k_phasor = torch.polar(a_k, -phi_k)
        v_complex = torch.complex(v, torch.zeros_like(v))
        gated_kv = k_phasor * v_complex * w
        gamma = core.bank_gamma(0, x.device)
        S = _scan(gated_kv, gamma, None)
        gated_ak = torch.complex(a_k, torch.zeros_like(a_k)) * w
        A = _scan(gated_ak, gamma, None).real
        q_phasor = torch.polar(a_q, phi_q)
        raw = (q_phasor * S).real / (a_q * A).clamp(min=core.config.denom_eps).detach()
        B, N, _ = x.shape
        D = self.embed_dim
        return {"state": torch.cat([S.real, S.imag], -1).reshape(B, N, 2 * D),
                "raw_readout": raw.reshape(B, N, D),
                "selective_readout": raw.reshape(B, N, D),   # v2-S has no separate read gate
                "fused": self.core(x)}

    def state_bytes(self, B=1):
        return self.core.state_bytes(B)


def build_variant(name: str, embed_dim=96, num_heads=4, **kw) -> nn.Module:
    if name == "V1":
        return V1Adapter(embed_dim, num_heads)
    if name == "V2-S":
        return V2SAdapter(embed_dim, num_heads)
    if name == "V3-B":
        return V3Variant(cfg_v3b(embed_dim, num_heads, **kw), "V3-B")
    if name == "V3-AB":
        return V3Variant(cfg_v3ab(embed_dim, num_heads, **kw), "V3-AB")
    if name == "V3-ABC":
        return V3Variant(cfg_v3abc(embed_dim, num_heads, **kw), "V3-ABC")
    if name in _CELL_CFG:
        return V3Variant(_CELL_CFG[name](embed_dim, num_heads, **kw), name)
    raise ValueError(f"unknown variant {name}")
