#!/usr/bin/env python3
"""apply_phase2_5_patches.py — 6c.3C Phase 2.5: template-gated INT4 dispatch.

Eliminates Phase 2.3's stock-FA perf regression by splitting the splitkv
kernel into stock and _int4kv compiled variants. Only the _int4kv
variant carries the INT4 scratchpad and transform body. Stock kernel
launches at the SAME smem footprint as pre-Phase-2.3 (~80 KB/block on
Qwen2.5-7B), restoring 2 blocks/SM occupancy on A100.

Mechanism:
  - Add `bool Is_int4kv = false` template parameter through the
    chain: run_flash_splitkv_fwd -> flash_fwd_splitkv_kernel ->
    compute_attn_splitkv -> compute_attn_1rowblock_splitkv.
  - run_mha_fwd_splitkv_dispatch (stock) keeps the default Is_int4kv=false.
    run_mha_fwd_splitkv_dispatch_int4kv passes Is_int4kv=true.
  - The Phase 2.3 smem allocation `__shared__ float smem_int4_scratch[1024]`
    becomes `__shared__ OptionalInt4Scratch<Is_int4kv, ...> smem_int4_box`
    via a conditional struct. When Is_int4kv=false, OptionalInt4Scratch
    is an empty struct (1 byte smem, no occupancy hit). When true, it
    holds the 4 KB scratch array.
  - The Phase 2.3 runtime gates `if (params.is_int4kv)` become
    `if constexpr (Is_int4kv)`. When false, the transform code doesn't
    compile in (no register pressure, no code bloat).

Files modified (in /workspace/dev/vllm-flash-attn-dev):
  - csrc/flash_attn/src/int4_inline.h:
      add OptionalInt4Scratch<bool Has, int kFloats> template struct.
  - csrc/flash_attn/src/flash_fwd_kernel.h:
      a) compute_attn_1rowblock_splitkv: add Is_int4kv template param.
      b) compute_attn_splitkv: add Is_int4kv template param, pass through.
      c) Phase 2.3 smem alloc -> OptionalInt4Scratch.
      d) Phase 2.3 runtime gates -> if constexpr (Is_int4kv).
  - csrc/flash_attn/src/flash_fwd_launch_template.h:
      a) flash_fwd_splitkv_kernel (DEFINE_FLASH_FORWARD_KERNEL): add
         Is_int4kv template param, pass through to compute_attn_splitkv.
      b) run_flash_splitkv_fwd: add Is_int4kv template param, pass to
         the kernel instantiation.
      c) run_mha_fwd_splitkv_dispatch_int4kv (Phase 2.1): call
         run_flash_splitkv_fwd<..., /*Is_int4kv=*/true>.

Idempotent: each patch checks a sentinel string. Re-run = no-op.

Acceptance:
  - verify_phase2_3.py STILL passes (cosine >= 0.995, max-abs <= 1e-2).
  - smoke_test_fa_install.sh stock FA p50 within ±10% of 2026-05-20
    baseline 67 us (Phase 2.3 had 80 us / +19.3% — Phase 2.5 should
    drop back to ~68-70 us).
  - Wheel size drops from ~208 MB to ~145 MB (helper body only
    instantiates in the _int4kv kernel variant now).
"""

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1: int4_inline.h — add OptionalInt4Scratch template
# ============================================================

OPTIONAL_SCRATCH_ANCHOR = '''namespace FLASH_NAMESPACE {

using namespace cute;'''

OPTIONAL_SCRATCH_ADDITION = '''namespace FLASH_NAMESPACE {

using namespace cute;

////////////////////////////////////////////////////////////////////////////////
// 6c.3C Phase 2.5: template-gated smem scratchpad for the INT4 transform.
//
// When the enclosing kernel template parameter Is_int4kv == false (stock
// FA path), the primary template specializes to an empty struct (1 byte
// smem, no occupancy hit). When Is_int4kv == true, the partial
// specialization gives us a `data[kFloats]` member sized for the
// transform's max/min scratch (typically 4 KB at kBlockN=128/kHeadDim=128).
//
// Empty struct ABI: sizeof(empty struct) == 1 in C++ standard so distinct
// instances have unique addresses. CUDA __shared__ allocates the 1 byte,
// which is negligible vs the 80 KB FA already uses.
////////////////////////////////////////////////////////////////////////////////

template <bool Has, int kFloats>
struct OptionalInt4Scratch {
    // Empty primary template — used when Has == false. data member is
    // absent so any access to it inside the kernel must be gated on
    // `if constexpr (Is_int4kv)` to avoid compile-time errors.
};

template <int kFloats>
struct OptionalInt4Scratch<true, kFloats> {
    float data[kFloats];
};'''


