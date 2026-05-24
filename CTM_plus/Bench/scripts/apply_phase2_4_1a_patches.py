#!/usr/bin/env python3
"""apply_phase2_4_1a_patches.py — 6c.3C Phase 2.4.1a: packed-K plumbing.

Minimal data-plumbing for the Phase 2.4 packed-K side channel:

  - Extends Flash_fwd_params with new pointer / stride / flag fields.
  - Adds Int4KvPackedGuard (mirrors Phase 4's Int4KvProtectMaskGuard) —
    thread-local capture of packed-K pointers in mha_fwd_kvcache_int4
    that run_mha_fwd reads on entry.
  - Extends mha_fwd_kvcache_int4 C++ signature with new optional Tensor
    args + 2 new ints (packed_group_size, packed_n_protect).
  - Updates the pybind schema in flash_api_torch_lib.cpp.
  - Extends flash_attn_with_int4_kvcache Python wrapper with new
    kwargs that pass through to the C++ entry.

NO KERNEL TEMPLATE CHANGES. The kernel still runs Phase 2.3/4 in-register
quant — the new packed pointers sit in params but are unread until
Phase 2.4.1b adds the Is_int4kv_packed template gate + the custom HBM
load helper.

Acceptance for Phase 2.4.1a:
  - Build succeeds with the new fields.
  - Phase 5A smoke still GREEN (no numerical behavior change).
  - Phase 4 / 5A verifies all still pass.
  - The new wrapper accepts packed kwargs without crashing (pointer
    plumbing works even though kernel ignores them).

After 2.4.1a GREEN, Phase 2.4.1b adds the kernel-side packed-K consumer.

Idempotent. Re-run = no-op.
"""

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1: flash.h — extend Flash_fwd_params with packed-K fields
# ============================================================

FLASH_H_OLD_FIELDS = """    index_t k_cache_fp16_protect_batch_stride = 0;
    index_t k_cache_fp16_protect_head_stride = 0;
    int group_size_k = 0;
    int group_size_v = 0;
    int n_protect = 0;
    bool is_int4kv = false;"""

FLASH_H_NEW_FIELDS = """    index_t k_cache_fp16_protect_batch_stride = 0;
    index_t k_cache_fp16_protect_head_stride = 0;
    int group_size_k = 0;
    int group_size_v = 0;
    int n_protect = 0;
    bool is_int4kv = false;

    // ===== 6c.3C Phase 2.4: packed-K HBM storage side channel ======
    // When is_int4kv_packed = true, the kernel reads packed uint8 K
    // from HBM (with per-group scale + x_min + a compact protect-BF16
    // sidecar) INSTEAD OF cp.async-loading BF16 K + in-register quant.
    // Plumbed by Phase 2.4.1a; consumed by the Phase 2.4.1b kernel.
    void * __restrict__ k_packed_int4_ptr = nullptr;          // (1, S, H_kv, D/2) uint8
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


def patch_flash_h(path: Path) -> None:
    src = path.read_text()
    if "is_int4kv_packed" in src:
        print(f"  SKIP (already patched): {path}")
        return
    if FLASH_H_OLD_FIELDS not in src:
        raise RuntimeError(
            f"can't find Phase 1 INT4 fields anchor in {path} — "
            "Phase 1 must be applied first"
        )
    src = src.replace(FLASH_H_OLD_FIELDS, FLASH_H_NEW_FIELDS, 1)
    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 2: flash_api.cpp — Int4KvPackedGuard + run_mha_fwd plumb
# ============================================================

# --- 2a: add Int4KvPackedGuard after Phase 4's Int4KvProtectMaskGuard ---

API_GUARD_PHASE4_BLOCK = """// 6c.3C Phase 4: thread-local capture of the protect-K mask pointer.
// mha_fwd_kvcache_int4 sets this via Int4KvProtectMaskGuard before
// forwarding to mha_fwd_kvcache; run_mha_fwd reads it on entry and
// writes params.k_cache_protect_mask_ptr.
thread_local const void *_int4kv_protect_mask_ptr = nullptr;
struct Int4KvProtectMaskGuard {
    Int4KvProtectMaskGuard(const void *ptr) { _int4kv_protect_mask_ptr = ptr; }
    ~Int4KvProtectMaskGuard() { _int4kv_protect_mask_ptr = nullptr; }
};
}  // namespace"""

