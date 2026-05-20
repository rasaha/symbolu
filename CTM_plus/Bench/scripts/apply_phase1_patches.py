#!/usr/bin/env python3
"""apply_phase1_patches.py — 6c.3C Phase 1 additive scaffolding.

Modifies 4 files in /workspace/dev/vllm-flash-attn-dev:

  * vllm_flash_attn/flash_attn_interface.py — new flash_attn_with_int4_kvcache
    Python wrapper (Phase 1: no-op delegate to flash_attn_with_kvcache).
    NOTE: this is the SLIM (~24KB) vllm-specific file, NOT the
    ~63KB standalone flash_attn/flash_attn_interface.py — only the
    vllm one ships in the wheel that lands in venv-vllm.
  * vllm_flash_attn/__init__.py — re-export the new wrapper via
    RELATIVE import (`from .flash_attn_interface import ...`).
    Absolute `from flash_attn.flash_attn_interface import ...` would
    pull in the standalone flash_attn package which tries to import
    flash_attn_2_cuda (not installed) and crashes.
  * csrc/flash_attn/src/flash.h — extend Flash_fwd_params with
    INT4 KV pointer/stride fields. ALL NULL/0 default.
  * csrc/flash_attn/flash_api.cpp — new mha_fwd_kvcache_int4 C++ entry
    (Phase 1: forwards to mha_fwd_kvcache, ignores INT4 args).
  * csrc/flash_attn/flash_api_torch_lib.cpp — forward decl + pybind
    schema + ops.impl for mha_fwd_kvcache_int4.

All edits are additive and idempotent (re-running is a no-op).
The script also REPAIRS the previously-buggy absolute import in
__init__.py if encountered.

Acceptance criterion (verify_phase1.py):
  flash_attn_with_int4_kvcache(q, k_bf16, v_bf16, cache_seqlens=csl)
    == flash_attn_with_kvcache(q, k_bf16, v_bf16, cache_seqlens=csl)
  bit-for-bit on Qwen2.5-7B shapes (B=1, H_q=28, H_kv=4, D=128, S=16k).
"""

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1: flash_attn/flash_attn_interface.py
# ============================================================

PY_PATCH = '''

# ============================================================
# 6c.3C Phase 1 — INT4 KV cache no-op delegate.
# Added by apply_phase1_patches.py. Phase 1 just forwards to
# flash_attn_with_kvcache and ignores the INT4 args so the
# Phase 1 parity test can assert bit-equality. Phase 2+ will
# route to flash_attn_gpu.fwd_kvcache_int4 once we have a real
# INT4 dispatch arm.
# ============================================================

def flash_attn_with_int4_kvcache(
    q,
    k_cache,
    v_cache,
    k=None,
    v=None,
    # INT4 KV cache extension args (Phase 1: accepted but ignored)
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
    # Same as flash_attn_with_kvcache
    rotary_cos=None,
    rotary_sin=None,
    cache_seqlens=None,
    cache_batch_idx=None,
    cache_leftpad=None,
    block_table=None,
    softmax_scale=None,
    causal=False,
    window_size=(-1, -1),
    softcap=0.0,
    rotary_interleaved=True,
    alibi_slopes=None,
    num_splits=0,
    return_softmax_lse=False,
):
    """Phase 1 no-op delegate to flash_attn_with_kvcache.

    See KERNEL_6C3C_RUNBOOK.md Phase 1.1 + Phase 1/2 code-read note.
    Phase 2+ will assert INT4 dtype on k_cache/v_cache and route to
    the new mha_fwd_kvcache_int4 C++ entry. For now, INT4 args are
    accepted but ignored so the Phase 1 parity test can assert
    bit-equality with flash_attn_with_kvcache(...).
    """
    return flash_attn_with_kvcache(
        q,
        k_cache,
        v_cache,
        k=k,
        v=v,
        rotary_cos=rotary_cos,
        rotary_sin=rotary_sin,
        cache_seqlens=cache_seqlens,
        cache_batch_idx=cache_batch_idx,
        cache_leftpad=cache_leftpad,
        block_table=block_table,
        softmax_scale=softmax_scale,
        causal=causal,
        window_size=window_size,
        softcap=softcap,
        rotary_interleaved=rotary_interleaved,
        alibi_slopes=alibi_slopes,
        num_splits=num_splits,
        return_softmax_lse=return_softmax_lse,
    )
'''