def patch_int4_inline_h_add_optional_scratch(path: Path) -> None:
    src = path.read_text()
    if "OptionalInt4Scratch" in src:
        print(f"  SKIP (already patched): {path}")
        return
    if OPTIONAL_SCRATCH_ANCHOR not in src:
        raise RuntimeError(
            f"can't find FLASH_NAMESPACE opening anchor in {path}"
        )
    src = src.replace(OPTIONAL_SCRATCH_ANCHOR, OPTIONAL_SCRATCH_ADDITION, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 2: flash_fwd_kernel.h
# ============================================================

# --- 2a: add Is_int4kv to compute_attn_1rowblock_splitkv template ---

ROWBLOCK_TEMPLATE_OLD = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_local, "
    "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, "
    "bool Split, bool Append_KV, typename Params>\n"
    "inline __device__ void compute_attn_1rowblock_splitkv("
)
ROWBLOCK_TEMPLATE_NEW = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_local, "
    "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, "
    "bool Split, bool Append_KV, bool Is_int4kv, typename Params>  "
    "// 6c.3C Phase 2.5: + Is_int4kv\n"
    "inline __device__ void compute_attn_1rowblock_splitkv("
)


# --- 2b: add Is_int4kv to compute_attn_splitkv (wrapper that calls 1rowblock) ---

COMPUTE_SPLITKV_TEMPLATE_OLD = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_local, "
    "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, "
    "bool Split, bool Append_KV, typename Params>\n"
    "inline __device__ void compute_attn_splitkv("
)
COMPUTE_SPLITKV_TEMPLATE_NEW = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_local, "
    "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, "
    "bool Split, bool Append_KV, bool Is_int4kv, typename Params>  "
    "// 6c.3C Phase 2.5: + Is_int4kv\n"
    "inline __device__ void compute_attn_splitkv("
)

# --- 2c: forward the Is_int4kv param at the compute_attn_splitkv -> compute_attn_1rowblock_splitkv call site ---

COMPUTE_SPLITKV_CALL_OLD = (
    "    FLASH_NAMESPACE::compute_attn_1rowblock_splitkv<Kernel_traits, "
    "Is_causal, Is_local, Has_alibi, Is_even_MN, Is_even_K, Is_softcap, "
    "Split, Append_KV>(params, bidb, bidh, m_block, n_split_idx, num_n_splits);"
)
COMPUTE_SPLITKV_CALL_NEW = (
    "    FLASH_NAMESPACE::compute_attn_1rowblock_splitkv<Kernel_traits, "
    "Is_causal, Is_local, Has_alibi, Is_even_MN, Is_even_K, Is_softcap, "
    "Split, Append_KV, Is_int4kv>(params, bidb, bidh, m_block, n_split_idx, "
    "num_n_splits);  // 6c.3C Phase 2.5: + Is_int4kv"
)


# --- 2d: replace Phase 2.3's static smem alloc with OptionalInt4Scratch ---
# This anchor was INSERTED by Phase 2.3's patcher. We modify it now.

SMEM_ALLOC_OLD_23 = """    // 6c.3C Phase 2.3: scratchpad for the NO-OP INT4 quant->dequant transform
    // on K. Used only when params.is_int4kv (runtime gate; uniform branch).
    // Static smem: 2 * (kBlockN / 32) * kHeadDim floats. At Qwen2.5-7B
    // shapes (kBlockN=128, kHeadDim=128) -> 4 KB. kInt4GroupSize must
    // divide kBlockN (asserted in int4_inline.h via static_assert).
    constexpr int kInt4GroupSize = 32;
    constexpr int kInt4ScratchFloats =
        2 * (Kernel_traits::kBlockN / kInt4GroupSize) * Kernel_traits::kHeadDim;
    __shared__ float smem_int4_scratch[kInt4ScratchFloats];"""

SMEM_ALLOC_NEW_25 = """    // 6c.3C Phase 2.5: template-gated INT4 scratchpad. When Is_int4kv=false
    // (stock FA), OptionalInt4Scratch primary template is empty (1 byte
    // smem, no occupancy hit). When Is_int4kv=true, the partial
    // specialization gives a `data` array sized for max/min scratch.
    constexpr int kInt4GroupSize = 32;
    constexpr int kInt4ScratchFloats =
        2 * (Kernel_traits::kBlockN / kInt4GroupSize) * Kernel_traits::kHeadDim;
    __shared__ FLASH_NAMESPACE::OptionalInt4Scratch<Is_int4kv, kInt4ScratchFloats> smem_int4_box;"""


# --- 2e: change masking-loop runtime gate `if (params.is_int4kv)` -> `if constexpr (Is_int4kv)` ---

