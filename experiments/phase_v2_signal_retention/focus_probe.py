"""
focus_probe.py — shared probe utilities for the Phase v2 signal-retention study.

Freeze a trained variant; extract features at a chosen position (local h, Phase
readout g, per-bank state); fit a lightweight linear probe to decode the focus
identity; report top-1 / top-k / AUROC-ish. Also relevance-F1 (is fact vendor ==
focus) and control features (shuffled / random).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.phase_guided_slots_v2.task_schema import VENDORS
from .train import collate

N_VENDOR = len(VENDORS)


def fit_probe(X, y, ncls, Xte, yte, steps=300):
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Xn, Xten = (X - mu) / sd, (Xte - mu) / sd
    W = nn.Linear(X.shape[1], ncls)
    opt = torch.optim.Adam(W.parameters(), lr=0.05, weight_decay=1e-3)
    with torch.enable_grad():
        for _ in range(steps):
            opt.zero_grad(); F.cross_entropy(W(Xn), y).backward(); opt.step()
    with torch.no_grad():
        lg = W(Xten)
        top1 = (lg.argmax(-1) == yte).float().mean().item()
        k = min(3, ncls)
        topk = (lg.topk(k, -1).indices == yte[:, None]).any(-1).float().mean().item()
    return {"top1": top1, "topk": topk}


@torch.no_grad()
def _phase_state(model, ids, device):
    """Recurrent Phase STATE at sequence end, flattened to real features.
    V1: frozen state [B,H,Dh]; V2: per-bank state [B,banks,H,Dh]."""
    x = model.embed(ids) + model.pos(torch.arange(ids.shape[1], device=device).clamp(max=8191)).unsqueeze(0)
    h = model.local(x, return_residual_add=True)
    core = model.phase.core if hasattr(model.phase, "core") else model.phase.core
    out = core(h, return_state=True)
    S = out.state.complex_memory                    # [B, ...] complex
    return torch.view_as_real(S).reshape(S.shape[0], -1)   # [B, feat]


@torch.no_grad()
def features_at_last_anchor(model, exs, pad_id, device="cpu"):
    """Return local h and Phase readout g at the last anchor, plus the Phase STATE at
    sequence end (the §10 'Phase state only' feature), plus focus label."""
    ids, focus, batch = collate(exs, pad_id, device)
    h, g = model.encode(ids)
    state = _phase_state(model, ids, device)         # [B, feat]  (per example, seq-end)
    HH, GG, ST, Y = [], [], [], []
    for i, e in enumerate(batch):
        if not e.anchor_pos:
            continue
        p = min(e.anchor_pos[-1], ids.shape[1] - 1)
        HH.append(h[i, p]); GG.append(g[i, p]); ST.append(state[i]); Y.append(e.focus_vendor_id)
    return {"h": torch.stack(HH), "g": torch.stack(GG),
            "bank_state": torch.stack(ST), "y": torch.tensor(Y)}


def probe_focus(model, exs, pad_id, feature="g"):
    f = features_at_last_anchor(model, exs, pad_id)
    X = f[feature] if feature in f else f["g"]
    y = f["y"]
    n = len(y); perm = torch.randperm(n); tr, te = perm[:int(.7 * n)], perm[int(.7 * n):]
    ncls = N_VENDOR
    res = {}
    res["main"] = fit_probe(X[tr], y[tr], ncls, X[te], y[te])
    res["shuffled"] = fit_probe(X[torch.randperm(n)][tr], y[tr], ncls, X[torch.randperm(n)][te], y[te])
    res["random"] = fit_probe(torch.randn_like(X)[tr], y[tr], ncls, torch.randn_like(X)[te], y[te])
    res["chance"] = 1.0 / ncls
    return res