def patch_python(path: Path):
    src = path.read_text()
    if "def flash_attn_with_int4_kvcache" in src:
        print(f"  SKIP (already patched): {path}")
        return
    path.write_text(src.rstrip() + "\n" + PY_PATCH)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 2: vllm_flash_attn/__init__.py — re-export the new wrapper
# ============================================================
#
# IMPORTANT: must use RELATIVE import. Absolute
# `from flash_attn.flash_attn_interface import ...` resolves to the
# standalone flash_attn package (not what vllm uses), which then
# tries to `import flash_attn_2_cuda` and crashes since that wheel
# isn't installed in venv-vllm.

FIXED_INIT_LINE = (
    "from .flash_attn_interface import flash_attn_with_int4_kvcache  "
    "# 6c.3C Phase 1\n"
)

BROKEN_INIT_LINE = (
    "from flash_attn.flash_attn_interface import "
    "flash_attn_with_int4_kvcache  # 6c.3C Phase 1\n"
)


def patch_init_py(path: Path):
    src = path.read_text()
    if FIXED_INIT_LINE.strip() in src:
        print(f"  SKIP (already correctly patched): {path}")
        return
    if BROKEN_INIT_LINE.strip() in src:
        # Repair the previous (buggy) absolute import.
        new_src = src.replace(BROKEN_INIT_LINE, FIXED_INIT_LINE)
        # Also handle the case where the broken line lacks a trailing
        # newline (older variant of this script).
        new_src = new_src.replace(BROKEN_INIT_LINE.rstrip(), FIXED_INIT_LINE.rstrip())
        path.write_text(new_src)
        print(f"  REPAIRED (relative import): {path}")
        return
    # Fresh apply.
    path.write_text(src.rstrip() + "\n" + FIXED_INIT_LINE)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 3: csrc/flash_attn/src/flash.h — Flash_fwd_params fields
# ============================================================

FLASH_H_FIELDS = """
    // ===== 6c.3C Phase 1: INT4 KV cache extension (NULL / 0 default) =====
    // Phase 1 plumbs these but the kernel does not read them yet.
    // Phase 4 (protected-K sidecar) consumes them after Phase 2 (INT4 K).
    void * __restrict__ k_scale_ptr = nullptr;
    void * __restrict__ k_offset_ptr = nullptr;
    void * __restrict__ v_scale_ptr = nullptr;
    void * __restrict__ v_offset_ptr = nullptr;
    void * __restrict__ k_cache_protect_mask_ptr = nullptr;
    void * __restrict__ k_cache_protect_indices_ptr = nullptr;
    void * __restrict__ k_cache_fp16_protect_ptr = nullptr;
    index_t k_scale_batch_stride = 0;
    index_t k_scale_row_stride = 0;
    index_t v_scale_batch_stride = 0;
    index_t v_scale_row_stride = 0;
    index_t k_cache_protect_mask_stride = 0;
    index_t k_cache_fp16_protect_batch_stride = 0;
    index_t k_cache_fp16_protect_head_stride = 0;
    int group_size_k = 0;
    int group_size_v = 0;
    int n_protect = 0;
    bool is_int4kv = false;
"""


def patch_flash_h(path: Path):
    src = path.read_text()
    if "is_int4kv" in src:
        print(f"  SKIP (already patched): {path}")
        return
    # Anchor: the very last field of Flash_fwd_params.
    anchor = "bool seqlenq_ngroups_swapped;"
    if anchor not in src:
        raise RuntimeError(f"can't find anchor `{anchor}` in {path}")
    # Insert the new fields RIGHT AFTER the anchor line.
    lines = src.split("\n")
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and anchor in line:
            out.append(FLASH_H_FIELDS.rstrip())
            inserted = True
    path.write_text("\n".join(out))
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 4: csrc/flash_attn/flash_api.cpp — mha_fwd_kvcache_int4
# ============================================================

