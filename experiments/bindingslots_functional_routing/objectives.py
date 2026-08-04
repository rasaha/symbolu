#!/usr/bin/env python3
"""Address-specific functional-routing auxiliary objectives (training-only).

Each is a drop-in replacement for the frozen `interventions.alignment_loss` with the IDENTICAL
signature `(model, x_aux, fact_pos, query_pos, eps=1e-6) -> (loss_tensor, overlap_float)`, so the
frozen `stabilize.run_arm` loop can be run UNCHANGED with exactly one function swapped in memory
(the interventions.py file on disk is never edited; its sha256 is preserved). The swap is the whole
intervention surface: architecture, optimizer, curriculum, λ-schedule, evaluation, and causal
ablations all remain the frozen code path.

s*(f) = argmax_j stop_gradient(w[f,j])  (deterministic; torch.argmax returns the lowest index on
ties). No answer-label token, evaluator outcome, future checkpoint, or classifier label is used —
only the slot-address vectors the frozen capture hook already exposes.
"""
from __future__ import annotations

import torch


def _capture(model, x_aux):
    """Run the frozen capture hook forward and return the per-layer slot mixers."""
    import interventions as IV  # frozen module (unmodified on disk)
    slots = model.slot_mixers()
    IV.enable_capture(model, True)
    _ = model(x_aux)  # grad-enabled; logits discarded (no output-token supervision)
    return IV, slots


def correct_slot_prob_loss(model, x_aux, fact_pos, query_pos, eps=1e-6):
    """O1: L = -log(r[q, s*] + eps), averaged over layers and batch.

    Requires the read distribution to place probability on the SPECIFIC slot that received the
    write, not merely to agree in aggregate. `overlap` is returned for logging parity only.
    """
    IV, slots = _capture(model, x_aux)
    B = x_aux.size(0)
    idx = torch.arange(B)
    terms, overlaps = [], []
    for sm in slots:
        w = sm._sfs_waddr[idx, fact_pos]     # [B, M] write address at the value token
        r = sm._sfs_raddr[idx, query_pos]    # [B, M] read address at the query
        s_star = w.detach().argmax(dim=-1)   # [B] stop-grad top-write slot (lowest index on ties)
        r_star = r[idx, s_star]              # [B] read prob on s*
        terms.append(-(r_star + eps).log())  # [B]
        overlaps.append((w * r).sum(-1))     # [B] aggregate overlap (diagnostic)
    IV.enable_capture(model, False)
    return torch.stack(terms).mean(), torch.stack(overlaps).mean().detach().item()


def address_margin_loss(model, x_aux, fact_pos, query_pos, eps=1e-6, m=3.0):
    """O2: L = mean max(0, m - (z[q, s*] - max_{j != s*} z[q, j])), z = pre-softmax read logits.

    Requires an explicit read-logit separation of at least `m` between the written slot and its
    strongest competitor. Margin m is frozen at 3.0.
    """
    IV, slots = _capture(model, x_aux)
    B = x_aux.size(0)
    idx = torch.arange(B)
    terms, overlaps = [], []
    for sm in slots:
        w = sm._sfs_waddr[idx, fact_pos]     # [B, M]
        z = sm._sfs_rlogit[idx, query_pos]   # [B, M] read logits
        r = sm._sfs_raddr[idx, query_pos]    # [B, M] (diagnostic overlap only)
        s_star = w.detach().argmax(dim=-1)   # [B]
        z_star = z[idx, s_star]              # [B]
        z_masked = z.clone()
        z_masked[idx, s_star] = float("-inf")
        z_other = z_masked.max(dim=-1).values  # [B] strongest competitor
        margin = z_star - z_other               # [B]
        terms.append(torch.clamp(m - margin, min=0.0))
        overlaps.append((w * r).sum(-1))
    IV.enable_capture(model, False)
    return torch.stack(terms).mean(), torch.stack(overlaps).mean().detach().item()
