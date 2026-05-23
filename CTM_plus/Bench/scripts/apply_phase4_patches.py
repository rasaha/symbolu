#!/usr/bin/env python3
"""apply_phase4_patches.py — 6c.3C Phase 4: protect-K BF16 sidecar (in-kernel).

§20.4.3 algorithm: for each (batch, kv_head) pair, the top-~4% K channels
by magnitude carry most of the qK dot signal. Keeping those channels at
BF16 while quantizing the rest to INT4 recovers FP16-level attention
quality (closes the cosine gap from Phase 2.3/3's ~0.99 toward ~0.9999).

Phase 4 v1 implementation strategy:
  In the NO-OP transform proof (Phases 2.3/3), HBM K is still BF16; the
  INT4 quant happens only in-register inside the helper. So "protecting"
  a channel means SKIPPING the quant/dequant for that channel — its
  original BF16 value already lives in smem from the cp.async. No
  separate BF16 sidecar tensor is required at this phase.
  Phase 2.4+ (REAL INT4 HBM read) will introduce the sidecar.

Mask provenance for testing:
  Phase 5 generates the mask in vLLM at prefill-end (top-4% by magnitude
  per (B, H_kv)). For Phase 4 NO-OP testing, the verify script computes
  the mask in Python from K's magnitudes and passes it through the
  flash_attn_with_int4_kvcache(..., protect_mask=mask) call.

Files modified (in /workspace/dev/vllm-flash-attn-dev):
  - csrc/flash_attn/src/int4_inline.h:
      Extend int4_quant_dequant_K_block_inplace with an optional
      `const int8_t *protect_mask = nullptr` parameter. In both Pass 1
      (max/min reduction) and Pass 2 (quant/dequant), skip elements
      where mask[d] != 0. Protected channels retain their original
      BF16 value in smem.
  - csrc/flash_attn/src/flash_fwd_kernel.h:
      At function entry, declare per-(bidb, bidh) `k_protect_mask_local`
      pointer slice from params.k_cache_protect_mask_ptr (NULL when no
      mask provided). Pass to both K-wait helper calls.
  - csrc/flash_attn/flash_api.cpp:
      Add Int4KvProtectMaskGuard (mirrors Phase 2.2's Int4KvDispatchGuard
      pattern). Captures protect_mask data_ptr() into a thread_local
      void*; run_mha_fwd reads it on entry and sets
      params.k_cache_protect_mask_ptr. mha_fwd_kvcache_int4 wires
      protect_mask_.has_value() ? protect_mask_->data_ptr() : nullptr
      into the guard.

Idempotent. Sentinel: "Int4KvProtectMaskGuard" in flash_api.cpp,
"const int8_t *protect_mask" in int4_inline.h's K helper.

Acceptance:
  - verify_phase4.py: cosine >= 0.9990 (Phase 2.3 hit 0.9968 unprotected;
    4% protection should close most of the remaining ~0.003 gap). The
    threshold will be tightened to match the route-B algorithm floor
    once diagnose_phase4_drift.py establishes the PyTorch reference.
  - smoke_test_fa_install.sh: stock FA p50 still ~67 us (Is_int4kv=false
    template variant carries no mask logic).

Prerequisites: Phase 2.3 + 2.5 + 3 applied.
"""

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1: int4_inline.h — extend K helper with protect_mask
# ============================================================

# --- 1a: extend the K helper signature ---

K_SIG_OLD = """template <typename Kernel_traits, int kGroupSize,
          typename EngineK, typename LayoutK,
          typename EngineC, typename LayoutC>
__device__ __forceinline__ void int4_quant_dequant_K_block_inplace(
    cute::Tensor<EngineK, LayoutK> &tKsK,
    cute::Tensor<EngineC, LayoutC> const &tKVcKV,
    float *smem_scratch) {"""

K_SIG_NEW = """template <typename Kernel_traits, int kGroupSize,
          typename EngineK, typename LayoutK,
          typename EngineC, typename LayoutC>
__device__ __forceinline__ void int4_quant_dequant_K_block_inplace(
    cute::Tensor<EngineK, LayoutK> &tKsK,
    cute::Tensor<EngineC, LayoutC> const &tKVcKV,
    float *smem_scratch,
    const int8_t *protect_mask = nullptr) {"""

