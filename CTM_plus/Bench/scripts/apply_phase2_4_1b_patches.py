#!/usr/bin/env python3
"""apply_phase2_4_1b_patches.py — 6c.3C Phase 2.4.1b: packed-K kernel read.

Adds the actual CUDA path that reads packed uint8 K from HBM (instead
of cp.async-loading BF16 K + in-register quant). Wires through:

  1. NEW int4_packed_load.h — the helper. Per K block, cooperatively
     loads packed K bytes + scales + xmins + protect_bf16 from HBM to
     per-block smem scratchpads, then per-thread iterates the CUTLASS
     tKsK fragment, looks up (n, d) coord via tKVcKV, decides
     protected-vs-unprotected, unpacks nibble + dequant for
     unprotected channels, writes BF16 to tKsK.

  2. NEW OptionalPackedScratch template (in the same header) — the
     conditional smem allocation. Mirrors Phase 2.5's
     OptionalInt4Scratch. When Is_int4kv_packed=true, allocates
     ~5 KB of smem (8 KB packed + 2 KB scales+xmins + 2 KB
     protect + 128 B slot ≈ 12 KB at kMaxNProtect=8). When false,
     empty struct (1 byte).

  3. Is_int4kv_packed template param plumbed through
     run_flash_splitkv_fwd -> flash_fwd_splitkv_kernel ->
     compute_attn_splitkv -> compute_attn_1rowblock_splitkv.

  4. NEW dispatch arm run_mha_fwd_splitkv_dispatch_int4kv_packed
     (mirrors Phase 2.1's _int4kv arm) + new .cu instantiation file
     flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu.

  5. flash.h forward decl for the new dispatch.

  6. flash_api.cpp run_mha_fwd routes to _int4kv_packed when
     params.is_int4kv_packed (set by Phase 2.4.1a from the new
     packed pointers). Also adds a runtime assert that
     params.packed_n_protect <= 8 (= compile-time kMaxNProtect) so
     misuse fails loudly instead of corrupting smem.

  7. At the 3 K-load sites in compute_attn_1rowblock_splitkv:
     `if constexpr (Is_int4kv_packed) { call helper } else if
     constexpr (Is_int4kv) { existing Phase 2.3/4 transform }`.
     Mutually exclusive — OptionalInt4Scratch goes empty when packed.

V1 simplifications (NOT optimizations — correctness first):
  - Synchronous __ldg (uint4 16-byte vectorized) loads for packed K.
    cp.async is the v1.1 perf optimization.
  - Scales/xmins/protect loaded with simple per-element BF16 reads.
    Could vectorize but small data; not worth complexity for v1.
  - The pre-existing cp.async of BF16 K (Phase 2.3 path) still fires
    when Is_int4kv_packed=true — wasteful (loads 32 KB we ignore) but
    mechanically simpler. Removing is a v1.1 perf optimization that
    would also free 32 KB of smem traffic.
  - kMaxNProtect = 8 (compile-time smem stride). Supports
    protect_fraction up to 6.25%. Default 4% (n_protect=5) fits.
    Safe-mode 8% (n_protect=10) does NOT — runtime assert in
    flash_api.cpp catches this.

Numerical convention (must match Phase 2.4.0's Python pack):
  q_unsigned = byte's nibble (low if d even, high if d odd), in [0,15]
  x_hat = q_unsigned * scale + x_min  (scale + x_min from per-group HBM)
  Protected channels (protect_slot[d] >= 0): read sProtect[n, slot]
    directly, bypass dequant.
  bf16 read: __bfloat162float exact. Write: __float2bfloat16_rn (RTNE).

Acceptance:
  - Build succeeds (all splitkv .cu TUs recompile, ~10-12 min).
  - verify_phase2_4_1b.py PASS: cosine >= 0.9995 vs Phase 5A reference.
  - verify_phase4.py + Phase 5A smoke STILL PASS (template gating
    isolates the packed path; non-packed callers unchanged).

Prerequisites: Phase 1 + 2.1 + 2.2 + 2.3 + 2.5 + 3 + 4 + 2.4.1a applied.
"""

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1: NEW file csrc/flash_attn/src/int4_packed_load.h
# ============================================================

