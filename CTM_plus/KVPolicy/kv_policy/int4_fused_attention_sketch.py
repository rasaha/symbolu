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
# 2. Asymmetric INT4: x_dequant = x_int4 * scale + offset where
#    x_int4 ∈ [-8, +7] is the SIGNED 4-bit value AFTER the unpack
#    step has subtracted the unsigned-shift (see Invariant 6 for the
#    byte layout). The pack/unpack codepath does the +8 / -8 shifts
#    internally; by the time the kernel reads `x_int4`, it is already
#    in the signed range. The `offset` field absorbs the +8*scale
#    bias term:
#      offset = x_min + 8 * scale
#    so that
#      x_int4 * scale + offset = (q_unsigned - 8) * scale + x_min + 8*scale
#                              = q_unsigned * scale + x_min
#                              ≈ original input.
#    Must match ``dequantize_per_channel_int4`` /
#    ``dequantize_per_token_int4`` in ``int4_per_channel_kv.py``.
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
#
# 7. Protected-K (§20.4.2 / §20.4.3 ship config). A small STATIC set of
#    K channels (~4%, fixed per (layer, head) by offline calibration)
#    is stored as FP16 and bypasses the INT4 dequant entirely. The
#    kernel reads those channels from a compact FP16 side-tensor and
#    every other channel from INT4. Numerically:
#       k_effective = where(protect_mask, k_fp16, dequant(k_int4))
#    matching ``_restore_outlier_channels`` in
#    ``int4_per_channel_hf_cache.py`` — the route-B protected-K path
#    that §20.4.2-4 measured at 100% needle. The mask is STATIC: it is
#    NEVER recomputed at runtime (§20.4.3 validated a frozen set). V is
#    uniform INT4 — only K is protected.
#    ``fused_int4_attention_reference`` models this via the optional
#    ``k_fp16`` / ``k_protect_mask`` arguments.


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
    k_fp16: "torch.Tensor" = None,         # (B, H_kv, S_kv, D) fp16 — protected-K
    k_protect_mask: "torch.Tensor" = None, # (H_kv, D) bool — protected-K
) -> "torch.Tensor":
    """Reference for the fused INT4 unpack-attend kernel.

    Operation:
      attn_out = softmax(Q @ K^T * softmax_scale) @ V
    where K and V are reconstructed inline from INT4 packed values
    plus per-group scales (+ offsets if asymmetric).

    Protected-K (§20.4.2): when ``k_fp16`` and ``k_protect_mask`` are
    both given, the K channels selected by the mask take their FP16
    originals instead of the INT4 dequant — ``k_effective =
    where(mask, k_fp16, dequant(k_int4))``. This mirrors
    ``_restore_outlier_channels`` in ``int4_per_channel_hf_cache.py``,
    the route-B protected-K path the kernel must match numerically.
    In the real kernel the protected channels are a compact static
    FP16 side-tensor; passing the full ``k_fp16`` + mask here is the
    equivalent numerical contract. V is never protected.

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

    # ---- Protected-K overlay (§20.4.2) ----
    # The channels in k_protect_mask keep their FP16 originals; every
    # other channel stays INT4-dequantized. In the kernel the protected
    # channels are a compact static FP16 side-tensor read directly from
    # HBM; here the full k_fp16 + mask is the equivalent numerical
    # contract. Mirrors _restore_outlier_channels (route-B).
    if k_protect_mask is not None and k_fp16 is not None:
        k_dequant = torch.where(
            k_protect_mask.to(torch.bool)[None, :, None, :],
            k_fp16.to(k_dequant.dtype),
            k_dequant,
        )

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
    group_size_k: int = 32,
    group_size_v: int = 32,
    asymmetric: bool = True,
    k_protect_fraction: float = 0.0,
) -> int:
    """HBM bytes loaded for K + V in one attention call.

    FP16 path: 2 bytes per element × 2 (K and V) × B × H_kv × S_kv × D.
    INT4 path: 0.5 bytes per element × 2 + per-group scale + per-group
    offset (when asymmetric=True; the §18.3 ship config). Scale-storage
    overhead at group_size=32 on D=128 is small (~5-10% of the INT4
    value bytes); the per-group offset doubles it.

    ``k_protect_fraction`` > 0 models the §20.4.2 outlier-protected-K
    config — the winning long-context config. A fraction ``f`` of K
    channels stay FP16 (2 bytes/elem, no scale); the rest (1−f) are
    INT4 + scale. V is uniform INT4. The protected-channel index set is
    a per-layer mask (H_kv·D bits), amortised to ~0 bytes/token —
    omitted. This answers the Exp-6 go/no-go question: does the mixed
    FP16+INT4 K layout still leave enough bandwidth headroom for a
    fused kernel to be worth building.

    The kernel's win is the ~4× reduction on the dominant term (the
    K/V values themselves). Defaults match the §18.3 ship config so
    the partner-shareable ceiling speedup is computed honestly.
    """
    elements_kv = B * H_kv * S_kv * D
    if not int4:
        return 2 * elements_kv * 2  # K + V, FP16, 2 bytes/elem
    # Metadata factor: scale alone (sym) or scale+offset (asym).
    meta_factor = 2 if asymmetric else 1
    f = max(0.0, min(1.0, k_protect_fraction))
    # V — uniform INT4 (per-token, group along head_dim).
    v_val_bytes = elements_kv * 0.5
    v_scale_bytes = (
        B * H_kv * S_kv * max(1, D // group_size_v) * 2 * meta_factor
    )
    # K — outlier-protected: fraction f of channels FP16, rest INT4.
    # Only the INT4 channels carry per-group scales.
    k_int4_val_bytes = (1.0 - f) * elements_kv * 0.5
    k_fp16_val_bytes = f * elements_kv * 2
    k_scale_bytes = (
        (1.0 - f)
        * B * H_kv * max(1, S_kv // group_size_k) * D * 2 * meta_factor
    )
    return int(
        v_val_bytes + v_scale_bytes
        + k_int4_val_bytes + k_fp16_val_bytes + k_scale_bytes
    )


def speedup_ceiling(
    *, B: int, H_kv: int, S_kv: int, D: int,
    group_size_k: int = 32,
    group_size_v: int = 32,
    asymmetric: bool = True,
    k_protect_fraction: float = 0.0,
) -> float:
    """Upper bound on the fused-kernel speedup, assuming K/V load is
    the bottleneck. Real speedup will be lower (compute also runs).

    Defaults match the §18.3 ship config (group=32, asymmetric=True);
    pass `asymmetric=False` for the symmetric-only ceiling, or
    `k_protect_fraction` > 0 for the §20.4.2 outlier-protected-K
    ceiling (the winning long-context config).
    """
    fp16 = hbm_bytes_for_attention(B=B, H_kv=H_kv, S_kv=S_kv, D=D, int4=False)
    int4 = hbm_bytes_for_attention(
        B=B, H_kv=H_kv, S_kv=S_kv, D=D, int4=True,
        group_size_k=group_size_k, group_size_v=group_size_v,
        asymmetric=asymmetric, k_protect_fraction=k_protect_fraction,
    )
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

def _round_trip_demo() -> dict:
    """End-to-end round-trip: take real Qwen-shape K/V, quantize through
    the route-B ops, then run the fused reference and compare to a
    naive "dequant K, dequant V, attention" baseline.

    This is the spec's correctness check — the fused reference must
    produce numerically equivalent output to the naive pipeline (within
    FP16 rounding). A kernel author who wrote the docstring's wrong
    formula (the audit's H1 finding pre-fix) would fail this comparison.
    """
    if torch is None:
        raise ImportError("torch not installed; demo can't run.")
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
        quantize_per_token_int4, dequantize_per_token_int4,
        pack_int4,
    )

    B, H_q, H_kv, D = 1, 28, 4, 128
    S_q, S_kv = 1, 64
    group_size_k = 32
    group_size_v = 32

    torch.manual_seed(0)
    q = torch.randn(B, H_q, S_q, D, dtype=torch.float16)
    k_fp16 = torch.randn(B, H_kv, S_kv, D, dtype=torch.float16)
    v_fp16 = torch.randn(B, H_kv, S_kv, D, dtype=torch.float16)

    # Quantize through the actual route-B ops (single-batch). These
    # produce the scales/offsets the kernel must consume.
    # K: per-channel along seq with group=32 + asymmetric.
    k_int4, k_scale, k_offset = quantize_per_channel_int4(
        k_fp16[0].transpose(0, 1).contiguous(),  # (S, H_kv, D)
        group_size=group_size_k, asymmetric=True,
    )
    # V: per-token along head_dim with group=32 + asymmetric.
    v_int4, v_scale, v_offset = quantize_per_token_int4(
        v_fp16[0].transpose(0, 1).contiguous(),  # (S, H_kv, D)
        group_size=group_size_v, asymmetric=True,
    )

    # Pack INT4 along head_dim (matches route-B's storage layout).
    k_packed_sd_kv = pack_int4(k_int4)  # (S, H_kv, D/2) uint8
    v_packed_sd_kv = pack_int4(v_int4)
    # Reshape to the spec's expected layout (B, H_kv, S, D/2).
    k_packed = k_packed_sd_kv.transpose(0, 1).contiguous().unsqueeze(0)
    v_packed = v_packed_sd_kv.transpose(0, 1).contiguous().unsqueeze(0)

    # Reshape scales/offsets to the spec's expected layout.
    # K: quantize returned (n_groups, H, D); spec wants (B, n_groups, H, D).
    k_scale = k_scale.unsqueeze(0).to(torch.float16)
    k_offset = k_offset.unsqueeze(0).to(torch.float16)
    # V: quantize returned (S, H, n_groups); spec wants (B, S, H, n_groups).
    v_scale = v_scale.unsqueeze(0).to(torch.float16)
    v_offset = v_offset.unsqueeze(0).to(torch.float16)

    spec = FusedAttentionSpec(
        B=B, H_q=H_q, H_kv=H_kv, S_q=S_q, S_kv=S_kv, D=D,
        block_size=16, group_size_k=group_size_k, group_size_v=group_size_v,
        asymmetric=True,
    )
    out_fused = fused_int4_attention_reference(
        q=q, k_packed=k_packed, k_scale=k_scale, k_offset=k_offset,
        v_packed=v_packed, v_scale=v_scale, v_offset=v_offset,
        spec=spec,
    )

    # Naive baseline: dequant K + V, then standard scaled-dot-product
    # attention. This is the contract the fused reference must match.
    k_dequant_sd = dequantize_per_channel_int4(
        k_int4, k_scale[0].to(k_int4.device), dtype=torch.float16,
        group_size=group_size_k, offset=k_offset[0].to(k_int4.device),
    )  # (S, H_kv, D)
    v_dequant_sd = dequantize_per_token_int4(
        v_int4, v_scale[0].to(v_int4.device), dtype=torch.float16,
        group_size=group_size_v, offset=v_offset[0].to(v_int4.device),
    )
    k_naive = k_dequant_sd.transpose(0, 1).unsqueeze(0)  # (1, H_kv, S, D)
    v_naive = v_dequant_sd.transpose(0, 1).unsqueeze(0)
    # GQA broadcast.
    G_q = H_q // H_kv
    k_naive_gqa = k_naive.unsqueeze(2).expand(
        B, H_kv, G_q, S_kv, D,
    ).reshape(B, H_q, S_kv, D)
    v_naive_gqa = v_naive.unsqueeze(2).expand(
        B, H_kv, G_q, S_kv, D,
    ).reshape(B, H_q, S_kv, D)
    softmax_scale = 1.0 / math.sqrt(D)
    scores = torch.matmul(q, k_naive_gqa.transpose(-1, -2)) * softmax_scale
    attn = torch.softmax(scores.float(), dim=-1).to(q.dtype)
    out_naive = torch.matmul(attn, v_naive_gqa)

    max_abs_diff = (out_fused - out_naive).abs().max().item()
    cos_sim = torch.nn.functional.cosine_similarity(
        out_fused.flatten().float(), out_naive.flatten().float(), dim=0,
    ).item()

    return {
        "output_shape": tuple(out_fused.shape),
        "output_dtype": str(out_fused.dtype),
        "max_abs_diff_vs_naive": max_abs_diff,
        "cosine_similarity_vs_naive": cos_sim,
    }


def _protected_k_round_trip_demo() -> dict:
    """Protected-K (§20.4.2) variant of ``_round_trip_demo``.

    A static ~4% set of K channels keeps FP16 originals; the rest go
    through INT4. Verifies ``fused_int4_attention_reference`` with the
    ``k_fp16`` / ``k_protect_mask`` arguments matches a naive "dequant
    K → overlay protected channels → attention" pipeline, and that
    protection brings the output *closer* to the true FP16 attention
    than uniform INT4 does. This is the numerical spec the 6c kernel's
    layer-1 correctness test is written against.
    """
    if torch is None:
        raise ImportError("torch not installed; demo can't run.")
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
        quantize_per_token_int4, dequantize_per_token_int4, pack_int4,
    )

    B, H_q, H_kv, D = 1, 28, 4, 128
    S_q, S_kv = 1, 64
    gk = gv = 32
    torch.manual_seed(0)
    q = torch.randn(B, H_q, S_q, D, dtype=torch.float16)
    k_fp16 = torch.randn(B, H_kv, S_kv, D, dtype=torch.float16)
    v_fp16 = torch.randn(B, H_kv, S_kv, D, dtype=torch.float16)
    # Inject outlier channels so protection visibly matters.
    for h, d in [(0, 0), (2, 64), (1, 100)]:
        k_fp16[:, h, :, d] *= 40.0

    # Static protected mask: top 4% of (H_kv, D) channels by max-abs.
    mag = k_fp16.abs().amax(dim=2).amax(dim=0)            # (H_kv, D)
    n_protect = max(1, round(0.04 * H_kv * D))
    idx = torch.topk(mag.reshape(-1), n_protect).indices
    mask = torch.zeros(H_kv * D, dtype=torch.bool)
    mask[idx] = True
    mask = mask.reshape(H_kv, D)

    # Quantize K/V through the route-B ops (single-batch).
    k_int4, k_scale, k_offset = quantize_per_channel_int4(
        k_fp16[0].transpose(0, 1).contiguous(), group_size=gk, asymmetric=True,
    )
    v_int4, v_scale, v_offset = quantize_per_token_int4(
        v_fp16[0].transpose(0, 1).contiguous(), group_size=gv, asymmetric=True,
    )
    k_packed = pack_int4(k_int4).transpose(0, 1).contiguous().unsqueeze(0)
    v_packed = pack_int4(v_int4).transpose(0, 1).contiguous().unsqueeze(0)
    k_scale = k_scale.unsqueeze(0).to(torch.float16)
    k_offset = k_offset.unsqueeze(0).to(torch.float16)
    v_scale = v_scale.unsqueeze(0).to(torch.float16)
    v_offset = v_offset.unsqueeze(0).to(torch.float16)

    spec = FusedAttentionSpec(
        B=B, H_q=H_q, H_kv=H_kv, S_q=S_q, S_kv=S_kv, D=D,
        block_size=16, group_size_k=gk, group_size_v=gv, asymmetric=True,
    )
    out_protected = fused_int4_attention_reference(
        q=q, k_packed=k_packed, k_scale=k_scale, k_offset=k_offset,
        v_packed=v_packed, v_scale=v_scale, v_offset=v_offset, spec=spec,
        k_fp16=k_fp16, k_protect_mask=mask,
    )
    out_uniform = fused_int4_attention_reference(
        q=q, k_packed=k_packed, k_scale=k_scale, k_offset=k_offset,
        v_packed=v_packed, v_scale=v_scale, v_offset=v_offset, spec=spec,
    )

    # Naive contract: dequant K, overlay the protected channels, attend.
    k_dq = dequantize_per_channel_int4(
        k_int4, k_scale[0], dtype=torch.float16, group_size=gk,
        offset=k_offset[0],
    ).transpose(0, 1).unsqueeze(0)                         # (1, H_kv, S, D)
    k_dq = torch.where(mask[None, :, None, :], k_fp16, k_dq)
    v_dq = dequantize_per_token_int4(
        v_int4, v_scale[0], dtype=torch.float16, group_size=gv,
        offset=v_offset[0],
    ).transpose(0, 1).unsqueeze(0)
    G_q = H_q // H_kv
    sc = 1.0 / math.sqrt(D)

    def _attn(k_kv, v_kv):
        k = k_kv.unsqueeze(2).expand(B, H_kv, G_q, S_kv, D).reshape(B, H_q, S_kv, D)
        v = v_kv.unsqueeze(2).expand(B, H_kv, G_q, S_kv, D).reshape(B, H_q, S_kv, D)
        s = torch.matmul(q, k.transpose(-1, -2)) * sc
        a = torch.softmax(s.float(), dim=-1).to(q.dtype)
        return torch.matmul(a, v)

    out_naive = _attn(k_dq, v_dq)
    # True FP16 attention (V still FP16 here — measures the K effect).
    out_true = _attn(k_fp16, v_fp16)

    def _cos(a, b):
        return torch.nn.functional.cosine_similarity(
            a.flatten().float(), b.flatten().float(), dim=0,
        ).item()

    return {
        "n_protected_channels": int(n_protect),
        "max_abs_diff_vs_naive": (out_protected - out_naive).abs().max().item(),
        "cosine_vs_naive": _cos(out_protected, out_naive),
        "cosine_protected_vs_true_fp16": _cos(out_protected, out_true),
        "cosine_uniform_vs_true_fp16": _cos(out_uniform, out_true),
    }


if __name__ == "__main__":
    if torch is None:
        raise SystemExit("torch not installed; sketch can't run.")

    # Real round-trip: quantize Qwen-shape K/V through the route-B
    # ops, then verify the fused reference matches a naive dequant-
    # then-attention pipeline.
    result = _round_trip_demo()
    print(f"output shape: {result['output_shape']} dtype: {result['output_dtype']}")
    print(f"vs naive dequant+attention:")
    print(f"  max abs diff:      {result['max_abs_diff_vs_naive']:.6f}")
    print(f"  cosine similarity: {result['cosine_similarity_vs_naive']:.6f}")

    # HBM ceiling at the §18.3 ship config (asymmetric=True).
    speedup = speedup_ceiling(B=1, H_kv=4, S_kv=64, D=128)
    print()
    print(f"HBM-traffic ceiling speedup vs FP16 (asymmetric, group=32): {speedup:.2f}x")
    print(
        f"  FP16 bytes: "
        f"{hbm_bytes_for_attention(B=1, H_kv=4, S_kv=64, D=128, int4=False):,}"
    )
    print(
        f"  INT4 bytes: "
        f"{hbm_bytes_for_attention(B=1, H_kv=4, S_kv=64, D=128, int4=True):,}"
    )
    # For reference, the symmetric-only ceiling (no offset storage).
    speedup_sym = speedup_ceiling(B=1, H_kv=4, S_kv=64, D=128, asymmetric=False)
    print(f"  (symmetric-only ceiling, no offset:  {speedup_sym:.2f}x)")
    # §20.4.2 outlier-protected-K ceiling — the winning long-context
    # config (top 4% of K channels FP16, rest INT4, V INT4).
    speedup_prot = speedup_ceiling(
        B=1, H_kv=4, S_kv=64, D=128, k_protect_fraction=0.04,
    )
    print(
        f"  (protected-K 4% ceiling — §20.4.2 config:  {speedup_prot:.2f}x)"
    )

    # Protected-K reference round-trip — the 6c kernel's layer-1 spec.
    pk = _protected_k_round_trip_demo()
    print()
    print(f"protected-K reference ({pk['n_protected_channels']} channels FP16):")
    print(f"  vs naive dequant+overlay+attention:")
    print(f"    max abs diff:      {pk['max_abs_diff_vs_naive']:.6f}")
    print(f"    cosine similarity: {pk['cosine_vs_naive']:.6f}")
    print(f"  cosine vs true FP16 attention:")
    print(f"    protected-K: {pk['cosine_protected_vs_true_fp16']:.6f}")
    print(f"    uniform INT4: {pk['cosine_uniform_vs_true_fp16']:.6f}  "
          f"(protected should be >= uniform)")
