"""Preregistered non-learned phase-extraction mappings.

USE is natively phase-based; transformer channels are vectors. We map each channel vector to a
scalar phase with one of three fixed, non-learned mappings, compared separately (USE must not
silently pick one):

  A. complex_pair        phi = atan2(v[1], v[0])                    (first two coordinates)
  B. reference_projection phi = atan2(u2.v, u1.v)                    (two fixed orthonormal dirs)
  C. temporal_change     phi = atan2(u2.dv, u1.dv), dv = v[t]-v[t-1] (direction of change)

The reference directions u1,u2 are fixed once per channel dimensionality by a deterministic seed
(no learning). All mappings return a phase in (-pi, pi] per (batch, position).
"""

from __future__ import annotations

from typing import Dict

import torch

MAPPINGS = ["complex_pair", "reference_projection", "temporal_change"]


class PhaseExtractor:
    """Deterministic phase extractor with fixed per-dim reference directions."""

    def __init__(self, seed: int = 20260722):
        self.seed = seed
        self._refs: Dict[int, torch.Tensor] = {}

    def _ref(self, dim: int) -> torch.Tensor:
        """Return fixed orthonormal [2, dim] reference directions for this dimensionality."""
        if dim not in self._refs:
            g = torch.Generator().manual_seed(self.seed + dim)
            a = torch.randn(dim, 2, generator=g)
            q, _ = torch.linalg.qr(a)              # q: [dim,2] orthonormal columns
            self._refs[dim] = q.t().contiguous()   # [2,dim]
        return self._refs[dim]

    def extract(self, v: torch.Tensor, mapping: str) -> torch.Tensor:
        """v: [..., dim] -> phase [...] in (-pi, pi]."""
        dim = v.shape[-1]
        if mapping == "complex_pair":
            if dim < 2:
                raise ValueError("complex_pair needs dim>=2")
            return torch.atan2(v[..., 1], v[..., 0])
        if mapping == "reference_projection":
            u = self._ref(dim).to(v.dtype)
            p1 = v @ u[0]
            p2 = v @ u[1]
            return torch.atan2(p2, p1)
        if mapping == "temporal_change":
            # difference along the position axis (assumed second-to-last: [...,N,dim])
            dv = torch.zeros_like(v)
            dv[..., 1:, :] = v[..., 1:, :] - v[..., :-1, :]
            u = self._ref(dim).to(v.dtype)
            p1 = dv @ u[0]
            p2 = dv @ u[1]
            return torch.atan2(p2, p1)
        raise ValueError(f"unknown mapping {mapping!r}")