INT4_PACKED_LOAD_H_CONTENT = r"""/******************************************************************************
 * 6c.3C Phase 2.4.1b — packed-K HBM load helper.
 *
 * When the kernel template param Is_int4kv_packed=true, this helper
 * REPLACES the existing cp.async-BF16-K + Phase 2.3 in-register quant
 * sequence with: load packed uint8 K from HBM, unpack to INT4 in
 * registers, dequantize via per-group scale + x_min, blend protected
 * channels from a separate BF16 sidecar, write BF16 result to sK.
 *
 * Numerical convention: must match Phase 2.4.0's Python pack
 * (kv_policy/phase2_4_packed_kv.py) AND Phase 2.3's in-register
 * quant (int4_inline.h):
 *
 *   At write (Python pack):
 *     scale       = max((x_max - x_min) / 15.0f, 1e-8f)
 *     q_unsigned  = round((x - x_min) / scale).clamp(0, 15)
 *     byte[d/2]   = q_unsigned[d_even] | (q_unsigned[d_odd] << 4)
 *
 *   At read (this kernel):
 *     byte        = smem.k_packed[n * (kHeadDim/2) + d/2]
 *     nibble      = (d & 1) ? (byte >> 4) : (byte & 0x0F)
 *     x_hat       = (float)nibble * scale + x_min
 *     write       = __float2bfloat16_rn(x_hat)
 *
 *   Protected channels (smem.protect_slot[d] >= 0):
 *     x_hat       = smem.k_protect[n * kMaxNProtect + slot]
 *     write       = x_hat  (direct BF16, no dequant)
 *
 * V1 design (correctness over performance):
 *   - Synchronous __ldg(uint4*) loads for packed K (4 x 16-byte per
 *     thread). cp.async upgrade is v1.1.
 *   - Scales/xmins/protect loaded per-element BF16. Small data;
 *     vectorization is v1.1.
 *   - Per-thread fragment iteration via tKsK + tKVcKV coord lookup,
 *     same pattern as Phase 2.3's int4_quant_dequant_K_block_inplace.
 *   - kMaxNProtect is a COMPILE-TIME upper bound for the smem stride.
 *     Runtime n_protect must be <= kMaxNProtect (caller asserts).
 *
 * Caller invariants:
 *   - HBM K_packed sidecar layout: (B, S_max, H_kv, D/2) uint8.
 *   - HBM K_scale / K_xmin layout: (B, S_max/G, H_kv, D) BF16.
 *   - HBM K_protect_bf16 layout: (B, S_max, H_kv, n_protect) BF16
 *     where n_protect is per-call dynamic (<= kMaxNProtect).
 *   - HBM protect_slot layout: (H_kv, D) int8, -1 if not protected,
 *     else slot in [0, n_protect).
 *   - Caller does NOT need to sync before calling (we sync at entry
 *     defensively). Caller MUST __syncthreads() after return before
 *     the GEMM consumes the modified sK.
 ******************************************************************************/

#pragma once

#include <cuda_bf16.h>
#include <cuda_fp16.h>
#include <cute/tensor.hpp>

#include "namespace_config.h"
#include "kernel_traits.h"
#include "int4_inline.h"   // for int4_inline_to_float / int4_inline_from_float

namespace FLASH_NAMESPACE {

using namespace cute;

////////////////////////////////////////////////////////////////////////////////
// OptionalPackedScratch — conditional smem allocation for the packed path.
//
// When Has=false, instantiates as an empty struct (1 byte smem).
// When Has=true, allocates ~5-12 KB of smem (depending on kMaxNProtect)
// for the packed K + scale + xmin + protect staging buffers.
////////////////////////////////////////////////////////////////////////////////

template <bool Has, int kBlockN, int kHeadDim, int kGroupSize, int kMaxNProtect, typename Element>
struct OptionalPackedScratch {
    // Empty primary template — used when Has=false.
};

template <int kBlockN, int kHeadDim, int kGroupSize, int kMaxNProtect, typename Element>
struct OptionalPackedScratch<true, kBlockN, kHeadDim, kGroupSize, kMaxNProtect, Element> {
    static_assert(kHeadDim % 2 == 0, "kHeadDim must be even for nibble packing");
    static_assert(kBlockN % kGroupSize == 0,
                  "kBlockN must be a multiple of kGroupSize for per-group scales");

    static constexpr int kPackedBytesPerToken = kHeadDim / 2;
    static constexpr int kNGroupsPerBlock     = kBlockN / kGroupSize;

    // Layout (matters for the helper's index math):
    //   k_packed[n * kPackedBytesPerToken + d/2]   — packed nibbles
    //   k_scale [g * kHeadDim + d]                  — per-(g, d) scale
    //   k_xmin  [g * kHeadDim + d]                  — per-(g, d) x_min
    //   k_protect[n * kMaxNProtect + slot]          — protected channels (compact)
    //   protect_slot[d]                             — slot index or -1
    uint8_t k_packed[kBlockN * kPackedBytesPerToken];
    Element k_scale [kNGroupsPerBlock * kHeadDim];
    Element k_xmin  [kNGroupsPerBlock * kHeadDim];
    Element k_protect[kBlockN * kMaxNProtect];
    int8_t  protect_slot[kHeadDim];
};


////////////////////////////////////////////////////////////////////////////////
// int4_packed_load_K_block — cooperative HBM load + dequant + protect blend.
//
// REPLACES the existing cp.async-BF16-K + Phase 2.3 transform when the
// kernel is built with Is_int4kv_packed=true.
//
// Per-thread workload at Qwen2.5-7B target (kBlockN=128, kHeadDim=128,
// nthreads=128):
//   Load phase:
//     - K_packed: 1 token's 64 bytes per thread = 4 x __ldg(uint4*).
//     - Scales:   4 BF16 elements per thread (kNGroupsPerBlock * kHeadDim
//                 / nthreads = 4*128/128).
//     - X_mins:   4 BF16 elements per thread.
//     - Protect:  ceil(kBlockN * n_protect / nthreads) elements per thread.
//     - Slot:     1 int8 per thread (kHeadDim / nthreads = 128/128).
//   Dequant phase:
//     - ~128 BF16 elements per thread to write into tKsK.
//
// Layout assumptions for the HBM pointers (set by Phase 2.4.1a from
// flash_api.cpp's Int4KvPackedGuard plumbing):
//   gmem_k_packed:    (B, S_max, H_kv, D/2) uint8, row-major last
//   gmem_k_scale:     (B, S_max/G, H_kv, D)  Element (BF16/FP16)
//   gmem_k_xmin:      (B, S_max/G, H_kv, D)  Element
//   gmem_k_protect:   (B, S_max, H_kv, n_protect)  Element  [n_protect dynamic]
//   gmem_protect_slot: (H_kv, D) int8  [no batch dim]
////////////////////////////////////////////////////////////////////////////////

template <typename Kernel_traits, int kGroupSize, int kMaxNProtect,
          typename EngineK, typename LayoutK,
          typename EngineC, typename LayoutC,
          typename Scratch>
__device__ __forceinline__ void int4_packed_load_K_block(
    cute::Tensor<EngineK, LayoutK>       &tKsK,
    cute::Tensor<EngineC, LayoutC> const &tKVcKV,
    Scratch                              &smem,
    const uint8_t                        *gmem_k_packed_base,    // ptr already includes bidb*S_max*H_kv*D/2
    const typename Kernel_traits::Element *gmem_k_scale_base,    // ptr already includes bidb*n_groups_total*H_kv*D
    const typename Kernel_traits::Element *gmem_k_xmin_base,
    const typename Kernel_traits::Element *gmem_k_protect_base,  // ptr already includes bidb*S_max*H_kv*n_protect
    const int8_t                         *gmem_protect_slot_base, // ptr already at bidh row start
    int bidh,
    int S_max,
    int H_kv,
    int n_protect,
    int n_block_token_start,
    int s_curr) {

    using Element = typename Kernel_traits::Element;
    constexpr int kBlockN  = Kernel_traits::kBlockN;
    constexpr int kHeadDim = Kernel_traits::kHeadDim;
    constexpr int kPackedBytesPerToken = kHeadDim / 2;
    constexpr int kNGroupsPerBlock     = kBlockN / kGroupSize;

    const int tidx     = threadIdx.x;
    const int nthreads = blockDim.x;

    // Defensive sync at entry — multiple invocations should not see
    // each other's stale scratch.
    __syncthreads();

    // -----------------------------------------------------------------
    // Phase A: cooperative load packed K bytes (~8 KB for our target).
    //   Each thread loads ONE token's 64 bytes = 4 x uint4 (16-byte) loads.
    //   nthreads=128 => one token per thread when kBlockN=128 (perfect fit).
    // -----------------------------------------------------------------
    for (int t = tidx; t < kBlockN; t += nthreads) {
        uint8_t *smem_dst = &smem.k_packed[t * kPackedBytesPerToken];
        int global_t = n_block_token_start + t;
        if (global_t < 0 || global_t >= s_curr) {
            // OOB token (last block's tail). Zero the smem slot so dequant
            // produces x = xmin — the kernel's masking will zero out the
            // qK score for OOB positions anyway, so the value is
            // numerically harmless.
            #pragma unroll
            for (int b = 0; b < kPackedBytesPerToken; b += 16) {
                *reinterpret_cast<uint4*>(smem_dst + b) = make_uint4(0u, 0u, 0u, 0u);
            }
            continue;
        }
        // HBM stride: each token has H_kv heads x kPackedBytesPerToken bytes.
        // Offset to this token's bidh head's bytes:
        //   gmem_base + global_t * H_kv * kPackedBytesPerToken + bidh * kPackedBytesPerToken
        // gmem_k_packed_base already includes the batch offset; we add the
        // (token, head) offset here.
        const uint8_t *gmem_src = gmem_k_packed_base
            + global_t * H_kv * kPackedBytesPerToken
            + bidh * kPackedBytesPerToken;
        #pragma unroll
        for (int b = 0; b < kPackedBytesPerToken; b += 16) {
            uint4 v = __ldg(reinterpret_cast<const uint4*>(gmem_src + b));
            *reinterpret_cast<uint4*>(smem_dst + b) = v;
        }
    }

    // -----------------------------------------------------------------
    // Phase B: cooperative load scales (n_groups_per_block * kHeadDim).
    // -----------------------------------------------------------------
    {
        const int n_groups_total = S_max / kGroupSize;
        const int g_base         = n_block_token_start / kGroupSize;
        for (int i = tidx; i < kNGroupsPerBlock * kHeadDim; i += nthreads) {
            const int g = i / kHeadDim;
            const int d = i % kHeadDim;
            const int global_g = g_base + g;
            Element val = Element(0);
            if (global_g >= 0 && global_g < n_groups_total) {
                // (B, n_groups_total, H_kv, D) layout.
                val = gmem_k_scale_base[global_g * H_kv * kHeadDim + bidh * kHeadDim + d];
            }
            smem.k_scale[g * kHeadDim + d] = val;
        }
    }

    // -----------------------------------------------------------------
    // Phase C: cooperative load xmins (same shape/layout as scales).
    // -----------------------------------------------------------------
    {
        const int n_groups_total = S_max / kGroupSize;
        const int g_base         = n_block_token_start / kGroupSize;
        for (int i = tidx; i < kNGroupsPerBlock * kHeadDim; i += nthreads) {
            const int g = i / kHeadDim;
            const int d = i % kHeadDim;
            const int global_g = g_base + g;
            Element val = Element(0);
            if (global_g >= 0 && global_g < n_groups_total) {
                val = gmem_k_xmin_base[global_g * H_kv * kHeadDim + bidh * kHeadDim + d];
            }
            smem.k_xmin[g * kHeadDim + d] = val;
        }
    }

    // -----------------------------------------------------------------
    // Phase D: cooperative load protect_bf16 (kBlockN * n_protect).
    // -----------------------------------------------------------------
    if (n_protect > 0) {
        for (int i = tidx; i < kBlockN * n_protect; i += nthreads) {
            const int t = i / n_protect;
            const int slot = i % n_protect;
            const int global_t = n_block_token_start + t;
            Element val = Element(0);
            if (global_t >= 0 && global_t < s_curr) {
                // (B, S_max, H_kv, n_protect) layout.
                val = gmem_k_protect_base[global_t * H_kv * n_protect + bidh * n_protect + slot];
            }
            smem.k_protect[t * kMaxNProtect + slot] = val;
        }
    }

    // -----------------------------------------------------------------
    // Phase E: cooperative load protect_slot for bidh (kHeadDim bytes).
    // gmem_protect_slot_base is already at bidh's row start.
    // -----------------------------------------------------------------
    for (int d = tidx; d < kHeadDim; d += nthreads) {
        smem.protect_slot[d] = gmem_protect_slot_base[d];
    }

    __syncthreads();  // All loads visible.

    // -----------------------------------------------------------------
    // Phase F: per-thread fragment iterate — unpack + dequant + blend,
    //          write BF16 to tKsK (the smem K tile the GEMM consumes).
    // -----------------------------------------------------------------
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

                Element x_hat;
                int8_t slot = smem.protect_slot[d];
                if (slot >= 0 && slot < n_protect) {
                    // Protected channel: read from compact BF16 sidecar.
                    x_hat = smem.k_protect[n * kMaxNProtect + slot];
                } else {
                    // Unprotected: unpack INT4 + dequant per route-B convention.
                    uint8_t byte = smem.k_packed[n * kPackedBytesPerToken + (d >> 1)];
                    uint8_t nibble = (d & 1) ? ((byte >> 4) & 0x0F) : (byte & 0x0F);
                    int g = n / kGroupSize;
                    float scale = int4_inline_to_float<Element>(smem.k_scale[g * kHeadDim + d]);
                    float xmin  = int4_inline_to_float<Element>(smem.k_xmin[g * kHeadDim + d]);
                    float x     = static_cast<float>(nibble) * scale + xmin;
                    x_hat = int4_inline_from_float<Element>(x);
                }
                tKsK(i0, i1, i2) = x_hat;
            }
        }
    }
    // No exit sync — caller adds __syncthreads() before the GEMM
    // consumes the modified sK.
}

}  // namespace FLASH_NAMESPACE
"""


