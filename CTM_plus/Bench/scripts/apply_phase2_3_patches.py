#!/usr/bin/env python3
"""apply_phase2_3_patches.py — 6c.3C Phase 2.3: NO-OP INT4 transform on K.

Modifies the dev tree at /workspace/dev/vllm-flash-attn-dev:

  1. NEW csrc/flash_attn/src/int4_inline.h
     - Header-only helper, FLASH_NAMESPACE-wrapped.
     - Exports int4_quant_dequant_K_block_inplace<Kernel_traits, kGroupSize>(
           tKsK, tKVcKV, smem_scratch) which:
       a. Inits a 2*(kBlockN/kGroupSize)*kHeadDim float smem scratchpad
          with -inf/+inf (max/min slots).
       b. Pass 1: every thread iterates its (CPY, CPY_N, CPY_K) fragment
          of tKsK, looks up (n, d) from the matching coord-tensor tKVcKV,
          atomically updates smem_scratch[group_idx][d] {max, min} via
          float-CAS (atomicCAS on the bit reinterpretation, with float
          comparison done in float — handles negatives correctly).
       c. Pass 2: every thread iterates the fragment again, reads the
          group's (max, min) from smem, computes
              scale = max((x_max - x_min) / 15, 1e-8)
              q = clamp(__float2int_rn((x - x_min) / scale), 0, 15)
              x_hat = q * scale + x_min   [exact match to route-B's
              quantize_per_channel_int4 with asymmetric=True, bits=4]
          and writes x_hat back into tKsK via the swizzle-aware tensor
          element write.
     - Static_assert gates kBlockN % kGroupSize == 0, so traits with
       kBlockN < 32 (if any) won't instantiate.

  2. MODIFY csrc/flash_attn/src/flash_fwd_kernel.h
     - Add `#include "int4_inline.h"` after `#include "rotary.h"`.
     - In compute_attn_1rowblock_splitkv, after the prologue K cp.async
       and BEFORE clear(acc_o), declare:
           constexpr int kInt4GroupSize = 32;
           constexpr int kInt4ScratchFloats = 2 * (Kernel_traits::kBlockN
               / kInt4GroupSize) * Kernel_traits::kHeadDim;
           __shared__ float smem_int4_scratch[kInt4ScratchFloats];
       Static smem (~4 KB at kBlockN=128, kHeadDim=128). If smem
       overflows on build, fallback is to carve out of the dynamic
       extern __shared__ char smem_[] buffer (Phase 2.3.1).
     - At the masking loop's K-wait (cp_async_wait<0>; __syncthreads;
       followed by blank line + `// Advance gV` + `if (masking_step > 0)`),
       insert the runtime-gated transform call + trailing sync.
     - At the non-masking loop's K-wait (cp_async_wait<0>; __syncthreads;
       directly followed by `// Advance gV` + `if (block_table == nullptr)`),
       insert the same transform call.
     - The two K-wait sites are uniquely identified by the surrounding
       code: the V-wait sites have different following code (a print
       comment or `if (n_block > n_block_min)`). The patcher fails loudly
       if any anchor string isn't found exactly once.

Idempotent: each patch checks a sentinel string before applying.
Re-running on an already-patched tree is a no-op.

Acceptance: verify_phase2_3.py — cosine >= 0.9999 AND max-abs <= 1e-2
between flash_attn_with_int4_kvcache and flash_attn_with_kvcache on
Qwen2.5-7B shapes (B=1, H_q=28, H_kv=4, D=128, S=16k).
"""

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1: new file csrc/flash_attn/src/int4_inline.h
# ============================================================

