"""
diagnostics.py — read-only metrics for the Lightweight Phase core and blocks.

Everything here runs under ``torch.no_grad`` and has no effect on training. These
are the metrics referenced by the stage reports (Stage 6 path-contribution
instrumentation and Stage 1 health signals).
"""

from __future__ import annotations

from typing import Dict

import torch
from torch import Tensor


@torch.no_grad()
def mean_resultant_length(phi: Tensor) -> Tensor:
    """R = |mean_d exp(i·φ)| pooled over batch/seq → per-head [H].

    phi: [B, N, H, Dh]. R→0 uniform (healthy), R→1 collapsed.
    """
    z = torch.exp(1j * phi.to(torch.float32)).mean(dim=-1)  # [B,N,H]
    return z.abs().mean(dim=(0, 1))


@torch.no_grad()
def tensor_norm(x: Tensor) -> float:
    return x.norm().item()


@torch.no_grad()
def path_contribution(local_out: Tensor, phase_out: Tensor) -> Dict[str, float]:
    """Relative output-norm contribution of the local vs phase paths (Stage 6)."""
    ln = local_out.norm().item()
    pn = phase_out.norm().item()
    total = ln + pn + 1e-12
    return {
        "local_norm": ln,
        "phase_norm": pn,
        "local_fraction": ln / total,
        "phase_fraction": pn / total,
    }


@torch.no_grad()
def prediction_change_rate(logits_a: Tensor, logits_b: Tensor) -> float:
    """Fraction of positions whose argmax prediction changes between a and b.

    Used for causal ablations: disable a path and measure how often the top-1
    next-token prediction flips.
    """
    pa = logits_a.argmax(dim=-1)
    pb = logits_b.argmax(dim=-1)
    return (pa != pb).float().mean().item()