def patch_int4_packed_load_h(path: Path) -> None:
    if path.exists():
        existing = path.read_text()
        if existing == INT4_PACKED_LOAD_H_CONTENT:
            print(f"  SKIP (already up to date): {path}")
            return
        if "int4_packed_load_K_block" in existing:
            print(f"  REWRITE (content drift): {path}")
            path.write_text(INT4_PACKED_LOAD_H_CONTENT)
            return
        raise RuntimeError(
            f"{path} exists but doesn't contain Phase 2.4.1b helper — "
            "refusing to overwrite a foreign file"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(INT4_PACKED_LOAD_H_CONTENT)
    print(f"  CREATED: {path}")


# ============================================================
# Patch 2: NEW file flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu
# ============================================================

NEW_CU_CONTENT = """// 6c.3C Phase 2.4.1b — packed-K dispatch instantiation for Qwen2.5-7B.
// Auto-picked by the flash_fwd_*.cu glob in CMakeLists. Mirrors the
// Phase 2.1 _int4kv .cu file; differs only by calling the _packed
// dispatch variant which instantiates the kernel with
// Is_int4kv_packed=true.
#include "namespace_config.h"
#include "flash_fwd_launch_template.h"

namespace FLASH_NAMESPACE {

template void run_mha_fwd_splitkv_dispatch_int4kv_packed<cutlass::bfloat16_t, 128, false>(
    Flash_fwd_params &params, cudaStream_t stream);

} // namespace FLASH_NAMESPACE
"""


def patch_new_cu(path: Path) -> None:
    if path.exists():
        print(f"  SKIP (already exists): {path}")
        return
    path.write_text(NEW_CU_CONTENT)
    print(f"  CREATED: {path}")


# ============================================================
# Patch 3: flash.h — forward decl for new dispatch
# ============================================================

FLASH_H_FWD_DECL_OLD = (
    "template<typename T, int Headdim, bool Is_causal> void "
    "run_mha_fwd_splitkv_dispatch_int4kv(Flash_fwd_params &params, cudaStream_t stream);  // 6c.3C Phase 2.2"
)
FLASH_H_FWD_DECL_NEW = (
    FLASH_H_FWD_DECL_OLD
    + "\ntemplate<typename T, int Headdim, bool Is_causal> void "
    "run_mha_fwd_splitkv_dispatch_int4kv_packed(Flash_fwd_params &params, cudaStream_t stream);  // 6c.3C Phase 2.4.1b"
)


def patch_flash_h(path: Path) -> None:
    src = path.read_text()
    if "run_mha_fwd_splitkv_dispatch_int4kv_packed" in src:
        print(f"  SKIP (already patched): {path}")
        return
    if FLASH_H_FWD_DECL_OLD not in src:
        raise RuntimeError(
            f"can't find Phase 2.2 _int4kv fwd decl anchor in {path}"
        )
    src = src.replace(FLASH_H_FWD_DECL_OLD, FLASH_H_FWD_DECL_NEW, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 4: flash_fwd_launch_template.h — template plumbing + dispatch arm
# ============================================================

KERNEL_DEFINE_OLD = '''DEFINE_FLASH_FORWARD_KERNEL(flash_fwd_splitkv_kernel, bool Is_causal, bool Is_local, bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, bool Split, bool Append_KV, bool Is_int4kv) {  // 6c.3C Phase 2.5: + Is_int4kv
    #if defined(ARCH_SUPPORTS_FLASH)
        FLASH_NAMESPACE::compute_attn_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv>(params);
    #else
        FLASH_UNSUPPORTED_ARCH
    #endif
}'''

KERNEL_DEFINE_NEW = '''DEFINE_FLASH_FORWARD_KERNEL(flash_fwd_splitkv_kernel, bool Is_causal, bool Is_local, bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, bool Split, bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed) {  // 6c.3C Phase 2.4.1b: + Is_int4kv_packed
    #if defined(ARCH_SUPPORTS_FLASH)
        FLASH_NAMESPACE::compute_attn_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed>(params);
    #else
        FLASH_UNSUPPORTED_ARCH
    #endif
}'''


RUN_SPLITKV_FWD_TEMPLATE_OLD = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_int4kv = false>  "
    "// 6c.3C Phase 2.5: + Is_int4kv\n"
    "void run_flash_splitkv_fwd(Flash_fwd_params &params, cudaStream_t stream) {"
)
RUN_SPLITKV_FWD_TEMPLATE_NEW = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_int4kv = false, bool Is_int4kv_packed = false>  "
    "// 6c.3C Phase 2.4.1b: + Is_int4kv_packed\n"
    "void run_flash_splitkv_fwd(Flash_fwd_params &params, cudaStream_t stream) {"
)

