#!/usr/bin/env python3
"""apply_phase3_patches.py — 6c.3C Phase 3: INT4 NO-OP transform on V.

Mirrors Phase 2.3 for V. Key axis difference:
  - K is per-CHANNEL quantized (group along seq, kGroupSize=32 across
    kBlockN dimension; each group produces one scale per head_dim
    position).
  - V is per-TOKEN quantized (group along head_dim, kGroupSize=32
    across kHeadDim dimension; each (token, group) produces one scale).

Per kv_policy/int4_per_channel_kv.py::quantize_per_token_int4 (asym path):
    x_max = group_max(V)                       # max over d in group
    x_min = group_min(V)
    scale = fmaxf((x_max - x_min) / 15.0f, 1e-8f)
    q_unsigned = clamp(__float2int_rn((x - x_min) / scale), 0, 15)
    x_hat = q_unsigned * scale + x_min

Same arithmetic and rounding convention as K; different slot indexing
in the smem scratchpad:
  - K slots:  slot = (n / kGroupSize) * kHeadDim + d   ; n_slots = (kBlockN/kGroupSize) * kHeadDim
  - V slots:  slot = n * (kHeadDim / kGroupSize) + (d / kGroupSize)
                                                       ; n_slots = kBlockN * (kHeadDim/kGroupSize)

At the Qwen2.5-7B target (kBlockN=128, kHeadDim=128, kGroupSize=32),
both have 512 slots * 2 (max/min) = 1024 floats = 4 KB. So K and V
SHARE the same Phase 2.5-allocated `smem_int4_box.data` buffer.
Sequential usage (K transform at K-wait, V transform at V-wait, separated
by the qK gemm) means they don't conflict.

Files modified (in /workspace/dev/vllm-flash-attn-dev):
  - csrc/flash_attn/src/int4_inline.h:
      add `int4_quant_dequant_V_block_inplace` helper.
  - csrc/flash_attn/src/flash_fwd_kernel.h:
      a) Masking-loop V-wait insertion: between `cp_async_wait<0>() +
         __syncthreads()` and the `// print(tVsV)` comment that
         precedes the next-K cp.async block.
      b) Non-masking-loop V-wait insertion: between `cp_async_wait<0>()
         + __syncthreads()` and `if (n_block > n_block_min) {`.

Idempotent. Re-run = no-op.

Acceptance:
  - verify_phase3.py (new): both K and V transforms fire. Compares
    flash_attn_with_int4_kvcache to flash_attn_with_kvcache; gate is
    cosine >= 0.985 (lower than Phase 2.3's 0.995 because V quantization
    adds drift on top of K quantization). The diagnostic equivalent for
    V — running the route-B PyTorch reference for both K AND V on the
    same input — gives the expected algorithm floor.
  - verify_phase2_3.py still passes (K-only path doesn't change; the
    runtime gate is now redundant since template selects).
  - smoke_test_fa_install.sh stock-FA path stays at ~67 us baseline
    (Is_int4kv=false template specialization unchanged from Phase 2.5).

Prerequisites: Phase 2.3 + Phase 2.5 must be applied first.
"""

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1: int4_inline.h — add V transform helper
# ============================================================
#
# The anchor is the END of the K helper (last `}` of
# int4_quant_dequant_K_block_inplace, plus blank line) so we can insert
# the V helper right after it.

V_HELPER_INSERT_OLD = """    // No exit sync — caller adds __syncthreads() before the GEMM that
    // consumes the modified smem K.
}

}  // namespace FLASH_NAMESPACE
"""