INT4_INLINE_H_CONTENT = r"""/******************************************************************************
 * 6c.3C Phase 2.3 — NO-OP INT4 quant->dequant transform on K in smem.
 *
 * When params.is_int4kv == true, after K has been loaded into smem
 * (via cp.async + cp_async_wait + __syncthreads) and BEFORE the qK^T
 * gemm consumes it, run a per-group max/min reduction -> asymmetric
 * INT4 quantize -> INT4 dequantize cycle, writing back to the same
 * smem locations.
 *
 * group_size_k = 32 along the seq axis (kBlockN axis). For
 * kBlockN = 128, that's 4 groups per K block. Per-(group, head_dim)
 * scales/offsets are derived from the loaded K's per-group {max, min}
 * and used immediately — not stored back to HBM (HBM K layout stays
 * BF16 in Phase 2.3; Phase 2.5+ changes that).
 *
 * Numerics match kv_policy/int4_per_channel_kv.py::
 *   quantize_per_channel_int4(K, group_size=32, asymmetric=True, bits=4)
 * exactly:
 *   x_max = group_max(K)
 *   x_min = group_min(K)
 *   scale = fmaxf((x_max - x_min) / 15.0f, 1e-8f)
 *   q_unsigned = clamp(__float2int_rn((x - x_min) / scale), 0, 15)
 *   x_hat = q_unsigned * scale + x_min
 * Internal arithmetic is FP32. __float2int_rn is round-to-nearest-even,
 * which matches PyTorch's .round(). BF16 <-> FP32 conversions are exact
 * (BF16 mantissa fits in FP32).
 *
 * Implementation: smem-scratchpad reduction. Each thread iterates its
 * CUTLASS-partitioned smem K fragment (tKsK), looks up the (n, d) coord
 * from the matching identity-tensor partition (tKVcKV), and contributes
 * to a (n_groups, kHeadDim, 2 = {max, min}) float scratchpad via
 * float-bit CAS atomics. Two threadblock syncs added per call.
 *
 * Cooperative reduction strategy: chosen over warp-aligned shuffle so
 * the helper does NOT depend on the GmemTiledCopyQKVPaged atom's
 * thread-to-(seq, dim) mapping. Slower (high contention on the 512-slot
 * scratch) but provably correct for the v1 NO-OP transform proof.
 ******************************************************************************/

#pragma once

#include <cuda_bf16.h>
#include <cuda_fp16.h>
#include <cute/tensor.hpp>

#include "namespace_config.h"
#include "kernel_traits.h"

namespace FLASH_NAMESPACE {

using namespace cute;

////////////////////////////////////////////////////////////////////////////////
// Atomic max/min on float via int-CAS reinterpretation.
//
// Plain atomicMax/Min on int reinterpretations of floats is incorrect for
// negative values because the int sort order doesn't match the float
// sort order across zero. We solve it by doing the value comparison in
// FLOAT and using CAS only to commit the update — the comparison is
// monotone in true float magnitude.
////////////////////////////////////////////////////////////////////////////////

__device__ __forceinline__ void int4_inline_atomic_max_float(float *addr, float val) {
    int *as_int = reinterpret_cast<int *>(addr);
    int old_bits = *as_int;
    int assumed;
    do {
        float cur = __int_as_float(old_bits);
        if (val <= cur) return;
        assumed = old_bits;
        old_bits = atomicCAS(as_int, assumed, __float_as_int(val));
    } while (assumed != old_bits);
}

__device__ __forceinline__ void int4_inline_atomic_min_float(float *addr, float val) {
    int *as_int = reinterpret_cast<int *>(addr);
    int old_bits = *as_int;
    int assumed;
    do {
        float cur = __int_as_float(old_bits);
        if (val >= cur) return;
        assumed = old_bits;
        old_bits = atomicCAS(as_int, assumed, __float_as_int(val));
    } while (assumed != old_bits);
}

////////////////////////////////////////////////////////////////////////////////
// BF16/FP16-agnostic float-from-element / element-from-float helpers.
////////////////////////////////////////////////////////////////////////////////

template <typename Element>
__device__ __forceinline__ float int4_inline_to_float(Element e);

template <>
__device__ __forceinline__ float int4_inline_to_float<__nv_bfloat16>(__nv_bfloat16 e) {
    return __bfloat162float(e);
}

template <>
__device__ __forceinline__ float int4_inline_to_float<cutlass::bfloat16_t>(cutlass::bfloat16_t e) {
    return static_cast<float>(e);
}

template <>
__device__ __forceinline__ float int4_inline_to_float<__half>(__half e) {
    return __half2float(e);
}

template <>
__device__ __forceinline__ float int4_inline_to_float<cutlass::half_t>(cutlass::half_t e) {
    return static_cast<float>(e);
}

template <typename Element>
__device__ __forceinline__ Element int4_inline_from_float(float x);

template <>
__device__ __forceinline__ __nv_bfloat16 int4_inline_from_float<__nv_bfloat16>(float x) {
    return __float2bfloat16_rn(x);
}

template <>
__device__ __forceinline__ cutlass::bfloat16_t int4_inline_from_float<cutlass::bfloat16_t>(float x) {
    return static_cast<cutlass::bfloat16_t>(x);
}

template <>
__device__ __forceinline__ __half int4_inline_from_float<__half>(float x) {
    return __float2half_rn(x);
}

template <>
__device__ __forceinline__ cutlass::half_t int4_inline_from_float<cutlass::half_t>(float x) {
    return static_cast<cutlass::half_t>(x);
}

////////////////////////////////////////////////////////////////////////////////
// int4_quant_dequant_K_block_inplace
//
// Caller invariants:
//   - K is committed in smem via cp_async_wait<0>() + __syncthreads().
//   - smem_scratch is a float buffer of size
//       2 * (Kernel_traits::kBlockN / kGroupSize) * Kernel_traits::kHeadDim.
//   - tKsK and tKVcKV are the thread's CUTLASS partitions of the K smem
//     tile and its (n, d) identity tensor respectively, both of shape
//     (CPY, CPY_N, CPY_K).
//
// Postcondition:
//   - smem K has been overwritten with x_hat (the dequant of the INT4
//     quant of x), per route-B's exact arithmetic.
//   - Caller MUST __syncthreads() after this call before the GEMM
//     consumes the modified smem K (call site adds this sync explicitly).
////////////////////////////////////////////////////////////////////////////////

template <typename Kernel_traits, int kGroupSize,
          typename EngineK, typename LayoutK,
          typename EngineC, typename LayoutC>
__device__ __forceinline__ void int4_quant_dequant_K_block_inplace(
    cute::Tensor<EngineK, LayoutK> &tKsK,
    cute::Tensor<EngineC, LayoutC> const &tKVcKV,
    float *smem_scratch) {

    using Element = typename Kernel_traits::Element;
    constexpr int kBlockN  = Kernel_traits::kBlockN;
    constexpr int kHeadDim = Kernel_traits::kHeadDim;
    static_assert(kBlockN % kGroupSize == 0,
                  "int4_quant_dequant_K_block_inplace requires kBlockN % kGroupSize == 0");
    constexpr int kNGroups = kBlockN / kGroupSize;
    constexpr int kSlots   = kNGroups * kHeadDim;

    float *smem_max = smem_scratch;
    float *smem_min = smem_scratch + kSlots;

    const int tidx     = threadIdx.x;
    const int nthreads = blockDim.x;

    // Pass 0: init scratchpad slots to -inf / +inf.
    // Caller already synced, but we sync again at entry defensively
    // (multiple invocations could compound; cost is one bar.sync).
    __syncthreads();
    #pragma unroll 1
    for (int i = tidx; i < kSlots; i += nthreads) {
        smem_max[i] = -INFINITY;
        smem_min[i] = +INFINITY;
    }
    __syncthreads();

    // Pass 1: stream the per-thread K fragment into the scratchpad.
    // CUTE tensors index as (i0, i1, i2). tKVcKV(i0, i1, i2) returns the
    // (n, d) tuple via cute::get<0/1>. Element read goes through the
    // swizzled layout — float(tKsK(i0, i1, i2)) gives the correct value.
    #pragma unroll
    for (int i0 = 0; i0 < size<0>(tKsK); ++i0) {
        #pragma unroll
        for (int i1 = 0; i1 < size<1>(tKsK); ++i1) {
            #pragma unroll
            for (int i2 = 0; i2 < size<2>(tKsK); ++i2) {
                auto coord = tKVcKV(i0, i1, i2);
                int n = int(cute::get<0>(coord));
                int d = int(cute::get<1>(coord));
                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;
                const int g = n / kGroupSize;
                const int slot = g * kHeadDim + d;
                const float x = int4_inline_to_float<Element>(tKsK(i0, i1, i2));
                int4_inline_atomic_max_float(&smem_max[slot], x);
                int4_inline_atomic_min_float(&smem_min[slot], x);
            }
        }
    }
    __syncthreads();

    // Pass 2: stream the per-thread fragment again, computing quant/dequant
    // against the per-group (max, min) read from the scratchpad. Writes
    // x_hat back into the swizzled smem K location.
    constexpr float kInvFifteen = 1.0f / 15.0f;  // matches asym_div = 15 (4-bit unsigned range)
    constexpr float kScaleClamp = 1e-8f;          // matches .clamp(min=1e-8)
    #pragma unroll
    for (int i0 = 0; i0 < size<0>(tKsK); ++i0) {
        #pragma unroll
        for (int i1 = 0; i1 < size<1>(tKsK); ++i1) {
            #pragma unroll
            for (int i2 = 0; i2 < size<2>(tKsK); ++i2) {
                auto coord = tKVcKV(i0, i1, i2);
                int n = int(cute::get<0>(coord));
                int d = int(cute::get<1>(coord));
                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;
                const int g = n / kGroupSize;
                const int slot = g * kHeadDim + d;
                const float x_max = smem_max[slot];
                const float x_min = smem_min[slot];
                const float scale = fmaxf((x_max - x_min) * kInvFifteen, kScaleClamp);
                const float x = int4_inline_to_float<Element>(tKsK(i0, i1, i2));
                int q = __float2int_rn((x - x_min) / scale);
                q = max(0, min(15, q));
                const float x_hat = static_cast<float>(q) * scale + x_min;
                tKsK(i0, i1, i2) = int4_inline_from_float<Element>(x_hat);
            }
        }
    }
    // No exit sync — caller adds __syncthreads() before the GEMM that
    // consumes the modified smem K.
}

}  // namespace FLASH_NAMESPACE
"""