KERNEL_INSTANTIATION_OLD = (
    "auto kernel = &flash_fwd_splitkv_kernel<Kernel_traits, Is_causal, "
    "Is_local && !Is_causal, Has_alibi, IsEvenMNConst && !Append_KV && "
    "IsEvenKConst && !Is_local && Kernel_traits::kHeadDim <= 128, "
    "IsEvenKConst, Is_softcap, Split, Append_KV, Is_int4kv>;  "
    "// 6c.3C Phase 2.5: + Is_int4kv"
)
KERNEL_INSTANTIATION_NEW = (
    "auto kernel = &flash_fwd_splitkv_kernel<Kernel_traits, Is_causal, "
    "Is_local && !Is_causal, Has_alibi, IsEvenMNConst && !Append_KV && "
    "IsEvenKConst && !Is_local && Kernel_traits::kHeadDim <= 128, "
    "IsEvenKConst, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed>;  "
    "// 6c.3C Phase 2.4.1b: + Is_int4kv_packed"
)


DISPATCH_INT4KV_PACKED = """
// 6c.3C Phase 2.4.1b: packed-K dispatch. Routes to the kernel template
// instantiated with Is_int4kv_packed=true, which (when wired up at the
// K-load sites in flash_fwd_kernel.h) calls int4_packed_load_K_block
// instead of the Phase 2.3 in-register quant. The instantiation file
// is flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu.
template<typename T, int Headdim, bool Is_causal>
void run_mha_fwd_splitkv_dispatch_int4kv_packed(Flash_fwd_params &params, cudaStream_t stream) {
    constexpr static int kBlockM = 64;
    constexpr static int kBlockN = Headdim <= 64 ? 256 : (Headdim <= 128 ? 128 : 64);
    run_flash_splitkv_fwd<Flash_fwd_kernel_traits<Headdim, kBlockM, kBlockN, 4, false, false, T>, Is_causal, /*Is_int4kv=*/true, /*Is_int4kv_packed=*/true>(params, stream);
}
"""

