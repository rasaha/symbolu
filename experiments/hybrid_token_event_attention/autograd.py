"""
autograd.py — a minimal, dependency-free reverse-mode autograd over 2-D matrices.

Why this exists: this sandbox has no numpy / torch / transformers installed, and the decisive
scientific object under test — the *bounded event-to-event attention operator* (§4) — is tiny
(K ≤ 16 slots, d ≤ 32). Rather than fabricate numbers we cannot run, we implement just enough
autograd in pure stdlib Python to *actually train and evaluate* the event path and the small
local token stand-in on CPU, deterministically and reproducibly.

A `Tensor` wraps a rectangular list-of-lists `data` (rows x cols), an equally-shaped `grad`, the
set of parent tensors, and a `_backward` closure that accumulates parent grads from this node's
grad. `backward()` does a topological sort and runs the closures in reverse.

Supported ops (all the event/token models need): matmul, add (with row-vector bias broadcast),
elementwise add/mul/scale, relu, tanh, row-softmax, row-mean, index_rows (embedding lookup),
concat_rows, stack, and cross_entropy. Sizes are small; clarity beats speed.
"""
from __future__ import annotations

import math
from typing import Callable, List, Optional, Sequence, Set


class Tensor:
    __slots__ = ("data", "grad", "_backward", "_parents", "requires_grad", "shape")

    def __init__(self, data: List[List[float]], requires_grad: bool = False,
                 _parents: Sequence["Tensor"] = ()):  # data is rows x cols
        self.data = data
        self.shape = (len(data), len(data[0]) if data else 0)
        self.requires_grad = requires_grad
        self.grad = [[0.0] * self.shape[1] for _ in range(self.shape[0])]
        self._backward: Callable[[], None] = lambda: None
        self._parents = tuple(_parents)

    # ---- construction helpers ----
    @staticmethod
    def zeros(r: int, c: int, requires_grad: bool = False) -> "Tensor":
        return Tensor([[0.0] * c for _ in range(r)], requires_grad)

    def zero_grad(self) -> None:
        for row in self.grad:
            for j in range(len(row)):
                row[j] = 0.0

    # ---- autograd core ----
    def backward(self, seed: Optional[List[List[float]]] = None) -> None:
        # seed grad (default: ones for a 1x1 scalar loss)
        if seed is None:
            if self.shape != (1, 1):
                raise ValueError("backward() with no seed requires a scalar (1x1) tensor")
            self.grad[0][0] = 1.0
        else:
            self.grad = [row[:] for row in seed]
        topo: List[Tensor] = []
        seen: Set[int] = set()

        def build(t: "Tensor") -> None:
            if id(t) in seen:
                return
            seen.add(id(t))
            for p in t._parents:
                build(p)
            topo.append(t)

        build(self)
        for t in reversed(topo):
            t._backward()


# ---------- elementwise / structural ops ----------
def _acc(t: Tensor, r: int, c: int, v: float) -> None:
    t.grad[r][c] += v


def matmul(a: Tensor, b: Tensor) -> Tensor:
    ar, ac = a.shape
    br, bc = b.shape
    assert ac == br, f"matmul shape mismatch {a.shape} x {b.shape}"
    out = [[0.0] * bc for _ in range(ar)]
    for i in range(ar):
        ai = a.data[i]
        oi = out[i]
        for k in range(ac):
            aik = ai[k]
            if aik == 0.0:
                continue
            bk = b.data[k]
            for j in range(bc):
                oi[j] += aik * bk[j]
    res = Tensor(out, a.requires_grad or b.requires_grad, (a, b))

    def _bw() -> None:
        g = res.grad
        # dA = g @ b^T ; dB = a^T @ g
        for i in range(ar):
            gi = g[i]
            for k in range(ac):
                s = 0.0
                bk = b.data[k]
                for j in range(bc):
                    s += gi[j] * bk[j]
                a.grad[i][k] += s
        for k in range(ac):
            for j in range(bc):
                s = 0.0
                for i in range(ar):
                    s += a.data[i][k] * g[i][j]
                b.grad[k][j] += s

    res._backward = _bw
    return res


def add_bias(x: Tensor, b: Tensor) -> Tensor:
    """x (r x c) + b (1 x c) broadcast over rows."""
    r, c = x.shape
    assert b.shape == (1, c)
    out = [[x.data[i][j] + b.data[0][j] for j in range(c)] for i in range(r)]
    res = Tensor(out, x.requires_grad or b.requires_grad, (x, b))

    def _bw() -> None:
        for i in range(r):
            for j in range(c):
                g = res.grad[i][j]
                x.grad[i][j] += g
                b.grad[0][j] += g

    res._backward = _bw
    return res


def add(a: Tensor, b: Tensor) -> Tensor:
    r, c = a.shape
    assert a.shape == b.shape
    out = [[a.data[i][j] + b.data[i][j] for j in range(c)] for i in range(r)]
    res = Tensor(out, a.requires_grad or b.requires_grad, (a, b))

    def _bw() -> None:
        for i in range(r):
            for j in range(c):
                g = res.grad[i][j]
                a.grad[i][j] += g
                b.grad[i][j] += g

    res._backward = _bw
    return res


