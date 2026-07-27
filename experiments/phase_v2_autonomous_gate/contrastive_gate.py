"""
contrastive_gate.py — arm E objective (§ Required training arms).

Rank relevant events above distractors in write score, with no per-token oracle label
beyond the relevant/distractor grouping:

    L_gate = mean_examples max(0, margin - mean(B_relevant) + mean(B_distractor))
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor


def contrastive_loss(gate: Tensor, relevant_mask: Tensor, distractor_mask: Tensor,
                     margin: float = 0.3) -> Tensor:
    """gate:[B,N] mean over heads; masks:[B,N] bool."""
    B = gate.shape[0]
    losses = []
    for b in range(B):
        rm, dm = relevant_mask[b], distractor_mask[b]
        if rm.any() and dm.any():
            losses.append(F.relu(margin - gate[b][rm].mean() + gate[b][dm].mean()))
    if not losses:
        return torch.zeros((), device=gate.device)
    return torch.stack(losses).mean()