API_CPP_FN = """
// ============================================================
// 6c.3C Phase 1 — INT4 KV cache no-op forwarder.
// Added by apply_phase1_patches.py. In Phase 1, this forwards
// to mha_fwd_kvcache and ignores the INT4 args. The new
// Flash_fwd_params fields stay NULL/0 since Phase 1 doesn't
// build a different code path. Phase 2 adds the dispatch arm
// + the cloned _int4kv kernel variant.
// ============================================================
std::vector<at::Tensor>
mha_fwd_kvcache_int4(at::Tensor &q,
                     const at::Tensor &kcache,
                     const at::Tensor &vcache,
                     std::optional<const at::Tensor> &k_,
                     std::optional<const at::Tensor> &v_,
                     std::optional<const at::Tensor> &seqlens_k_,
                     std::optional<const at::Tensor> &rotary_cos_,
                     std::optional<const at::Tensor> &rotary_sin_,
                     std::optional<const at::Tensor> &cache_batch_idx_,
                     std::optional<const at::Tensor> &leftpad_k_,
                     std::optional<at::Tensor> &block_table_,
                     std::optional<at::Tensor> &alibi_slopes_,
                     std::optional<at::Tensor> &out_,
                     const float softmax_scale,
                     bool is_causal,
                     int window_size_left,
                     int window_size_right,
                     const float softcap,
                     bool is_rotary_interleaved,
                     int num_splits,
                     // INT4 extension (Phase 1: ignored)
                     std::optional<const at::Tensor> &k_scale_,
                     std::optional<const at::Tensor> &k_offset_,
                     std::optional<const at::Tensor> &v_scale_,
                     std::optional<const at::Tensor> &v_offset_,
                     std::optional<const at::Tensor> &k_fp16_protect_,
                     std::optional<const at::Tensor> &protect_mask_,
                     std::optional<const at::Tensor> &protect_indices_,
                     int group_size_k,
                     int group_size_v,
                     int n_protect) {
    (void)k_scale_; (void)k_offset_; (void)v_scale_; (void)v_offset_;
    (void)k_fp16_protect_; (void)protect_mask_; (void)protect_indices_;
    (void)group_size_k; (void)group_size_v; (void)n_protect;
    return mha_fwd_kvcache(
        q, kcache, vcache, k_, v_, seqlens_k_,
        rotary_cos_, rotary_sin_, cache_batch_idx_, leftpad_k_,
        block_table_, alibi_slopes_, out_,
        softmax_scale, is_causal,
        window_size_left, window_size_right,
        softcap, is_rotary_interleaved, num_splits);
}
"""


