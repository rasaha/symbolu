"""KVPro V3 Gate-1 — quantizers for the symmetric-residual falsification study.

Offline (CPU-runnable) quantizers that REPLICATE the production int4_protected granularity so the
"affine" arm here is bit-faithful to the shipped writer, and the symmetric candidates differ ONLY in
dropping xmin (S1) / adding a coarse bias (S2) / applying to one of K,V (S3,S4).

Production reference (verified in phase5b_4c_paged_writer.py):
  K:  per-BLOCK (BS tokens) per-(H,D):  scale=((amax-amin)/15).clamp(1e-8);
      q=round((x-xmin)/scale).clamp(0,15);  x_hat=q*scale+xmin            (unsigned affine, _ASYM_DIV=15)
  V:  per-TOKEN per-(H,group) group=v_group_size(=32):  same affine math per group.
  Protect: K-only, per-channel (H,D) mask; protected channels kept EXACT (unchanged) — the residual
           (non-protected) channels are what int4 actually represents.

Candidates (symmetric, signed [-7,7], no xmin unless noted):
  S1  symmetric residual INT4         scale=amax(|x|)/7;  q=clamp(round(x/scale),-7,7);  x_hat=q*scale
  S2  symmetric + coarse per-channel bias b[h,d] (per-LAYER, one value/channel): x_hat=q*scale+b
  S3  affine K, symmetric V
  S4  symmetric K, affine V

This module does NOT pack bits (offline math is in fp); byte accounting lives in accounting.py.
"""
from __future__ import annotations

from typing import Optional, Tuple

import torch

_ASYM_DIV = 15.0          # unsigned 4-bit affine, matches production
_SCALE_CLAMP = 1e-8
_SYM_LEVELS = 7           # signed [-7, 7]


