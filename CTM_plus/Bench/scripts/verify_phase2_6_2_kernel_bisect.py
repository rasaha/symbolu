"""Phase 2.6.2 kernel bisection.

verify_phase2_6_2 PASSES at S=16384 with data-derived per-head topk
protect_mask. The 5B.4c.3 V-isolation T5 FAILED at S=128 with
uniform-per-head protect_mask (first 5 channels for every head).
Both use pack_k_for_phase2_4 + pack_v_for_phase2_6 — bit-equal packers.

This bisects: which fixture detail flips the kernel from
working->zero output?

Bisection matrix (4 cells):
  A. S=16384, mask=data-derived  -> known-good (verify_phase2_6_2)
  B. S=16384, mask=uniform        -> ?
  C. S=128,   mask=data-derived  -> ?
  D. S=128,   mask=uniform        -> known-broken (5B.4c.3 T5)

If B passes and C fails: small S triggers the bug.
If B fails and C passes: uniform mask triggers it.
If both B and C fail: BOTH are needed.
If both pass: something else in 5B.4c.3 T5 caused the zero (regression).

Also exercises num_splits=0 (auto) vs num_splits=1 (force single split)
for the small-S cases — splitkv heuristics may be the culprit.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))

import torch
from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4
from kv_policy.phase2_6_packed_v import pack_v_for_phase2_6
from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache

DEVICE = "cuda"
DTYPE  = torch.bfloat16

B, H_Q, H_KV, D = 1, 28, 4, 128
GROUP_SIZE_K = 32
GROUP_SIZE_V = 32
N_PROTECT    = 5


def cosine(a, b) -> float:
    af, bf = a.float().flatten(), b.float().flatten()
    return float(torch.nn.functional.cosine_similarity(
        af.unsqueeze(0), bf.unsqueeze(0)).item())


def build_data_mask(k):
    """Top-N_PROTECT by per-head max-abs magnitude. Different channels per head."""
    ch_mag = k.float().abs().amax(dim=1)              # (B, H_kv, D)
    _, topk_idx = ch_mag.topk(N_PROTECT, dim=-1)
    mask = torch.zeros((B, H_KV, D), dtype=torch.int8, device=k.device)
    mask.scatter_(-1, topk_idx, 1)
    return mask


def build_uniform_mask():
    """First N_PROTECT channels protected for every head."""
    mask = torch.zeros((B, H_KV, D), dtype=torch.int8, device=DEVICE)
    mask[:, :, :N_PROTECT] = 1
    return mask


def run_cell(name, S, mask, num_splits=0, backing="real"):
    """Run one (S, mask, backing) cell.
    backing in {"real", "zero", "random"} controls the K/V positional args
    of the packed kernel call. The ref call always uses real K/V.
    """
    torch.manual_seed(42)
    k = torch.randn(B, S, H_KV, D, device=DEVICE, dtype=DTYPE)
    v = torch.randn(B, S, H_KV, D, device=DEVICE, dtype=DTYPE)
    q = torch.randn(B, 1, H_Q, D, device=DEVICE, dtype=DTYPE)
    cache_seqlens = torch.tensor([S], dtype=torch.int32, device=DEVICE)

    if callable(mask):
        protect_mask = mask(k)
    else:
        protect_mask = mask
    mask_for_pack = protect_mask[0].to(torch.int8)

    ref = flash_attn_with_int4_kvcache(
        q, k, v, cache_seqlens=cache_seqlens,
        protect_mask=protect_mask, n_protect=N_PROTECT,
        causal=False,
    )

    k_packed = pack_k_for_phase2_4(
        k, group_size=GROUP_SIZE_K,
        protect_fraction=N_PROTECT / D,
        frozen_protect_mask=mask_for_pack,
    )
    v_packed = pack_v_for_phase2_6(v, v_group_size=GROUP_SIZE_V)

    if backing == "real":
        k_arg, v_arg = k, v
    elif backing == "zero":
        k_arg = torch.zeros_like(k)
        v_arg = torch.zeros_like(v)
    elif backing == "random":
        torch.manual_seed(999)
        k_arg = torch.randn_like(k)
        v_arg = torch.randn_like(v)
    else:
        raise ValueError(backing)

    packed = flash_attn_with_int4_kvcache(
        q, k_arg, v_arg, cache_seqlens=cache_seqlens,
        protect_mask=protect_mask, n_protect=N_PROTECT,
        causal=False,
        k_packed_int4=k_packed["k_int4"].contiguous(),
        k_packed_scale=k_packed["k_scale"].contiguous(),
        k_packed_xmin=k_packed["k_xmin"].contiguous(),
        k_packed_protect_bf16=k_packed["k_protect_bf16"].contiguous(),
        k_packed_protect_slot=k_packed["protect_slot"].contiguous(),
        packed_group_size=GROUP_SIZE_K,
        packed_n_protect=k_packed["n_protect"],
        v_packed_int4=v_packed["v_int4"].contiguous(),
        v_packed_scale=v_packed["v_scale"].contiguous(),
        v_packed_xmin=v_packed["v_xmin"].contiguous(),
        v_packed_group_size=GROUP_SIZE_V,
        num_splits=num_splits,
    )

    cos = cosine(ref, packed)
    ref_sum = ref.float().abs().sum().item()
    pk_sum  = packed.float().abs().sum().item()
    print(f"  {name}: cosine={cos:.7f}  ref_sum={ref_sum:.4e}  packed_sum={pk_sum:.4e}")
    return cos


def main() -> int:
    if not torch.cuda.is_available():
        print("FAIL: needs CUDA"); return 1

    print("======================================================")
    print("Phase 2.6.2 kernel bisection")
    print("======================================================")
    print(f"  B={B}  H_Q={H_Q}  H_KV={H_KV}  D={D}  N_PROTECT={N_PROTECT}")
    print(f"  GROUP_SIZE_K={GROUP_SIZE_K}  GROUP_SIZE_V={GROUP_SIZE_V}")

    print()
    print("Cell A: S=16384, mask=data-derived (known-good baseline):")
    cos_A = run_cell("A", 16384, build_data_mask)

    print()
    print("Cell B: S=16384, mask=uniform-first-N:")
    cos_B = run_cell("B", 16384, build_uniform_mask())

    print()
    print("Cell C: S=128, mask=data-derived:")
    cos_C = run_cell("C", 128, build_data_mask)

    print()
    print("Cell D: S=128, mask=uniform-first-N (known-broken from 5B.4c.3 T5):")
    cos_D = run_cell("D", 128, build_uniform_mask())

    print()
    print("Cell C': S=128, mask=data-derived, num_splits=1:")
    cos_Cp = run_cell("C'", 128, build_data_mask, num_splits=1)

    print()
    print("Cell D': S=128, mask=uniform, num_splits=1:")
    cos_Dp = run_cell("D'", 128, build_uniform_mask(), num_splits=1)

    # ---- Backing-content sensitivity ----
    print()
    print("--- BACKING-CONTENT sensitivity at small S ---")
    print()
    print("Cell E_real: S=128, uniform mask, REAL bf16 backing:")
    cos_Er = run_cell("E_real",   128, build_uniform_mask(), backing="real")
    print("Cell E_zero: S=128, uniform mask, ZERO bf16 backing:")
    cos_Ez = run_cell("E_zero",   128, build_uniform_mask(), backing="zero")
    print("Cell E_rand: S=128, uniform mask, RANDOM bf16 backing:")
    cos_Erd = run_cell("E_rand",  128, build_uniform_mask(), backing="random")
    print()
    print("Cell F_real: S=512, uniform mask, REAL bf16 backing:")
    cos_Fr = run_cell("F_real",   512, build_uniform_mask(), backing="real")
    print("Cell F_zero: S=512, uniform mask, ZERO bf16 backing:")
    cos_Fz = run_cell("F_zero",   512, build_uniform_mask(), backing="zero")

    print()
    print("======================================================")
    print("Bisection summary")
    print("======================================================")
    rows = [
        ("A     (S=16384, data-derived mask, num_splits=auto, real)",  cos_A),
        ("B     (S=16384, uniform mask,      num_splits=auto, real)",  cos_B),
        ("C     (S=128,   data-derived mask, num_splits=auto, real)",  cos_C),
        ("D     (S=128,   uniform mask,      num_splits=auto, real)",  cos_D),
        ("C'    (S=128,   data-derived mask, num_splits=1,    real)",  cos_Cp),
        ("D'    (S=128,   uniform mask,      num_splits=1,    real)",  cos_Dp),
        ("E_real (S=128,  uniform mask,      backing=real)            ", cos_Er),
        ("E_zero (S=128,  uniform mask,      backing=zero)            ", cos_Ez),
        ("E_rand (S=128,  uniform mask,      backing=random)          ", cos_Erd),
        ("F_real (S=512,  uniform mask,      backing=real)            ", cos_Fr),
        ("F_zero (S=512,  uniform mask,      backing=zero)            ", cos_Fz),
    ]
    for label, c in rows:
        verdict = "PASS" if c >= 0.995 else "FAIL"
        print(f"  {label}: cosine={c:.7f}  [{verdict}]")

    print()
    if cos_Ez < 0.995 and cos_Er >= 0.995:
        print("  >>> CONFIRMED: at small S=128, packed kernel reads bf16 backing.")
        print("      With REAL backing: PASS. With ZERO backing: FAIL.")
        if cos_Fz >= 0.995:
            print("      At S=512 the kernel does NOT depend on backing.")
            print("      => Bug specifically at small S: packed helper doesn't fully")
            print("         override smem before consumption. The fix path is either")
            print("         (a) keep parallel bf16 K/V cache for the impl, or")
            print("         (b) patch the kernel's K/V load site to skip the cp.async")
            print("             when Is_int4kv_packed=true.")
    elif cos_Ez >= 0.995:
        print("  Backing-content independence holds at small S too. The original")
        print("  5B.4c.3 T5 failure must be due to some other fixture quirk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