DISPATCH_ANCHOR = """// 6c.3C Phase 2.1: INT4 KV dispatch.
// 6c.3C Phase 2.5: routes to Is_int4kv=true template specialization.
// This is what enables template-gating — the kernel instantiation
// reached from here carries the INT4 scratchpad and transform; the
// stock dispatch path (run_mha_fwd_splitkv_dispatch) defaults to
// Is_int4kv=false and gets the un-instrumented kernel binary.
// Instantiation file: flash_fwd_split_hdim128_bf16_int4kv_sm80.cu.
template<typename T, int Headdim, bool Is_causal>
void run_mha_fwd_splitkv_dispatch_int4kv(Flash_fwd_params &params, cudaStream_t stream) {
    constexpr static int kBlockM = 64;
    constexpr static int kBlockN = Headdim <= 64 ? 256 : (Headdim <= 128 ? 128 : 64);
    run_flash_splitkv_fwd<Flash_fwd_kernel_traits<Headdim, kBlockM, kBlockN, 4, false, false, T>, Is_causal, /*Is_int4kv=*/true>(params, stream);
}"""


def _exactly_once(src: str, needle: str, label: str) -> None:
    count = src.count(needle)
    if count == 0:
        raise RuntimeError(
            f"anchor '{label}' not found — Phase 2.1/2.2/2.5/2.4.1a must be applied"
        )
    if count > 1:
        raise RuntimeError(f"anchor '{label}' matches {count} times — not unique")


