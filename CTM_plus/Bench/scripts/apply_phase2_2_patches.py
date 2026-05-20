#!/usr/bin/env python3
"""apply_phase2_2_patches.py — 6c.3C Phase 2.2: route through the new INT4 dispatch.

Modifies 3 files in /workspace/dev/vllm-flash-attn-dev. Active code
path becomes Python -> flash_attn_with_int4_kvcache ->
torch.ops._vllm_fa2_C.fwd_kvcache_int4 -> mha_fwd_kvcache_int4 ->
mha_fwd_kvcache + thread-local Int4KvDispatchGuard ->
run_mha_fwd -> run_mha_fwd_splitkv_dispatch_int4kv (the dead-code
function from Phase 2.1, now LIVE).

The cloned _int4kv kernel is still identical content to stock, so
bit-equality with stock FA must hold. verify_phase1.py is the
unchanged acceptance test.

Patches:

  1. csrc/flash_attn/flash_api.cpp
     - Add Int4KvDispatchGuard RAII helper (thread-local routing
       flag) at file scope, right before run_mha_fwd (line ~241).
     - Modify run_mha_fwd to read the flag into params.is_int4kv
       on entry, and conditionally dispatch to
       run_mha_fwd_splitkv_dispatch_int4kv when params.is_int4kv is
       true. Only at the v1-supported instantiation
       (bf16/hdim128/non-causal) via if constexpr — other shapes
       fall back to stock since the _int4kv dispatch is not
       instantiated for them yet.
     - Modify mha_fwd_kvcache_int4 body to instantiate
       Int4KvDispatchGuard before forwarding to mha_fwd_kvcache.

  2. vllm_flash_attn/flash_attn_interface.py
     - Replace flash_attn_with_int4_kvcache body: now calls
       torch.ops._vllm_fa2_C.fwd_kvcache_int4 directly (preprocesses
       like flash_attn_with_kvcache: maybe_contiguous, softmax_scale
       default, cache_seqlens int->tensor) and passes the INT4 args
       through to the C++ side (where they're still ignored).

Idempotent: re-running is a no-op (each patch checks for a sentinel
string before applying).

Acceptance criterion (verify_phase1.py):
  Python wrapper now routes through the new C++ entry + new dispatch
  + cloned (identical) kernel. Output must STILL be bit-equal to
  flash_attn_with_kvcache(...) on Qwen2.5-7B shapes.
"""

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1A: flash_api.cpp — add the Int4KvDispatchGuard helper
# ============================================================

GUARD_HELPER = '''
// ============================================================
// 6c.3C Phase 2.2: thread-local routing flag.
// mha_fwd_kvcache_int4 sets this via Int4KvDispatchGuard before
// forwarding to mha_fwd_kvcache; run_mha_fwd reads it on entry
// and writes params.is_int4kv. The split-kv dispatch site below
// then routes to run_mha_fwd_splitkv_dispatch_int4kv when
// params.is_int4kv == true. Thread-local makes the pattern safe
// under concurrent calls.
// ============================================================
namespace {
thread_local bool _int4kv_dispatch = false;
struct Int4KvDispatchGuard {
    Int4KvDispatchGuard() { _int4kv_dispatch = true; }
    ~Int4KvDispatchGuard() { _int4kv_dispatch = false; }
};
}  // namespace

'''


# ============================================================
# Patch 1B: flash_api.cpp — modify run_mha_fwd
# ============================================================

RUN_MHA_FWD_OLD = '''void run_mha_fwd(Flash_fwd_params &params, cudaStream_t stream, bool force_split_kernel=false) {
    FP16_SWITCH(!params.is_bf16, [&] {
        HEADDIM_SWITCH(params.d, [&] {
            BOOL_SWITCH(params.is_causal, Is_causal, [&] {
                if (params.num_splits <= 1 && !force_split_kernel) {  // If we don't set it num_splits == 0
                    run_mha_fwd_<elem_type, kHeadDim, Is_causal>(params, stream);
                } else {
                    run_mha_fwd_splitkv_dispatch<elem_type, kHeadDim, Is_causal>(params, stream);
                }
            });
        });
    });
}'''

RUN_MHA_FWD_NEW = '''void run_mha_fwd(Flash_fwd_params &params, cudaStream_t stream, bool force_split_kernel=false) {
    // 6c.3C Phase 2.2: read thread-local dispatch flag set by
    // Int4KvDispatchGuard. params.is_int4kv stays false when
    // called via the stock mha_fwd_kvcache path.
    params.is_int4kv = _int4kv_dispatch;
    FP16_SWITCH(!params.is_bf16, [&] {
        HEADDIM_SWITCH(params.d, [&] {
            BOOL_SWITCH(params.is_causal, Is_causal, [&] {
                if (params.num_splits <= 1 && !force_split_kernel) {  // If we don't set it num_splits == 0
                    run_mha_fwd_<elem_type, kHeadDim, Is_causal>(params, stream);
                } else {
                    // 6c.3C Phase 2.2: route to _int4kv dispatch only at the v1-
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
                    }
                }
            });
        });
    });
}'''


# ============================================================
# Patch 1C: flash_api.cpp — modify mha_fwd_kvcache_int4 body
# ============================================================

INT4_BODY_OLD = '''    (void)k_scale_; (void)k_offset_; (void)v_scale_; (void)v_offset_;
    (void)k_fp16_protect_; (void)protect_mask_; (void)protect_indices_;
    (void)group_size_k; (void)group_size_v; (void)n_protect;
    return mha_fwd_kvcache(
        q, kcache, vcache, k_, v_, seqlens_k_,
        rotary_cos_, rotary_sin_, cache_batch_idx_, leftpad_k_,
        block_table_, alibi_slopes_, out_,
        softmax_scale, is_causal,
        window_size_left, window_size_right,
        softcap, is_rotary_interleaved, num_splits);'''

