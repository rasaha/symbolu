#!/usr/bin/env python3
"""verify_phase2_4_1b.py — Phase 2.4.1b correctness gate.

Compares the packed-K HBM read path against the Phase 5A BF16-backed
reference on Qwen2.5-7B shapes. Both paths consume the SAME logical K
(same protect mask, same algorithm); the only difference is HOW the
bits are stored and read.

Test:
  1. Generate synthetic K (BF16) at Qwen2.5-7B shapes: B=1, S=16k,
     H_kv=4, D=128. Plus synthetic V (BF16), Q (BF16, H_q=28).
  2. Compute protect_mask via top-fraction (same selection rule as
     Phase 5A + Phase 4 verify).
  3. Reference path: flash_attn_with_int4_kvcache(q, k, v, ...,
     protect_mask=mask, n_protect=...).  -> ref_out
  4. Pack K via Phase 2.4.0 pack_k_for_phase2_4 -> dict of sidecar
     tensors.
  5. Packed path: flash_attn_with_int4_kvcache(q, k, v, ...,
     k_packed_int4=..., k_packed_scale=..., k_packed_xmin=...,
     k_packed_protect_bf16=..., k_packed_protect_slot=...,
     packed_group_size=32, packed_n_protect=n_protect,
     protect_mask=mask, n_protect=n_protect).  -> packed_out
  6. Gate: cosine(ref_out.flatten(), packed_out.flatten()) >= 0.9995.

If cosine misses 0.9995:
  - 0.9990 <= cos < 0.9995: likely BF16 scale precision. Flip to FP32
    scale in phase2_4_packed_kv.py (cast scales/xmins to float32) and
    in int4_packed_load.h (read as float), rebuild.
  - cos < 0.9990: real bug. Diagnose via per-element compare of
    unpack_k_from_phase2_4(packed) vs the kernel output.

Exits 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))

try:
    import torch
except ImportError:
    print("FAIL: torch not installed")
    sys.exit(1)

from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
if DEVICE != "cuda":
    print("FAIL: needs CUDA")
    sys.exit(1)

DTYPE = torch.bfloat16

# Qwen2.5-7B shapes.
B            = 1
S            = 16384       # seqlen of the K/V cache. Multiple of group_size=32.
H_Q          = 28          # query heads
H_KV         = 4           # GQA grouped kv heads
D            = 128
GROUP_SIZE_K = 32
PROTECT_FRACTION = 0.04    # default per Phase 6.4 GREEN
N_PROTECT    = max(1, int(round(D * PROTECT_FRACTION)))   # = 5

COSINE_GATE = 0.9995


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    af = a.float().flatten()
    bf = b.float().flatten()
    return float(torch.nn.functional.cosine_similarity(af.unsqueeze(0), bf.unsqueeze(0)).item())


def build_protect_mask(k: torch.Tensor) -> torch.Tensor:
    """Top-N_PROTECT channels per (b, h_kv) by max-abs across seq.
    Returns (B, H_kv, D) int8: 1=protected, 0=quantize.
    """
    ch_mag = k.float().abs().amax(dim=1)  # (B, H_kv, D)
    _, topk_idx = ch_mag.topk(N_PROTECT, dim=-1)
    mask = torch.zeros((B, H_KV, D), dtype=torch.int8, device=k.device)
    mask.scatter_(-1, topk_idx, 1)
    return mask


def main() -> int:
    print("=" * 70)
    print("Phase 2.4.1b verify — packed-K kernel vs Phase 5A reference")
    print("=" * 70)
    print(f"  shapes: B={B}, S={S}, H_q={H_Q}, H_kv={H_KV}, D={D}")
    print(f"  group_size_k={GROUP_SIZE_K}, protect_fraction={PROTECT_FRACTION},"
          f" n_protect={N_PROTECT}")
    print(f"  cosine gate: >= {COSINE_GATE}")
    print()

    try:
        from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache
    except ImportError as e:
        print(f"FAIL: can't import flash_attn_with_int4_kvcache: {e}")
        return 1

    torch.manual_seed(42)
    k = torch.randn(B, S, H_KV, D, device=DEVICE, dtype=DTYPE)
    v = torch.randn(B, S, H_KV, D, device=DEVICE, dtype=DTYPE)
    # Single decode step: q has S_q=1.
    q = torch.randn(B, 1, H_Q, D, device=DEVICE, dtype=DTYPE)

    protect_mask = build_protect_mask(k)
    cache_seqlens = torch.tensor([S], dtype=torch.int32, device=DEVICE)

    # ----- Reference: Phase 5A path (BF16 K + in-register quant +
    # protect-K mask). -----
    print("[1/2] Reference path (Phase 5A in-register quant)")
    ref_out = flash_attn_with_int4_kvcache(
        q, k, v,
        cache_seqlens=cache_seqlens,
        protect_mask=protect_mask,
        n_protect=N_PROTECT,
        causal=False,
    )
    print(f"  ref_out: shape={tuple(ref_out.shape)}, dtype={ref_out.dtype}")

    # ----- Packed path: pack K via Phase 2.4.0, pass packed args. -----
    print()
    print("[2/2] Packed path (Phase 2.4.1b kernel HBM read)")
    packed = pack_k_for_phase2_4(
        k, group_size=GROUP_SIZE_K, protect_fraction=PROTECT_FRACTION,
    )
    # Sanity-check shapes match what the kernel expects.
    assert packed["k_int4"].shape          == (B, S, H_KV, D // 2),         packed["k_int4"].shape
    assert packed["k_scale"].shape         == (B, S // GROUP_SIZE_K, H_KV, D), packed["k_scale"].shape
    assert packed["k_xmin"].shape          == (B, S // GROUP_SIZE_K, H_KV, D), packed["k_xmin"].shape
    assert packed["k_protect_bf16"].shape  == (B, S, H_KV, N_PROTECT),       packed["k_protect_bf16"].shape
    assert packed["protect_slot"].shape    == (H_KV, D),                     packed["protect_slot"].shape
    print(f"  packed tensors: k_int4 {tuple(packed['k_int4'].shape)} {packed['k_int4'].dtype}, "
          f"k_scale {tuple(packed['k_scale'].shape)} {packed['k_scale'].dtype}, ...")
    print(f"  n_protect={packed['n_protect']}, group_size={packed['group_size']}")

    # Make all packed tensors contiguous (kernel reads with vector loads).
    k_int4         = packed["k_int4"].contiguous()
    k_scale        = packed["k_scale"].contiguous()
    k_xmin         = packed["k_xmin"].contiguous()
    k_protect_bf16 = packed["k_protect_bf16"].contiguous()
    k_protect_slot = packed["protect_slot"].contiguous()

    packed_out = flash_attn_with_int4_kvcache(
        q, k, v,
        cache_seqlens=cache_seqlens,
        protect_mask=protect_mask,
        n_protect=N_PROTECT,
        causal=False,
        # Phase 2.4.1b packed kwargs (set by 2.4.1a plumbing):
        k_packed_int4=k_int4,
        k_packed_scale=k_scale,
        k_packed_xmin=k_xmin,
        k_packed_protect_bf16=k_protect_bf16,
        k_packed_protect_slot=k_protect_slot,
        packed_group_size=GROUP_SIZE_K,
        packed_n_protect=packed["n_protect"],
    )
    print(f"  packed_out: shape={tuple(packed_out.shape)}, dtype={packed_out.dtype}")

    # ----- Compare -----
    cos = cosine(ref_out, packed_out)
    diff = (ref_out.float() - packed_out.float()).abs()
    max_abs = float(diff.max().item())
    mean_abs = float(diff.mean().item())
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  cosine(ref, packed)     = {cos:.7f}    (gate {COSINE_GATE})")
    print(f"  max-abs diff            = {max_abs:.6e}")
    print(f"  mean-abs diff           = {mean_abs:.6e}")
    print()

    if cos >= COSINE_GATE:
        print(f"Phase 2.4.1b: GREEN (cosine {cos:.6f} >= {COSINE_GATE})")
        return 0

    print(f"Phase 2.4.1b: FAIL (cosine {cos:.6f} < {COSINE_GATE})")
    if cos >= 0.999:
        print("  cosine in [0.999, 0.9995) — likely BF16 scale precision.")
        print("  Consider FP32 scale fallback (see DESIGN_QUESTIONS Q3).")
    elif cos >= 0.99:
        print("  cosine in [0.99, 0.999) — significant drift, not just BF16 LSB.")
        print("  Suspect pointer arithmetic or nibble extraction bug.")
    else:
        print("  cosine < 0.99 — gross mismatch. Suspect template-gate "
              "leakage or wrong dispatch routing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