def patch_flash_fwd_launch_template_h(path: Path) -> None:
    src = path.read_text()
    if "run_mha_fwd_splitkv_dispatch_int4kv_packed" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, KERNEL_DEFINE_OLD, "Phase 2.5 flash_fwd_splitkv_kernel DEFINE")
    src = src.replace(KERNEL_DEFINE_OLD, KERNEL_DEFINE_NEW, 1)

    _exactly_once(src, RUN_SPLITKV_FWD_TEMPLATE_OLD, "Phase 2.5 run_flash_splitkv_fwd template")
    src = src.replace(RUN_SPLITKV_FWD_TEMPLATE_OLD, RUN_SPLITKV_FWD_TEMPLATE_NEW, 1)

    _exactly_once(src, KERNEL_INSTANTIATION_OLD, "Phase 2.5 kernel instantiation")
    src = src.replace(KERNEL_INSTANTIATION_OLD, KERNEL_INSTANTIATION_NEW, 1)

    _exactly_once(src, DISPATCH_ANCHOR, "Phase 2.5 _int4kv dispatch (anchor for inserting _packed after)")
    src = src.replace(DISPATCH_ANCHOR, DISPATCH_ANCHOR + "\n" + DISPATCH_INT4KV_PACKED, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 5: flash_api.cpp — run_mha_fwd routes to _packed dispatch + assert
# ============================================================

API_RUN_DISPATCH_OLD = """                    // 6c.3C Phase 2.2: route to _int4kv dispatch only at the v1-
                    // supported instantiation (bf16/hdim128/non-causal). Other
                    // shapes fall back to stock — the _int4kv dispatch isn't
                    // instantiated for them yet (v1 scope is Qwen2.5-7B only).
                    if constexpr (std::is_same_v<elem_type, cutlass::bfloat16_t> && kHeadDim == 128 && !Is_causal) {
                        if (params.is_int4kv) {
                            run_mha_fwd_splitkv_dispatch_int4kv<elem_type, kHeadDim, Is_causal>(params, stream);
                        } else {
                            run_mha_fwd_splitkv_dispatch<elem_type, kHeadDim, Is_causal>(params, stream);
                        }
                    } else {
                        run_mha_fwd_splitkv_dispatch<elem_type, kHeadDim, Is_causal>(params, stream);
                    }"""

API_RUN_DISPATCH_NEW = """                    // 6c.3C Phase 2.4.1b: three-way dispatch on packed > int4 > stock.
                    // packed > int4kv: Phase 2.4.1a sets params.is_int4kv_packed
                    // iff all 5 packed pointers are non-null AND the caller
                    // passed the new packed_* kwargs. Otherwise fall through
                    // to the Phase 2.2 _int4kv path (in-register quant on
                    // BF16 K) when params.is_int4kv is set, else stock.
                    if constexpr (std::is_same_v<elem_type, cutlass::bfloat16_t> && kHeadDim == 128 && !Is_causal) {
                        if (params.is_int4kv_packed) {
                            // Runtime guard: kMaxNProtect = 8 compile-time bound.
                            // Caller (Python) must pass packed_n_protect <= 8.
                            TORCH_CHECK(params.packed_n_protect <= 8,
                                "Phase 2.4.1b: packed_n_protect=", params.packed_n_protect,
                                " exceeds compile-time kMaxNProtect=8. ",
                                "Default protect_fraction=0.04 -> n_protect=5 is fine. ",
                                "Safe-mode 0.08 -> n_protect=10 requires rebuilding with ",
                                "kMaxNProtect=16 (see KERNEL_6C3C_PHASE2_4_1B_DESIGN_QUESTIONS.md Q1).");
                            run_mha_fwd_splitkv_dispatch_int4kv_packed<elem_type, kHeadDim, Is_causal>(params, stream);
                        } else if (params.is_int4kv) {
                            run_mha_fwd_splitkv_dispatch_int4kv<elem_type, kHeadDim, Is_causal>(params, stream);
                        } else {
                            run_mha_fwd_splitkv_dispatch<elem_type, kHeadDim, Is_causal>(params, stream);
                        }
                    } else {
                        run_mha_fwd_splitkv_dispatch<elem_type, kHeadDim, Is_causal>(params, stream);
                    }"""


def patch_flash_api_cpp(path: Path) -> None:
    src = path.read_text()
    if "run_mha_fwd_splitkv_dispatch_int4kv_packed" in src:
        print(f"  SKIP (already patched): {path}")
        return
    _exactly_once(src, API_RUN_DISPATCH_OLD, "Phase 2.2 dispatch branch in run_mha_fwd")
    src = src.replace(API_RUN_DISPATCH_OLD, API_RUN_DISPATCH_NEW, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 6: flash_fwd_kernel.h — template plumbing + smem alloc + K-load wiring
# ============================================================

INCLUDE_OLD = '''#include "int4_inline.h"  // 6c.3C Phase 2.3 NO-OP INT4 transform on K'''

INCLUDE_NEW = '''#include "int4_inline.h"        // 6c.3C Phase 2.3 NO-OP INT4 transform on K
#include "int4_packed_load.h"   // 6c.3C Phase 2.4.1b packed-K HBM load helper'''


ROWBLOCK_TEMPLATE_OLD = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_local, "
    "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, "
    "bool Split, bool Append_KV, bool Is_int4kv, typename Params>  "
    "// 6c.3C Phase 2.5: + Is_int4kv\n"
    "inline __device__ void compute_attn_1rowblock_splitkv("
)
ROWBLOCK_TEMPLATE_NEW = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_local, "
    "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, "
    "bool Split, bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed, typename Params>  "
    "// 6c.3C Phase 2.4.1b: + Is_int4kv_packed\n"
    "inline __device__ void compute_attn_1rowblock_splitkv("
)


COMPUTE_SPLITKV_TEMPLATE_OLD = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_local, "
    "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, "
    "bool Split, bool Append_KV, bool Is_int4kv, typename Params>  "
    "// 6c.3C Phase 2.5: + Is_int4kv\n"
    "inline __device__ void compute_attn_splitkv("
)
COMPUTE_SPLITKV_TEMPLATE_NEW = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_local, "
    "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, "
    "bool Split, bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed, typename Params>  "
    "// 6c.3C Phase 2.4.1b: + Is_int4kv_packed\n"
    "inline __device__ void compute_attn_splitkv("
)

COMPUTE_SPLITKV_CALL_OLD = (
    "    FLASH_NAMESPACE::compute_attn_1rowblock_splitkv<Kernel_traits, "
    "Is_causal, Is_local, Has_alibi, Is_even_MN, Is_even_K, Is_softcap, "
    "Split, Append_KV, Is_int4kv>(params, bidb, bidh, m_block, n_split_idx, "
    "num_n_splits);  // 6c.3C Phase 2.5: + Is_int4kv"
)
COMPUTE_SPLITKV_CALL_NEW = (
    "    FLASH_NAMESPACE::compute_attn_1rowblock_splitkv<Kernel_traits, "
    "Is_causal, Is_local, Has_alibi, Is_even_MN, Is_even_K, Is_softcap, "
    "Split, Append_KV, Is_int4kv, Is_int4kv_packed>(params, bidb, bidh, m_block, n_split_idx, "
    "num_n_splits);  // 6c.3C Phase 2.4.1b: + Is_int4kv_packed"
)