V_HELPER_INSERT_NEW = """    // No exit sync — caller adds __syncthreads() before the GEMM that
    // consumes the modified smem K.
}

////////////////////////////////////////////////////////////////////////////////
// int4_quant_dequant_V_block_inplace — Phase 3 sibling of the K helper.
//
// V is per-TOKEN quantized (group along head_dim), unlike K which is
// per-CHANNEL (group along seq). The reduction axis flips: for each
// (n, g_d) pair where g_d in [0, kHeadDim/kGroupSize), compute max/min
// over the 32 head_dim positions in that group, for the specific token
// n.
//
// Slot indexing in the smem scratchpad differs from K:
//   K slot = (n / kGroupSize) * kHeadDim + d
//   V slot = n * (kHeadDim / kGroupSize) + (d / kGroupSize)
// Total slot count is kBlockN * (kHeadDim / kGroupSize) — equals K's
// allocation at kBlockN==kHeadDim (the Qwen2.5-7B target), so K and V
// share the same scratchpad buffer (sequential lifetime — K transforms
// at K-wait, V transforms at V-wait, with qK gemm between).
//
// Same rounding convention and FP32 arithmetic as the K helper; the only
// numerical difference is the per-(n, group_d) scale/min vs per-(group_n,
// d) scale/min.
////////////////////////////////////////////////////////////////////////////////

template <typename Kernel_traits, int kGroupSize,
          typename EngineV, typename LayoutV,
          typename EngineC, typename LayoutC>
__device__ __forceinline__ void int4_quant_dequant_V_block_inplace(
    cute::Tensor<EngineV, LayoutV> &tVsV,
    cute::Tensor<EngineC, LayoutC> const &tKVcKV,
    float *smem_scratch) {

    using Element = typename Kernel_traits::Element;
    constexpr int kBlockN  = Kernel_traits::kBlockN;
    constexpr int kHeadDim = Kernel_traits::kHeadDim;
    static_assert(kHeadDim % kGroupSize == 0,
                  "int4_quant_dequant_V_block_inplace requires kHeadDim % kGroupSize == 0");
    constexpr int kNVGroups = kHeadDim / kGroupSize;
    constexpr int kSlots    = kBlockN * kNVGroups;

    float *smem_max = smem_scratch;
    float *smem_min = smem_scratch + kSlots;

    const int tidx     = threadIdx.x;
    const int nthreads = blockDim.x;

    // Pass 0: init scratchpad slots to -inf / +inf.
    __syncthreads();
    #pragma unroll 1
    for (int i = tidx; i < kSlots; i += nthreads) {
        smem_max[i] = -INFINITY;
        smem_min[i] = +INFINITY;
    }
    __syncthreads();

    // Pass 1: stream the per-thread V fragment into the scratchpad.
    #pragma unroll
    for (int i0 = 0; i0 < size<0>(tVsV); ++i0) {
        #pragma unroll
        for (int i1 = 0; i1 < size<1>(tVsV); ++i1) {
            #pragma unroll
            for (int i2 = 0; i2 < size<2>(tVsV); ++i2) {
                auto coord = tKVcKV(i0, i1, i2);
                int n = int(cute::get<0>(coord));
                int d = int(cute::get<1>(coord));
                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;
                const int g = d / kGroupSize;        // group along head_dim
                const int slot = n * kNVGroups + g;
                const float x = int4_inline_to_float<Element>(tVsV(i0, i1, i2));
                int4_inline_atomic_max_float(&smem_max[slot], x);
                int4_inline_atomic_min_float(&smem_min[slot], x);
            }
        }
    }
    __syncthreads();

    // Pass 2: stream the per-thread V fragment again, computing
    // quant/dequant against the per-(n, group_d) (max, min) read from
    // the scratchpad.
    constexpr float kInvFifteen = 1.0f / 15.0f;
    constexpr float kScaleClamp = 1e-8f;
    #pragma unroll
    for (int i0 = 0; i0 < size<0>(tVsV); ++i0) {
        #pragma unroll
        for (int i1 = 0; i1 < size<1>(tVsV); ++i1) {
            #pragma unroll
            for (int i2 = 0; i2 < size<2>(tVsV); ++i2) {
                auto coord = tKVcKV(i0, i1, i2);
                int n = int(cute::get<0>(coord));
                int d = int(cute::get<1>(coord));
                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;
                const int g = d / kGroupSize;
                const int slot = n * kNVGroups + g;
                const float x_max = smem_max[slot];
                const float x_min = smem_min[slot];
                const float scale = fmaxf((x_max - x_min) * kInvFifteen, kScaleClamp);
                const float x = int4_inline_to_float<Element>(tVsV(i0, i1, i2));
                int q = __float2int_rn((x - x_min) / scale);
                q = max(0, min(15, q));
                const float x_hat = static_cast<float>(q) * scale + x_min;
                tVsV(i0, i1, i2) = int4_inline_from_float<Element>(x_hat);
            }
        }
    }
    // No exit sync — caller adds __syncthreads() before the GEMM that
    // consumes the modified smem V.
}

}  // namespace FLASH_NAMESPACE
"""


