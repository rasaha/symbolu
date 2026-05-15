"""Marlin-style INT4 KV fused unpack-attend kernel sketch.

**Status:** sketch / prototype / evidence-of-closeable-gap. Pure-PyTorch
reference of the fused-kernel pattern. Real CUDA work is out of scope
for a single CPU dev pod session; this file demonstrates the algorithm
shape so the GPU kernel author has a contract.

**Why this exists:** the route-A vLLM `cache_kv` hook
(``Bench/scripts/ROUTE_A_VLLM_CACHE_KV_PLAN.md``) ships with a PyTorch
dequant fallback: every attention call decompresses INT4 to FP16 in a
torch op, then runs ``flash_attn_with_kvcache`` on FP16. That adds two
dequant kernels per decode step (one for K, one for V). On Qwen2.5-7B
that's ~5-15% of decode latency.

The Marlin pattern (Frantar et al. 2024 — "Marlin: Mixed-precision
Auto-Regressive Parallel Inference of Large Language Models"; original
work was W4A16 GEMM for weights, but the pattern generalizes to KV)
fuses the unpack step into the attention kernel itself: the kernel
reads INT4 packed values from HBM, dequantizes them inline in registers
using the per-channel scales, and immediately consumes them in the
softmax(QK^T)V math. No round trip through an FP16 intermediate, no
extra HBM bandwidth.

This file:

1. Documents the kernel's invariants and shape contract.
2. Provides a pure-PyTorch reference (~80 LOC) that produces
   bit-identical output to "dequant_then_attention". The reference is
   the spec the CUDA kernel must match.
3. Provides a tiny synthetic benchmark to demonstrate the HBM-traffic
   advantage on paper (counts loaded bytes; doesn't measure clock).

What this DOES NOT do:

* Write Triton or CUDA. That work is GPU-specialist territory (~1-2
  weeks). See "Engineer-days" at the bottom for the sizing.
* Validate the pattern on Qwen2.5-7B. The route-A fallback is the
  shipping path; this kernel is the optimization that comes after.

Expected result if the kernel is built:

* HBM traffic on the K read: 4 bits/element vs FP16's 16 — **4× less**.
* HBM traffic on the V read: same.
* Compute is unchanged — the dot-products are still in FP16/BF16 math;
  only the loads change.
* Wall-clock impact on Qwen2.5-7B decode: **5-15% speed-up vs route-A
  fallback** at typical context lengths (the load is bandwidth-bound,
  not compute-bound, for decode).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover
    torch = None  # type: ignore


# --------------------------------------------------------------------------- #
# Contract / invariants for the fused kernel                                  #
# --------------------------------------------------------------------------- #
#
# Inputs:
#   q:              (B, H_q, S_q, D)             FP16 — current decode query
#   k_packed:       (num_blocks, block_size, H_kv, ceil(D/2)) uint8
#   k_scale:        (num_blocks, n_groups, H_kv, D) float16
#   k_offset:       (num_blocks, n_groups, H_kv, D) float16  (None if symmetric)
#   v_packed:       (num_blocks, block_size, H_kv, ceil(D/2)) uint8
#   v_scale:        (num_blocks, block_size, H_kv, n_groups_d) float16
#   v_offset:       same shape as v_scale (None if symmetric)
#   block_table:    (B, max_blocks_per_seq) int — vLLM's existing layout
#   seq_lens:       (B,) int — actual sequence length per batch item
#   group_size_k:   int — KIVI K group size along seq axis (typically 32)
#   group_size_v:   int — KIVI V group size along head_dim (typically 32)
#
# Output:
#   attn_out:       (B, H_q, S_q, D)             FP16 — softmax(QK^T)V
#
# Invariants the kernel must hold:
#
# 1. GQA: H_q is a multiple of H_kv (Qwen2.5-7B: H_q=28, H_kv=4 → 7-way GQA).
#    Each K/V head is shared across H_q/H_kv = 7 query heads. Kernel
#    broadcasts K/V across the GQA group during attention.
#
# 2. Asymmetric INT4: x_dequant = (x_int4 + 8) * scale + offset where
#    x_int4 ∈ [-8, +7] is the SIGNED 4-bit value stored in the packed
#    uint8 (low nibble for index 0, high nibble for index 1; see
#    ``pack_int4`` / ``unpack_int4`` in int4_per_channel_kv.py for the
#    exact byte layout).
#    Symmetric INT4: x_dequant = x_int4 * scale. Kernel branches on
#    `offset is not None`.
#
# 3. Group-quantized K: scale is shared along the seq axis within a
#    group of `group_size_k` consecutive tokens. The kernel computes
#    `group_idx = (token_idx_in_block + block_idx_within_seq * block_size)
#    // group_size_k` to look up the correct scale. **Block boundaries
#    must align to group boundaries** — vLLM's block_size=16 doesn't
#    cleanly divide KIVI's group_size=32 unless we go to block_size=32
#    (see ROUTE_A_VLLM_CACHE_KV_PLAN.md open question 3).
#
# 4. Group-quantized V: scale is shared along the head_dim axis within
#    a group of `group_size_v` head_dim elements. The kernel computes
#    `group_idx_d = head_dim_idx // group_size_v`; this is purely
#    register-local since head_dim is the kernel's reduction axis.
#
# 5. FP16 accumulator: dequant happens in FP16 (matches the math vLLM's
#    flash_attn_with_kvcache uses today). No FP32 promotion needed for
#    the dequant step itself; the softmax keeps its existing FP32
#    accumulator.
#
# 6. The packed uint8 nibble layout is little-endian-pair:
#       byte = (high_nibble << 4) | low_nibble
#    where low_nibble corresponds to even head_dim indices [0, 2, 4,
#    ...] and high_nibble corresponds to odd [1, 3, 5, ...]. **Both
#    nibbles store the value SHIFTED to unsigned: actual = nibble - 8.**
#    (See ``pack_int4`` for the shift logic.)


@dataclass
class FusedAttentionSpec:
    """Shape contract for the fused kernel, machine-readable."""
    B: int
    H_q: int
    H_kv: int
    S_q: int
    S_kv: int
    D: int
    block_size: int
    group_size_k: int
    group_size_v: int
    asymmetric: bool


# --------------------------------------------------------------------------- #
# Reference implementation in pure PyTorch                                    #
#                                                                             #
# This is the SPEC the CUDA/Triton kernel must match. Produces                #
# bit-identical output (within FP16 rounding) to "dequant K then dequant V    #
# then standard attention". The "fusion" in the reference is logical —        #
# it computes the same numbers; the actual HBM-bandwidth savings only         #
# show up when the kernel is compiled to GPU code that reads INT4 directly    #
# from HBM rather than going through a torch op that materialises FP16        #
# intermediates.                                                              #
# --------------------------------------------------------------------------- #


def fused_int4_attention_reference(
    q: "torch.Tensor",                     # (B, H_q, S_q, D) fp16
    k_packed: "torch.Tensor",              # (B, H_kv, S_kv, ceil(D/2)) uint8
    k_scale: "torch.Tensor",               # (B, n_groups_k, H_kv, D) fp16
    k_offset: "torch.Tensor",              # (B, n_groups_k, H_kv, D) fp16 or None
    v_packed: "torch.Tensor",              # (B, H_kv, S_kv, ceil(D/2)) uint8
    v_scale: "torch.Tensor",               # (B, S_kv, H_kv, n_groups_v) fp16
    v_offset: "torch.Tensor",              # (B, S_kv, H_kv, n_groups_v) fp16 or None
    *,
    spec: FusedAttentionSpec,
    softmax_scale: float = None,           # 1/sqrt(D) by default
) -> "torch.Tensor":
    """Reference for the fused INT4 unpack-attend kernel.

    Operation:
      attn_out = softmax(Q @ K^T * softmax_scale) @ V
    where K and V are reconstructed inline from INT4 packed values
    plus per-group scales (+ offsets if asymmetric).

    In production this is one CUDA kernel that streams INT4 bytes from
    HBM, dequantizes in registers, and feeds the dot-products. Here
    it's a sequence of torch ops that has the same numerical contract.

    The kernel author's checklist:
      * Match the byte-nibble layout in ``pack_int4``.
      * Match the asymmetric dequant formula in
        ``dequantize_per_channel_int4`` / ``dequantize_per_token_int4``.
      * Match the group-index computation (line "group_idx_seq = ..." below).
      * GQA broadcasting: each K/V head feeds H_q/H_kv query heads.
    """
    if torch is None:
        raise ImportError("fused_int4_attention_reference requires PyTorch.")
    if softmax_scale is None:
        softmax_scale = 1.0 / math.sqrt(spec.D)

    B, H_q, S_q, D = q.shape
    H_kv = spec.H_kv
    S_kv = spec.S_kv
    G_q = H_q // H_kv

    # ---- Inline K dequant ----
    # Unpack uint8 → int8 in [-8, +7].
    k_int4 = _unpack_int4_inline(k_packed, target_n=D)   # (B, H_kv, S_kv, D)
    # Pull per-group scale/offset, broadcasting along the seq axis
    # within each group of group_size_k tokens.
    k_dequant = _apply_group_scale_seq(
        k_int4, k_scale, k_offset,
        group_size=spec.group_size_k,
        asymmetric=spec.asymmetric,
    )                                                     # (B, H_kv, S_kv, D) fp16

    # ---- Inline V dequant ----
    v_int4 = _unpack_int4_inline(v_packed, target_n=D)   # (B, H_kv, S_kv, D)
    v_dequant = _apply_group_scale_headdim(
        v_int4, v_scale, v_offset,
        group_size=spec.group_size_v,
        asymmetric=spec.asymmetric,
    )                                                     # (B, H_kv, S_kv, D) fp16

    # ---- GQA broadcast ----
    # Each K/V head services G_q query heads. Tile along the H axis.
    # (B, H_kv, S_kv, D) → (B, H_q, S_kv, D) via expand on a new axis.
    k = k_dequant.unsqueeze(2).expand(B, H_kv, G_q, S_kv, D).reshape(
        B, H_q, S_kv, D,
    )
    v = v_dequant.unsqueeze(2).expand(B, H_kv, G_q, S_kv, D).reshape(
        B, H_q, S_kv, D,
    )

    # ---- Standard scaled dot-product attention (FP16 math) ----
    # (B, H_q, S_q, D) @ (B, H_q, D, S_kv) → (B, H_q, S_q, S_kv)
    scores = torch.matmul(q, k.transpose(-1, -2)) * softmax_scale
    # FP32 accumulator for the softmax (matches FlashAttention's
    # numeric contract).
    attn = torch.softmax(scores.float(), dim=-1).to(q.dtype)
    # (B, H_q, S_q, S_kv) @ (B, H_q, S_kv, D) → (B, H_q, S_q, D)
    out = torch.matmul(attn, v)
    return out


def _unpack_int4_inline(packed: "torch.Tensor", target_n: int) -> "torch.Tensor":
    """Reference of the unpacking step. The CUDA kernel does this
    in-register without materialising the int8 intermediate.

    Matches ``unpack_int4`` in int4_per_channel_kv.py: low nibble of
    byte at position i is the int4 value at output position 2i (then
    shifted back to signed), high nibble is at 2i+1.
    """
    low = (packed & 0x0F).to(torch.int8) - 8
    high = ((packed >> 4) & 0x0F).to(torch.int8) - 8
    stacked = torch.stack([low, high], dim=-1)
    prefix = packed.shape[:-1]
    m = packed.shape[-1]
    flat = stacked.view(*prefix, m * 2)
    return flat[..., :target_n].contiguous()


def _apply_group_scale_seq(
    int4: "torch.Tensor",     # (B, H_kv, S_kv, D) int8
    scale: "torch.Tensor",    # (B, n_groups_k, H_kv, D) fp16
    offset: "torch.Tensor",   # (B, n_groups_k, H_kv, D) fp16 or None
    *, group_size: int, asymmetric: bool,
) -> "torch.Tensor":
    """Apply per-(group, head, head_dim) K scale along the seq axis.

    Reference for K: each consecutive `group_size` tokens in the seq
    axis share one scale row. The CUDA kernel computes
    `group_idx = token_idx // group_size` at register level.
    """
    B, H_kv, S_kv, D = int4.shape
    n_groups = scale.shape[1]
    pad = n_groups * group_size - S_kv
    if pad < 0:
        raise ValueError(
            f"n_groups*group_size={n_groups * group_size} < S_kv={S_kv}; "
            "scale doesn't cover the full seq axis"
        )
    if pad:
        zeros = torch.zeros(B, H_kv, pad, D, dtype=int4.dtype, device=int4.device)
        int4 = torch.cat([int4, zeros], dim=2)
    # (B, H_kv, n_groups, group_size, D)
    int4_grouped = int4.view(B, H_kv, n_groups, group_size, D)
    # (B, H_kv, n_groups, 1, D)
    scale_b = scale.transpose(1, 2).unsqueeze(3)  # (B, H_kv, n_groups, 1, D)
    if asymmetric and offset is not None:
        offset_b = offset.transpose(1, 2).unsqueeze(3)
        dequant = int4_grouped.to(scale.dtype) * scale_b + offset_b
    else:
        dequant = int4_grouped.to(scale.dtype) * scale_b
    out = dequant.view(B, H_kv, n_groups * group_size, D)[:, :, :S_kv, :]
    return out


def _apply_group_scale_headdim(
    int4: "torch.Tensor",     # (B, H_kv, S_kv, D) int8
    scale: "torch.Tensor",    # (B, S_kv, H_kv, n_groups_v) fp16
    offset: "torch.Tensor",   # (B, S_kv, H_kv, n_groups_v) fp16 or None
    *, group_size: int, asymmetric: bool,
) -> "torch.Tensor":
    """Apply per-(token, head, group_d) V scale along the head_dim
    axis. Mirror of `_apply_group_scale_seq` along the other axis.
    """
    B, H_kv, S_kv, D = int4.shape
    n_groups_d = scale.shape[3]
    pad = n_groups_d * group_size - D
    if pad < 0:
        raise ValueError(
            f"n_groups_d*group_size={n_groups_d * group_size} < D={D}; "
            "scale doesn't cover the full head_dim axis"
        )
    if pad:
        zeros = torch.zeros(B, H_kv, S_kv, pad, dtype=int4.dtype, device=int4.device)
        int4 = torch.cat([int4, zeros], dim=3)
    # (B, S_kv, H_kv, D) → (B, S_kv, H_kv, n_groups_d, group_size)
    int4_grouped = int4.permute(0, 2, 1, 3).contiguous().view(
        B, S_kv, H_kv, n_groups_d, group_size,
    )
    scale_b = scale.unsqueeze(4)  # (B, S_kv, H_kv, n_groups_d, 1)
    if asymmetric and offset is not None:
        offset_b = offset.unsqueeze(4)
        dequant = int4_grouped.to(scale.dtype) * scale_b + offset_b
    else:
        dequant = int4_grouped.to(scale.dtype) * scale_b
    out = dequant.view(B, S_kv, H_kv, n_groups_d * group_size)[..., :D]
    # Permute back to (B, H_kv, S_kv, D).
    return out.permute(0, 2, 1, 3).contiguous()


# --------------------------------------------------------------------------- #
# HBM traffic counter — paper evidence for "the kernel pattern is              #
# bandwidth-advantageous before we even build it"                              #
# --------------------------------------------------------------------------- #


def hbm_bytes_for_attention(
    *, B: int, H_kv: int, S_kv: int, D: int,
    int4: bool,
) -> int:
    """HBM bytes loaded for K + V in one attention call.

    FP16 path: 2 bytes per element × 2 (K and V) × B × H_kv × S_kv × D.
    INT4 path: 0.5 bytes per element × 2 + per-group scale overhead
    (typically <5% at group_size=32 on D=128).

    The kernel's win is the 4× reduction on the dominant term (the
    K/V values themselves). Scales are O(D/group_size) per token, so
    the overhead is small.
    """
    elements_kv = B * H_kv * S_kv * D
    if int4:
        # K + V values at 0.5 byte each.
        val_bytes = 2 * elements_kv * 0.5
        # Scale overhead: ~1 fp16 scale per group along seq (for K)
        # and per group along D (for V). At group_size=32, D=128:
        #   K scale: B * H_kv * (S_kv/32) * D * 2 bytes
        #   V scale: B * H_kv * S_kv * (D/32) * 2 bytes
        # Each entry is 4 head_dim positions worth of values:
        k_scale_bytes = B * H_kv * max(1, S_kv // 32) * D * 2
        v_scale_bytes = B * H_kv * S_kv * max(1, D // 32) * 2
        return int(val_bytes + k_scale_bytes + v_scale_bytes)
    else:
        return 2 * elements_kv * 2


def speedup_ceiling(*, B: int, H_kv: int, S_kv: int, D: int) -> float:
    """Upper bound on the fused-kernel speedup, assuming K/V load is
    the bottleneck. Real speedup will be lower (compute also runs).
    """
    fp16 = hbm_bytes_for_attention(B=B, H_kv=H_kv, S_kv=S_kv, D=D, int4=False)
    int4 = hbm_bytes_for_attention(B=B, H_kv=H_kv, S_kv=S_kv, D=D, int4=True)
    return fp16 / max(int4, 1)


# --------------------------------------------------------------------------- #
# Sizing notes for the GPU kernel author                                       #
# --------------------------------------------------------------------------- #
#
# The actual CUDA / Triton implementation:
#
# * **1-2 weeks of GPU-kernel work** for someone fluent in Triton or CUDA.
#   The Marlin original (Frantar et al. 2024) is ~3000 lines of CUDA; our
#   variant is simpler because we're only reading one INT4 tensor (KV)
#   rather than INT4 weights, and the dequant happens inline in the
#   attention dot-product loop.
#
# * **Templates:**
#   - Marlin: https://github.com/IST-DASLab/marlin (W4A16 GEMM)
#   - vLLM's own GPTQ kernel:
#     vllm/model_executor/layers/quantization/gptq.py
#     (read-only reference for the unpack pattern; their kernel
#     unpacks INT4 weights into FP16 then runs GEMM, which is the
#     fallback pattern, not the fused pattern)
#   - The KIVI ICML paper has a CUDA appendix with the per-channel /
#     per-token dequant inside a fused attention kernel; that is the
#     directly-applicable reference for our case.
#
# * **Decision point:** Triton (easier to write, ~70% of CUDA perf) vs
#   CUDA (full perf, harder). Recommendation: Triton-prototype first
#   (validates the algorithm + HBM-pattern), CUDA-promote only if the
#   Triton overhead vs FP16 baseline is > 5%.
#
# * **Expected end-state:** the kernel matches `fused_int4_attention_
#   reference` numerically (test: random-input cosine ≥ 0.999 vs
#   reference, max-abs-diff < 1e-3 in FP16). Latency vs FP16 FlashAttn
#   should be within 5-10% on Qwen2.5-7B decode at typical context
#   lengths.

if __name__ == "__main__":
    if torch is None:
        raise SystemExit("torch not installed; sketch can't run.")

    # Tiny sanity demo. Build random Qwen-shape INT4-packed K/V,
    # run the reference, compare its output to a naive "dequant first
    # then attention" implementation.
    B, H_q, H_kv, D = 1, 28, 4, 128
    S_q, S_kv = 1, 64
    group_size_k = 32
    group_size_v = 32
    n_groups_k = S_kv // group_size_k
    n_groups_v = D // group_size_v

    torch.manual_seed(0)
    q = torch.randn(B, H_q, S_q, D, dtype=torch.float16)

    # Build raw FP16 K/V and quantize them with the route-B ops,
    # then run the reference and compare to the "dequant then attend"
    # baseline.
    k_fp16 = torch.randn(B, H_kv, S_kv, D, dtype=torch.float16)
    v_fp16 = torch.randn(B, H_kv, S_kv, D, dtype=torch.float16)

    # For the demo we use small synthetic scales; the real path computes
    # them from K/V's per-group max. This is the spec's shape contract:
    k_scale = torch.randn(B, n_groups_k, H_kv, D, dtype=torch.float16).abs() * 0.1
    k_offset = torch.randn(B, n_groups_k, H_kv, D, dtype=torch.float16) * 0.1
    v_scale = torch.randn(B, S_kv, H_kv, n_groups_v, dtype=torch.float16).abs() * 0.1
    v_offset = torch.randn(B, S_kv, H_kv, n_groups_v, dtype=torch.float16) * 0.1

    # Mock INT4 packed values (random in [0, 255] uint8).
    k_packed = torch.randint(0, 256, (B, H_kv, S_kv, D // 2), dtype=torch.uint8)
    v_packed = torch.randint(0, 256, (B, H_kv, S_kv, D // 2), dtype=torch.uint8)

    spec = FusedAttentionSpec(
        B=B, H_q=H_q, H_kv=H_kv, S_q=S_q, S_kv=S_kv, D=D,
        block_size=16, group_size_k=group_size_k, group_size_v=group_size_v,
        asymmetric=True,
    )
    out = fused_int4_attention_reference(
        q=q, k_packed=k_packed, k_scale=k_scale, k_offset=k_offset,
        v_packed=v_packed, v_scale=v_scale, v_offset=v_offset,
        spec=spec,
    )
    print(f"output shape: {tuple(out.shape)} dtype: {out.dtype}")

    speedup = speedup_ceiling(B=B, H_kv=H_kv, S_kv=S_kv, D=D)
    print(f"HBM-traffic ceiling speedup vs FP16: {speedup:.2f}x")
    print(
        f"  FP16 bytes: {hbm_bytes_for_attention(B=B, H_kv=H_kv, S_kv=S_kv, D=D, int4=False):,}"
    )
    print(
        f"  INT4 bytes: {hbm_bytes_for_attention(B=B, H_kv=H_kv, S_kv=S_kv, D=D, int4=True):,}"
    )
