"""Video-DiT reused-feature-cache compression — CORE LIBRARY (CPU-runnable).

Shared primitives for the pre-registered feasibility study
(docs/VIDEO_DIT_FEATURE_CACHE_COMPRESSION_FEASIBILITY_PLAN.md). Everything here operates on CAPTURED
tensors and runs on CPU; nothing here touches the KVPro core implementation.

Scope guard (read the plan): this study is about tensors that are STORED AND REUSED ACROSS DENOISING
STEPS in a video diffusion transformer — persistent cross-step cache objects. It is NOT about weight
quantization, one-pass activation quantization, latent compression, or transient tensors that are never
reused. The comparison is always full-precision cached features vs COMPRESSED cached features UNDER THE
SAME cache/reuse schedule. Compression and compute-skipping are complementary, not alternatives.

Canonical captured-tensor shape used throughout:  (T, N, C)
  T = number of cached snapshots of one cache object at one layer (one per step where it was cached),
  N = spatial/token positions in that snapshot,
  C = channel dimension.
This mirrors the tensor-capture spec in the plan doc and in capture_dit_cache.py.

Production reuse: where the repo's INT4 quantizer is importable we use its EXACT per-reduction affine
primitive (experiments/kvpro_v3_symmetric_residual/quantizers.affine_int4) for the INT4 numbers, so the
low-bit math matches the shipped kernel's intent rather than an approximation. INT8 uses the same affine
structure at 8 bits (the production module is INT4-only). The `int_math` provenance string records which
path was taken. The feasibility signal (does protection add value over uniform quant on cross-step cache
objects) is granularity-agnostic, but production math is preferred.

Evidence tier for everything in this module: **Measured — CPU tensor analysis**. CPU analysis CANNOT
establish whether the real workload is capacity-, bandwidth-, communication-, or compute-bound, nor can
tensor reconstruction error stand in for output-video quality. Those require GPU profiling and
end-to-end generation (Stage B).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import torch

# Canonical cache-object vocabulary (kept separate; never averaged together — see plan §7).
CACHE_OBJECTS = (
    "residual_block",
    "hidden_states",
    "attn_out",
    "cross_attn_out",
    "temporal_attn_out",
    "feature_delta",
    "predicted_residual",
)

_EPS = 1e-12


# --------------------------------------------------------------------------- #
# Production quantizer wiring (optional; mirrors kvpro_video_understanding).
# --------------------------------------------------------------------------- #
def load_production_quantizer():
    """Return the repo's production quantizers module if importable, else None."""
    try:
        repo = Path(__file__).resolve().parents[2]
        p = str(repo / "experiments" / "kvpro_v3_symmetric_residual")
        if p not in sys.path:
            sys.path.insert(0, p)
        import quantizers as Q  # noqa: N811
        return Q
    except Exception:
        return None


_Q = load_production_quantizer()
INT_MATH = (
    "production: quantizers.affine_int4 (per-reduction affine) for INT4; self-contained affine for INT8"
    if _Q is not None
    else "fallback: self-contained affine int4/int8 (production quantizer not importable)"
)


# --------------------------------------------------------------------------- #
# Quant / dequant primitives.
# --------------------------------------------------------------------------- #
def _affine_qdq(x: torch.Tensor, nbits: int, red_dim: int, symmetric: bool = False) -> torch.Tensor:
    """Affine (or symmetric) quant-dequant of `x` over `red_dim`. Returns reconstructed float tensor.

    INT4 affine defers to the production primitive when available (matches shipped numerics)."""
    xf = x.float()
    if symmetric:
        levels = (1 << (nbits - 1)) - 1  # e.g. 7 for int4, 127 for int8
        scale = (xf.abs().amax(dim=red_dim, keepdim=True) / levels).clamp(min=1e-8)
        q = (xf / scale).round().clamp(-levels, levels)
        return q * scale
    # asymmetric / affine unsigned
    if nbits == 4 and _Q is not None:
        x_hat, _, _ = _Q.affine_int4(xf, red_dim=red_dim)  # production math
        return x_hat.float()
    hi = (1 << nbits) - 1
    xmax = xf.amax(dim=red_dim, keepdim=True)
    xmin = xf.amin(dim=red_dim, keepdim=True)
    scale = ((xmax - xmin) / hi).clamp(min=1e-8)
    q = ((xf - xmin) / scale).round().clamp(0, hi)
    return q * scale + xmin