def patch_int4_inline_h_add_v_helper(path: Path) -> None:
    src = path.read_text()
    if "int4_quant_dequant_V_block_inplace" in src:
        print(f"  SKIP (already patched): {path}")
        return
    if V_HELPER_INSERT_OLD not in src:
        raise RuntimeError(
            f"can't find K-helper end anchor in {path} "
            "(Phase 2.3 must be applied first)"
        )
    src = src.replace(V_HELPER_INSERT_OLD, V_HELPER_INSERT_NEW, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 2: flash_fwd_kernel.h — V transform insertion at V-wait sites
# ============================================================

# --- 2a: masking-loop V-wait ---
# Distinguishing context: the V-wait is followed by a commented-out
# `print(tVsV)` debug line; the K-wait's Phase 2.5 transform block is
# right before the masking K-wait insertion. The unique anchor is the
# print(tVsV) comment.

MASKING_V_WAIT_OLD = """        FLASH_NAMESPACE::cp_async_wait<0>();
        __syncthreads();
        // if (tidx == 0 && blockIdx.y == 0 && blockIdx.z == 0) { print(tVsV); }
        // __syncthreads();

        if (n_block > n_block_min) {"""

MASKING_V_WAIT_NEW = """        FLASH_NAMESPACE::cp_async_wait<0>();
        __syncthreads();

        // 6c.3C Phase 3: template-gated INT4 transform on V (per-token
        // quant, group along head_dim). Same scratchpad as K (sequential
        // lifetime — K at K-wait, V at V-wait, separated by qK gemm).
        if constexpr (Is_int4kv && (Kernel_traits::kHeadDim % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_V_block_inplace<
                Kernel_traits, kInt4GroupSize>(tVsV, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }
        // if (tidx == 0 && blockIdx.y == 0 && blockIdx.z == 0) { print(tVsV); }
        // __syncthreads();

        if (n_block > n_block_min) {"""

# --- 2b: non-masking-loop V-wait ---
# Distinguishing context: V-wait is followed directly by
# `if (n_block > n_block_min)` (the next-K cp.async block) and then
# `// Advance gK`. The upstream file has trailing whitespace on lines
# inside this block that broke an earlier longer anchor, so we keep
# the anchor short and end before any whitespace-quirky lines.
# Phase 2.5 K-wait sites have Phase 2.5 transform code between
# __syncthreads() and `if (n_block > n_block_min)`, so this anchor
# uniquely matches the non-masking V-wait in the post-2.5 splitkv
# function (and is absent from compute_attn_1rowblock's similar pattern
# because that one's `if (n_block > n_block_min)` is followed directly
# by FLASH_NAMESPACE::copy, not `// Advance gK`).

NONMASKING_V_WAIT_OLD = """        FLASH_NAMESPACE::cp_async_wait<0>();
        __syncthreads();
        if (n_block > n_block_min) {
            // Advance gK
            if (block_table == nullptr) {
                tKgK.data() = tKgK.data() + (-int(kBlockN * params.k_row_stride));
            } else {"""

NONMASKING_V_WAIT_NEW = """        FLASH_NAMESPACE::cp_async_wait<0>();
        __syncthreads();
        // 6c.3C Phase 3: template-gated INT4 transform on V.
        if constexpr (Is_int4kv && (Kernel_traits::kHeadDim % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_V_block_inplace<
                Kernel_traits, kInt4GroupSize>(tVsV, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }
        if (n_block > n_block_min) {
            // Advance gK
            if (block_table == nullptr) {
                tKgK.data() = tKgK.data() + (-int(kBlockN * params.k_row_stride));
            } else {"""


def _exactly_once(src: str, needle: str, label: str) -> None:
    count = src.count(needle)
    if count == 0:
        raise RuntimeError(
            f"anchor '{label}' not found — Phase 2.3 + 2.5 must be applied first"
        )
    if count > 1:
        raise RuntimeError(
            f"anchor '{label}' matches {count} times — not unique"
        )


def patch_flash_fwd_kernel_h_v_transforms(path: Path) -> None:
    src = path.read_text()
    if "int4_quant_dequant_V_block_inplace" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, MASKING_V_WAIT_OLD, "masking-loop V-wait + print(tVsV) comment")
    src = src.replace(MASKING_V_WAIT_OLD, MASKING_V_WAIT_NEW, 1)

    _exactly_once(src, NONMASKING_V_WAIT_OLD, "non-masking-loop V-wait + next-K cp.async block")
    src = src.replace(NONMASKING_V_WAIT_OLD, NONMASKING_V_WAIT_NEW, 1)

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
        (DEV_ROOT / "csrc/flash_attn/src/int4_inline.h",
         patch_int4_inline_h_add_v_helper),
        (DEV_ROOT / "csrc/flash_attn/src/flash_fwd_kernel.h",
         patch_flash_fwd_kernel_h_v_transforms),
    ]

    print("Applying Phase 3 patches:")
    for path, fn in targets:
        try:
            fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR on {path}: {e}", file=sys.stderr)
            return 1

    print()
    print("Patches applied. Rebuild + reinstall + verify next.")
    print("  flash_fwd_kernel.h is included by every splitkv .cu (rebuild")
    print("  all ~14 splitkv TUs, ~8-12 min hot cache on sm80).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
