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


def run_cell(name, S, mask, num_splits=0):
    """Run one (S, mask) cell. Returns (cosine, output_sum_abs, ref_sum_abs)."""
    torch.manual_seed(42)
    k = torch.randn(B, S, H_KV, D, device=DEVICE, dtype=DTYPE)
    v = torch.randn(B, S, H_KV, D, device=DEVICE, dtype=DTYPE)
    q = torch.randn(B, 1, H_Q, D, device=DEVICE, dtype=DTYPE)
    cache_seqlens = torch.tensor([S], dtype=torch.int32, device=DEVICE)

    # If mask is callable, build from k. Else use as-is.
    if callable(mask):
        protect_mask = mask(k)
    else:
        protect_mask = mask
    mask_for_pack = protect_mask[0].to(torch.int8)    # (H, D)

    # Reference (Phase 5A): bf16 K + V + in-register quant via protect_mask.
    ref = flash_attn_with_int4_kvcache(
        q, k, v, cache_seqlens=cache_seqlens,
        protect_mask=protect_mask, n_protect=N_PROTECT,
        causal=False,
    )

    # Packed: pack K + V, call kernel.
    k_packed = pack_k_for_phase2_4(
        k, group_size=GROUP_SIZE_K,
        protect_fraction=N_PROTECT / D,
        frozen_protect_mask=mask_for_pack,
    )
    v_packed = pack_v_for_phase2_6(v, v_group_size=GROUP_SIZE_V)

    packed = flash_attn_with_int4_kvcache(
        q, k, v, cache_seqlens=cache_seqlens,
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

    print()
    print("======================================================")
    print("Bisection summary")
    print("======================================================")
    rows = [
        ("A   (S=16384, data-derived mask, num_splits=auto)", cos_A),
        ("B   (S=16384, uniform mask,      num_splits=auto)", cos_B),
        ("C   (S=128,   data-derived mask, num_splits=auto)", cos_C),
        ("D   (S=128,   uniform mask,      num_splits=auto)", cos_D),
        ("C'  (S=128,   data-derived mask, num_splits=1   )", cos_Cp),
        ("D'  (S=128,   uniform mask,      num_splits=1   )", cos_Dp),
    ]
    for label, c in rows:
        verdict = "PASS" if c >= 0.995 else "FAIL"
        print(f"  {label}: cosine={c:.7f}  [{verdict}]")

    print()
    if cos_B < 0.995:
        print("  Verdict: uniform mask FAILS at large S too — protect_mask path bug.")
    elif cos_C < 0.995:
        print("  Verdict: small S FAILS at data-derived mask too — small-S kernel bug.")
    elif cos_D < 0.995:
        print("  Verdict: BOTH small S and uniform mask are needed to trigger.")
    else:
        print("  Verdict: nothing broken — original 5B.4c.3 T5 was a different bug.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