def quantize_uniform(
    x: torch.Tensor,
    nbits: int,
    granularity: str = "per_block",
    symmetric: bool = False,
    block_size: int = 32,
) -> torch.Tensor:
    """Uniform low-bit quant-dequant of a (T,N,C) or (N,C) tensor.

    granularity:
      per_tensor  — one scale for the whole snapshot
      per_channel — one scale per channel C (reduce over positions)
      per_block   — blocks of `block_size` positions along N, per (block, channel)
    Returns reconstructed float tensor of the same shape.
    """
    if x.ndim == 2:
        x = x.unsqueeze(0)
        squeeze = True
    else:
        squeeze = False
    T, N, C = x.shape
    if granularity == "per_tensor":
        out = torch.stack([_affine_qdq(x[t].reshape(-1), nbits, 0, symmetric).reshape(N, C) for t in range(T)])
    elif granularity == "per_channel":
        out = _affine_qdq(x, nbits, red_dim=1, symmetric=symmetric)  # reduce over positions N
    elif granularity == "per_block":
        out = torch.empty_like(x, dtype=torch.float32)
        n_full = N // block_size
        if n_full:
            head = x[:, : n_full * block_size, :].reshape(T, n_full, block_size, C)
            deq = _affine_qdq(head, nbits, red_dim=2, symmetric=symmetric)  # reduce within-block positions
            out[:, : n_full * block_size, :] = deq.reshape(T, n_full * block_size, C)
        if N - n_full * block_size:
            tail = x[:, n_full * block_size :, :]
            out[:, n_full * block_size :, :] = _affine_qdq(tail, nbits, red_dim=1, symmetric=symmetric)
    else:
        raise ValueError(f"unknown granularity {granularity!r}")
    return out.squeeze(0) if squeeze else out


def protected_quantize(
    x: torch.Tensor,
    nbits: int,
    protect_mask: torch.Tensor,
    protect_dtype: torch.dtype = torch.bfloat16,
    granularity: str = "per_block",
    symmetric: bool = False,
    block_size: int = 32,
) -> torch.Tensor:
    """Keep a bounded subset (protect_mask) at `protect_dtype`; quantize the rest to `nbits`.

    protect_mask is a bool tensor broadcastable to x's last dims. Channel protection -> shape (C,) or
    (1,C); token protection -> shape (N,1); hybrid -> (N,C). Protected values incur ONLY the
    protect_dtype rounding (bf16 by default, matching production intent)."""
    xq = quantize_uniform(x, nbits, granularity, symmetric, block_size)
    prot = x.to(protect_dtype).float()
    m = protect_mask.to(torch.bool)
    while m.ndim < x.ndim:
        m = m.unsqueeze(0)
    m = m.expand_as(x)
    return torch.where(m, prot, xq)


def lowrank_residual_reconstruct(x: torch.Tensor, x_quant: torch.Tensor, rank: int) -> torch.Tensor:
    """Add a rank-`rank` SVD approximation of the residual (x - x_quant) back onto x_quant, per snapshot.

    Models the 'quantization + low-rank residual' branch (an SVDQuant-style outlier-absorbing residual,
    applied here to a cross-step cache object). Returns reconstructed float tensor."""
    if x.ndim == 2:
        x = x.unsqueeze(0)
        x_quant = x_quant.unsqueeze(0)
        squeeze = True
    else:
        squeeze = False
    out = torch.empty_like(x, dtype=torch.float32)
    for t in range(x.shape[0]):
        r = (x[t].float() - x_quant[t].float())
        k = max(1, min(rank, min(r.shape) - 1)) if min(r.shape) > 1 else 1
        try:
            U, S, Vh = torch.linalg.svd(r, full_matrices=False)
            approx = (U[:, :k] * S[:k]) @ Vh[:k, :]
        except Exception:
            approx = torch.zeros_like(r)
        out[t] = x_quant[t].float() + approx
    return out.squeeze(0) if squeeze else out


# --------------------------------------------------------------------------- #
# Reconstruction metrics.
# --------------------------------------------------------------------------- #
def rel_l2(ref: torch.Tensor, test: torch.Tensor) -> float:
    a, b = ref.float(), test.float()
    return (torch.linalg.vector_norm(b - a) / (torch.linalg.vector_norm(a) + _EPS)).item()


def cosine_sim(ref: torch.Tensor, test: torch.Tensor) -> float:
    a, b = ref.float().reshape(-1), test.float().reshape(-1)
    return (torch.dot(a, b) / (a.norm() * b.norm() + _EPS)).item()


def max_channel_rel_err(ref: torch.Tensor, test: torch.Tensor) -> float:
    """Worst per-channel relative L2 error (channels = last dim)."""
    a = ref.float().reshape(-1, ref.shape[-1])
    b = test.float().reshape(-1, test.shape[-1])
    num = torch.linalg.vector_norm(b - a, dim=0)
    den = torch.linalg.vector_norm(a, dim=0) + _EPS
    return (num / den).max().item()


