"""KVPro V3 Step-0 (Part F) — protected-K INT8 fake-quant (P8), ORTHOGONAL to the S1-S4 residual study.

Question: can the PROTECTED K channels (currently kept exact / bf16 in the sidecar) be stored as INT8
without a quality regression, holding EVERYTHING else at the current shipped baseline?

Baseline ("affine" cell): affine INT4 residual K + affine INT4 V, protected channels kept EXACT.
P8 cells differ from that baseline in ONE way only: the protected K channels are stored INT8 instead
of exact. The INT4 residual and the V path are untouched — so any quality delta is attributable purely
to protected-sidecar precision. P8 is evaluated INDEPENDENTLY; it is NOT combined with S1-S4 here.

Granularity: one scale (P8sym) or scale+zero (P8aff) per protected channel (h_kv, d), calibrated over
the token axis. That matches a per-channel sidecar scale that costs ~0 bytes/token, so the per-token
protected footprint drops from 2 B (bf16) to 1 B (int8) — see accounting.py prot_B=1.

Equations (per protected channel c, over its token values x_t):
  P8sym:  s = max_t|x_t| / 127 ;              q = clamp(round(x/s), -127, 127) ;  x̂ = q·s
  P8aff:  s = (max_t x - min_t x) / 255 ;     q = clamp(round((x-min)/s), 0, 255) ; x̂ = q·s + min

Pure torch, CPU-runnable. The residual/V math is REUSED verbatim from quantizers.py.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, Tuple

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quantizers as Q          # noqa: E402  (exact INT4 residual + V math, unchanged)

_I8_SYM = 127                   # signed int8 levels [-127, 127]
_I8_AFF = 255                   # unsigned int8 levels [0, 255]
_CLAMP = 1e-8

# P8 cell -> protected scheme. Baseline is the existing "affine" cell (exact/bf16 protected).
_P8 = {"P8sym": "symmetric", "P8aff": "affine"}


def protected_int8_symmetric(x: torch.Tensor, red_dim: int) -> Tuple[torch.Tensor, torch.Tensor]:
    """Per-channel signed INT8 over `red_dim`. Returns (x_hat, scale)."""
    xf = x.float()
    scale = (xf.abs().amax(dim=red_dim, keepdim=True) / _I8_SYM).clamp(min=_CLAMP)
    q = (xf / scale).round().clamp(-_I8_SYM, _I8_SYM)
    return q * scale, scale


def protected_int8_affine(x: torch.Tensor, red_dim: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Per-channel unsigned affine INT8 over `red_dim`. Returns (x_hat, scale, xmin)."""
    xf = x.float()
    xmax = xf.amax(dim=red_dim, keepdim=True)
    xmin = xf.amin(dim=red_dim, keepdim=True)
    scale = ((xmax - xmin) / _I8_AFF).clamp(min=_CLAMP)
    q = ((xf - xmin) / scale).round().clamp(0, _I8_AFF)
    return q * scale + xmin, scale, xmin


def candidate_names():
    return list(_P8)


def reconstruct_p8(K: torch.Tensor, V: torch.Tensor, protect_mask_hd: torch.Tensor,
                   candidate: str, BS: int = 32, v_group_size: int = 32) -> Tuple[torch.Tensor, torch.Tensor]:
    """Reconstruct (K_hat, V_hat) with the shipped affine INT4 residual + affine INT4 V UNCHANGED, and
    the protected K channels stored INT8 (per-channel over the token axis) instead of exact.
    candidate in {P8sym, P8aff}. protect_mask_hd: (H, D) bool/int, K-only (identical mask to production)."""
    if candidate not in _P8:
        raise ValueError(f"unknown P8 candidate {candidate!r}; choose {list(_P8)}")
    # residual + V: byte-identical to the 'affine' baseline arm
    K_hat = Q.quantize_k_sequence(K, BS, "affine")
    V_hat = Q.quantize_v_sequence(V, v_group_size, "affine")

    m = protect_mask_hd.to(torch.bool)                       # (H, D)
    if m.any():
        Kf = K.float()
        if _P8[candidate] == "symmetric":
            prot_hat, _ = protected_int8_symmetric(Kf, red_dim=0)          # per-(h,d) over tokens
        else:
            prot_hat, _, _ = protected_int8_affine(Kf, red_dim=0)
        prot = m.view(1, *m.shape).expand_as(K_hat)          # (S, H, D)
        K_hat = torch.where(prot, prot_hat, K_hat)
    return K_hat, V_hat


def protected_stream_bytes(n_protect: int, sidecar_B_bf16: int = 2) -> Dict[str, float]:
    """Per-token protected-sidecar bytes: bf16 (current) vs int8 (P8). Scale/zero are per-CHANNEL
    (amortized ~0/token). This is a modeled byte delta, NOT a measured TPS change."""
    bf16 = n_protect * sidecar_B_bf16
    int8 = n_protect * 1
    return {
        "protected_bytes_per_tok_head_layer_bf16": float(bf16),
        "protected_bytes_per_tok_head_layer_int8": float(int8),
        "protected_bytes_saved": float(bf16 - int8),
        "protected_stream_reduction_pct": round(100.0 * (bf16 - int8) / bf16, 2) if bf16 else 0.0,
    }
