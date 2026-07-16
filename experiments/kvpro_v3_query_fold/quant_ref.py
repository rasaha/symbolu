"""Production-faithful K affine quantization (CPU-pure, self-contained).

Mirrors phase5b_4c_paged_writer.py (K path, `_ASYM_DIV=15`, per-block per-channel
affine) and experiments/kvpro_v3_symmetric_residual/quantizers.affine_int4 — kept
self-contained so the RunPod loose scripts need no cross-experiment import.

Production K (verified phase5b_4c_paged_writer.py:18,35,1109-1132):
  per BLOCK (BS tokens) per (H, D-channel):
    scale = ((amax - amin) / 15).clamp(1e-8)      amax/amin over the block's tokens
    code  = round((x - amin) / scale).clamp(0,15) uint4  (stored in the low nibble)
    x_hat = code * scale + amin
"""
from __future__ import annotations

from typing import Tuple

import torch

_ASYM_DIV = 15.0
_SCALE_CLAMP = 1e-8


def _affine(x: torch.Tensor, red_dim: int):
    xf = x.to(torch.float32)
    xmax = xf.amax(dim=red_dim, keepdim=True)
    xmin = xf.amin(dim=red_dim, keepdim=True)
    scale = ((xmax - xmin) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
    q = ((xf - xmin) / scale).round().clamp(0, 15)
    return q, scale, xmin


def production_k_metadata(K: torch.Tensor, BS: int = 32
                          ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """K: (S, H, D) fp. Returns (s_prod (B,H,D), xmin_prod (B,H,D), codes (S,H,D) uint8),
    B = ceil(S/BS). Full blocks reduce over the BS-token axis; a partial trailing block
    reduces over its real tokens (matches the writer's partial-block handling)."""
    S, H, D = K.shape
    n_full = S // BS
    n_blocks = (S + BS - 1) // BS
    s_prod = torch.empty(n_blocks, H, D, dtype=torch.float32)
    x_prod = torch.empty(n_blocks, H, D, dtype=torch.float32)
    codes = torch.zeros(S, H, D, dtype=torch.uint8)
    if n_full:
        head = K[:n_full * BS].reshape(n_full, BS, H, D)
        q, sc, xm = _affine(head, red_dim=1)                 # sc/xm: (n_full,1,H,D)
        s_prod[:n_full] = sc[:, 0]
        x_prod[:n_full] = xm[:, 0]
        codes[:n_full * BS] = q.reshape(n_full * BS, H, D).to(torch.uint8)
    if n_full < n_blocks:                                    # partial trailing block
        tail = K[n_full * BS:]
        q, sc, xm = _affine(tail, red_dim=0)                 # sc/xm: (1,H,D)
        s_prod[n_full] = sc[0]
        x_prod[n_full] = xm[0]
        codes[n_full * BS:] = q.to(torch.uint8)
    return s_prod, x_prod, codes


def dequant_k(codes: torch.Tensor, s_prod: torch.Tensor, xmin_prod: torch.Tensor,
              BS: int = 32) -> torch.Tensor:
    """Inverse: codes (S,H,D) uint8 + per-block s/xmin (B,H,D) -> K_hat (S,H,D). Exact
    production affine reconstruction (no protect overlay here)."""
    S, H, D = codes.shape
    out = torch.empty(S, H, D, dtype=torch.float32)
    B = s_prod.shape[0]
    for b in range(B):
        lo, hi = b * BS, min((b + 1) * BS, S)
        if lo >= S:
            break
        out[lo:hi] = codes[lo:hi].to(torch.float32) * s_prod[b] + xmin_prod[b]
    return out
