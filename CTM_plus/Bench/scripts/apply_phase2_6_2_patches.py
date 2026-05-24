#!/usr/bin/env python3
"""apply_phase2_6_2_patches.py — 6c.3C Phase 2.6.2: packed-V kernel read.

Extends the Phase 2.4.1a/b infrastructure to ALSO read V from packed
INT4 storage. When Is_int4kv_packed=true, the kernel now reads BOTH
packed K (existing 2.4.1b path) AND packed V (this phase). V's group
axis is HEAD_DIM (per-token, v_group_size=32 channels per group);
NO protect-V sidecar.

Changes (all to /workspace/dev/vllm-flash-attn-dev):
  - csrc/flash_attn/src/flash.h:
      Adds v_packed_{int4,scale,xmin}_ptr fields + v_packed_group_size
      to Flash_fwd_params (after the K-packed block from 2.4.1a).
  - csrc/flash_attn/flash_api.cpp:
      Extends Int4KvPackedPtrs struct with V fields.
      mha_fwd_kvcache_int4 signature extended with 3 new tensor args
      + 1 int.
      Plumbs V pointers into params via Int4KvPackedGuard.
      is_int4kv_packed only fires when ALL packed (K AND V) tensors
      are present.
  - csrc/flash_attn/flash_api_torch_lib.cpp:
      Updates fwd decl + pybind schema for the 4 new args.
  - vllm_flash_attn/flash_attn_interface.py:
      flash_attn_with_int4_kvcache gains v_packed_int4, v_packed_scale,
      v_packed_xmin, v_packed_group_size kwargs.
  - csrc/flash_attn/src/int4_packed_load.h:
      OptionalPackedScratch gains v_packed/v_scale/v_xmin smem arrays.
      Adds int4_packed_load_V_block helper (mirror of K helper, group
      axis along head_dim, no protect).
  - csrc/flash_attn/src/flash_fwd_kernel.h:
      Adds V HBM base pointers at entry (gmem_v_packed/scale/xmin).
      At both V-wait sites (masking + non-masking loops), routes
      Is_int4kv_packed → int4_packed_load_V_block instead of Phase 3's
      in-register V quant.

Acceptance (verify_phase2_6_2.py):
  - cosine >= 0.9995 vs Phase 5A reference on Qwen-shaped synthetic
    K + V (both packed).
  - max-abs diff bounded.

Prerequisites: Phase 1 + 2.1 + 2.2 + 2.3 + 2.5 + 3 + 4 + 2.4.1a + 2.4.1b
applied. Idempotent (re-running is no-op).
"""
import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1: flash.h — extend Flash_fwd_params with V-packed fields
# ============================================================

FLASH_H_OLD_PACKED_BLOCK = """    void * __restrict__ k_packed_int4_ptr = nullptr;          // (1, S, H_kv, D/2) uint8
    void * __restrict__ k_packed_scale_ptr = nullptr;         // (1, S/G, H_kv, D) bf16
    void * __restrict__ k_packed_xmin_ptr = nullptr;          // (1, S/G, H_kv, D) bf16
    void * __restrict__ k_packed_protect_bf16_ptr = nullptr;  // (1, S, H_kv, n_protect) bf16
    void * __restrict__ k_packed_protect_slot_ptr = nullptr;  // (H_kv, D) int8 (-1 if not protected)
    index_t k_packed_int4_row_stride = 0;          // bytes per token (= H_kv * D/2)
    index_t k_packed_scale_group_stride = 0;       // bytes per group (= H_kv * D * 2)
    index_t k_packed_xmin_group_stride = 0;        // same
    index_t k_packed_protect_row_stride = 0;       // bytes per token (= H_kv * n_protect * 2)
    int packed_group_size = 0;
    int packed_n_protect = 0;
    bool is_int4kv_packed = false;"""