# --- 1b: Pass 1 inner body — add mask check after bounds check ---

K_PASS1_OLD = """                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;
                const int g = n / kGroupSize;
                const int slot = g * kHeadDim + d;
                const float x = int4_inline_to_float<Element>(tKsK(i0, i1, i2));
                int4_inline_atomic_max_float(&smem_max[slot], x);
                int4_inline_atomic_min_float(&smem_min[slot], x);"""

K_PASS1_NEW = """                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;
                // 6c.3C Phase 4: skip protected channels (top-~4% magnitude
                // outliers per §20.4.3). The original BF16 value in smem
                // is left untouched and feeds the qK gemm at full precision.
                if (protect_mask != nullptr && protect_mask[d] != 0) continue;
                const int g = n / kGroupSize;
                const int slot = g * kHeadDim + d;
                const float x = int4_inline_to_float<Element>(tKsK(i0, i1, i2));
                int4_inline_atomic_max_float(&smem_max[slot], x);
                int4_inline_atomic_min_float(&smem_min[slot], x);"""

# --- 1c: Pass 2 inner body — same mask check ---

K_PASS2_OLD = """                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;
                const int g = n / kGroupSize;
                const int slot = g * kHeadDim + d;
                const float x_max = smem_max[slot];
                const float x_min = smem_min[slot];
                const float scale = fmaxf((x_max - x_min) * kInvFifteen, kScaleClamp);
                const float x = int4_inline_to_float<Element>(tKsK(i0, i1, i2));
                int q = __float2int_rn((x - x_min) / scale);
                q = max(0, min(15, q));
                const float x_hat = static_cast<float>(q) * scale + x_min;
                tKsK(i0, i1, i2) = int4_inline_from_float<Element>(x_hat);"""

K_PASS2_NEW = """                if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;
                // 6c.3C Phase 4: same mask check as Pass 1.
                if (protect_mask != nullptr && protect_mask[d] != 0) continue;
                const int g = n / kGroupSize;
                const int slot = g * kHeadDim + d;
                const float x_max = smem_max[slot];
                const float x_min = smem_min[slot];
                const float scale = fmaxf((x_max - x_min) * kInvFifteen, kScaleClamp);
                const float x = int4_inline_to_float<Element>(tKsK(i0, i1, i2));
                int q = __float2int_rn((x - x_min) / scale);
                q = max(0, min(15, q));
                const float x_hat = static_cast<float>(q) * scale + x_min;
                tKsK(i0, i1, i2) = int4_inline_from_float<Element>(x_hat);"""


def _exactly_once(src: str, needle: str, label: str) -> None:
    count = src.count(needle)
    if count == 0:
        raise RuntimeError(
            f"anchor '{label}' not found — verify Phase 2.3 + 2.5 + 3 applied"
        )
    if count > 1:
        raise RuntimeError(
            f"anchor '{label}' matches {count} times — not unique"
        )