API_GUARD_PHASE_2_4_1A_BLOCK = """// 6c.3C Phase 4: thread-local capture of the protect-K mask pointer.
// mha_fwd_kvcache_int4 sets this via Int4KvProtectMaskGuard before
// forwarding to mha_fwd_kvcache; run_mha_fwd reads it on entry and
// writes params.k_cache_protect_mask_ptr.
thread_local const void *_int4kv_protect_mask_ptr = nullptr;
struct Int4KvProtectMaskGuard {
    Int4KvProtectMaskGuard(const void *ptr) { _int4kv_protect_mask_ptr = ptr; }
    ~Int4KvProtectMaskGuard() { _int4kv_protect_mask_ptr = nullptr; }
};

// 6c.3C Phase 2.4.1a: thread-local capture of packed-K side channel
// pointers. When ALL of these are non-null, params.is_int4kv_packed is
// set to true in run_mha_fwd, and the Phase 2.4.1b kernel (when wired
// in) reads from packed HBM storage instead of cp.async-loading BF16 K.
// In 2.4.1a these pointers are plumbed but NOT yet read by the kernel.
struct Int4KvPackedPtrs {
    const void *k_int4_ptr           = nullptr;
    const void *k_scale_ptr          = nullptr;
    const void *k_xmin_ptr           = nullptr;
    const void *k_protect_bf16_ptr   = nullptr;
    const void *k_protect_slot_ptr   = nullptr;
    int packed_group_size            = 0;
    int packed_n_protect             = 0;
};
thread_local Int4KvPackedPtrs _int4kv_packed_ptrs;
struct Int4KvPackedGuard {
    Int4KvPackedGuard(const Int4KvPackedPtrs &p) { _int4kv_packed_ptrs = p; }
    ~Int4KvPackedGuard() { _int4kv_packed_ptrs = Int4KvPackedPtrs{}; }
};
}  // namespace"""


# --- 2b: run_mha_fwd reads new thread-local on entry ---

API_RUN_MHA_FWD_OLD = """    // 6c.3C Phase 2.2: read thread-local dispatch flag set by
    // Int4KvDispatchGuard. params.is_int4kv stays false when
    // called via the stock mha_fwd_kvcache path.
    params.is_int4kv = _int4kv_dispatch;
    // 6c.3C Phase 4: protect-K mask pointer plumbed via a sibling guard.
    params.k_cache_protect_mask_ptr = const_cast<void*>(_int4kv_protect_mask_ptr);"""

