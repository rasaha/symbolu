"""
ablations.py — causal ablations of the selective write gate (§13).

For a trained variant, re-probe focus decoding with the gate overridden at inference:
  learned (baseline), forced_one (=v1 dense), forced_zero, random, shuffled.
The claimed selective-write gain must DISAPPEAR when the meaningful gate is removed
or randomized. Applied by re-running the Phase readout with a gate_override tensor.
"""
from __future__ import annotations

import torch
from .focus_data import generate_focus
from .focus_probe import fit_probe, collate
from experiments.phase_guided_slots_v2.task_schema import VENDORS

N_VENDOR = len(VENDORS)


@torch.no_grad()
def _phase_g_with_gate(model, ids, mode):
    """Recompute Phase readout g with an overridden gate. Returns g [B,N,D]."""
    x = model.embed(ids) + model.pos(torch.arange(ids.shape[1]).clamp(max=8191)).unsqueeze(0)
    h = model.local(x, return_residual_add=True)
    xn = model.phase.core.norm(h)
    w = model.phase.core._gate(xn)                     # learned gate [B,N,H]
    if mode == "learned":
        gov = w
    elif mode == "forced_one":
        gov = torch.ones_like(w)
    elif mode == "forced_zero":
        gov = torch.zeros_like(w)
    elif mode == "random":
        gov = torch.rand_like(w)
    elif mode == "shuffled":
        gov = w[:, torch.randperm(w.shape[1])]
    else:
        raise ValueError(mode)
    return model.phase.readout(h, gate_override=gov)


@torch.no_grad()
def run_ablations(model, vocab, seed=3, n=200, target_len=256, n_distractors=24):
    if model.variant_name == "V1":
        return {}
    exs = generate_focus(vocab, "test", seed, n, n_distractors=n_distractors, target_len=target_len)
    ids, focus, batch = collate(exs, vocab.pad_id, "cpu")
    out = {}
    for mode in ("learned", "forced_one", "forced_zero", "random", "shuffled"):
        g = _phase_g_with_gate(model, ids, mode)
        GG, Y = [], []
        for i, e in enumerate(batch):
            if not e.anchor_pos:
                continue
            p = min(e.anchor_pos[-1], ids.shape[1] - 1)
            GG.append(g[i, p]); Y.append(e.focus_vendor_id)
        X = torch.stack(GG); y = torch.tensor(Y)
        nn_ = len(y); perm = torch.randperm(nn_); tr, te = perm[:int(.7 * nn_)], perm[int(.7 * nn_):]
        out[mode] = fit_probe(X[tr], y[tr], N_VENDOR, X[te], y[te])["top1"]
    out["chance"] = 1.0 / N_VENDOR
    return out
