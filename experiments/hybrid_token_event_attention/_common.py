"""
_common.py — deterministic RNG, parameter init, and a tiny SGD optimizer.

Everything is seeded through a small linear-congruential generator so runs are byte-for-byte
reproducible without numpy. No wall-clock, no os.urandom.
"""
from __future__ import annotations

import math
from typing import Dict, List

from .autograd import Tensor


class RNG:
    """Deterministic LCG (Numerical Recipes constants) with a Box-Muller normal."""

    def __init__(self, seed: int = 0):
        self.state = (seed * 2862933555777941757 + 3037000493) & ((1 << 64) - 1)

    def _next(self) -> int:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return self.state

    def random(self) -> float:
        return (self._next() >> 11) / float(1 << 53)

    def randint(self, lo: int, hi: int) -> int:  # inclusive lo, exclusive hi
        return lo + int(self.random() * (hi - lo))

    def choice(self, seq):
        return seq[self.randint(0, len(seq))]

    def normal(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        u1 = max(self.random(), 1e-12)
        u2 = self.random()
        return mu + sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def shuffle(self, seq: List) -> None:
        for i in range(len(seq) - 1, 0, -1):
            j = self.randint(0, i + 1)
            seq[i], seq[j] = seq[j], seq[i]


def param(rows: int, cols: int, rng: RNG, scale: float = None) -> Tensor:
    """Xavier-ish init."""
    if scale is None:
        scale = math.sqrt(1.0 / max(1, cols))
    data = [[rng.normal(0.0, scale) for _ in range(cols)] for _ in range(rows)]
    return Tensor(data, requires_grad=True)


def zeros_param(rows: int, cols: int) -> Tensor:
    return Tensor([[0.0] * cols for _ in range(rows)], requires_grad=True)


class SGD:
    """Plain SGD with momentum and optional weight decay; operates on a name->Tensor dict."""

    def __init__(self, params: Dict[str, Tensor], lr: float = 0.1, momentum: float = 0.9,
                 weight_decay: float = 0.0):
        self.params = params
        self.lr = lr
        self.momentum = momentum
        self.wd = weight_decay
        self.vel: Dict[str, List[List[float]]] = {
            k: [[0.0] * v.shape[1] for _ in range(v.shape[0])] for k, v in params.items()}

    def zero_grad(self) -> None:
        for p in self.params.values():
            p.zero_grad()

    def step(self, max_norm: float = 2.0) -> None:
        # global gradient-norm clipping (stabilises the deeper attention / bridge paths)
        sq = 0.0
        for p in self.params.values():
            for row in p.grad:
                for g in row:
                    sq += g * g
        norm = math.sqrt(sq)
        gscale = (max_norm / norm) if norm > max_norm else 1.0
        for name, p in self.params.items():
            v = self.vel[name]
            for i in range(p.shape[0]):
                gi = p.grad[i]
                for j in range(p.shape[1]):
                    g = gi[j] * gscale + self.wd * p.data[i][j]
                    v[i][j] = self.momentum * v[i][j] - self.lr * g
                    p.data[i][j] += v[i][j]


def freeze(t: Tensor) -> Tensor:
    t.requires_grad = False
    return t