# --------------------------------------------------------------------------- #
# Per-channel affine (production math), reduction over `red_dim`.
# --------------------------------------------------------------------------- #
def affine_int4(x: torch.Tensor, red_dim: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Affine unsigned 4-bit over `red_dim` (keepdim scale/xmin). Returns (x_hat, scale, xmin)."""
    xf = x.float()
    xmax = xf.amax(dim=red_dim, keepdim=True)
    xmin = xf.amin(dim=red_dim, keepdim=True)
    scale = ((xmax - xmin) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
    q = ((xf - xmin) / scale).round().clamp(0, 15)
    x_hat = q * scale + xmin
    return x_hat, scale, xmin


def symmetric_int4(x: torch.Tensor, red_dim: int,
                   bias: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
    """Symmetric signed 4-bit over `red_dim`. If `bias` given (S2), quantize (x-bias) and add it back.
    Returns (x_hat, scale)."""
    xf = x.float()
    xc = xf - bias if bias is not None else xf
    scale = (xc.abs().amax(dim=red_dim, keepdim=True) / _SYM_LEVELS).clamp(min=_SCALE_CLAMP)
    q = (xc / scale).round().clamp(-_SYM_LEVELS, _SYM_LEVELS)
    x_hat = q * scale
    if bias is not None:
        x_hat = x_hat + bias
    return x_hat, scale


# --------------------------------------------------------------------------- #
# K: block the sequence into BS-token blocks; quantize per-(block, H, D-channel).
# --------------------------------------------------------------------------- #
def quantize_k_sequence(K: torch.Tensor, BS: int, scheme: str,
                        bias: Optional[torch.Tensor] = None) -> torch.Tensor:
    """K: (S, H, D) fp -> reconstructed (S, H, D). scheme in {affine, symmetric}. Partial last block
    quantized over its real tokens (matches the writer). bias (H,D) only for scheme=symmetric (S2)."""
    S, H, D = K.shape
    out = torch.empty_like(K, dtype=torch.float32)
    for s0 in range(0, S, BS):
        blk = K[s0:s0 + BS]                       # (T<=BS, H, D)
        if scheme == "affine":
            deq, _, _ = affine_int4(blk, red_dim=0)
        elif scheme == "symmetric":
            deq, _ = symmetric_int4(blk, red_dim=0, bias=bias)
        else:
            raise ValueError(f"unknown K scheme {scheme!r}")
        out[s0:s0 + blk.shape[0]] = deq
    return out


# --------------------------------------------------------------------------- #
# V: per-token, grouped over head_dim into groups of v_group_size.
# --------------------------------------------------------------------------- #
def quantize_v_sequence(V: torch.Tensor, v_group_size: int, scheme: str,
                        bias: Optional[torch.Tensor] = None) -> torch.Tensor:
    """V: (S, H, D) fp -> reconstructed (S, H, D). Per-token, per-(H, group of v_group_size)."""
    S, H, D = V.shape
    if D % v_group_size != 0:
        raise ValueError(f"D={D} not divisible by v_group_size={v_group_size}")
    ng = D // v_group_size
    vg = V.float().view(S, H, ng, v_group_size)
    if scheme == "affine":
        deq, _, _ = affine_int4(vg, red_dim=3)
    elif scheme == "symmetric":
        b = bias.view(1, H, ng, v_group_size) if bias is not None else None
        deq, _ = symmetric_int4(vg, red_dim=3, bias=b)
    else:
        raise ValueError(f"unknown V scheme {scheme!r}")
    return deq.view(S, H, D)


# --------------------------------------------------------------------------- #
# Residual application: protected K channels kept EXACT; everything else quantized.
# --------------------------------------------------------------------------- #
_CANDIDATES = {
    #            K scheme     V scheme     K bias   V bias
    "affine":   ("affine",    "affine",    False,   False),   # == production (baseline)
    "S1":       ("symmetric", "symmetric", False,   False),
    "S2":       ("symmetric", "symmetric", True,    True),
    "S3":       ("affine",    "symmetric", False,   False),
    "S4":       ("symmetric", "affine",    False,   False),
}


def per_channel_mean_k(K: torch.Tensor) -> torch.Tensor:
    """S2 coarse bias for K: per-(H,D) mean over the whole captured sequence (one value/channel)."""
    return K.float().mean(dim=0)                  # (H, D)


def per_group_mean_v(V: torch.Tensor, v_group_size: int) -> torch.Tensor:
    """S2 coarse bias for V: per-(H,group) mean, broadcast to channels. Returns (H, D)."""
    S, H, D = V.shape
    ng = D // v_group_size
    m = V.float().view(S, H, ng, v_group_size).mean(dim=(0, 3))       # (H, ng)
    return m.unsqueeze(-1).expand(H, ng, v_group_size).reshape(H, D)


def reconstruct(K: torch.Tensor, V: torch.Tensor, protect_mask_hd: torch.Tensor,
                candidate: str, BS: int = 32, v_group_size: int = 32) -> Tuple[torch.Tensor, torch.Tensor]:
    """Reconstruct (K_hat, V_hat) under a candidate. protect_mask_hd: (H,D) bool/int (K-only).
    Protected K channels are copied EXACT from fp (isolating the residual-quant effect); this is held
    identical across all candidates, so the ONLY variable is the residual scheme."""
    if candidate not in _CANDIDATES:
        raise ValueError(f"unknown candidate {candidate!r}; choose {list(_CANDIDATES)}")
    k_scheme, v_scheme, k_bias_on, v_bias_on = _CANDIDATES[candidate]
    k_bias = per_channel_mean_k(K) if k_bias_on else None
    v_bias = per_group_mean_v(V, v_group_size) if v_bias_on else None

    K_hat = quantize_k_sequence(K, BS, k_scheme, bias=k_bias)
    V_hat = quantize_v_sequence(V, v_group_size, v_scheme, bias=v_bias)

    # Protected K channels: exact fp (K-only protection).
    prot = protect_mask_hd.to(torch.bool).view(1, *protect_mask_hd.shape)   # (1,H,D)
    K_hat = torch.where(prot.expand_as(K_hat), K.float(), K_hat)
    return K_hat, V_hat


def candidate_names():
    return list(_CANDIDATES)
