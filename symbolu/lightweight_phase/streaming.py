"""
streaming.py — Stage 2 helpers: chunked scan and streaming-equivalence checks.

The Phase core already exposes the incremental ``step`` API and ``forward`` with
``initial_state``. This module provides convenience wrappers used by tests and by
downstream generation code:

    run_chunked(layer, x, chunk_sizes)  — process x in chunks, carrying PhaseState
    stream_tokens(layer, x)             — token-by-token, returns [B, N, D]
    max_abs_error(a, b)                 — scalar float, for tolerance assertions

Constant-memory contract: none of these helpers retain per-token state beyond the
single carried PhaseState (size independent of N).
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import torch
from torch import Tensor

from .phase_core import LightweightPhaseAttention, PhaseState


def stream_tokens(layer: LightweightPhaseAttention, x: Tensor,
                  initial_state: Optional[PhaseState] = None) -> Tensor:
    """Run ``layer`` one token at a time; return stacked outputs [B, N, D]."""
    B, N, D = x.shape
    state = initial_state
    outs: List[Tensor] = []
    for t in range(N):
        o_t, state = layer.step(x[:, t], state)
        outs.append(o_t)
    return torch.stack(outs, dim=1)


def run_chunked(layer: LightweightPhaseAttention, x: Tensor,
                chunk_sizes: Sequence[int],
                initial_state: Optional[PhaseState] = None) -> Tensor:
    """Process x in chunks of the given sizes, carrying PhaseState across boundaries.

    ``sum(chunk_sizes)`` must equal N. Returns the concatenated output [B, N, D].
    """
    B, N, D = x.shape
    if sum(chunk_sizes) != N:
        raise ValueError(f"chunk_sizes sum {sum(chunk_sizes)} != N {N}")
    state = initial_state
    outs: List[Tensor] = []
    pos = 0
    for cs in chunk_sizes:
        chunk = x[:, pos:pos + cs]
        out = layer(chunk, initial_state=state, return_state=True)
        outs.append(out.output)
        state = out.state
        pos += cs
    return torch.cat(outs, dim=1)


def max_abs_error(a: Tensor, b: Tensor) -> float:
    return (a - b).abs().max().item()