API_RUN_MHA_FWD_NEW = """    // 6c.3C Phase 2.2: read thread-local dispatch flag set by
    // Int4KvDispatchGuard. params.is_int4kv stays false when
    // called via the stock mha_fwd_kvcache path.
    params.is_int4kv = _int4kv_dispatch;
    // 6c.3C Phase 4: protect-K mask pointer plumbed via a sibling guard.
    params.k_cache_protect_mask_ptr = const_cast<void*>(_int4kv_protect_mask_ptr);
    // 6c.3C Phase 2.4.1a: packed-K side channel pointers. is_int4kv_packed
    // is true iff all four required tensor pointers are non-null
    // (k_int4 + k_scale + k_xmin + k_protect_bf16 + k_protect_slot).
    // The Phase 2.4.1b kernel will gate on this flag.
    params.k_packed_int4_ptr          = const_cast<void*>(_int4kv_packed_ptrs.k_int4_ptr);
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


# --- 2c: extend mha_fwd_kvcache_int4 signature with new packed args ---

API_INT4_SIG_OLD = """                     std::optional<const at::Tensor> &k_scale_,
                     std::optional<const at::Tensor> &k_offset_,
                     std::optional<const at::Tensor> &v_scale_,
                     std::optional<const at::Tensor> &v_offset_,
                     std::optional<const at::Tensor> &k_fp16_protect_,
                     std::optional<const at::Tensor> &protect_mask_,
                     std::optional<const at::Tensor> &protect_indices_,
                     int group_size_k,
                     int group_size_v,
                     int n_protect) {"""

API_INT4_SIG_NEW = """                     std::optional<const at::Tensor> &k_scale_,
                     std::optional<const at::Tensor> &k_offset_,
                     std::optional<const at::Tensor> &v_scale_,
                     std::optional<const at::Tensor> &v_offset_,
                     std::optional<const at::Tensor> &k_fp16_protect_,
                     std::optional<const at::Tensor> &protect_mask_,
                     std::optional<const at::Tensor> &protect_indices_,
                     int group_size_k,
                     int group_size_v,
                     int n_protect,
                     // 6c.3C Phase 2.4.1a: packed-K side channel.
                     std::optional<const at::Tensor> &k_packed_int4_,
                     std::optional<const at::Tensor> &k_packed_scale_,
                     std::optional<const at::Tensor> &k_packed_xmin_,
                     std::optional<const at::Tensor> &k_packed_protect_bf16_,
                     std::optional<const at::Tensor> &k_packed_protect_slot_,
                     int packed_group_size,
                     int packed_n_protect) {"""


# --- 2d: extend mha_fwd_kvcache_int4 body to instantiate Int4KvPackedGuard ---

API_INT4_BODY_OLD = """    Int4KvProtectMaskGuard mask_guard(mask_ptr);
    return mha_fwd_kvcache("""

API_INT4_BODY_NEW = """    Int4KvProtectMaskGuard mask_guard(mask_ptr);
    // 6c.3C Phase 2.4.1a: capture packed-K side channel pointers (if all
    // supplied) into a thread-local that run_mha_fwd reads. NULL pointers
    // mean "not packed mode" and run_mha_fwd will set
    // params.is_int4kv_packed = false.
    Int4KvPackedPtrs packed_ptrs;
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
    Int4KvPackedGuard packed_guard(packed_ptrs);
    return mha_fwd_kvcache("""


def patch_flash_api_cpp(path: Path) -> None:
    src = path.read_text()
    if "Int4KvPackedGuard" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, API_GUARD_PHASE4_BLOCK, "Phase 4 protect-mask guard block")
    src = src.replace(API_GUARD_PHASE4_BLOCK, API_GUARD_PHASE_2_4_1A_BLOCK, 1)

    _exactly_once(src, API_RUN_MHA_FWD_OLD, "run_mha_fwd Phase 4 plumb lines")
    src = src.replace(API_RUN_MHA_FWD_OLD, API_RUN_MHA_FWD_NEW, 1)

    _exactly_once(src, API_INT4_SIG_OLD, "mha_fwd_kvcache_int4 signature tail")
    src = src.replace(API_INT4_SIG_OLD, API_INT4_SIG_NEW, 1)

    _exactly_once(src, API_INT4_BODY_OLD, "mha_fwd_kvcache_int4 body (mask_guard + return)")
    src = src.replace(API_INT4_BODY_OLD, API_INT4_BODY_NEW, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 3: flash_api_torch_lib.cpp — pybind schema for new args
# ============================================================

TORCH_LIB_FWD_OLD = """                     std::optional<const at::Tensor> &k_scale_,
                     std::optional<const at::Tensor> &k_offset_,
                     std::optional<const at::Tensor> &v_scale_,
                     std::optional<const at::Tensor> &v_offset_,
                     std::optional<const at::Tensor> &k_fp16_protect_,
                     std::optional<const at::Tensor> &protect_mask_,
                     std::optional<const at::Tensor> &protect_indices_,
                     int group_size_k,
                     int group_size_v,
                     int n_protect);"""

TORCH_LIB_FWD_NEW = """                     std::optional<const at::Tensor> &k_scale_,
                     std::optional<const at::Tensor> &k_offset_,
                     std::optional<const at::Tensor> &v_scale_,
                     std::optional<const at::Tensor> &v_offset_,
                     std::optional<const at::Tensor> &k_fp16_protect_,
                     std::optional<const at::Tensor> &protect_mask_,
                     std::optional<const at::Tensor> &protect_indices_,
                     int group_size_k,
                     int group_size_v,
                     int n_protect,
                     std::optional<const at::Tensor> &k_packed_int4_,
                     std::optional<const at::Tensor> &k_packed_scale_,
                     std::optional<const at::Tensor> &k_packed_xmin_,
                     std::optional<const at::Tensor> &k_packed_protect_bf16_,
                     std::optional<const at::Tensor> &k_packed_protect_slot_,
                     int packed_group_size,
                     int packed_n_protect);"""

TORCH_LIB_SCHEMA_OLD = ('"int group_size_k, int group_size_v, int n_protect) -> Tensor[]"')

TORCH_LIB_SCHEMA_NEW = ('"int group_size_k, int group_size_v, int n_protect, '
                        'Tensor? k_packed_int4, Tensor? k_packed_scale, '
                        'Tensor? k_packed_xmin, Tensor? k_packed_protect_bf16, '
                        'Tensor? k_packed_protect_slot, '
                        'int packed_group_size, int packed_n_protect) -> Tensor[]"')


def patch_torch_lib_cpp(path: Path) -> None:
    src = path.read_text()
    if "k_packed_int4_" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, TORCH_LIB_FWD_OLD, "torch_lib forward decl of mha_fwd_kvcache_int4")
    src = src.replace(TORCH_LIB_FWD_OLD, TORCH_LIB_FWD_NEW, 1)

    _exactly_once(src, TORCH_LIB_SCHEMA_OLD, "torch_lib pybind schema tail")
    src = src.replace(TORCH_LIB_SCHEMA_OLD, TORCH_LIB_SCHEMA_NEW, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 4: vllm_flash_attn/flash_attn_interface.py — wrapper kwargs
# ============================================================

# Add new kwargs to the wrapper signature and pass them to the torch.ops call.

PY_WRAPPER_OLD_SIG = """def flash_attn_with_int4_kvcache(
    q,
    k_cache,
    v_cache,
    k=None,
    v=None,
    k_scale=None,
    k_offset=None,
    v_scale=None,
    v_offset=None,
    k_fp16_protect=None,
    protect_mask=None,
    protect_indices=None,
    group_size_k=32,
    group_size_v=32,
    n_protect=0,"""

PY_WRAPPER_NEW_SIG = """def flash_attn_with_int4_kvcache(
    q,
    k_cache,
    v_cache,
    k=None,
    v=None,
    k_scale=None,
    k_offset=None,
    v_scale=None,
    v_offset=None,
    k_fp16_protect=None,
    protect_mask=None,
    protect_indices=None,
    group_size_k=32,
    group_size_v=32,
    n_protect=0,
    # 6c.3C Phase 2.4.1a: packed-K side channel kwargs.
    k_packed_int4=None,
    k_packed_scale=None,
    k_packed_xmin=None,
    k_packed_protect_bf16=None,
    k_packed_protect_slot=None,
    packed_group_size=32,
    packed_n_protect=0,"""

PY_WRAPPER_OLD_CALL = """    out, softmax_lse = torch.ops._vllm_fa2_C.fwd_kvcache_int4(
        q, k_cache, v_cache,
        k, v,
        cache_seqlens,
        rotary_cos, rotary_sin,
        cache_batch_idx,
        cache_leftpad,
        block_table,
        alibi_slopes,
        out,
        softmax_scale,
        causal,
        window_size[0],
        window_size[1],
        softcap,
        rotary_interleaved,
        num_splits,
        # INT4 args (Phase 2.2: ignored by the C++ side via (void) casts).
        k_scale, k_offset,
        v_scale, v_offset,
        k_fp16_protect,
        protect_mask, protect_indices,
        group_size_k, group_size_v, n_protect,
    )"""

PY_WRAPPER_NEW_CALL = """    out, softmax_lse = torch.ops._vllm_fa2_C.fwd_kvcache_int4(
        q, k_cache, v_cache,
        k, v,
        cache_seqlens,
        rotary_cos, rotary_sin,
        cache_batch_idx,
        cache_leftpad,
        block_table,
        alibi_slopes,
        out,
        softmax_scale,
        causal,
        window_size[0],
        window_size[1],
        softcap,
        rotary_interleaved,
        num_splits,
        # INT4 args (Phase 2.2: ignored by the C++ side via (void) casts).
        k_scale, k_offset,
        v_scale, v_offset,
        k_fp16_protect,
        protect_mask, protect_indices,
        group_size_k, group_size_v, n_protect,
        # 6c.3C Phase 2.4.1a: packed-K side channel (kernel reads them
        # in Phase 2.4.1b; in 2.4.1a these flow through and sit in
        # params unread).
        k_packed_int4, k_packed_scale, k_packed_xmin,
        k_packed_protect_bf16, k_packed_protect_slot,
        packed_group_size, packed_n_protect,
    )"""


def patch_python_wrapper(path: Path) -> None:
    src = path.read_text()
    if "k_packed_int4" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, PY_WRAPPER_OLD_SIG, "Python wrapper signature head")
    src = src.replace(PY_WRAPPER_OLD_SIG, PY_WRAPPER_NEW_SIG, 1)

    _exactly_once(src, PY_WRAPPER_OLD_CALL, "Python wrapper torch.ops call")
    src = src.replace(PY_WRAPPER_OLD_CALL, PY_WRAPPER_NEW_CALL, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Shared anchor-uniqueness helper.
# ============================================================

def _exactly_once(src: str, needle: str, label: str) -> None:
    count = src.count(needle)
    if count == 0:
        raise RuntimeError(
            f"anchor '{label}' not found — verify Phase 1/2.2/4 applied first"
        )
    if count > 1:
        raise RuntimeError(
            f"anchor '{label}' matches {count} times — not unique"
        )


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
    ]
    print("Applying Phase 2.4.1a patches:")
    for path, fn in targets:
        try:
            fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR on {path}: {e}", file=sys.stderr)
            return 1
    print()
    print("Patches applied. Next: rebuild + reinstall + verify.")
    print("  flash_api.cpp + flash.h modified -> rebuild touches just")
    print("  the flash_api TU (~30s incremental).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