# --------------------------------------------------------------------------- #
# Structure / redundancy / distribution metrics.
# --------------------------------------------------------------------------- #
def channel_rms(x: torch.Tensor) -> torch.Tensor:
    """(T,N,C) or (N,C) -> per-channel RMS over all positions/snapshots -> (C,)."""
    xf = x.float().reshape(-1, x.shape[-1])
    return xf.pow(2).mean(dim=0).sqrt()


def token_rms(x: torch.Tensor) -> torch.Tensor:
    """Per-position RMS over channels (averaged across snapshots) -> (N,)."""
    xf = x.float()
    if xf.ndim == 2:
        xf = xf.unsqueeze(0)
    return xf.pow(2).mean(dim=2).sqrt().mean(dim=0)  # (N,)


def concentration_ratio(mags: torch.Tensor, frac: float) -> float:
    """(energy share of top-frac entries) / frac. ~1 uniform; >>1 concentrated outliers."""
    flat = mags.flatten().pow(2)
    k = max(1, int(round(frac * flat.numel())))
    top = torch.topk(flat, k).values.sum()
    share = (top / (flat.sum() + _EPS)).item()
    return share / frac


def kurtosis(mags: torch.Tensor) -> float:
    v = mags.flatten().float()
    m = v.mean()
    s = v.std() + _EPS
    return ((v - m).pow(4).mean() / s.pow(4)).item()


def dynamic_range_db(x: torch.Tensor) -> float:
    a = x.float().abs()
    hi = a.max().item()
    lo = a[a > 0].min().item() if (a > 0).any() else _EPS
    return 20.0 * math.log10((hi + _EPS) / (lo + _EPS))


def entropy_bits(x: torch.Tensor, nbins: int = 256) -> float:
    """Shannon entropy (bits) of the value histogram — a coarse compressibility proxy."""
    xf = x.float().reshape(-1)
    lo, hi = xf.min().item(), xf.max().item()
    if hi <= lo:
        return 0.0
    hist = torch.histc(xf, bins=nbins, min=lo, max=hi)
    p = hist / (hist.sum() + _EPS)
    p = p[p > 0]
    return float(-(p * p.log2()).sum().item())


def temporal_redundancy(x: torch.Tensor) -> dict:
    """How similar are consecutive cached snapshots (the reuse premise). x: (T,N,C), needs T>=2.

    Returns mean step-to-step relative delta magnitude and mean cosine similarity between
    consecutive snapshots. Low delta / high cosine = temporally redundant = delta-codable."""
    if x.ndim != 3 or x.shape[0] < 2:
        return {"consecutive_rel_delta_mean": float("nan"), "consecutive_cosine_mean": float("nan")}
    deltas, coss = [], []
    for t in range(1, x.shape[0]):
        deltas.append(rel_l2(x[t - 1], x[t]))
        coss.append(cosine_sim(x[t - 1], x[t]))
    return {
        "consecutive_rel_delta_mean": round(sum(deltas) / len(deltas), 5),
        "consecutive_cosine_mean": round(sum(coss) / len(coss), 5),
    }


def spatial_redundancy(x: torch.Tensor, rank_frac: float = 0.1) -> dict:
    """Low-rank energy captured by the top rank_frac singular values of one snapshot (N,C).

    High captured-energy at small rank = spatially redundant = low-rank-codable."""
    xf = x.float()
    if xf.ndim == 3:
        xf = xf[0]
    try:
        S = torch.linalg.svdvals(xf)
    except Exception:
        return {"lowrank_energy_frac_at_10pct": float("nan")}
    k = max(1, int(round(rank_frac * S.numel())))
    frac = (S[:k].pow(2).sum() / (S.pow(2).sum() + _EPS)).item()
    return {"lowrank_energy_frac_at_10pct": round(frac, 4)}


def top_channel_mask(x: torch.Tensor, frac: float) -> torch.Tensor:
    """Top-frac channels by RMS -> bool (C,)."""
    mags = channel_rms(x)
    C = mags.numel()
    k = max(1, int(round(frac * C)))
    mask = torch.zeros(C, dtype=torch.bool)
    mask[torch.topk(mags, k).indices] = True
    return mask


