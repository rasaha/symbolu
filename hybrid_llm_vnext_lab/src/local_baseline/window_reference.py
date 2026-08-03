"""
window_reference.py — minimal stdlib local/sliding-window baseline.

A dependency-free causal windowed-mean mixer over vectors. It is the "A" (local-only)
reference used to exercise the slot subsystem: it deliberately has NO long-range memory, so a
probe that requires binding a fact seen far earlier cannot be solved by the window alone —
which is exactly the contrast the phase_lc A/B/C ladder measured (window baseline ~chance on
beyond-window needles; slots carried the improvement).

This is NOT the neural baseline used for training (that is torch and RESOURCE_BLOCKED). It is a
structural reference for algorithmic probes and for composing with SlotReference.
"""

from __future__ import annotations

from typing import List, Sequence

Vector = Sequence[float]


class LocalWindowReference:
    """Causal windowed mean: out_t = mean(x_{max(0,t-w+1)..t}). O(N*W), never O(N*N)."""

    def __init__(self, window: int = 64):
        assert window >= 1
        self.window = window

    def forward(self, xs: Sequence[Vector]) -> List[List[float]]:
        n = len(xs)
        d = len(xs[0]) if n else 0
        out: List[List[float]] = []
        for t in range(n):
            lo = max(0, t - self.window + 1)
            span = xs[lo : t + 1]
            acc = [0.0] * d
            for v in span:
                for i in range(d):
                    acc[i] += v[i]
            k = len(span)
            out.append([a / k for a in acc])
        return out