def patch_api_cpp(path: Path):
    src = path.read_text()
    if "mha_fwd_kvcache_int4" in src:
        print(f"  SKIP (already patched): {path}")
        return
    # Try inserting before namespace close; otherwise EOF.
    ns_close = "} // namespace FLASH_NAMESPACE"
    if ns_close in src:
        new_src = src.replace(ns_close, API_CPP_FN.rstrip() + "\n\n" + ns_close)
    else:
        new_src = src.rstrip() + "\n" + API_CPP_FN
    path.write_text(new_src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 5: csrc/flash_attn/flash_api_torch_lib.cpp
# ============================================================

TORCH_LIB_FWD = """

std::vector<at::Tensor>
mha_fwd_kvcache_int4(at::Tensor &q,
                     const at::Tensor &kcache,
                     const at::Tensor &vcache,
                     std::optional<const at::Tensor> &k_,
                     std::optional<const at::Tensor> &v_,
                     std::optional<const at::Tensor> &seqlens_k_,
                     std::optional<const at::Tensor> &rotary_cos_,
                     std::optional<const at::Tensor> &rotary_sin_,
                     std::optional<const at::Tensor> &cache_batch_idx_,
                     std::optional<const at::Tensor> &leftpad_k_,
                     std::optional<at::Tensor> &block_table_,
                     std::optional<at::Tensor> &alibi_slopes_,
                     std::optional<at::Tensor> &out_,
                     const float softmax_scale,
                     bool is_causal,
                     int window_size_left,
                     int window_size_right,
                     const float softcap,
                     bool is_rotary_interleaved,
                     int num_splits,
                     std::optional<const at::Tensor> &k_scale_,
                     std::optional<const at::Tensor> &k_offset_,
                     std::optional<const at::Tensor> &v_scale_,
                     std::optional<const at::Tensor> &v_offset_,
                     std::optional<const at::Tensor> &k_fp16_protect_,
                     std::optional<const at::Tensor> &protect_mask_,
                     std::optional<const at::Tensor> &protect_indices_,
                     int group_size_k,
                     int group_size_v,
                     int n_protect);
"""

TORCH_LIB_REG = """
    // 6c.3C Phase 1: INT4 KV cache no-op forwarder.
    ops.def("fwd_kvcache_int4(Tensor! q, Tensor kcache, Tensor vcache, Tensor? k, Tensor? v, Tensor? seqlens_k, "
            "Tensor? rotary_cos, Tensor? rotary_sin, Tensor? cache_batch_idx, Tensor? leftpad_k, Tensor? block_table, "
            "Tensor? alibi_slopes, Tensor!? out, float softmax_scale, bool is_causal, int window_size_left, "
            "int window_size_right, float softcap, bool is_rotary_interleaved, int num_splits, "
            "Tensor? k_scale, Tensor? k_offset, Tensor? v_scale, Tensor? v_offset, "
            "Tensor? k_fp16_protect, Tensor? protect_mask, Tensor? protect_indices, "
            "int group_size_k, int group_size_v, int n_protect) -> Tensor[]");
    ops.impl("fwd_kvcache_int4", torch::kCUDA, make_pytorch_shim(&mha_fwd_kvcache_int4));
"""


def patch_torch_lib(path: Path):
    src = path.read_text()
    if "mha_fwd_kvcache_int4" in src:
        print(f"  SKIP (already patched): {path}")
        return

    # Insert forward decl AFTER mha_fwd_kvcache's existing forward decl.
    # The decl ends with `int num_splits);` AFTER the `mha_fwd_kvcache(` start.
    start_idx = src.find("mha_fwd_kvcache(")
    if start_idx == -1:
        raise RuntimeError(f"can't find mha_fwd_kvcache decl in {path}")
    end_marker = "int num_splits);"
    end_idx = src.find(end_marker, start_idx)
    if end_idx == -1:
        raise RuntimeError(f"can't find end of mha_fwd_kvcache decl in {path}")
    end_idx += len(end_marker)
    new_src = src[:end_idx] + TORCH_LIB_FWD + src[end_idx:]

    # Insert registration AFTER the existing fwd_kvcache ops.impl.
    reg_anchor = 'ops.impl("fwd_kvcache", torch::kCUDA, make_pytorch_shim(&mha_fwd_kvcache));'
    if reg_anchor not in new_src:
        raise RuntimeError(f"can't find ops.impl(fwd_kvcache) anchor in {path}")
    new_src = new_src.replace(
        reg_anchor,
        reg_anchor + TORCH_LIB_REG.rstrip(),
    )

    path.write_text(new_src)
    print(f"  PATCHED: {path}")


# ============================================================
# Main
# ============================================================

def main():
    if not DEV_ROOT.exists():
        print(f"ERROR: dev tree not at {DEV_ROOT}", file=sys.stderr)
        return 1

    targets = [
        # The vllm-specific slim flash_attn_interface.py is the one
        # that ships in the wheel. The ~63KB standalone
        # flash_attn/flash_attn_interface.py is dormant for vllm
        # purposes (kept untouched if it was patched by a previous
        # buggy run — harmless).
        (DEV_ROOT / "vllm_flash_attn/flash_attn_interface.py", patch_python),
        (DEV_ROOT / "vllm_flash_attn/__init__.py", patch_init_py),
        (DEV_ROOT / "csrc/flash_attn/src/flash.h", patch_flash_h),
        (DEV_ROOT / "csrc/flash_attn/flash_api.cpp", patch_api_cpp),
        (DEV_ROOT / "csrc/flash_attn/flash_api_torch_lib.cpp", patch_torch_lib),
    ]
    print("Applying Phase 1 patches:")
    for path, fn in targets:
        if not path.exists():
            print(f"  MISSING: {path}", file=sys.stderr)
            return 1
        try:
            fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR on {path}: {e}", file=sys.stderr)
            return 1

    print()
    print("Patches applied. Next steps:")
    print("  cd /workspace/dev/vllm-flash-attn-dev")
    print("  TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16 NVCC_THREADS=2 \\")
    print("      python setup.py bdist_wheel  # incremental — only changed TUs")
    print("  bash /workspace/symbolu/CTM_plus/Bench/scripts/install_dev_vllm_flash_attn.sh")
    print("  python /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase1.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