def patch_int4_inline_h(path: Path) -> None:
    if path.exists():
        existing = path.read_text()
        if existing == INT4_INLINE_H_CONTENT:
            print(f"  SKIP (already up to date): {path}")
            return
        if "int4_quant_dequant_K_block_inplace" in existing:
            # Content drift — overwrite with current canonical version.
            print(f"  REWRITE (content drift): {path}")
            path.write_text(INT4_INLINE_H_CONTENT)
            return
        raise RuntimeError(
            f"{path} exists but doesn't contain the Phase 2.3 helper — "
            "refusing to overwrite a foreign file. Investigate manually."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(INT4_INLINE_H_CONTENT)
    print(f"  CREATED: {path}")


# ============================================================
# Patch 2: csrc/flash_attn/src/flash_fwd_kernel.h
# ============================================================

# --- 2a: include the new header -------------------------------------------

INCLUDE_OLD = '''#include "rotary.h"

namespace FLASH_NAMESPACE {'''

INCLUDE_NEW = '''#include "rotary.h"
#include "int4_inline.h"  // 6c.3C Phase 2.3 NO-OP INT4 transform on K

namespace FLASH_NAMESPACE {'''


# --- 2b: smem scratchpad alloc + group-size constexpr ---------------------
# Anchor: prologue K cp.async + commented diagnostic + clear(acc_o).
# The matching block appears EXACTLY ONCE in the file (it's in
# compute_attn_1rowblock_splitkv, distinct from compute_attn_1rowblock
# which has a different prologue pattern).

SMEM_ALLOC_OLD = '''    int n_block = n_block_max - 1;
    // We don't need to clear the sK smem tiles since we'll mask out the scores anyway.
    FLASH_NAMESPACE::copy<Is_even_MN, Is_even_K>(gmem_tiled_copy_KV, tKgK, tKsK, tKVcKV, tKVpKV,
                                                 binfo.actual_seqlen_k - n_block * kBlockN);
    cute::cp_async_fence();

    // FLASH_NAMESPACE::cp_async_wait<0>();
    // __syncthreads();
    // if (tidx == 0 && blockIdx.y == 0 && blockIdx.z == 0) { print(tKsK); }
    // __syncthreads();

    clear(acc_o);'''

SMEM_ALLOC_NEW = '''    int n_block = n_block_max - 1;
    // We don't need to clear the sK smem tiles since we'll mask out the scores anyway.
    FLASH_NAMESPACE::copy<Is_even_MN, Is_even_K>(gmem_tiled_copy_KV, tKgK, tKsK, tKVcKV, tKVpKV,
                                                 binfo.actual_seqlen_k - n_block * kBlockN);
    cute::cp_async_fence();

    // FLASH_NAMESPACE::cp_async_wait<0>();
    // __syncthreads();
    // if (tidx == 0 && blockIdx.y == 0 && blockIdx.z == 0) { print(tKsK); }
    // __syncthreads();

    // 6c.3C Phase 2.3: scratchpad for the NO-OP INT4 quant->dequant transform
    // on K. Used only when params.is_int4kv (runtime gate; uniform branch).
    // Static smem: 2 * (kBlockN / 32) * kHeadDim floats. At Qwen2.5-7B
    // shapes (kBlockN=128, kHeadDim=128) -> 4 KB. kInt4GroupSize must
    // divide kBlockN (asserted in int4_inline.h via static_assert).
    constexpr int kInt4GroupSize = 32;
    constexpr int kInt4ScratchFloats =
        2 * (Kernel_traits::kBlockN / kInt4GroupSize) * Kernel_traits::kHeadDim;
    __shared__ float smem_int4_scratch[kInt4ScratchFloats];

    clear(acc_o);'''


# --- 2c: masking-loop K-wait transform insertion --------------------------
# Anchor disambiguates from the V-wait sites by the BLANK LINE between
# __syncthreads() and "// Advance gV", and by the following
# `if (masking_step > 0) {` (the V-wait sites have either a print comment
# or `if (n_block > n_block_min)` next).

MASKING_TRANSFORM_OLD = '''        FLASH_NAMESPACE::cp_async_wait<0>();
        __syncthreads();

        // Advance gV
        if (masking_step > 0) {
            if (block_table == nullptr) {'''

MASKING_TRANSFORM_NEW = '''        FLASH_NAMESPACE::cp_async_wait<0>();
        __syncthreads();

        // 6c.3C Phase 2.3: NO-OP INT4 transform on K (runtime-gated;
        // uniform branch -> nvcc CSEs to ~zero cost on the stock path).
        // if constexpr guard prevents instantiation for traits where
        // kBlockN % 32 != 0 (e.g. kBlockN=16).
        if constexpr (Kernel_traits::kBlockN % kInt4GroupSize == 0) {
            if (params.is_int4kv) {
                FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                    Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_scratch);
                __syncthreads();
            }
        }

        // Advance gV
        if (masking_step > 0) {
            if (block_table == nullptr) {'''


# --- 2d: non-masking-loop K-wait transform insertion ----------------------

NONMASKING_TRANSFORM_OLD = '''        FLASH_NAMESPACE::cp_async_wait<0>();
        __syncthreads();
        // Advance gV
        if (block_table == nullptr) {'''

NONMASKING_TRANSFORM_NEW = '''        FLASH_NAMESPACE::cp_async_wait<0>();
        __syncthreads();
        // 6c.3C Phase 2.3: NO-OP INT4 transform on K (runtime-gated).
        if constexpr (Kernel_traits::kBlockN % kInt4GroupSize == 0) {
            if (params.is_int4kv) {
                FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                    Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_scratch);
                __syncthreads();
            }
        }
        // Advance gV
        if (block_table == nullptr) {'''


def _exactly_once(src: str, needle: str, label: str) -> None:
    count = src.count(needle)
    if count == 0:
        raise RuntimeError(
            f"anchor '{label}' not found in flash_fwd_kernel.h — file "
            "has likely drifted from SHA 720c948. Inspect manually."
        )
    if count > 1:
        raise RuntimeError(
            f"anchor '{label}' matches {count} times in flash_fwd_kernel.h "
            "— not unique enough for a safe replacement. Extend the anchor "
            "with more surrounding context."
        )


def patch_flash_fwd_kernel_h(path: Path) -> None:
    src = path.read_text()

    # Idempotency sentinel: the helper-call line is unique to Phase 2.3.
    if "int4_quant_dequant_K_block_inplace" in src:
        print(f"  SKIP (already patched): {path}")
        return

    # 2a: include the header.
    _exactly_once(src, INCLUDE_OLD, "include block (rotary.h + namespace)")
    src = src.replace(INCLUDE_OLD, INCLUDE_NEW, 1)

    # 2b: smem scratchpad alloc.
    _exactly_once(src, SMEM_ALLOC_OLD, "splitkv prologue + clear(acc_o)")
    src = src.replace(SMEM_ALLOC_OLD, SMEM_ALLOC_NEW, 1)

    # 2c: masking-loop transform insertion.
    _exactly_once(src, MASKING_TRANSFORM_OLD, "masking-loop K-wait + Advance gV (masking_step > 0)")
    src = src.replace(MASKING_TRANSFORM_OLD, MASKING_TRANSFORM_NEW, 1)

    # 2d: non-masking-loop transform insertion.
    _exactly_once(src, NONMASKING_TRANSFORM_OLD, "non-masking-loop K-wait + Advance gV (block_table)")
    src = src.replace(NONMASKING_TRANSFORM_OLD, NONMASKING_TRANSFORM_NEW, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Main
# ============================================================

def main() -> int:
    if not DEV_ROOT.exists():
        print(f"ERROR: dev tree not at {DEV_ROOT}", file=sys.stderr)
        print(
            "  Are you running on the GPU pod? This script must run there.",
            file=sys.stderr,
        )
        return 1

    targets = [
        (DEV_ROOT / "csrc/flash_attn/src/int4_inline.h",      patch_int4_inline_h),
        (DEV_ROOT / "csrc/flash_attn/src/flash_fwd_kernel.h", patch_flash_fwd_kernel_h),
    ]

    print("Applying Phase 2.3 patches:")
    for path, fn in targets:
        try:
            fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR on {path}: {e}", file=sys.stderr)
            return 1

    print()
    print("Patches applied. Next: incremental rebuild + install + verify.")
    print("  flash_fwd_kernel.h is included by ~14 splitkv .cu TUs; the")
    print("  rebuild will recompile all of them (~8-12 min on sm80,")
    print("  hot cache).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