FLASH_H_NEW_PACKED_BLOCK = """    void * __restrict__ k_packed_int4_ptr = nullptr;          // (1, S, H_kv, D/2) uint8
    void * __restrict__ k_packed_scale_ptr = nullptr;         // (1, S/G, H_kv, D) bf16
    void * __restrict__ k_packed_xmin_ptr = nullptr;          // (1, S/G, H_kv, D) bf16
    void * __restrict__ k_packed_protect_bf16_ptr = nullptr;  // (1, S, H_kv, n_protect) bf16
    void * __restrict__ k_packed_protect_slot_ptr = nullptr;  // (H_kv, D) int8 (-1 if not protected)
    index_t k_packed_int4_row_stride = 0;          // bytes per token (= H_kv * D/2)
    index_t k_packed_scale_group_stride = 0;       // bytes per group (= H_kv * D * 2)
    index_t k_packed_xmin_group_stride = 0;        // same
    index_t k_packed_protect_row_stride = 0;       // bytes per token (= H_kv * n_protect * 2)
    int packed_group_size = 0;
    int packed_n_protect = 0;
    bool is_int4kv_packed = false;

    // ===== 6c.3C Phase 2.6.2: packed-V HBM storage side channel ====
    // When is_int4kv_packed = true, kernel reads packed uint8 V
    // (per-token, group along head_dim) INSTEAD OF cp.async-loading
    // BF16 V + Phase 3 in-register quant. No protect-V sidecar
    // (V doesn't have K's outlier-channel concentration).
    void * __restrict__ v_packed_int4_ptr = nullptr;          // (1, S, H_kv, D/2) uint8
    void * __restrict__ v_packed_scale_ptr = nullptr;         // (1, S, H_kv, D/v_group_size) bf16
    void * __restrict__ v_packed_xmin_ptr = nullptr;          // (1, S, H_kv, D/v_group_size) bf16
    int v_packed_group_size = 0;"""


