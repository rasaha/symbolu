"""
equivalence.py — Stage 4 narrow adapter: Lightweight ↔ production PhaseAttentionLayer.

This maps weights and configuration between the canonical
:class:`LightweightPhaseAttention` and the production
``symbolu.phase_transformer.PhaseAttentionLayer`` so their forward outputs,
gradients, and state can be compared under equivalent settings.

Supported-equivalence configuration (FROZEN, see PHASE_EQUIVALENCE_REPORT.md):
    cosine_mode      = "standard"
    bounded_phase    = True
    zero_mean_cosine = False
    dual_channel     = False
    dropout          = 0.0
    aux_scale        = matched (default 1.0)
    amp parameterization: production a = 0.05 + 0.95·σ(·)  ⇒  lightweight
        amp_floor=0.05, amp_scale=0.95  (set explicitly by matched_phase_config)

Non-equivalent production features are enumerated in the report and are NOT
silently mapped away: shifted/complex cosine modes, zero_mean_cosine,
dual-channel intent, multi-channel phase, write gates, warm-start, and the
learned-decay *initialization schedule* (0.97 + 0.0295·σ(logit), a different
γ range than the lightweight γ_min/γ_max parameterization).
"""

from __future__ import annotations

from dataclasses import replace

import torch

from .config import PhaseConfig
from .phase_core import LightweightPhaseAttention

# Production amplitude parameterization: a = AMP_FLOOR + AMP_SCALE·sigmoid(.)
PROD_AMP_FLOOR = 0.05
PROD_AMP_SCALE = 0.95


def matched_phase_config(embed_dim: int, num_heads: int,
                         decay_mode: str = "none",
                         aux_scale: float = 1.0,
                         **overrides) -> PhaseConfig:
    """A PhaseConfig whose math matches production standard-mode Phase."""
    cfg = PhaseConfig(
        embed_dim=embed_dim,
        num_heads=num_heads,
        bounded_phase=True,
        amp_floor=PROD_AMP_FLOOR,
        amp_scale=PROD_AMP_SCALE,
        denom_eps=0.1,
        detach_denominator=True,
        aux_scale=aux_scale,
        dropout=0.0,
        decay_mode=decay_mode,
    )
    if overrides:
        cfg = replace(cfg, **overrides)
    return cfg


def build_production_layer(embed_dim: int, num_heads: int,
                           decay_gamma: float = 1.0,
                           learned_decay: bool = False,
                           aux_scale: float = 1.0):
    """Construct a production PhaseAttentionLayer in the supported-equivalence config."""
    from symbolu.phase_transformer import PhaseAttentionLayer

    return PhaseAttentionLayer(
        embed_dim=embed_dim,
        num_heads=num_heads,
        dropout=0.0,
        aux_scale=aux_scale,
        cosine_mode="standard",
        decay_gamma=decay_gamma,
        learned_decay=learned_decay,
        bounded_phase=True,
        zero_mean_cosine=False,
        dual_channel_mode=False,
        phase_channels=1,
        phase_write_gate=False,
    )


@torch.no_grad()
def copy_production_into_lightweight(prod, light: LightweightPhaseAttention) -> None:
    """Copy production weights into a matched lightweight layer.

    Weight map (see reference_equations.md §7 for why offsets are irrelevant):
        norm            → norm
        W_q_fused[:D]   → W_phi_q       W_q_fused[D:2D] → W_a_q
        W_k_fused[:D]   → W_phi_k       W_k_fused[D:2D] → W_a_k
        v_proj          → W_v           out_proj        → W_out
    Production's fixed per-head phase offsets are added to both φ_q and φ_k and
    therefore cancel in the real readout — they are intentionally not mapped.
    """
    D = light.embed_dim
    light.norm.weight.copy_(prod.norm.weight)
    light.norm.bias.copy_(prod.norm.bias)

    light.W_phi_q.weight.copy_(prod.W_q_fused.weight[:D])
    light.W_a_q.weight.copy_(prod.W_q_fused.weight[D:2 * D])
    light.W_phi_k.weight.copy_(prod.W_k_fused.weight[:D])
    light.W_a_k.weight.copy_(prod.W_k_fused.weight[D:2 * D])
    light.W_v.weight.copy_(prod.v_proj.weight)
    light.W_out.weight.copy_(prod.out_proj.weight)


def make_matched_pair(embed_dim: int, num_heads: int,
                      decay_gamma: float = 1.0,
                      learned_decay: bool = False,
                      aux_scale: float = 1.0):
    """Return (production_layer, lightweight_layer) with identical weights.

    For learned_decay=True the γ *values* are matched by reading the production
    per-head γ and installing them as a lightweight fixed_per_head config, since
    the two use different logit parameterizations (documented divergence).
    """
    prod = build_production_layer(embed_dim, num_heads, decay_gamma=decay_gamma,
                                  learned_decay=learned_decay, aux_scale=aux_scale).eval()

    if learned_decay:
        # Read production's effective per-head gamma and pin the lightweight to it.
        with torch.no_grad():
            gamma = (0.97 + 0.0295 * torch.sigmoid(prod.decay_logit)).tolist()
        # Represent as explicit fixed_per_head by monkeypatching gamma_per_head.
        cfg = matched_phase_config(embed_dim, num_heads, decay_mode="fixed_per_head",
                                   aux_scale=aux_scale, gamma_min=min(gamma), gamma_max=max(gamma))
        light = LightweightPhaseAttention(cfg).eval()
        g_tensor = torch.tensor(gamma, dtype=torch.float32)
        light.gamma_per_head = lambda device, dtype=torch.float32, _g=g_tensor: _g.to(device=device, dtype=dtype)
    else:
        decay_mode = "none" if decay_gamma == 1.0 else "fixed_scalar"
        extra = {}
        if decay_mode == "fixed_scalar":
            extra = dict(gamma_min=min(decay_gamma, 0.5), gamma_max=1.0, initial_gamma=decay_gamma)
        cfg = matched_phase_config(embed_dim, num_heads, decay_mode=decay_mode,
                                   aux_scale=aux_scale, **extra)
        light = LightweightPhaseAttention(cfg).eval()

    copy_production_into_lightweight(prod, light)
    return prod, light
