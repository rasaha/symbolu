"""
dynamics_analysis.py — §15 stability and state-dynamics diagnostics for V3 variants.

Per head / position: write rate B_t, read rate C_t, effective γ_t and horizon, state
norm, phase rotation. Flags pathologies (γ saturating/collapsing, write/read all/none,
state explosion/cancellation, inactive/identical heads) and reports per-head
specialization + pairwise head correlation.
"""
from __future__ import annotations

import torch

from .config import DataCfg
from . import dataset as D


@torch.no_grad()
def analyze(model, vocab, dcfg: DataCfg, distance=256, seed=0, n=200):
    if not model.variant_name.startswith("V3"):
        return {"variant": model.variant_name, "note": "diagnostics defined for V3 only"}
    data = D.generate(vocab, dcfg, distance, n, 7000 + seed)
    ids, wtgt, probe_pos, focus = D.collate(data, vocab.PAD)
    core = model.variant.core
    x = model.embed(ids)
    out = core(x, return_diagnostics=True)
    d = out.diagnostics
    gamma_h = d["gamma_per_head"]
    write_h = d["write_rate_per_head"]
    read_h = d["read_rate_per_head"]
    horizon_h = (1.0 / (1.0 - gamma_h.clamp(max=1 - 1e-6)))
    snorm = d["state_norm_per_head"]

    # per-head specialization: how differently heads write across positions
    xn = core.norm(x)
    _, gamma_full, Bt, Ct = core._controls(xn)          # [B,N,H]
    wr = Bt.mean(0)                                       # [N,H]
    # pairwise head correlation of write-rate-over-position
    wrc = wr - wr.mean(0, keepdim=True)
    denom = wrc.norm(dim=0, keepdim=True) + 1e-6
    corr = (wrc / denom).T @ (wrc / denom)               # [H,H]
    H = gamma_h.shape[0]
    offdiag = corr[~torch.eye(H, dtype=torch.bool)].abs().mean().item()

    flags = {
        "gamma_saturating": bool((gamma_h > 0.999).any().item()),
        "gamma_collapsed": bool((gamma_h < 0.905).all().item()),
        "write_all": bool((write_h > 0.95).all().item()),
        "write_none": bool((write_h < 0.05).all().item()),
        "read_all": bool((read_h > 0.95).all().item()),
        "read_none": bool((read_h < 0.05).all().item()),
        "state_explosion": bool((snorm > 50).any().item()),
        "state_cancellation": bool((snorm < 1e-3).any().item()),
        "inactive_heads": int((write_h < 0.05).sum().item()),
        "identical_heads": bool(offdiag > 0.98),
    }
    return {
        "variant": model.variant_name,
        "gamma_per_head": gamma_h.tolist(),
        "write_rate_per_head": write_h.tolist(),
        "read_rate_per_head": read_h.tolist(),
        "effective_horizon_per_head": horizon_h.tolist(),
        "state_norm_per_head": snorm.tolist(),
        "mean_pairwise_head_write_corr": offdiag,
        "gamma_mean": d["gamma_mean"].item(),
        "write_rate_mean": d["write_rate_mean"].item(),
        "read_rate_mean": d["read_rate_mean"].item(),
        "omega_abs_mean": d["omega_abs_mean"].item(),
        "flags": flags,
    }