SMEM_ALLOC_OLD = """    // 6c.3C Phase 2.5: template-gated INT4 scratchpad. When Is_int4kv=false
    // (stock FA), OptionalInt4Scratch primary template is empty (1 byte
    // smem, no occupancy hit). When Is_int4kv=true, the partial
    // specialization gives a `data` array sized for max/min scratch.
    constexpr int kInt4GroupSize = 32;
    constexpr int kInt4ScratchFloats =
        2 * (Kernel_traits::kBlockN / kInt4GroupSize) * Kernel_traits::kHeadDim;
    __shared__ FLASH_NAMESPACE::OptionalInt4Scratch<Is_int4kv, kInt4ScratchFloats> smem_int4_box;

    // 6c.3C Phase 4: per-(bidb, bidh) slice of the (B, H_kv, D) int8 protect
    // mask. NULL when no mask is supplied (Phase 2.3/3 unprotected behavior).
    // Mask layout: byte-per-channel, 1 = protected (skip quant), 0 = quantize.
    // Computed only in the Is_int4kv specialization; defaults to nullptr in
    // the stock kernel variant so the helper short-circuits.
    const int8_t *k_protect_mask_local = nullptr;
    if constexpr (Is_int4kv) {
        if (params.k_cache_protect_mask_ptr != nullptr) {
            k_protect_mask_local =
                reinterpret_cast<const int8_t*>(params.k_cache_protect_mask_ptr)
                + bidb * params.h_k * params.d
                + bidh * params.d;
        }
    }"""

SMEM_ALLOC_NEW = """    // 6c.3C Phase 2.5: template-gated INT4 scratchpad. Stays allocated
    // when Is_int4kv=true regardless of Is_int4kv_packed because the
    // V transform (Phase 3 in-register quant) uses it on BOTH paths
    // (V is NOT packed in Phase 2.4; packing V is Phase 2.6). On the
    // packed K path the K transform doesn't use it but V does.
    constexpr int kInt4GroupSize = 32;
    constexpr int kInt4ScratchFloats =
        2 * (Kernel_traits::kBlockN / kInt4GroupSize) * Kernel_traits::kHeadDim;
    __shared__ FLASH_NAMESPACE::OptionalInt4Scratch<Is_int4kv, kInt4ScratchFloats> smem_int4_box;

    // 6c.3C Phase 2.4.1b: template-gated packed-K scratchpad. Empty struct
    // when Is_int4kv_packed=false. When true, ~12 KB at Qwen2.5-7B target.
    constexpr int kPackedMaxNProtect = 8;  // upper bound on n_protect for compile-time alloc
    __shared__ FLASH_NAMESPACE::OptionalPackedScratch<
        Is_int4kv_packed,
        Kernel_traits::kBlockN, Kernel_traits::kHeadDim,
        kInt4GroupSize, kPackedMaxNProtect,
        typename Kernel_traits::Element> smem_packed_box;

    // 6c.3C Phase 4: per-(bidb, bidh) slice of the (B, H_kv, D) int8 protect
    // mask. NULL when no mask is supplied (Phase 2.3/3 unprotected behavior).
    // Only the K transform consumes this; on the packed K path the K transform
    // is replaced and this variable stays nullptr (harmless).
    const int8_t *k_protect_mask_local = nullptr;
    if constexpr (Is_int4kv && !Is_int4kv_packed) {
        if (params.k_cache_protect_mask_ptr != nullptr) {
            k_protect_mask_local =
                reinterpret_cast<const int8_t*>(params.k_cache_protect_mask_ptr)
                + bidb * params.h_k * params.d
                + bidh * params.d;
        }
    }

    // 6c.3C Phase 2.4.1b: per-(bidb, bidh) HBM base pointers for the
    // packed-K side channel. Computed once at function entry; passed
    // to the helper at each K-load site.
    using PackedElement = typename Kernel_traits::Element;
    const uint8_t      *gmem_k_packed_base       = nullptr;
    const PackedElement *gmem_k_scale_base        = nullptr;
    const PackedElement *gmem_k_xmin_base         = nullptr;
    const PackedElement *gmem_k_protect_base      = nullptr;
    const int8_t       *gmem_protect_slot_base   = nullptr;
    int                 packed_n_protect         = 0;
    if constexpr (Is_int4kv_packed) {
        gmem_k_packed_base      = reinterpret_cast<const uint8_t*>(params.k_packed_int4_ptr)
                                  + bidb * params.seqlen_k * params.h_k * (params.d / 2);
        gmem_k_scale_base       = reinterpret_cast<const PackedElement*>(params.k_packed_scale_ptr)
                                  + bidb * (params.seqlen_k / kInt4GroupSize) * params.h_k * params.d;
        gmem_k_xmin_base        = reinterpret_cast<const PackedElement*>(params.k_packed_xmin_ptr)
                                  + bidb * (params.seqlen_k / kInt4GroupSize) * params.h_k * params.d;
        packed_n_protect        = params.packed_n_protect;
        gmem_k_protect_base     = reinterpret_cast<const PackedElement*>(params.k_packed_protect_bf16_ptr)
                                  + bidb * params.seqlen_k * params.h_k * packed_n_protect;
        gmem_protect_slot_base  = reinterpret_cast<const int8_t*>(params.k_packed_protect_slot_ptr)
                                  + bidh * params.d;
    }"""


