"""Coherence block-scorer for semantic KV tiering (CPU-testable, GPU-ready).

A *block vector* is the per-block aggregate (e.g. mean value-vector) of the KV in
that block. The coherence score ranks blocks by alignment with the running
*context* representation — SCC's `S = cosine` signal — which is DIFFERENT from
attention magnitude (attention depends on the current query; coherence is the
block's alignment with the evolving semantic context, query-independent).

Pure-Python core operates on `list[list[float]]` so it is unit-testable without
torch. `score_torch` is the GPU path (tensors); it is a thin mirror of the same
math and is only imported when called.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

Vector = Sequence[float]
MODES = ("cos_value", "cos_key", "value_norm")


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: Vector) -> float:
    return math.sqrt(_dot(a, a))


def unit(a: Vector) -> list[float]:
    n = _norm(a) or 1.0
    return [x / n for x in a]


def context_centroid(block_vectors: Sequence[Vector], weights: Optional[Sequence[float]] = None) -> list[float]:
    """Running context representation = (optionally weighted) mean of block
    vectors, unit-normalized. Pass recency/attention weights to bias it."""
    n = len(block_vectors)
    if n == 0:
        return []
    d = len(block_vectors[0])
    w = list(weights) if weights is not None else [1.0] * n
    acc = [0.0] * d
    wsum = 0.0
    for v, wi in zip(block_vectors, w):
        for j in range(d):
            acc[j] += wi * v[j]
        wsum += wi
    if wsum:
        acc = [x / wsum for x in acc]
    return unit(acc)


def coherence_scores(
    block_vectors: Sequence[Vector],
    centroid: Optional[Vector] = None,
    mode: str = "cos_value",
    weights: Optional[Sequence[float]] = None,
) -> list[float]:
    """Coherence score per block.

    mode:
      cos_value / cos_key — cosine of each (value- or key-)block vector to the
                            context centroid (caller passes the right vectors).
      value_norm          — ‖v_b‖, a known cheap importance proxy (sanity comparator).
    """
    if not block_vectors:
        return []
    if mode == "value_norm":
        return [_norm(v) for v in block_vectors]
    if mode not in ("cos_value", "cos_key"):
        raise ValueError(f"unknown mode {mode!r} (one of {MODES})")
    c = list(centroid) if centroid is not None else context_centroid(block_vectors, weights)
    return [_dot(unit(v), c) for v in block_vectors]


# --------------------------------------------------------------------------- #
# GPU path — tensors. Mirror of the pure core; torch imported only when called.
# --------------------------------------------------------------------------- #
def score_torch(block_vectors, centroid=None, mode: str = "cos_value", weights=None):
    """block_vectors: [n_blocks, dim] torch tensor. Returns [n_blocks] scores.

    Drop-in for the GPU harness: pass per-block mean value (or key) vectors from
    the cache. Same semantics as the pure core; runs on-device, no .tolist()."""
    import torch  # local import keeps the module CPU-importable

    bv = block_vectors
    if mode == "value_norm":
        return bv.norm(dim=-1)
    if mode not in ("cos_value", "cos_key"):
        raise ValueError(f"unknown mode {mode!r} (one of {MODES})")
    if centroid is None:
        if weights is None:
            mean = bv.mean(dim=0, keepdim=True)
        else:
            w = weights.to(bv.dtype).unsqueeze(-1)
            mean = (bv * w).sum(0, keepdim=True) / w.sum().clamp_min(1e-9)
        centroid = torch.nn.functional.normalize(mean, dim=-1)
    bvn = torch.nn.functional.normalize(bv, dim=-1)
    return (bvn * centroid).sum(dim=-1)
