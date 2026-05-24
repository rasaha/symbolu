#!/usr/bin/env python3
"""verify_phase2_6_2.py — Phase 2.6.2 correctness gate.

Same shape as verify_phase2_4_1b.py but with BOTH K AND V packed.

  - Reference path:   flash_attn_with_int4_kvcache(q, k, v, protect_mask=...)
                      — Phase 5A in-register K quant + Phase 3 in-register
                      V quant, no packed args.
  - Packed path:      flash_attn_with_int4_kvcache(q, k, v,
                      k_packed_int4=..., k_packed_scale=...,
                      k_packed_xmin=..., k_packed_protect_bf16=...,
                      k_packed_protect_slot=...,
                      v_packed_int4=..., v_packed_scale=..., v_packed_xmin=...,
                      v_packed_group_size=32,
                      packed_group_size=32, packed_n_protect=...,
                      protect_mask=mask, n_protect=...)

Both K and V come through packed HBM storage on the packed path.
Reference dequantizes in-register from BF16.

Gate: cosine(ref_out, packed_out) >= 0.9995.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))

DEVICE = "cuda"
DTYPE  = "torch.bfloat16"

B            = 1
S            = 16384
H_Q          = 28
H_KV         = 4
D            = 128
GROUP_SIZE_K = 32
GROUP_SIZE_V = 32
PROTECT_FRACTION = 0.04
N_PROTECT    = 5

COSINE_GATE = 0.9995


def cosine(a, b) -> float:
    import torch
    af = a.float().flatten()
    bf = b.float().flatten()
    return float(torch.nn.functional.cosine_similarity(af.unsqueeze(0), bf.unsqueeze(0)).item())


def build_protect_mask(k):
    import torch
    ch_mag = k.float().abs().amax(dim=1)
    _, topk_idx = ch_mag.topk(N_PROTECT, dim=-1)
    mask = torch.zeros((B, H_KV, D), dtype=torch.int8, device=k.device)
    mask.scatter_(-1, topk_idx, 1)
    return mask


def main() -> int:
    import torch
    if not torch.cuda.is_available():
        print("FAIL: needs CUDA")
        return 1

    try:
        from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache
    except ImportError as e:
        print(f"FAIL: {e}")
        return 1

    from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4
    from kv_policy.phase2_6_packed_v import pack_v_for_phase2_6

    print("=" * 70)
    print("Phase 2.6.2 — packed K+V vs Phase 5A in-register reference")
    print("=" * 70)
    print(f"  shapes: B={B}, S={S}, H_q={H_Q}, H_kv={H_KV}, D={D}")
    print(f"  group_size_k={GROUP_SIZE_K}, group_size_v={GROUP_SIZE_V},"
          f" protect_fraction={PROTECT_FRACTION}, n_protect={N_PROTECT}")
    print(f"  cosine gate: >= {COSINE_GATE}")

    torch.manual_seed(42)
    k = torch.randn(B, S, H_KV, D, device=DEVICE, dtype=torch.bfloat16)
    v = torch.randn(B, S, H_KV, D, device=DEVICE, dtype=torch.bfloat16)
    q = torch.randn(B, 1, H_Q, D, device=DEVICE, dtype=torch.bfloat16)

    protect_mask = build_protect_mask(k)
    cache_seqlens = torch.tensor([S], dtype=torch.int32, device=DEVICE)

    print()
    print("[1/2] Reference path (Phase 5A in-register K + Phase 3 in-register V)")
    ref_out = flash_attn_with_int4_kvcache(
        q, k, v,
        cache_seqlens=cache_seqlens,
        protect_mask=protect_mask,
        n_protect=N_PROTECT,
        causal=False,
    )
    print(f"  ref_out shape={tuple(ref_out.shape)} dtype={ref_out.dtype}")

    print()
    print("[2/2] Packed path (Phase 2.4.1b K + Phase 2.6.2 V)")
    k_packed = pack_k_for_phase2_4(
        k, group_size=GROUP_SIZE_K, protect_fraction=PROTECT_FRACTION,
    )
    v_packed = pack_v_for_phase2_6(v, v_group_size=GROUP_SIZE_V)

    packed_out = flash_attn_with_int4_kvcache(
        q, k, v,
        cache_seqlens=cache_seqlens,
        protect_mask=protect_mask,
        n_protect=N_PROTECT,
        causal=False,
        # Phase 2.4.1b packed-K kwargs:
        k_packed_int4=k_packed["k_int4"].contiguous(),
        k_packed_scale=k_packed["k_scale"].contiguous(),
        k_packed_xmin=k_packed["k_xmin"].contiguous(),
        k_packed_protect_bf16=k_packed["k_protect_bf16"].contiguous(),
        k_packed_protect_slot=k_packed["protect_slot"].contiguous(),
        packed_group_size=GROUP_SIZE_K,
        packed_n_protect=k_packed["n_protect"],
        # Phase 2.6.2 packed-V kwargs:
        v_packed_int4=v_packed["v_int4"].contiguous(),
        v_packed_scale=v_packed["v_scale"].contiguous(),
        v_packed_xmin=v_packed["v_xmin"].contiguous(),
        v_packed_group_size=GROUP_SIZE_V,
    )
    print(f"  packed_out shape={tuple(packed_out.shape)} dtype={packed_out.dtype}")

    cos = cosine(ref_out, packed_out)
    diff = (ref_out.float() - packed_out.float()).abs()
    max_abs = float(diff.max().item())
    mean_abs = float(diff.mean().item())

    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  cosine(ref, packed) = {cos:.7f}  (gate {COSINE_GATE})")
    print(f"  max-abs diff        = {max_abs:.6e}")
    print(f"  mean-abs diff       = {mean_abs:.6e}")
    print()

    if cos >= COSINE_GATE:
        print(f"Phase 2.6.2: GREEN (cosine {cos:.6f} >= {COSINE_GATE})")
        return 0

    print(f"Phase 2.6.2: FAIL (cosine {cos:.6f} < {COSINE_GATE})")
    if cos >= 0.999:
        print("  cosine in [0.999, 0.9995) — likely BF16 scale precision on V.")
        print("  Consider FP32 V scale fallback (mirror K's Q3).")
    elif cos >= 0.99:
        print("  cosine in [0.99, 0.999) — significant V drift.")
        print("  Suspect pointer arithmetic or nibble extraction bug in V path.")
    else:
        print("  cosine < 0.99 — gross mismatch. Suspect template gate, K-V "
              "interaction, or wrong V layout.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
