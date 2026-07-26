"""
retention_losses.py — losses for the Phase-v2 oracle-retention experiment.

  L_answer : CE at <A> (trains value/read/decode — identical path across arms).
  L_write  : BCE, write gate → 1 at every fact anchor (fill memory).
  L_gatephase (v2 arms only): supervise the Phase v2-S write gate — write the focus
             HEADER and focus-relevant facts (1), skip distractors (0). Research
             scaffold; uses the distant focus cue, NOT the future query.
  L_retain : pairwise hinge — focus-relevant records must out-rank distractor records
             in retention r_final (§9-B): L = max(0, margin - mean r_focus + mean r_distr).
             This is the ONLY thing that makes retention trainable under discrete
             eviction, and it uses only the focus-cue label.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


def answer_loss(logits, aid):
    return F.cross_entropy(logits, aid)


def write_gate_loss(gate, anchor_mask):
    if not anchor_mask.any():
        return torch.zeros((), device=gate.device)
    # push gate → 1 at anchors (balanced against the many non-anchor 0s implicitly by
    # only supervising anchors as positives + a light budget on the rest)
    pos = gate[anchor_mask].clamp(1e-4, 1 - 1e-4)
    return F.binary_cross_entropy(pos, torch.ones_like(pos))


def phase_gate_loss(w, gate_target):
    """w:[B,N] mean phase gate; gate_target:[B,N] in {1,0,-1(ignore)}."""
    m = gate_target >= 0
    if not m.any():
        return torch.zeros((), device=w.device)
    return F.binary_cross_entropy(w[m].clamp(1e-4, 1 - 1e-4), gate_target[m])


def retention_hinge(r_final, focus_anchor_mask, distr_anchor_mask, margin=1.0):
    """Per example: focus-record retention must exceed distractor-record retention by
    a margin. r_final:[B,N]; masks:[B,N] bool."""
    B = r_final.shape[0]
    losses = []
    for b in range(B):
        fm, dm = focus_anchor_mask[b], distr_anchor_mask[b]
        if fm.any() and dm.any():
            rf = r_final[b][fm].mean()
            rd = r_final[b][dm].mean()
            losses.append(F.relu(margin - rf + rd))
    if not losses:
        return torch.zeros((), device=r_final.device)
    return torch.stack(losses).mean()