MASKING_GATE_OLD = """        // 6c.3C Phase 2.3: NO-OP INT4 transform on K (runtime-gated;
        // uniform branch -> nvcc CSEs to ~zero cost on the stock path).
        // if constexpr guard prevents instantiation for traits where
        // kBlockN % 32 != 0 (e.g. kBlockN=16).
        if constexpr (Kernel_traits::kBlockN % kInt4GroupSize == 0) {
            if (params.is_int4kv) {
                FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                    Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_scratch);
                __syncthreads();
            }
        }"""

MASKING_GATE_NEW = """        // 6c.3C Phase 2.5: template-gated INT4 transform on K. Compiles
        // out entirely when Is_int4kv=false (no smem cost on stock path).
        if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }"""

# --- 2f: same for the non-masking loop ---

NONMASKING_GATE_OLD = """        // 6c.3C Phase 2.3: NO-OP INT4 transform on K (runtime-gated).
        if constexpr (Kernel_traits::kBlockN % kInt4GroupSize == 0) {
            if (params.is_int4kv) {
                FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                    Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_scratch);
                __syncthreads();
            }
        }"""

NONMASKING_GATE_NEW = """        // 6c.3C Phase 2.5: template-gated INT4 transform on K.
        if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }"""


def _exactly_once(src: str, needle: str, label: str) -> None:
    count = src.count(needle)
    if count == 0:
        raise RuntimeError(
            f"anchor '{label}' not found — verify Phase 2.3 was applied "
            "first (apply_phase2_3.sh)"
        )
    if count > 1:
        raise RuntimeError(
            f"anchor '{label}' matches {count} times — not unique"
        )