# --------------------------------------------------------------------------- #
# Byte accounting — the HONEST net density, after all overheads (plan §6C/§10 G2).
# --------------------------------------------------------------------------- #
def byte_account(
    x: torch.Tensor,
    nbits: int,
    granularity: str,
    protect_frac: float = 0.0,
    protect_bits: int = 16,
    block_size: int = 32,
    scale_bits: int = 16,
    gate_meta_bytes_per_snapshot: int = 8,
    baseline_bits: int = 16,
) -> dict:
    """Net compressed bytes for one cache object, INCLUDING scales, zero-points, protected values, and
    gate metadata. Returns baseline vs compressed bytes and net density (baseline/compressed).

    Temporary decode buffers are NOT counted toward stored density (they are transient), but the plan
    flags them as a Stage-B systems cost; see the `temp_buffer_note` field."""
    if x.ndim == 2:
        x = x.unsqueeze(0)
    T, N, C = x.shape
    elems = T * N * C
    baseline_bytes = elems * baseline_bits / 8

    # payload
    n_prot = int(round(protect_frac * C))
    n_quant_channels = C - n_prot
    payload_bits = T * N * n_quant_channels * nbits + T * N * n_prot * protect_bits

    # scale/zero-point metadata (affine asymmetric => scale + zero; symmetric => scale only; assume affine)
    if granularity == "per_tensor":
        n_groups = T
    elif granularity == "per_channel":
        n_groups = T * C
    elif granularity == "per_block":
        n_groups = T * math.ceil(N / block_size) * C
    else:
        raise ValueError(granularity)
    meta_bits = n_groups * scale_bits * 2  # scale + zero-point

    # protected-channel index metadata (which channels are protected) + gate metadata
    index_bits = n_prot * max(1, math.ceil(math.log2(max(2, C))))
    gate_bits = T * gate_meta_bytes_per_snapshot * 8

    compressed_bytes = (payload_bits + meta_bits + index_bits + gate_bits) / 8
    return {
        "baseline_bytes": round(baseline_bytes, 1),
        "compressed_bytes": round(compressed_bytes, 1),
        "net_density_x": round(baseline_bytes / (compressed_bytes + _EPS), 4),
        "payload_bytes": round(payload_bits / 8, 1),
        "scale_meta_bytes": round(meta_bits / 8, 1),
        "protect_index_bytes": round(index_bits / 8, 1),
        "gate_meta_bytes": round(gate_bits / 8, 1),
        "protected_channels": n_prot,
        "temp_buffer_note": "decode scratch (dequant buffer) not counted in stored density; Stage-B systems cost",
    }


# --------------------------------------------------------------------------- #
# Reconstruction-error GATE — deterministic, pre-registered (plan §9).
# --------------------------------------------------------------------------- #
def gate_admit(ref: torch.Tensor, hat: torch.Tensor, rule: dict) -> dict:
    """Deterministic admission decision for ONE reconstructed cache object.

    rule keys (any subset; ALL present ones must pass to admit):
      max_rel_l2, min_cosine, max_channel_rel_err
    Returns {admit, action, metrics}. The gate NEVER silently admits a violating object: on violation
    the caller must fall back (full-precision cache / recompute / shorter reuse interval)."""
    m = {
        "rel_l2": rel_l2(ref, hat),
        "cosine": cosine_sim(ref, hat),
        "max_channel_rel_err": max_channel_rel_err(ref, hat),
    }
    ok = True
    if "max_rel_l2" in rule:
        ok = ok and m["rel_l2"] <= rule["max_rel_l2"]
    if "min_cosine" in rule:
        ok = ok and m["cosine"] >= rule["min_cosine"]
    if "max_channel_rel_err" in rule:
        ok = ok and m["max_channel_rel_err"] <= rule["max_channel_rel_err"]
    action = "admit_compressed_reuse" if ok else rule.get("fallback", "recompute_or_full_precision")
    return {"admit": bool(ok), "action": action, "metrics": {k: round(v, 6) for k, v in m.items()}}


def error_accumulation(
    snapshots: torch.Tensor,
    encode,
    reuse_len: int,
) -> dict:
    """Simulate REPEATED reuse of a compressed cache: encode once, then feed the reconstruction forward
    `reuse_len` times (re-encoding each time), tracking error growth vs the original.

    `encode` is a callable x -> reconstructed x. `snapshots` is (T,N,C); uses snapshot 0 as the seed.
    Returns the error trajectory and whether error is bounded (does not blow up)."""
    x0 = snapshots[0] if snapshots.ndim == 3 else snapshots
    cur = x0.float()
    errs = []
    for _ in range(max(1, reuse_len)):
        cur = encode(cur)
        errs.append(rel_l2(x0, cur))
    first, last = errs[0], errs[-1]
    return {
        "reuse_len": reuse_len,
        "error_trajectory": [round(e, 5) for e in errs],
        "error_growth_x": round(last / (first + _EPS), 3),
        "bounded": bool(last <= 1.5 * first + 1e-3),  # heuristic: <=1.5x first-step error = bounded
    }