INT4_BODY_NEW = '''    (void)k_scale_; (void)k_offset_; (void)v_scale_; (void)v_offset_;
    (void)k_fp16_protect_; (void)protect_mask_; (void)protect_indices_;
    (void)group_size_k; (void)group_size_v; (void)n_protect;
    // 6c.3C Phase 2.2: flip dispatch to _int4kv via thread-local.
    // RAII guard resets the flag on return (or exception).
    Int4KvDispatchGuard guard;
    return mha_fwd_kvcache(
        q, kcache, vcache, k_, v_, seqlens_k_,
        rotary_cos_, rotary_sin_, cache_batch_idx_, leftpad_k_,
        block_table_, alibi_slopes_, out_,
        softmax_scale, is_causal,
        window_size_left, window_size_right,
        softcap, is_rotary_interleaved, num_splits);'''


def patch_flash_api_cpp(path: Path):
    src = path.read_text()
    if "_int4kv_dispatch" in src and "Int4KvDispatchGuard guard;" in src:
        print(f"  SKIP (already patched): {path}")
        return

    # 1A: Add the guard helper right BEFORE run_mha_fwd.
    if "Int4KvDispatchGuard" not in src:
        anchor = "void run_mha_fwd(Flash_fwd_params &params,"
        if anchor not in src:
            raise RuntimeError(f"can't find run_mha_fwd anchor in {path}")
        src = src.replace(anchor, GUARD_HELPER + anchor, 1)

    # 1B: Modify run_mha_fwd body.
    if "_int4kv_dispatch" in src and RUN_MHA_FWD_OLD not in src:
        pass  # already done
    elif RUN_MHA_FWD_OLD in src:
        src = src.replace(RUN_MHA_FWD_OLD, RUN_MHA_FWD_NEW)
    else:
        raise RuntimeError(f"can't find run_mha_fwd body anchor in {path}")

    # 1C: Modify mha_fwd_kvcache_int4 body.
    if "Int4KvDispatchGuard guard;" in src:
        pass  # already done
    elif INT4_BODY_OLD in src:
        src = src.replace(INT4_BODY_OLD, INT4_BODY_NEW)
    else:
        raise RuntimeError(
            f"can't find mha_fwd_kvcache_int4 body anchor in {path}"
        )

    path.write_text(src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 2: vllm_flash_attn/flash_attn_interface.py
# ============================================================

PY_OLD_DELEGATE_HEAD = "def flash_attn_with_int4_kvcache("
PY_NEW_FN = '''def flash_attn_with_int4_kvcache(
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
    *,
    out=None,
):
    """6c.3C Phase 2.2 — routes through torch.ops._vllm_fa2_C.fwd_kvcache_int4.

    Initially identical numerics to flash_attn_with_kvcache: the
    C++ side dispatches via the parallel _int4kv kernel template,
    which has the same body as stock until Phase 4 (NO-OP transform
    + INT4 K read) modifies it. INT4 args are accepted but unused
    by the kernel until then.

    Acceptance test: verify_phase1.py — bit-equality with stock FA.
    """
    assert k_cache.stride(-1) == 1, "k_cache must have contiguous last dimension"
    assert v_cache.stride(-1) == 1, "v_cache must have contiguous last dimension"
    q, k, v = [maybe_contiguous(x) for x in (q, k, v)]
    if softmax_scale is None:
        softmax_scale = q.shape[-1] ** (-0.5)
    if cache_seqlens is not None and isinstance(cache_seqlens, int):
        cache_seqlens = torch.full(
            (k_cache.shape[0],), cache_seqlens, dtype=torch.int32, device=k_cache.device
        )
        cache_seqlens = maybe_contiguous(cache_seqlens)
    cache_batch_idx = maybe_contiguous(cache_batch_idx)
    block_table = maybe_contiguous(block_table)

    out, softmax_lse = torch.ops._vllm_fa2_C.fwd_kvcache_int4(
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
    )
    return (out, softmax_lse) if return_softmax_lse else out
'''


def patch_python(path: Path):
    src = path.read_text()
    if "torch.ops._vllm_fa2_C.fwd_kvcache_int4" in src:
        print(f"  SKIP (already patched): {path}")
        return
    # Find the Phase 1 version and replace it. The Phase 1 wrapper
    # starts at `def flash_attn_with_int4_kvcache(` and ends at the
    # matching closing of the body (it's the last function in the
    # file, at EOF essentially).
    start_idx = src.find(PY_OLD_DELEGATE_HEAD)
    if start_idx == -1:
        raise RuntimeError(
            f"can't find existing flash_attn_with_int4_kvcache in {path}"
        )
    # The Phase 1 wrapper extends to the end of the file (it was
    # appended). Replace from start_idx to EOF with the new function.
    src = src[:start_idx] + PY_NEW_FN
    path.write_text(src.rstrip() + "\n")
    print(f"  PATCHED: {path}")


# ============================================================
# Main
# ============================================================

def main():
    if not DEV_ROOT.exists():
        print(f"ERROR: dev tree not at {DEV_ROOT}", file=sys.stderr)
        return 1

    targets = [
        (DEV_ROOT / "csrc/flash_attn/flash_api.cpp", patch_flash_api_cpp),
        (DEV_ROOT / "vllm_flash_attn/flash_attn_interface.py", patch_python),
    ]

    print("Applying Phase 2.2 patches:")
    for path, fn in targets:
        try:
            fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR on {path}: {e}", file=sys.stderr)
            return 1

    print()
    print("Patches applied. Next: rebuild + install + verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