def patch_flash_fwd_kernel_h(path: Path) -> None:
    src = path.read_text()
    if "OptionalInt4Scratch<Is_int4kv" in src:
        print(f"  SKIP (already patched): {path}")
        return

    # 2a
    _exactly_once(src, ROWBLOCK_TEMPLATE_OLD, "compute_attn_1rowblock_splitkv template")
    src = src.replace(ROWBLOCK_TEMPLATE_OLD, ROWBLOCK_TEMPLATE_NEW, 1)

    # 2b
    _exactly_once(src, COMPUTE_SPLITKV_TEMPLATE_OLD, "compute_attn_splitkv template")
    src = src.replace(COMPUTE_SPLITKV_TEMPLATE_OLD, COMPUTE_SPLITKV_TEMPLATE_NEW, 1)

    # 2c
    _exactly_once(src, COMPUTE_SPLITKV_CALL_OLD, "compute_attn_splitkv -> 1rowblock call")
    src = src.replace(COMPUTE_SPLITKV_CALL_OLD, COMPUTE_SPLITKV_CALL_NEW, 1)

    # 2d
    _exactly_once(src, SMEM_ALLOC_OLD_23, "Phase 2.3 smem alloc")
    src = src.replace(SMEM_ALLOC_OLD_23, SMEM_ALLOC_NEW_25, 1)

    # 2e
    _exactly_once(src, MASKING_GATE_OLD, "Phase 2.3 masking-loop runtime gate")
    src = src.replace(MASKING_GATE_OLD, MASKING_GATE_NEW, 1)

    # 2f
    _exactly_once(src, NONMASKING_GATE_OLD, "Phase 2.3 non-masking-loop runtime gate")
    src = src.replace(NONMASKING_GATE_OLD, NONMASKING_GATE_NEW, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 3: flash_fwd_launch_template.h
# ============================================================

# --- 3a: flash_fwd_splitkv_kernel (DEFINE_FLASH_FORWARD_KERNEL) ---
# Add Is_int4kv to the macro arg list AND pass through to compute_attn_splitkv.

KERNEL_DEFINE_OLD = '''DEFINE_FLASH_FORWARD_KERNEL(flash_fwd_splitkv_kernel, bool Is_causal, bool Is_local, bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, bool Split, bool Append_KV) {
    #if defined(ARCH_SUPPORTS_FLASH)
        FLASH_NAMESPACE::compute_attn_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, Is_even_K, Is_softcap, Split, Append_KV>(params);
    #else
        FLASH_UNSUPPORTED_ARCH
    #endif
}'''

KERNEL_DEFINE_NEW = '''DEFINE_FLASH_FORWARD_KERNEL(flash_fwd_splitkv_kernel, bool Is_causal, bool Is_local, bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, bool Split, bool Append_KV, bool Is_int4kv) {  // 6c.3C Phase 2.5: + Is_int4kv
    #if defined(ARCH_SUPPORTS_FLASH)
        FLASH_NAMESPACE::compute_attn_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv>(params);
    #else
        FLASH_UNSUPPORTED_ARCH
    #endif
}'''


# --- 3b: run_flash_splitkv_fwd template and kernel instantiation ---

RUN_SPLITKV_FWD_TEMPLATE_OLD = (
    "template<typename Kernel_traits, bool Is_causal>\n"
    "void run_flash_splitkv_fwd(Flash_fwd_params &params, cudaStream_t stream) {"
)
RUN_SPLITKV_FWD_TEMPLATE_NEW = (
    "template<typename Kernel_traits, bool Is_causal, bool Is_int4kv = false>  "
    "// 6c.3C Phase 2.5: + Is_int4kv\n"
    "void run_flash_splitkv_fwd(Flash_fwd_params &params, cudaStream_t stream) {"
)

KERNEL_INSTANTIATION_OLD = (
    "auto kernel = &flash_fwd_splitkv_kernel<Kernel_traits, Is_causal, "
    "Is_local && !Is_causal, Has_alibi, IsEvenMNConst && !Append_KV && "
    "IsEvenKConst && !Is_local && Kernel_traits::kHeadDim <= 128, "
    "IsEvenKConst, Is_softcap, Split, Append_KV>;"
)
KERNEL_INSTANTIATION_NEW = (
    "auto kernel = &flash_fwd_splitkv_kernel<Kernel_traits, Is_causal, "
    "Is_local && !Is_causal, Has_alibi, IsEvenMNConst && !Append_KV && "
    "IsEvenKConst && !Is_local && Kernel_traits::kHeadDim <= 128, "
    "IsEvenKConst, Is_softcap, Split, Append_KV, Is_int4kv>;  "
    "// 6c.3C Phase 2.5: + Is_int4kv"
)


# --- 3c: run_mha_fwd_splitkv_dispatch_int4kv routes to Is_int4kv=true ---
# Phase 2.1 added this function — find its run_flash_splitkv_fwd call
# and add the Is_int4kv=true template arg.

INT4KV_DISPATCH_OLD = """// 6c.3C Phase 2.1: INT4 KV dispatch (initially identical body).
// Phase 2.2+ will modify this function's body to use the INT4 K/V
// read path. The instantiation file is
// flash_fwd_split_hdim128_bf16_int4kv_sm80.cu; new hdim/dtype
// instantiations follow the same pattern.
template<typename T, int Headdim, bool Is_causal>
void run_mha_fwd_splitkv_dispatch_int4kv(Flash_fwd_params &params, cudaStream_t stream) {
    constexpr static int kBlockM = 64;
    constexpr static int kBlockN = Headdim <= 64 ? 256 : (Headdim <= 128 ? 128 : 64);
    run_flash_splitkv_fwd<Flash_fwd_kernel_traits<Headdim, kBlockM, kBlockN, 4, false, false, T>, Is_causal>(params, stream);
}"""

INT4KV_DISPATCH_NEW = """// 6c.3C Phase 2.1: INT4 KV dispatch.
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


def patch_flash_fwd_launch_template_h(path: Path) -> None:
    src = path.read_text()
    if "/*Is_int4kv=*/true" in src and "bool Is_int4kv = false" in src:
        print(f"  SKIP (already patched): {path}")
        return

    # 3a
    _exactly_once(src, KERNEL_DEFINE_OLD, "flash_fwd_splitkv_kernel DEFINE block")
    src = src.replace(KERNEL_DEFINE_OLD, KERNEL_DEFINE_NEW, 1)

    # 3b
    _exactly_once(src, RUN_SPLITKV_FWD_TEMPLATE_OLD, "run_flash_splitkv_fwd template")
    src = src.replace(RUN_SPLITKV_FWD_TEMPLATE_OLD, RUN_SPLITKV_FWD_TEMPLATE_NEW, 1)
    _exactly_once(src, KERNEL_INSTANTIATION_OLD, "kernel instantiation inside run_flash_splitkv_fwd")
    src = src.replace(KERNEL_INSTANTIATION_OLD, KERNEL_INSTANTIATION_NEW, 1)

    # 3c
    _exactly_once(src, INT4KV_DISPATCH_OLD, "Phase 2.1 _int4kv dispatch")
    src = src.replace(INT4KV_DISPATCH_OLD, INT4KV_DISPATCH_NEW, 1)

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
         patch_int4_inline_h_add_optional_scratch),
        (DEV_ROOT / "csrc/flash_attn/src/flash_fwd_kernel.h",
         patch_flash_fwd_kernel_h),
        (DEV_ROOT / "csrc/flash_attn/src/flash_fwd_launch_template.h",
         patch_flash_fwd_launch_template_h),
    ]

    print("Applying Phase 2.5 patches:")
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
