"""
event_attention.py — bounded FULL event self-attention operator (§4).

    E ∈ R^(K × d)
    A_event = softmax( Q_event K_event^T / sqrt(d) )     # softmax axis = EVENT SLOTS
    H_event = A_event V_event

The softmax is taken over the K event slots (columns of the K×K score matrix), NOT over token
positions. At K = 8 the operator produces the 8×8 interaction matrix that §4 requires; `forward`
returns that exact matrix (plain floats) for audit and causal analysis.

This is the principal event arm (full slot-to-slot), chosen because the predecessor experiment
(`enterprise_slots_quadratic`, S5 vs S6) showed full self-attention beats query-to-slot-only.

`MeanPool` is the ablated readout used by H2: it drops the interaction entirely and just averages
the encoded rows. Same encoder, same head — the ONLY difference from H3 is the interaction, which
is exactly what the H3 − H2 comparison isolates.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .autograd import (Tensor, matmul, row_softmax, row_mean, add, scale, tanh, mul)
from ._common import RNG, param, zeros_param


def _transpose(t: Tensor) -> Tensor:
    r, c = t.shape
    out = [[t.data[i][j] for i in range(r)] for j in range(c)]
    res = Tensor(out, t.requires_grad, (t,))

    def _bw():
        for i in range(r):
            for j in range(c):
                t.grad[i][j] += res.grad[j][i]
    res._backward = _bw
    return res


class EventSelfAttention:
    """Single-head full event self-attention with a residual + tanh output projection."""

    def __init__(self, d: int, rng: RNG):
        self.d = d
        self.Wq = param(d, d, rng)
        self.Wk = param(d, d, rng)
        self.Wv = param(d, d, rng)
        # small output-projection init: attention starts near residual pass-through and
        # then *learns* the slot-to-slot interaction (otherwise random Wo injects noise the
        # short schedule cannot undo, and the pooling ablation spuriously wins).
        self.Wo = param(d, d, rng, scale=0.5 / math.sqrt(d))
        # GATED-RESIDUAL interaction: the readout is mean-pool(E) PLUS a learned, gated correction
        # computed from the slot-to-slot interaction. The gate is initialised to ZERO, so at the
        # start H3 is byte-identical to H2 (mean pooling) and can only *add* the interaction where
        # it demonstrably helps — the interaction never destroys the strong pooling baseline. This
        # makes "value of event-to-event interaction over pooling" both robust and cleanly isolated.
        self.gate = zeros_param(1, d)
        self._last_attn: List[List[float]] = []       # K x K slot-to-slot (audit)
        self._last_readout: List[float] = []           # 1 x K attention received per slot

    def params(self, prefix: str = "attn") -> Dict[str, Tensor]:
        return {f"{prefix}.Wq": self.Wq, f"{prefix}.Wk": self.Wk, f"{prefix}.Wv": self.Wv,
                f"{prefix}.Wo": self.Wo, f"{prefix}.gate": self.gate}

    def forward(self, E: Tensor) -> Tuple[Tensor, List[List[float]]]:
        Q = matmul(E, self.Wq)
        K = matmul(E, self.Wk)
        V = matmul(E, self.Wv)
        scores = scale(matmul(Q, _transpose(K)), 1.0 / math.sqrt(self.d))   # K x K
        A = row_softmax(scores)                                             # softmax over slots
        self._last_attn = [row[:] for row in A.data]                        # audit copy (K x K)
        delta = tanh(matmul(matmul(A, V), self.Wo))                        # K x d interaction
        return delta, self._last_attn

    def readout(self, E: Tensor) -> Tuple[Tensor, List[List[float]]]:
        delta, A = self.forward(E)
        # attention received per slot (column mass of A) → attribution weights
        k = len(A)
        self._last_readout = [sum(A[i][j] for i in range(k)) / k for j in range(k)] if k else []
        ctx = add(row_mean(E), mul(self.gate, row_mean(delta)))            # pool + gated interaction
        return ctx, A


class MeanPool:
    """H2 readout: mean-pool the encoded events; NO slot-to-slot interaction."""

    def __init__(self, d: int):
        self.d = d
        self._last_attn: List[List[float]] = []

    def params(self, prefix: str = "pool") -> Dict[str, Tensor]:
        return {}

    def readout(self, E: Tensor) -> Tuple[Tensor, List[List[float]]]:
        k = E.shape[0]
        self._last_attn = [[1.0 / k] * k for _ in range(k)]   # uniform "attention" for audit parity
        return row_mean(E), self._last_attn


# ---------- attention diagnostics (§11 attention-level) ----------
def attention_entropy(A: List[List[float]]) -> float:
    """Mean row entropy of the K×K matrix (nats)."""
    if not A:
        return 0.0
    tot = 0.0
    for row in A:
        tot += -sum(p * math.log(p + 1e-12) for p in row)
    return tot / len(A)


def mass_on(A: List[List[float]], slot_idxs: List[int]) -> float:
    """Average attention mass landing on a set of (required / irrelevant) slots."""
    if not A:
        return 0.0
    s = set(slot_idxs)
    tot = 0.0
    for row in A:
        tot += sum(row[j] for j in range(len(row)) if j in s)
    return tot / len(A)
