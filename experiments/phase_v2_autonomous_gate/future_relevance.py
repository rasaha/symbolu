"""
future_relevance.py — arm D objective (§ Required training arms).

Train the write gate with an auxiliary objective predicting whether the current event will
remain relevant at a later probe position — i.e. whether this event's entity is the focus
that the probe will query. In this task the future-relevance label of an event equals
(event entity == focus); the cue is always future-relevant. The signal is a *delayed
relevance* credit rather than a hand-authored write mask.

    L_future = BCE(B_t, future_relevant_t)   over cue + event positions
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor


def future_relevance_loss(gate: Tensor, future_label: Tensor, mask: Tensor) -> Tensor:
    """gate:[B,N] mean over heads; future_label:[B,N] in {0,1}; mask:[B,N] bool (supervised)."""
    if not mask.any():
        return torch.zeros((), device=gate.device)
    return F.binary_cross_entropy(gate[mask].clamp(1e-4, 1 - 1e-4), future_label[mask])