def patch_int4_inline_h(path: Path) -> None:
    src = path.read_text()
    if "const int8_t *protect_mask" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, K_SIG_OLD, "K helper signature")
    src = src.replace(K_SIG_OLD, K_SIG_NEW, 1)

    _exactly_once(src, K_PASS1_OLD, "K helper Pass 1 inner body")
    src = src.replace(K_PASS1_OLD, K_PASS1_NEW, 1)

    _exactly_once(src, K_PASS2_OLD, "K helper Pass 2 inner body")
    src = src.replace(K_PASS2_OLD, K_PASS2_NEW, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 2: flash_fwd_kernel.h — compute per-block mask slice + pass to helpers
# ============================================================

# --- 2a: add k_protect_mask_local computation after smem_int4_box decl ---

KERNEL_MASK_SLICE_OLD = """    constexpr int kInt4GroupSize = 32;
    constexpr int kInt4ScratchFloats =
        2 * (Kernel_traits::kBlockN / kInt4GroupSize) * Kernel_traits::kHeadDim;
    __shared__ FLASH_NAMESPACE::OptionalInt4Scratch<Is_int4kv, kInt4ScratchFloats> smem_int4_box;

    clear(acc_o);"""

KERNEL_MASK_SLICE_NEW = """    constexpr int kInt4GroupSize = 32;
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
    }

    clear(acc_o);"""

# --- 2b: masking K-wait helper call — pass k_protect_mask_local ---

KERNEL_MASKING_CALL_OLD = """        // 6c.3C Phase 2.5: template-gated INT4 transform on K. Compiles
        // out entirely when Is_int4kv=false (no smem cost on stock path).
        if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }"""

KERNEL_MASKING_CALL_NEW = """        // 6c.3C Phase 2.5/4: template-gated INT4 transform on K with optional
        // protect-K mask. The mask pointer is non-null only when the caller
        // supplied protect_mask=; protected channels skip quant and keep
        // their original BF16 smem value.
        if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data, k_protect_mask_local);
            __syncthreads();
        }"""

# --- 2c: non-masking K-wait helper call ---

KERNEL_NONMASKING_CALL_OLD = """        // 6c.3C Phase 2.5: template-gated INT4 transform on K.
        if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data);
            __syncthreads();
        }"""

KERNEL_NONMASKING_CALL_NEW = """        // 6c.3C Phase 2.5/4: template-gated INT4 transform on K with
        // optional protect-K mask.
        if constexpr (Is_int4kv && (Kernel_traits::kBlockN % kInt4GroupSize == 0)) {
            FLASH_NAMESPACE::int4_quant_dequant_K_block_inplace<
                Kernel_traits, kInt4GroupSize>(tKsK, tKVcKV, smem_int4_box.data, k_protect_mask_local);
            __syncthreads();
        }"""


def patch_flash_fwd_kernel_h(path: Path) -> None:
    src = path.read_text()
    if "k_protect_mask_local" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, KERNEL_MASK_SLICE_OLD, "smem_int4_box decl + clear(acc_o)")
    src = src.replace(KERNEL_MASK_SLICE_OLD, KERNEL_MASK_SLICE_NEW, 1)

    _exactly_once(src, KERNEL_MASKING_CALL_OLD, "Phase 2.5 masking-loop K helper call")
    src = src.replace(KERNEL_MASKING_CALL_OLD, KERNEL_MASKING_CALL_NEW, 1)

    _exactly_once(src, KERNEL_NONMASKING_CALL_OLD, "Phase 2.5 non-masking-loop K helper call")
    src = src.replace(KERNEL_NONMASKING_CALL_OLD, KERNEL_NONMASKING_CALL_NEW, 1)

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 3: flash_api.cpp — Int4KvProtectMaskGuard + plumb to params
# ============================================================

# --- 3a: add Int4KvProtectMaskGuard right after the existing Int4KvDispatchGuard ---

API_GUARD_OLD = """namespace {
thread_local bool _int4kv_dispatch = false;
struct Int4KvDispatchGuard {
    Int4KvDispatchGuard() { _int4kv_dispatch = true; }
    ~Int4KvDispatchGuard() { _int4kv_dispatch = false; }
};
}  // namespace"""

API_GUARD_NEW = """namespace {
thread_local bool _int4kv_dispatch = false;
struct Int4KvDispatchGuard {
    Int4KvDispatchGuard() { _int4kv_dispatch = true; }
    ~Int4KvDispatchGuard() { _int4kv_dispatch = false; }
};

// 6c.3C Phase 4: thread-local capture of the protect-K mask pointer.
// mha_fwd_kvcache_int4 sets this via Int4KvProtectMaskGuard before
// forwarding to mha_fwd_kvcache; run_mha_fwd reads it on entry and
// writes params.k_cache_protect_mask_ptr.
thread_local const void *_int4kv_protect_mask_ptr = nullptr;
struct Int4KvProtectMaskGuard {
    Int4KvProtectMaskGuard(const void *ptr) { _int4kv_protect_mask_ptr = ptr; }
    ~Int4KvProtectMaskGuard() { _int4kv_protect_mask_ptr = nullptr; }
};
}  // namespace"""


# --- 3b: run_mha_fwd reads the new thread-local on entry ---

API_RUN_MHA_FWD_OLD = """    // 6c.3C Phase 2.2: read thread-local dispatch flag set by
    // Int4KvDispatchGuard. params.is_int4kv stays false when
    // called via the stock mha_fwd_kvcache path.
    params.is_int4kv = _int4kv_dispatch;"""

