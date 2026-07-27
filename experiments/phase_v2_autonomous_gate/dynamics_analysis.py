"""
dynamics_analysis.py — gate dynamics + state health for the autonomous-gate study.

Reports overall/write-rate by category (cue, relevant, distractor, filler), relevant−distractor
gate margin, per-head gate specialization, state signal-to-noise ratio, state norm, and
write-all/write-none collapse flags.
"""
from __future__ import annotations

import torch

from experiments.phase_v3_selective_ssm import dataset as D
from experiments.phase_v3_selective_ssm.config import DataCfg


@torch.no_grad()
def analyze(model, vocab, dcfg: DataCfg, distance=1024, seed=0, n=200):
    data = D.generate(vocab, dcfg, distance, n, 7300 + seed)
    ids, wt, pp, fo = D.collate(data, vocab.PAD)
    gate = model.gate(ids)                       # [B,N,H]
    gm = gate.mean(-1)
    write_head = gate.mean(dim=(0, 1))           # [H]
    # SNR of the state at probe: focus (cue) contribution vs total norm
    f = model.features(ids, gate=gate)
    ar = torch.arange(ids.shape[0])
    state = f["state"][ar, pp]                    # [B,2D]
    snr = (state.pow(2).mean(-1) / (state.var(-1) + 1e-6)).mean().item()
    # per-head specialization: variance of per-head write rate
    spec = write_head.std().item()
    flags = {
        "write_all": bool((write_head > 0.95).all().item()),
        "write_none": bool((write_head < 0.05).all().item()),
        "inactive_heads": int((write_head < 0.05).sum().item()),
        "overall_write_rate": gm.mean().item(),
    }
    return {
        "distance": distance,
        "write_rate_mean": gm.mean().item(),
        "write_rate_per_head": write_head.tolist(),
        "head_specialization_std": spec,
        "state_snr": snr,
        "state_norm_mean": state.pow(2).mean(-1).sqrt().mean().item(),
        "flags": flags,
    }