def mul(a: Tensor, b: Tensor) -> Tensor:
    """Elementwise product (same shape)."""
    r, c = a.shape
    assert a.shape == b.shape
    out = [[a.data[i][j] * b.data[i][j] for j in range(c)] for i in range(r)]
    res = Tensor(out, a.requires_grad or b.requires_grad, (a, b))

    def _bw() -> None:
        for i in range(r):
            for j in range(c):
                g = res.grad[i][j]
                a.grad[i][j] += g * b.data[i][j]
                b.grad[i][j] += g * a.data[i][j]

    res._backward = _bw
    return res


def scale(x: Tensor, s: float) -> Tensor:
    r, c = x.shape
    out = [[x.data[i][j] * s for j in range(c)] for i in range(r)]
    res = Tensor(out, x.requires_grad, (x,))

    def _bw() -> None:
        for i in range(r):
            for j in range(c):
                x.grad[i][j] += res.grad[i][j] * s

    res._backward = _bw
    return res


def relu(x: Tensor) -> Tensor:
    r, c = x.shape
    out = [[x.data[i][j] if x.data[i][j] > 0 else 0.0 for j in range(c)] for i in range(r)]
    res = Tensor(out, x.requires_grad, (x,))

    def _bw() -> None:
        for i in range(r):
            for j in range(c):
                if x.data[i][j] > 0:
                    x.grad[i][j] += res.grad[i][j]

    res._backward = _bw
    return res


def tanh(x: Tensor) -> Tensor:
    r, c = x.shape
    out = [[math.tanh(x.data[i][j]) for j in range(c)] for i in range(r)]
    res = Tensor(out, x.requires_grad, (x,))

    def _bw() -> None:
        for i in range(r):
            for j in range(c):
                t = out[i][j]
                x.grad[i][j] += res.grad[i][j] * (1.0 - t * t)

    res._backward = _bw
    return res


def row_softmax(x: Tensor) -> Tensor:
    """softmax along columns for each row (axis = the K event slots when x is K x K)."""
    r, c = x.shape
    out = [[0.0] * c for _ in range(r)]
    for i in range(r):
        m = max(x.data[i])
        exps = [math.exp(v - m) for v in x.data[i]]
        s = sum(exps) or 1.0
        out[i] = [e / s for e in exps]
    res = Tensor(out, x.requires_grad, (x,))

    def _bw() -> None:
        for i in range(r):
            oi = out[i]
            gi = res.grad[i]
            dot = sum(gi[j] * oi[j] for j in range(c))
            for j in range(c):
                x.grad[i][j] += oi[j] * (gi[j] - dot)

    res._backward = _bw
    return res


def row_mean(x: Tensor) -> Tensor:
    """mean over rows -> 1 x c."""
    r, c = x.shape
    out = [[sum(x.data[i][j] for i in range(r)) / r for j in range(c)]]
    res = Tensor(out, x.requires_grad, (x,))

    def _bw() -> None:
        for i in range(r):
            for j in range(c):
                x.grad[i][j] += res.grad[0][j] / r

    res._backward = _bw
    return res


def index_rows(table: Tensor, idxs: Sequence[int]) -> Tensor:
    """Embedding lookup: select rows `idxs` from `table` (V x d) -> (len(idxs) x d)."""
    d = table.shape[1]
    out = [table.data[i][:] for i in idxs]
    res = Tensor(out, table.requires_grad, (table,))

    def _bw() -> None:
        for r_out, src in enumerate(idxs):
            for j in range(d):
                table.grad[src][j] += res.grad[r_out][j]

    res._backward = _bw
    return res


def concat_cols(a: Tensor, b: Tensor) -> Tensor:
    """concatenate two (r x .) tensors along columns."""
    r = a.shape[0]
    assert b.shape[0] == r
    ac, bc = a.shape[1], b.shape[1]
    out = [a.data[i][:] + b.data[i][:] for i in range(r)]
    res = Tensor(out, a.requires_grad or b.requires_grad, (a, b))

    def _bw() -> None:
        for i in range(r):
            for j in range(ac):
                a.grad[i][j] += res.grad[i][j]
            for j in range(bc):
                b.grad[i][j] += res.grad[i][ac + j]

    res._backward = _bw
    return res


def cross_entropy(logits: Tensor, target: int) -> Tensor:
    """logits: 1 x C. Returns scalar 1x1 loss = -log softmax[target]."""
    assert logits.shape[0] == 1
    row = logits.data[0]
    m = max(row)
    exps = [math.exp(v - m) for v in row]
    s = sum(exps)
    logp = [(v - m) - math.log(s) for v in row]
    loss = -logp[target]
    res = Tensor([[loss]], logits.requires_grad, (logits,))
    probs = [e / s for e in exps]

    def _bw() -> None:
        g = res.grad[0][0]
        for j in range(len(row)):
            logits.grad[0][j] += g * (probs[j] - (1.0 if j == target else 0.0))

    res._backward = _bw
    return res


def softmax_probs(logits: Tensor) -> List[float]:
    row = logits.data[0]
    m = max(row)
    exps = [math.exp(v - m) for v in row]
    s = sum(exps) or 1.0
    return [e / s for e in exps]