API_RUN_MHA_FWD_NEW = """    // 6c.3C Phase 2.2: read thread-local dispatch flag set by
    // Int4KvDispatchGuard. params.is_int4kv stays false when
    // called via the stock mha_fwd_kvcache path.
    params.is_int4kv = _int4kv_dispatch;
    // 6c.3C Phase 4: protect-K mask pointer plumbed via a sibling guard.
    params.k_cache_protect_mask_ptr = const_cast<void*>(_int4kv_protect_mask_ptr);"""


# --- 3c: mha_fwd_kvcache_int4 body — instantiate the new guard ---

API_INT4_BODY_OLD = """    (void)k_scale_; (void)k_offset_; (void)v_scale_; (void)v_offset_;
    (void)k_fp16_protect_; (void)protect_mask_; (void)protect_indices_;
    (void)group_size_k; (void)group_size_v; (void)n_protect;
    // 6c.3C Phase 2.2: flip dispatch to _int4kv via thread-local.
    // RAII guard resets the flag on return (or exception).
    Int4KvDispatchGuard guard;
    return mha_fwd_kvcache("""

API_INT4_BODY_NEW = """    (void)k_scale_; (void)k_offset_; (void)v_scale_; (void)v_offset_;
    (void)k_fp16_protect_; (void)protect_indices_;
    (void)group_size_k; (void)group_size_v; (void)n_protect;
    // 6c.3C Phase 2.2: flip dispatch to _int4kv via thread-local.
    Int4KvDispatchGuard guard;
    // 6c.3C Phase 4: validate + capture protect-K mask pointer.
    // Mask layout: (B, H_kv, D) int8; 1 = protected, 0 = quantize.
    const void *mask_ptr = nullptr;
    if (protect_mask_.has_value()) {
        const auto &mask = protect_mask_.value();
        TORCH_CHECK(mask.scalar_type() == at::kChar,
                    "protect_mask must be int8 (got ", mask.scalar_type(), ")");
        TORCH_CHECK(mask.dim() == 3,
                    "protect_mask must be 3-D (B, H_kv, D); got ", mask.dim(), "-D");
        TORCH_CHECK(mask.size(0) == kcache.size(0),
                    "protect_mask batch dim ", mask.size(0),
                    " != kcache batch ", kcache.size(0));
        TORCH_CHECK(mask.size(1) == kcache.size(2),
                    "protect_mask H_kv dim ", mask.size(1),
                    " != kcache H_kv ", kcache.size(2));
        TORCH_CHECK(mask.size(2) == kcache.size(3),
                    "protect_mask D dim ", mask.size(2),
                    " != kcache D ", kcache.size(3));
        TORCH_CHECK(mask.is_contiguous(),
                    "protect_mask must be contiguous");
        mask_ptr = mask.data_ptr();
    }
    Int4KvProtectMaskGuard mask_guard(mask_ptr);
    return mha_fwd_kvcache("""


def patch_flash_api_cpp(path: Path) -> None:
    src = path.read_text()
    if "Int4KvProtectMaskGuard" in src:
        print(f"  SKIP (already patched): {path}")
        return

    _exactly_once(src, API_GUARD_OLD, "Int4KvDispatchGuard namespace block")
    src = src.replace(API_GUARD_OLD, API_GUARD_NEW, 1)

    _exactly_once(src, API_RUN_MHA_FWD_OLD, "run_mha_fwd dispatch flag read")
    src = src.replace(API_RUN_MHA_FWD_OLD, API_RUN_MHA_FWD_NEW, 1)

    _exactly_once(src, API_INT4_BODY_OLD, "mha_fwd_kvcache_int4 body (guard + return)")
    src = src.replace(API_INT4_BODY_OLD, API_INT4_BODY_NEW, 1)

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
        (DEV_ROOT / "csrc/flash_attn/src/int4_inline.h",     patch_int4_inline_h),
        (DEV_ROOT / "csrc/flash_attn/src/flash_fwd_kernel.h", patch_flash_fwd_kernel_h),
        (DEV_ROOT / "csrc/flash_attn/flash_api.cpp",          patch_flash_api_cpp),
    ]

    print("Applying Phase 4 patches:")
    for path, fn in targets:
        try:
            fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR on {path}: {e}", file=sys.stderr)
            return 1

    print()
    print("Patches applied. Rebuild + reinstall + verify next.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
