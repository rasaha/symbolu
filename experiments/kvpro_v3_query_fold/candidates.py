"""KVPro V3 query-fold — candidate definitions + K reconstruction (CPU-pure).

Exactly four pre-registered candidates. Each changes ONLY how K's per-block,
per-channel scale & xmin are represented; V is production affine and protected K
channels are exact bf16 for every candidate, so the sole variable is the K metadata.

  affine (QF4)  scale=production        xmin=production        — the reference arm
  QF1           scale=α_d·β_b (rank-1)  xmin=production        — fold α_d into Q, β_b/block
  QF2           scale=α_d·β_b (rank-1)  xmin=u_d+v_b (additive) — QF1 + fully-folded xmin
  QF3           scale=rank-2 SVD        xmin=production        — 2 Q-transforms + 2 scalars/block

Framing (honest): the writer is assumed to quantize K onto the CANDIDATE'S grid, so
the int4 codes match the cheap metadata (`q = round((K - xmin_approx)/scale_approx)`).
This isolates whether the factored FORMAT has enough resolution — NOT a code/metadata
mismatch. A candidate whose factored grid ≈ production loses nothing; one whose factored
grid is coarse loses quality, and that is exactly what Phase F measures.
"""
from __future__ import annotations

from typing import Dict, Optional

import torch

try:                       # package import (tests) or flat import (loose RunPod script)
    from . import factorize
except ImportError:        # pragma: no cover - import wiring
    import factorize       # type: ignore

_SCALE_CLAMP = 1e-8

# Pre-registered candidate specs. scale_rank/xmin_rank only used by the SVD models.
CANDIDATE_SPECS: Dict[str, Dict[str, object]] = {
    "affine": {"scale": "production", "xmin": "production"},
    "QF1":    {"scale": "rank1_mult", "xmin": "production"},
    "QF2":    {"scale": "rank1_mult", "xmin": "additive"},
    "QF3":    {"scale": "svd", "scale_rank": 2, "xmin": "production"},
}
QF_CANDIDATES = ["QF1", "QF2", "QF3"]     # non-reference arms
ALL_CANDIDATES = ["affine"] + QF_CANDIDATES


def candidate_names():
    return list(ALL_CANDIDATES)


def _factor_scale(s_bd: torch.Tensor, model: str, rank: Optional[int]) -> Dict[str, object]:
    """Return {'grid': (B,D) approximated scale, 'n_block_meta': scalars kept per block,
    'n_channel_meta': foldable per-channel values}. n_block_meta is what the decode pays
    per block; n_channel_meta folds into Q once (≈ free per block)."""
    if model == "production":
        return {"grid": s_bd, "n_block_meta": s_bd.shape[1], "n_channel_meta": 0}
    if model == "rank1_mult":
        f = factorize.rank1_log_multiplicative(s_bd)
        return {"grid": f["fitted"].clamp_min(_SCALE_CLAMP), "n_block_meta": 1,
                "n_channel_meta": s_bd.shape[1], "fit": f}          # β_b per block, α_d folded
    if model == "svd":
        f = factorize.low_rank_svd(s_bd, int(rank))
        return {"grid": f["fitted"].clamp_min(_SCALE_CLAMP), "n_block_meta": f["R"],
                "n_channel_meta": s_bd.shape[1] * f["R"], "fit": f}  # R scalars/block, R vecs folded
    raise ValueError(f"unknown scale model {model!r}")


def _factor_xmin(x_bd: torch.Tensor, model: str, rank: Optional[int]) -> Dict[str, object]:
    if model == "production":
        return {"grid": x_bd, "n_block_meta": x_bd.shape[1], "n_channel_meta": 0}
    if model == "additive":
        f = factorize.two_way_additive(x_bd)
        return {"grid": f["fitted"], "n_block_meta": 1, "n_channel_meta": x_bd.shape[1], "fit": f}
    if model == "svd":
        f = factorize.low_rank_svd(x_bd, int(rank))
        return {"grid": f["fitted"], "n_block_meta": f["R"], "n_channel_meta": x_bd.shape[1] * f["R"],
                "fit": f}
    raise ValueError(f"unknown xmin model {model!r}")


def _requant_blocks(Kh: torch.Tensor, s_grid: torch.Tensor, x_grid: torch.Tensor,
                    BS: int) -> torch.Tensor:
    """Quantize Kh (S, D) onto the per-block factored grid (s_grid/x_grid: (B, D)) and
    dequantize. Matches the writer producing codes for the candidate's grid."""
    S, D = Kh.shape
    out = torch.empty(S, D, dtype=torch.float32)
    B = s_grid.shape[0]
    for b in range(B):
        lo, hi = b * BS, min((b + 1) * BS, S)
        if lo >= S:
            break
        blk = Kh[lo:hi].to(torch.float32)
        s = s_grid[b].to(torch.float32).clamp_min(_SCALE_CLAMP)
        x = x_grid[b].to(torch.float32)
        q = ((blk - x) / s).round().clamp(0, 15)
        out[lo:hi] = q * s + x
    if B * BS < S:                                   # tokens past the last block metadata row
        out[B * BS:] = Kh[B * BS:].to(torch.float32)  # (shouldn't happen; guard, exact passthrough)
    return out


def build_metadata(s_prod_bd: torch.Tensor, xmin_prod_bd: torch.Tensor,
                   candidate: str) -> Dict[str, object]:
    """Per-(layer,head) factored metadata + the per-block/per-channel accounting."""
    spec = CANDIDATE_SPECS[candidate]
    sf = _factor_scale(s_prod_bd, spec["scale"], spec.get("scale_rank"))
    xf = _factor_xmin(xmin_prod_bd, spec["xmin"], spec.get("xmin_rank"))
    return {
        "scale_grid": sf["grid"], "xmin_grid": xf["grid"],
        "block_meta_values": sf["n_block_meta"] + xf["n_block_meta"],     # kept per block
        "channel_meta_values": sf["n_channel_meta"] + xf["n_channel_meta"],  # folded once
        "scale_fit": sf.get("fit"), "xmin_fit": xf.get("fit"),
    }


def reconstruct_k(K: torch.Tensor, s_prod: torch.Tensor, xmin_prod: torch.Tensor,
                  protect_mask_hd: torch.Tensor, candidate: str, BS: int = 32
                  ) -> torch.Tensor:
    """K: (S, H, D) fp; s_prod/xmin_prod: (B, H, D) production per-block per-channel.
    Returns K_hat (S, H, D) under `candidate`, protected channels exact bf16."""
    if candidate not in CANDIDATE_SPECS:
        raise ValueError(f"unknown candidate {candidate!r}; choose {ALL_CANDIDATES}")
    S, H, D = K.shape
    K_hat = torch.empty(S, H, D, dtype=torch.float32)
    for h in range(H):
        meta = build_metadata(s_prod[:, h, :], xmin_prod[:, h, :], candidate)
        K_hat[:, h, :] = _requant_blocks(K[:, h, :], meta["scale_grid"], meta["xmin_grid"], BS)
    prot = protect_mask_hd.to(torch.bool).view(1, H, D).expand(S, H, D)
    K_hat = torch.where(prot, K.to(torch.float32), K_hat)
    return K_hat