def patch_flash_h(path: Path) -> None:
    src = path.read_text()
    if "v_packed_int4_ptr" in src:
        print(f"  SKIP (already patched): {path}")
        return
    _exactly_once(src, FLASH_H_OLD_PACKED_BLOCK, "flash.h Phase 2.4.1a packed-K block")
    src = src.replace(FLASH_H_OLD_PACKED_BLOCK, FLASH_H_NEW_PACKED_BLOCK, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 2: flash_api.cpp — extend Int4KvPackedPtrs + signature + plumb
# ============================================================

API_PACKED_PTRS_OLD = """struct Int4KvPackedPtrs {
    const void *k_int4_ptr           = nullptr;
    const void *k_scale_ptr          = nullptr;
    const void *k_xmin_ptr           = nullptr;
    const void *k_protect_bf16_ptr   = nullptr;
    const void *k_protect_slot_ptr   = nullptr;
    int packed_group_size            = 0;
    int packed_n_protect             = 0;
};"""

API_PACKED_PTRS_NEW = """struct Int4KvPackedPtrs {
    const void *k_int4_ptr           = nullptr;
    const void *k_scale_ptr          = nullptr;
    const void *k_xmin_ptr           = nullptr;
    const void *k_protect_bf16_ptr   = nullptr;
    const void *k_protect_slot_ptr   = nullptr;
    int packed_group_size            = 0;
    int packed_n_protect             = 0;
    // 6c.3C Phase 2.6.2: packed-V side channel.
    const void *v_int4_ptr           = nullptr;
    const void *v_scale_ptr          = nullptr;
    const void *v_xmin_ptr           = nullptr;
    int v_packed_group_size          = 0;
};"""


API_RUN_MHA_FWD_OLD = """    params.k_packed_int4_ptr          = const_cast<void*>(_int4kv_packed_ptrs.k_int4_ptr);
    params.k_packed_scale_ptr         = const_cast<void*>(_int4kv_packed_ptrs.k_scale_ptr);
    params.k_packed_xmin_ptr          = const_cast<void*>(_int4kv_packed_ptrs.k_xmin_ptr);
    params.k_packed_protect_bf16_ptr  = const_cast<void*>(_int4kv_packed_ptrs.k_protect_bf16_ptr);
    params.k_packed_protect_slot_ptr  = const_cast<void*>(_int4kv_packed_ptrs.k_protect_slot_ptr);
    params.packed_group_size          = _int4kv_packed_ptrs.packed_group_size;
    params.packed_n_protect           = _int4kv_packed_ptrs.packed_n_protect;
    params.is_int4kv_packed = (params.k_packed_int4_ptr != nullptr
                               && params.k_packed_scale_ptr != nullptr
                               && params.k_packed_xmin_ptr != nullptr
                               && params.k_packed_protect_bf16_ptr != nullptr
                               && params.k_packed_protect_slot_ptr != nullptr);"""

API_RUN_MHA_FWD_NEW = """    params.k_packed_int4_ptr          = const_cast<void*>(_int4kv_packed_ptrs.k_int4_ptr);
    params.k_packed_scale_ptr         = const_cast<void*>(_int4kv_packed_ptrs.k_scale_ptr);
    params.k_packed_xmin_ptr          = const_cast<void*>(_int4kv_packed_ptrs.k_xmin_ptr);
    params.k_packed_protect_bf16_ptr  = const_cast<void*>(_int4kv_packed_ptrs.k_protect_bf16_ptr);
    params.k_packed_protect_slot_ptr  = const_cast<void*>(_int4kv_packed_ptrs.k_protect_slot_ptr);
    params.packed_group_size          = _int4kv_packed_ptrs.packed_group_size;
    params.packed_n_protect           = _int4kv_packed_ptrs.packed_n_protect;
    // 6c.3C Phase 2.6.2: V-packed side channel.
    params.v_packed_int4_ptr          = const_cast<void*>(_int4kv_packed_ptrs.v_int4_ptr);
    params.v_packed_scale_ptr         = const_cast<void*>(_int4kv_packed_ptrs.v_scale_ptr);
    params.v_packed_xmin_ptr          = const_cast<void*>(_int4kv_packed_ptrs.v_xmin_ptr);
    params.v_packed_group_size        = _int4kv_packed_ptrs.v_packed_group_size;
    // is_int4kv_packed is true iff ALL packed-K AND packed-V tensors
    // are present (Phase 2.6.2 makes V required alongside K).
    params.is_int4kv_packed = (params.k_packed_int4_ptr != nullptr
                               && params.k_packed_scale_ptr != nullptr
                               && params.k_packed_xmin_ptr != nullptr
                               && params.k_packed_protect_bf16_ptr != nullptr
                               && params.k_packed_protect_slot_ptr != nullptr
                               && params.v_packed_int4_ptr != nullptr
                               && params.v_packed_scale_ptr != nullptr
                               && params.v_packed_xmin_ptr != nullptr);"""


API_INT4_SIG_OLD = """                     std::optional<const at::Tensor> &k_packed_int4_,
                     std::optional<const at::Tensor> &k_packed_scale_,
                     std::optional<const at::Tensor> &k_packed_xmin_,
                     std::optional<const at::Tensor> &k_packed_protect_bf16_,
                     std::optional<const at::Tensor> &k_packed_protect_slot_,
                     int packed_group_size,
                     int packed_n_protect) {"""

API_INT4_SIG_NEW = """                     std::optional<const at::Tensor> &k_packed_int4_,
                     std::optional<const at::Tensor> &k_packed_scale_,
                     std::optional<const at::Tensor> &k_packed_xmin_,
                     std::optional<const at::Tensor> &k_packed_protect_bf16_,
                     std::optional<const at::Tensor> &k_packed_protect_slot_,
                     int packed_group_size,
                     int packed_n_protect,
                     // 6c.3C Phase 2.6.2: V-packed side channel.
                     std::optional<const at::Tensor> &v_packed_int4_,
                     std::optional<const at::Tensor> &v_packed_scale_,
                     std::optional<const at::Tensor> &v_packed_xmin_,
                     int v_packed_group_size) {"""


API_INT4_BODY_OLD = """    Int4KvPackedPtrs packed_ptrs;
    if (k_packed_int4_.has_value() && k_packed_scale_.has_value()
            && k_packed_xmin_.has_value() && k_packed_protect_bf16_.has_value()
            && k_packed_protect_slot_.has_value()) {
        packed_ptrs.k_int4_ptr         = k_packed_int4_.value().data_ptr();
        packed_ptrs.k_scale_ptr        = k_packed_scale_.value().data_ptr();
        packed_ptrs.k_xmin_ptr         = k_packed_xmin_.value().data_ptr();
        packed_ptrs.k_protect_bf16_ptr = k_packed_protect_bf16_.value().data_ptr();
        packed_ptrs.k_protect_slot_ptr = k_packed_protect_slot_.value().data_ptr();
        packed_ptrs.packed_group_size  = packed_group_size;
        packed_ptrs.packed_n_protect   = packed_n_protect;
    }
    Int4KvPackedGuard packed_guard(packed_ptrs);"""

API_INT4_BODY_NEW = """    Int4KvPackedPtrs packed_ptrs;
    if (k_packed_int4_.has_value() && k_packed_scale_.has_value()
            && k_packed_xmin_.has_value() && k_packed_protect_bf16_.has_value()
            && k_packed_protect_slot_.has_value()) {
        packed_ptrs.k_int4_ptr         = k_packed_int4_.value().data_ptr();
        packed_ptrs.k_scale_ptr        = k_packed_scale_.value().data_ptr();
        packed_ptrs.k_xmin_ptr         = k_packed_xmin_.value().data_ptr();
        packed_ptrs.k_protect_bf16_ptr = k_packed_protect_bf16_.value().data_ptr();
        packed_ptrs.k_protect_slot_ptr = k_packed_protect_slot_.value().data_ptr();
        packed_ptrs.packed_group_size  = packed_group_size;
        packed_ptrs.packed_n_protect   = packed_n_protect;
    }
    // 6c.3C Phase 2.6.2: also capture V-packed pointers if supplied.
    if (v_packed_int4_.has_value() && v_packed_scale_.has_value()
            && v_packed_xmin_.has_value()) {
        packed_ptrs.v_int4_ptr  = v_packed_int4_.value().data_ptr();
        packed_ptrs.v_scale_ptr = v_packed_scale_.value().data_ptr();
        packed_ptrs.v_xmin_ptr  = v_packed_xmin_.value().data_ptr();
        packed_ptrs.v_packed_group_size = v_packed_group_size;
    }
    Int4KvPackedGuard packed_guard(packed_ptrs);"""


def patch_flash_api_cpp(path: Path) -> None:
    src = path.read_text()
    if "v_packed_int4_" in src:
        print(f"  SKIP (already patched): {path}")
        return
    _exactly_once(src, API_PACKED_PTRS_OLD, "Int4KvPackedPtrs struct (Phase 2.4.1a)")
    src = src.replace(API_PACKED_PTRS_OLD, API_PACKED_PTRS_NEW, 1)
    _exactly_once(src, API_RUN_MHA_FWD_OLD, "run_mha_fwd packed-K plumb (Phase 2.4.1a)")
    src = src.replace(API_RUN_MHA_FWD_OLD, API_RUN_MHA_FWD_NEW, 1)
    _exactly_once(src, API_INT4_SIG_OLD, "mha_fwd_kvcache_int4 sig tail (Phase 2.4.1a)")
    src = src.replace(API_INT4_SIG_OLD, API_INT4_SIG_NEW, 1)
    _exactly_once(src, API_INT4_BODY_OLD, "mha_fwd_kvcache_int4 body packed guard (Phase 2.4.1a)")
    src = src.replace(API_INT4_BODY_OLD, API_INT4_BODY_NEW, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 3: flash_api_torch_lib.cpp — pybind schema for V args
# ============================================================

TORCH_LIB_FWD_OLD = """                     std::optional<const at::Tensor> &k_packed_int4_,
                     std::optional<const at::Tensor> &k_packed_scale_,
                     std::optional<const at::Tensor> &k_packed_xmin_,
                     std::optional<const at::Tensor> &k_packed_protect_bf16_,
                     std::optional<const at::Tensor> &k_packed_protect_slot_,
                     int packed_group_size,
                     int packed_n_protect);"""

TORCH_LIB_FWD_NEW = """                     std::optional<const at::Tensor> &k_packed_int4_,
                     std::optional<const at::Tensor> &k_packed_scale_,
                     std::optional<const at::Tensor> &k_packed_xmin_,
                     std::optional<const at::Tensor> &k_packed_protect_bf16_,
                     std::optional<const at::Tensor> &k_packed_protect_slot_,
                     int packed_group_size,
                     int packed_n_protect,
                     std::optional<const at::Tensor> &v_packed_int4_,
                     std::optional<const at::Tensor> &v_packed_scale_,
                     std::optional<const at::Tensor> &v_packed_xmin_,
                     int v_packed_group_size);"""

TORCH_LIB_SCHEMA_OLD = ('"int group_size_k, int group_size_v, int n_protect, '
                        'Tensor? k_packed_int4, Tensor? k_packed_scale, '
                        'Tensor? k_packed_xmin, Tensor? k_packed_protect_bf16, '
                        'Tensor? k_packed_protect_slot, '
                        'int packed_group_size, int packed_n_protect) -> Tensor[]"')

TORCH_LIB_SCHEMA_NEW = ('"int group_size_k, int group_size_v, int n_protect, '
                        'Tensor? k_packed_int4, Tensor? k_packed_scale, '
                        'Tensor? k_packed_xmin, Tensor? k_packed_protect_bf16, '
                        'Tensor? k_packed_protect_slot, '
                        'int packed_group_size, int packed_n_protect, '
                        'Tensor? v_packed_int4, Tensor? v_packed_scale, '
                        'Tensor? v_packed_xmin, int v_packed_group_size'
                        ') -> Tensor[]"')


def patch_torch_lib_cpp(path: Path) -> None:
    src = path.read_text()
    if "v_packed_int4_" in src:
        print(f"  SKIP (already patched): {path}")
        return
    _exactly_once(src, TORCH_LIB_FWD_OLD, "torch_lib fwd decl (Phase 2.4.1a)")
    src = src.replace(TORCH_LIB_FWD_OLD, TORCH_LIB_FWD_NEW, 1)
    _exactly_once(src, TORCH_LIB_SCHEMA_OLD, "torch_lib pybind schema (Phase 2.4.1a)")
    src = src.replace(TORCH_LIB_SCHEMA_OLD, TORCH_LIB_SCHEMA_NEW, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 4: Python wrapper — add v_packed_* kwargs
# ============================================================

PY_WRAPPER_OLD_SIG = """    # 6c.3C Phase 2.4.1a: packed-K side channel kwargs.
    k_packed_int4=None,
    k_packed_scale=None,
    k_packed_xmin=None,
    k_packed_protect_bf16=None,
    k_packed_protect_slot=None,
    packed_group_size=32,
    packed_n_protect=0,"""

PY_WRAPPER_NEW_SIG = """    # 6c.3C Phase 2.4.1a: packed-K side channel kwargs.
    k_packed_int4=None,
    k_packed_scale=None,
    k_packed_xmin=None,
    k_packed_protect_bf16=None,
    k_packed_protect_slot=None,
    packed_group_size=32,
    packed_n_protect=0,
    # 6c.3C Phase 2.6.2: packed-V side channel kwargs.
    v_packed_int4=None,
    v_packed_scale=None,
    v_packed_xmin=None,
    v_packed_group_size=32,"""

PY_WRAPPER_OLD_CALL = """        # 6c.3C Phase 2.4.1a: packed-K side channel (kernel reads them
        # in Phase 2.4.1b; in 2.4.1a these flow through and sit in
        # params unread).
        k_packed_int4, k_packed_scale, k_packed_xmin,
        k_packed_protect_bf16, k_packed_protect_slot,
        packed_group_size, packed_n_protect,
    )"""

PY_WRAPPER_NEW_CALL = """        # 6c.3C Phase 2.4.1a: packed-K side channel.
        k_packed_int4, k_packed_scale, k_packed_xmin,
        k_packed_protect_bf16, k_packed_protect_slot,
        packed_group_size, packed_n_protect,
        # 6c.3C Phase 2.6.2: packed-V side channel.
        v_packed_int4, v_packed_scale, v_packed_xmin, v_packed_group_size,
    )"""


def patch_python_wrapper(path: Path) -> None:
    src = path.read_text()
    if "v_packed_int4" in src:
        print(f"  SKIP (already patched): {path}")
        return
    _exactly_once(src, PY_WRAPPER_OLD_SIG, "Python wrapper packed-K kwargs (Phase 2.4.1a)")
    src = src.replace(PY_WRAPPER_OLD_SIG, PY_WRAPPER_NEW_SIG, 1)
    _exactly_once(src, PY_WRAPPER_OLD_CALL, "Python wrapper torch.ops call tail")
    src = src.replace(PY_WRAPPER_OLD_CALL, PY_WRAPPER_NEW_CALL, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 5: int4_packed_load.h — add OptionalPackedScratch V members
# + int4_packed_load_V_block helper
# ============================================================

# The existing scratch struct (post-2.4.1b) — we add V members at the end.

SCRATCH_OLD = """    uint8_t k_packed[kBlockN * kPackedBytesPerToken];
    Element k_scale [kNGroupsPerBlock * kHeadDim];
    Element k_xmin  [kNGroupsPerBlock * kHeadDim];
    Element k_protect[kBlockN * kMaxNProtect];
    int8_t  protect_slot[kHeadDim];
};"""

SCRATCH_NEW = """    uint8_t k_packed[kBlockN * kPackedBytesPerToken];
    Element k_scale [kNGroupsPerBlock * kHeadDim];
    Element k_xmin  [kNGroupsPerBlock * kHeadDim];
    Element k_protect[kBlockN * kMaxNProtect];
    int8_t  protect_slot[kHeadDim];

    // 6c.3C Phase 2.6.2: V-side packed scratchpads.
    // V is per-token, group along head_dim → v_scale/v_xmin shape is
    // (kBlockN, kHeadDim/kGroupSize). kVGroupsPerToken = kHeadDim/kGroupSize.
    static constexpr int kVGroupsPerToken = kHeadDim / kGroupSize;
    uint8_t v_packed[kBlockN * kPackedBytesPerToken];
    Element v_scale [kBlockN * kVGroupsPerToken];
    Element v_xmin  [kBlockN * kVGroupsPerToken];
};"""


V_HELPER_INSERT_OLD = """}  // namespace FLASH_NAMESPACE"""

V_HELPER_INSERT_NEW = """////////////////////////////////////////////////////////////////////////////////
// int4_packed_load_V_block — Phase 2.6.2 V-side equivalent of K helper.
//
// V grouping: HEAD_DIM (per-token, kVGroupSize=32 channels per group).
// No protect-V sidecar (V doesn't exhibit K's outlier concentration).
//
// Layout assumptions (matches kv_policy/phase2_6_packed_v.py):
//   gmem_v_packed: (B, S_max, H_kv, D/2) uint8
//   gmem_v_scale:  (B, S_max, H_kv, D/kVGroupSize) Element
//   gmem_v_xmin:   (B, S_max, H_kv, D/kVGroupSize) Element
//
// Caller invariants:
//   - sV is committed in smem via cp_async_wait<0> + __syncthreads before
//     this is called (the existing V cp.async still fires; we OVERWRITE
//     the smem contents with dequant-from-packed values).
//   - tVsV is the thread's CUTLASS partition of the V smem tile.
//   - tKVcKV is the matching (n, d) identity tensor.
//
// Postcondition:
//   - smem V has been overwritten with x_hat values from packed HBM.
//   - Caller MUST __syncthreads() before the PV GEMM consumes sV.
////////////////////////////////////////////////////////////////////////////////

template <typename Kernel_traits, int kVGroupSize,
          typename EngineV, typename LayoutV,
          typename EngineC, typename LayoutC,
          typename Scratch>
__device__ __forceinline__ void int4_packed_load_V_block(
    cute::Tensor<EngineV, LayoutV>       &tVsV,
    cute::Tensor<EngineC, LayoutC> const &tKVcKV,
    Scratch                              &smem,
    const uint8_t                        *gmem_v_packed_base,
    const typename Kernel_traits::Element *gmem_v_scale_base,
    const typename Kernel_traits::Element *gmem_v_xmin_base,
    int bidh,
    int S_max,
    int H_kv,
    int n_block_token_start,
    int s_curr) {

    using Element = typename Kernel_traits::Element;
    constexpr int kBlockN  = Kernel_traits::kBlockN;
    constexpr int kHeadDim = Kernel_traits::kHeadDim;
    constexpr int kPackedBytesPerToken = kHeadDim / 2;
    constexpr int kVGroupsPerToken     = kHeadDim / kVGroupSize;

    const int tidx     = threadIdx.x;
    const int nthreads = blockDim.x;

    __syncthreads();

    // -----------------------------------------------------------------
    // Phase A: cooperative load packed V bytes (~8 KB).
    //   One token per thread at kBlockN=128, nthreads=128.
    //   Each thread does 4 × uint4 vector loads.
    // -----------------------------------------------------------------
    for (int t = tidx; t < kBlockN; t += nthreads) {
        uint8_t *smem_dst = &smem.v_packed[t * kPackedBytesPerToken];
        int global_t = n_block_token_start + t;
        if (global_t < 0 || global_t >= s_curr) {
            #pragma unroll
            for (int b = 0; b < kPackedBytesPerToken; b += 16) {
                *reinterpret_cast<uint4*>(smem_dst + b) = make_uint4(0u, 0u, 0u, 0u);
            }
            continue;
        }
        const uint8_t *gmem_src = gmem_v_packed_base
            + global_t * H_kv * kPackedBytesPerToken
            + bidh * kPackedBytesPerToken;
        #pragma unroll
        for (int b = 0; b < kPackedBytesPerToken; b += 16) {
            uint4 v = __ldg(reinterpret_cast<const uint4*>(gmem_src + b));
            *reinterpret_cast<uint4*>(smem_dst + b) = v;
        }
    }

    // -----------------------------------------------------------------
    // Phase B: cooperative load scales (kBlockN × kVGroupsPerToken).
    // V scale layout: per-(token, h_kv, channel_group), not per-group-seq.
    // -----------------------------------------------------------------
    for (int i = tidx; i < kBlockN * kVGroupsPerToken; i += nthreads) {
        const int t = i / kVGroupsPerToken;
        const int g = i % kVGroupsPerToken;
        const int global_t = n_block_token_start + t;
        Element val = Element(0);
        if (global_t >= 0 && global_t < s_curr) {
            val = gmem_v_scale_base[global_t * H_kv * kVGroupsPerToken
                                  + bidh * kVGroupsPerToken + g];
        }
        smem.v_scale[t * kVGroupsPerToken + g] = val;
    }

    // -----------------------------------------------------------------
    // Phase C: cooperative load xmins (same shape as scales).
    // -----------------------------------------------------------------
    for (int i = tidx; i < kBlockN * kVGroupsPerToken; i += nthreads) {
        const int t = i / kVGroupsPerToken;
        const int g = i % kVGroupsPerToken;
        const int global_t = n_block_token_start + t;
        Element val = Element(0);
        if (global_t >= 0 && global_t < s_curr) {
            val = gmem_v_xmin_base[global_t * H_kv * kVGroupsPerToken
                                 + bidh * kVGroupsPerToken + g];
        }
        smem.v_xmin[t * kVGroupsPerToken + g] = val;
    }

    __syncthreads();

    // -----------------------------------------------------------------
    // Phase D: per-thread fragment iterate — unpack + dequant — write
    //          bf16 V to sV (the smem V tile that PV GEMM consumes).
    // -----------------------------------------------------------------
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

                // V is grouped along HEAD_DIM: group = d / kVGroupSize.
                const int g = d / kVGroupSize;
                const uint8_t byte = smem.v_packed[n * kPackedBytesPerToken + (d >> 1)];
                const uint8_t nibble = (d & 1) ? ((byte >> 4) & 0x0F) : (byte & 0x0F);
                const float scale = int4_inline_to_float<Element>(
                    smem.v_scale[n * kVGroupsPerToken + g]);
                const float xmin = int4_inline_to_float<Element>(
                    smem.v_xmin[n * kVGroupsPerToken + g]);
                const float x = static_cast<float>(nibble) * scale + xmin;
                tVsV(i0, i1, i2) = int4_inline_from_float<Element>(x);
            }
        }
    }
    // No exit sync — caller adds __syncthreads() before PV GEMM consumes sV.
}

}  // namespace FLASH_NAMESPACE"""


def patch_int4_packed_load_h(path: Path) -> None:
    src = path.read_text()
    if "int4_packed_load_V_block" in src:
        print(f"  SKIP (already patched): {path}")
        return
    _exactly_once(src, SCRATCH_OLD, "OptionalPackedScratch K end (Phase 2.4.1b)")
    src = src.replace(SCRATCH_OLD, SCRATCH_NEW, 1)
    _exactly_once(src, V_HELPER_INSERT_OLD, "FLASH_NAMESPACE close brace (insertion point)")
    src = src.replace(V_HELPER_INSERT_OLD, V_HELPER_INSERT_NEW, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 6: flash_fwd_kernel.h — wire V load at V-wait sites
# ============================================================

# 6a — compute V base pointers at kernel entry, alongside K's gmem_k_*.

KERNEL_GMEM_OLD = """    using PackedElement = typename Kernel_traits::Element;
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

KERNEL_GMEM_NEW = """    using PackedElement = typename Kernel_traits::Element;
    const uint8_t      *gmem_k_packed_base       = nullptr;
    const PackedElement *gmem_k_scale_base        = nullptr;
    const PackedElement *gmem_k_xmin_base         = nullptr;
    const PackedElement *gmem_k_protect_base      = nullptr;
    const int8_t       *gmem_protect_slot_base   = nullptr;
    int                 packed_n_protect         = 0;
    // 6c.3C Phase 2.6.2: V-packed base pointers.
    const uint8_t      *gmem_v_packed_base       = nullptr;
    const PackedElement *gmem_v_scale_base        = nullptr;
    const PackedElement *gmem_v_xmin_base         = nullptr;
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
        // V: per-token, group along head_dim. n_groups_per_token = D / v_group_size.
        gmem_v_packed_base      = reinterpret_cast<const uint8_t*>(params.v_packed_int4_ptr)
                                  + bidb * params.seqlen_k * params.h_k * (params.d / 2);
        // For v_scale/xmin, the shape is (B, S, H_kv, D/v_group_size) bf16.
        const int kVGroupsPerToken = params.d / kInt4GroupSize;  // same v_group_size==kInt4GroupSize for v1
        gmem_v_scale_base       = reinterpret_cast<const PackedElement*>(params.v_packed_scale_ptr)
                                  + bidb * params.seqlen_k * params.h_k * kVGroupsPerToken;
        gmem_v_xmin_base        = reinterpret_cast<const PackedElement*>(params.v_packed_xmin_ptr)
                                  + bidb * params.seqlen_k * params.h_k * kVGroupsPerToken;
    }"""


# 6b/6c — V-wait sites. The Phase 3 patcher inserted a V transform at
# the same V-wait positions; we add a 5B.4-style branch BEFORE that.

V_MASKING_OLD = """        // 6c.3C Phase 3: template-gated INT4 transform on V (per-token
        // quant, group along head_dim). Same scratchpad as K (sequential
        // lifetime — K at K-wait, V at V-wait, separated by qK gemm).
        if constexpr (Is_int4kv && (Kernel_traits::kHeadDim % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_V_block_inplace<
                Kernel_traits, kInt4GroupSize>(tVsV, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }"""

V_MASKING_NEW = """        // 6c.3C Phase 2.6.2: packed-V HBM load REPLACES Phase 3's
        // in-register V quant when Is_int4kv_packed=true.
        if constexpr (Is_int4kv_packed && (Kernel_traits::kHeadDim % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_packed_load_V_block<
                Kernel_traits, kInt4GroupSize>(
                tVsV, tKVcKV, smem_packed_box,
                gmem_v_packed_base, gmem_v_scale_base, gmem_v_xmin_base,
                bidh, params.seqlen_k, params.h_k,
                n_block * Kernel_traits::kBlockN, params.seqlen_k);
            __syncthreads();
        } else if constexpr (Is_int4kv && (Kernel_traits::kHeadDim % kInt4GroupSize == 0)) {
            // 6c.3C Phase 3: in-register V transform (legacy non-packed path).
            FLASH_NAMESPACE::int4_quant_dequant_V_block_inplace<
                Kernel_traits, kInt4GroupSize>(tVsV, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }"""

V_NONMASKING_OLD = """        // 6c.3C Phase 3: template-gated INT4 transform on V.
        if constexpr (Is_int4kv && (Kernel_traits::kHeadDim % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_V_block_inplace<
                Kernel_traits, kInt4GroupSize>(tVsV, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }"""

V_NONMASKING_NEW = """        // 6c.3C Phase 2.6.2: packed-V HBM load (non-masking loop).
        if constexpr (Is_int4kv_packed && (Kernel_traits::kHeadDim % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_packed_load_V_block<
                Kernel_traits, kInt4GroupSize>(
                tVsV, tKVcKV, smem_packed_box,
                gmem_v_packed_base, gmem_v_scale_base, gmem_v_xmin_base,
                bidh, params.seqlen_k, params.h_k,
                n_block * Kernel_traits::kBlockN, params.seqlen_k);
            __syncthreads();
        } else if constexpr (Is_int4kv && (Kernel_traits::kHeadDim % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_V_block_inplace<
                Kernel_traits, kInt4GroupSize>(tVsV, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }"""


def patch_flash_fwd_kernel_h(path: Path) -> None:
    src = path.read_text()
    if "int4_packed_load_V_block" in src or "gmem_v_packed_base" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, KERNEL_GMEM_OLD, "kernel gmem K base ptrs (Phase 2.4.1b)")
    src = src.replace(KERNEL_GMEM_OLD, KERNEL_GMEM_NEW, 1)

    _exactly_once(src, V_MASKING_OLD, "Phase 3 V transform — masking-loop")
    src = src.replace(V_MASKING_OLD, V_MASKING_NEW, 1)

    _exactly_once(src, V_NONMASKING_OLD, "Phase 3 V transform — non-masking-loop")
    src = src.replace(V_NONMASKING_OLD, V_NONMASKING_NEW, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Shared helper.
# ============================================================

def _exactly_once(src: str, needle: str, label: str) -> None:
    count = src.count(needle)
    if count == 0:
        raise RuntimeError(
            f"anchor '{label}' not found — verify prior phases applied"
        )
    if count > 1:
        raise RuntimeError(f"anchor '{label}' matches {count} times — not unique")


# ============================================================
# Main
# ============================================================

def main() -> int:
    if not DEV_ROOT.exists():
        print(f"ERROR: dev tree not at {DEV_ROOT}", file=sys.stderr)
        return 1

    targets = [
        (DEV_ROOT / "csrc/flash_attn/src/flash.h",             patch_flash_h),
        (DEV_ROOT / "csrc/flash_attn/flash_api.cpp",           patch_flash_api_cpp),
        (DEV_ROOT / "csrc/flash_attn/flash_api_torch_lib.cpp", patch_torch_lib_cpp),
        (DEV_ROOT / "vllm_flash_attn/flash_attn_interface.py", patch_python_wrapper),
        (DEV_ROOT / "csrc/flash_attn/src/int4_packed_load.h",  patch_int4_packed_load_h),
        (DEV_ROOT / "csrc/flash_attn/src/flash_fwd_kernel.h",  patch_flash_fwd_kernel_h),
    ]
    print("Applying Phase 2.6.2 patches:")
    for path, fn in targets:
        try:
            fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR on {path}: {e}", file=sys.stderr)
            return 1
    print()
    print("Patches applied. Rebuild + reinstall + verify next.")
    print("  flash_fwd_kernel.h touched -> all ~14 splitkv .cu TUs recompile")
    print("  (~10-15 min cold build).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