MASKING_CALL_OLD = """        // 6c.3C Phase 2.5/4: template-gated INT4 transform on K with optional
        // protect-K mask. The mask pointer is non-null only when the caller
        // supplied protect_mask=; protected channels skip quant and keep
        // their original BF16 smem value.
        if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data, k_protect_mask_local);
            __syncthreads();
        }"""

MASKING_CALL_NEW = """        // 6c.3C Phase 2.4.1b: packed-K HBM load path. Mutually exclusive
        // with Phase 2.5 in-register quant via the template gate.
        if constexpr (Is_int4kv_packed && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_packed_load_K_block<
                Kernel_traits, kInt4GroupSize, kPackedMaxNProtect>(
                tKsK, tKVcKV, smem_packed_box,
                gmem_k_packed_base, gmem_k_scale_base, gmem_k_xmin_base,
                gmem_k_protect_base, gmem_protect_slot_base,
                bidh, params.seqlen_k, params.h_k, packed_n_protect,
                n_block * Kernel_traits::kBlockN, params.seqlen_k);
            __syncthreads();
        } else if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            // 6c.3C Phase 2.5/4: in-register quant on cp.async-loaded BF16 K.
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data, k_protect_mask_local);
            __syncthreads();
        }"""


NONMASKING_CALL_OLD = """        // 6c.3C Phase 2.5/4: template-gated INT4 transform on K with
        // optional protect-K mask.
        if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data, k_protect_mask_local);
            __syncthreads();
        }"""

NONMASKING_CALL_NEW = """        // 6c.3C Phase 2.4.1b: packed-K HBM load (non-masking loop).
        if constexpr (Is_int4kv_packed && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_packed_load_K_block<
                Kernel_traits, kInt4GroupSize, kPackedMaxNProtect>(
                tKsK, tKVcKV, smem_packed_box,
                gmem_k_packed_base, gmem_k_scale_base, gmem_k_xmin_base,
                gmem_k_protect_base, gmem_protect_slot_base,
                bidh, params.seqlen_k, params.h_k, packed_n_protect,
                n_block * Kernel_traits::kBlockN, params.seqlen_k);
            __syncthreads();
        } else if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data, k_protect_mask_local);
            __syncthreads();
        }"""


def patch_flash_fwd_kernel_h(path: Path) -> None:
    src = path.read_text()
    if "Is_int4kv_packed" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, INCLUDE_OLD, "Phase 2.3 int4_inline.h include")
    src = src.replace(INCLUDE_OLD, INCLUDE_NEW, 1)

    _exactly_once(src, ROWBLOCK_TEMPLATE_OLD, "Phase 2.5 compute_attn_1rowblock_splitkv template")
    src = src.replace(ROWBLOCK_TEMPLATE_OLD, ROWBLOCK_TEMPLATE_NEW, 1)

    _exactly_once(src, COMPUTE_SPLITKV_TEMPLATE_OLD, "Phase 2.5 compute_attn_splitkv template")
    src = src.replace(COMPUTE_SPLITKV_TEMPLATE_OLD, COMPUTE_SPLITKV_TEMPLATE_NEW, 1)

    _exactly_once(src, COMPUTE_SPLITKV_CALL_OLD, "Phase 2.5 compute_attn_splitkv -> 1rowblock call")
    src = src.replace(COMPUTE_SPLITKV_CALL_OLD, COMPUTE_SPLITKV_CALL_NEW, 1)

    _exactly_once(src, SMEM_ALLOC_OLD, "Phase 2.5/4 smem alloc + protect mask slice")
    src = src.replace(SMEM_ALLOC_OLD, SMEM_ALLOC_NEW, 1)

    _exactly_once(src, MASKING_CALL_OLD, "Phase 2.5/4 masking-loop K helper call")
    src = src.replace(MASKING_CALL_OLD, MASKING_CALL_NEW, 1)

    _exactly_once(src, NONMASKING_CALL_OLD, "Phase 2.5/4 non-masking-loop K helper call")
    src = src.replace(NONMASKING_CALL_OLD, NONMASKING_CALL_NEW, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Main
# ============================================================

def main() -> int:
    if not DEV_ROOT.exists():
        print(f"ERROR: dev tree not at {DEV_ROOT}", file=sys.stderr)
        return 1

    targets = [
        (DEV_ROOT / "csrc/flash_attn/src/int4_packed_load.h",
         patch_int4_packed_load_h),
        (DEV_ROOT / "csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu",
         patch_new_cu),
        (DEV_ROOT / "csrc/flash_attn/src/flash.h",
         patch_flash_h),
        (DEV_ROOT / "csrc/flash_attn/src/flash_fwd_launch_template.h",
         patch_flash_fwd_launch_template_h),
        (DEV_ROOT / "csrc/flash_attn/flash_api.cpp",
         patch_flash_api_cpp),
        (DEV_ROOT / "csrc/flash_attn/src/flash_fwd_kernel.h",
         patch_flash_fwd_kernel_h),
    ]
    print("Applying Phase 2.4.1b patches:")
    for path, fn in targets:
        try:
            fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR on {path}: {e}", file=sys.stderr)
            return 1
    print()
    print("Patches applied. Rebuild + reinstall + verify next.")
    print("  flash_fwd_kernel.h + flash_fwd_launch_template.h modified —")
    print("  ALL splitkv .cu TUs recompile. Plus the new")
    print("  flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu builds.")
    print("  Expect ~12-15 min cold-cache or ~8-10 min warm.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
