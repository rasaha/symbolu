# Kernel 6c.3C — Phase 1 + Phase 2 code-read (reference)

> Output of the 2026-05-20 background code-read of the actual files
> at SHA `720c948` via GitHub. Two artifacts:
>
> 1. **Phase 2 risk brief** — confirms (refutes-and-strengthens, in
>    fact) the runbook's "bypass CUTLASS for INT4" mitigation.
> 2. **Phase 1 patch sketch** — concrete additive diffs ready to apply
>    against `/workspace/dev/vllm-flash-attn-dev/` once Phase 0 build
>    completes and the smoke test runs green.
>
> Reference only — not the implementation. The runbook's Phase 1
> acceptance criterion ("bit-identical to stock FA when called with
> NULL quant args") differs subtly from the agent's sketch (which
> asserts INT4 dtype in the Python wrapper). When implementing, the
> Python wrapper in Phase 1 must be a no-op delegate to
> `flash_attn_with_kvcache` so the smoke test can verify parity.
> The agent's INT4-asserting wrapper is the Phase 3+ version.

---

## Artifact A — Phase 2 risk brief

### Copy-atom infrastructure

The K/V reads in `compute_attn_1rowblock_splitkv`
(`flash_fwd_kernel.h:~499`) use `Kernel_traits::GmemTiledCopyQKVPaged`
— a CUTLASS copy atom specialized for paged KV cache with block-table
indirection. Four copy sites:

1. **Initial K load** (~line 499):
   ```cpp
   FLASH_NAMESPACE::copy<Is_even_MN, Is_even_K>(gmem_tiled_copy_KV,
       tKgK, tKsK, tKVcKV, tKVpKV,
       binfo.actual_seqlen_k - n_block * kBlockN);
   ```
2. **Masked iteration K/V** (~530-560):
   ```cpp
   FLASH_NAMESPACE::copy<Is_even_MN, Is_even_K, /*Clear_OOB_MN=*/true>(
       gmem_tiled_copy_KV, tVgV, tVsV, tKVcKV, tKVpKV,
       binfo.actual_seqlen_k - n_block * kBlockN);
   ```
3. **Subsequent K loads:** same shape, `Is_even_MN=true`.
4. **Non-masked V reads:** same shape, V tile.

### Element type and load alignment

`GmemTiledCopyQKVPaged` is parameterized on the input tensor dtype
(BF16 in `flash_fwd_split_hdim128_bf16_sm80.cu`). CUTLASS cp.async
loads in 16-byte chunks aligned to uint128. BF16 = 2 bytes →
**8 elements per transaction**.

INT4 packed = 0.5 bytes/element. This **violates CUTLASS's
lane-width assumptions** — three concrete failure modes:

1. **Misaligned loads.** cp.async expects 2-byte (BF16) or 1-byte
   strides. INT4 packed as uint8 (one uint8 = two int4 values)
   makes the copy atom skip half-lanes or load garbage.
2. **Smem layout mismatch.** Thread tile `tKsK` expects BF16
   elements. Writing uint8 via the copy atom misaligns subsequent
   smem→register reads in the qK dot.
3. **Block-table stride mismatch.** The paged copy atom's
   `resolve_thread_kv_page_slice_offset` is element-size-agnostic,
   but returned pointers assume dense BF16. INT4 with group_size=32
   has page strides differing by 2× (512 elements = 256 B BF16 vs
   128 B INT4); pointer arithmetic skips half the data.

### Verdict — bypass CUTLASS is REQUIRED, not just plausible

The runbook's Phase 2 mitigation ("v1 picks (b): load-then-process
pattern that bypasses CUTLASS for the INT4 path") was the right
call. Phase 2 must:

1. Compute page-aware global pointers manually using scaled strides
   (stride × group_size / 2 for INT4).
2. Load via `__ldg(reinterpret_cast<uint4*>(ptr))` or
   `cp.async.global.16` with explicit offset arithmetic.
3. **Unpack uint4 in registers immediately after load** (two int4
   values per byte).
4. **Dequantize in-register** using scale/offset tensors (pulled
   into registers or smem miniset).
5. Write dequantized BF16 to `tKsK` via scalar stores or a
   lightweight custom smem barrier.

### Where dequant fits — in-register, pre-smem

The dequant must occur **after the global load but before writing
to shared memory**. Once INT4 unpacks to int4 scalars in registers
and dequants to BF16, the downstream qK dot sees standard BF16 in
smem — unchanged. This avoids secondary register-pressure swells
in the dot phase.

**Shared-memory constraints.** D=128, thread block = 64×128 = ~64
regs/thread for K smem tile (~8 KB/block). INT4 read 0.5 B/element
→ 4 KB global→smem; remaining 4 KB for O/LSE/workspace. A temp
uint4 smem ping-pong for unpacking is feasible (~1 KB more) —
acceptable at block_size=32 (page capacity 512 elements = 256 B
live INT4).

**Register pressure.** Unpack 2 int4 values (1 byte → 2×8-bit
intermediate → 2×bf16 via denorm+scale) ≈ 4-6 registers/thread;
with ~200 available, low-risk.

### Implications for runbook Phase 2 effort estimate

The runbook estimated Phase 2 at 5 engineer-days. The code-read
confirms the complexity but doesn't expand the surface — the
mitigation works as planned. The 5-day estimate stands.

The only new finding worth re-recording in the runbook: Phase 2's
acceptance criterion (cosine ≥ 0.999 vs the existing oracle) is
contingent on the *unpack* + *dequant* being numerically identical
to route-B's reference `quantize_per_channel_int4` /
`dequantize_per_channel_int4` ops. Borrow the exact int4-rounding
convention from `kv_policy/int4_per_channel_kv.py` to avoid a
silent ±1 LSB drift that would tank the cosine.

---

## Artifact B — Phase 1 patch sketch

### Runbook-Phase-1 reminder

Phase 1's acceptance criterion is "additive only, behaviour
bit-identical to stock FA when called with NULL quant args". The
patches below are concrete but **the Python wrapper must be a
no-op delegate** to `flash_attn_with_kvcache` in Phase 1 — the
agent's INT4-asserting version belongs in Phase 3+. Annotated
inline below where the sketch needs Phase-1-trimming.

### Patch 1 — `flash_attn/flash_attn_interface.py`

```python
def flash_attn_with_int4_kvcache(
    q, k_cache_int4, v_cache_int4, k=None, v=None,
    k_cache_scales=None, k_cache_offsets=None,
    v_cache_scales=None, v_cache_offsets=None,
    k_cache_protect_mask=None, k_cache_protect_indices=None,
    k_cache_fp16_protect=None,
    group_size_k=32, group_size_v=32, n_protect=0,
    rotary_cos=None, rotary_sin=None,
    cache_seqlens=None, cache_batch_idx=None,
    block_table=None,
    softmax_scale=None, causal=False,
    window_size=(-1, -1), softcap=0.0,
    rotary_interleaved=True, alibi_slopes=None,
    num_splits=0, return_softmax_lse=False,
):
    """Forward attention with INT4-quantized KV cache.

    Phase 1: no-op delegate to flash_attn_with_kvcache. INT4
    arguments are accepted but unused — the C++ side runs the stock
    BF16 path. Smoke test verifies parity with stock FA.

    Phase 2+: this wrapper will assert INT4 dtype on k_cache /
    v_cache and route to mha_fwd_kvcache_int4.
    """
    # PHASE 1 — DO NOT ENABLE THE ASSERT YET
    # assert k_cache_int4.dtype == torch.uint8 ...
    return flash_attn_with_kvcache(
        q, k_cache_int4, v_cache_int4, k=k, v=v,
        rotary_cos=rotary_cos, rotary_sin=rotary_sin,
        cache_seqlens=cache_seqlens, cache_batch_idx=cache_batch_idx,
        block_table=block_table,
        softmax_scale=softmax_scale, causal=causal,
        window_size=window_size, softcap=softcap,
        rotary_interleaved=rotary_interleaved,
        alibi_slopes=alibi_slopes,
        num_splits=num_splits, return_softmax_lse=return_softmax_lse,
    )
```

### Patch 2 — `csrc/flash_attn/src/flash.h`

```cpp
struct Flash_fwd_params : public Qkv_params {
    // ... existing fields ...

    // ----- INT4 KV extension (Phase 1: all NULL/0 by default) -----
    void*    k_scale_ptr               = nullptr;
    void*    k_offset_ptr              = nullptr;
    void*    v_scale_ptr               = nullptr;
    void*    v_offset_ptr              = nullptr;
    void*    k_cache_protect_mask_ptr  = nullptr;
    void*    k_cache_protect_indices_ptr = nullptr;
    void*    k_cache_fp16_protect_ptr  = nullptr;

    uint32_t k_scale_batch_stride      = 0;
    uint32_t k_scale_row_stride        = 0;
    uint32_t v_scale_batch_stride      = 0;
    uint32_t v_scale_row_stride        = 0;
    uint32_t k_cache_protect_mask_stride = 0;
    uint32_t k_cache_fp16_protect_batch_stride = 0;
    uint32_t k_cache_fp16_protect_head_stride  = 0;

    uint32_t group_size_k              = 0;
    uint32_t group_size_v              = 0;
    uint32_t n_protect                 = 0;
    bool     is_int4kv                 = false;
};
```

### Patch 3 — `csrc/flash_attn/flash_api.cpp`

Phase 1 simpler than agent's sketch: `mha_fwd_kvcache_int4` is just
a forwarding wrapper to `mha_fwd_kvcache`. Defer the dispatch-arm
plumbing to Phase 2.

```cpp
std::vector<at::Tensor>
mha_fwd_kvcache_int4(at::Tensor &q,
                     const at::Tensor &kcache,
                     const at::Tensor &vcache,
                     // ... full signature mirroring mha_fwd_kvcache ...
                     std::optional<const at::Tensor> &k_cache_scales,
                     std::optional<const at::Tensor> &v_cache_scales,
                     // ... etc ...
                     bool return_softmax_lse) {
    // Phase 1: ignore INT4 args, delegate to stock entry.
    // Phase 2 will validate INT4 dtype, plumb new params, route
    // to run_mha_fwd_splitkv_dispatch_int4kv.
    return mha_fwd_kvcache(q, kcache, vcache, /* etc */,
                           return_softmax_lse);
}
```

### Patch 4 — `csrc/flash_attn/flash_api_torch_lib.cpp`

```cpp
m.def("fwd_kvcache_int4",
      &mha_fwd_kvcache_int4,
      "q"_a, "kcache_int4"_a, "vcache_int4"_a,
      "k"_a = nullptr, "v"_a = nullptr,
      "k_cache_scales"_a = nullptr, "k_cache_offsets"_a = nullptr,
      "v_cache_scales"_a = nullptr, "v_cache_offsets"_a = nullptr,
      "k_cache_protect_mask"_a = nullptr,
      "k_cache_protect_indices"_a = nullptr,
      "k_cache_fp16_protect"_a = nullptr,
      "group_size_k"_a = 32, "group_size_v"_a = 32,
      "n_protect"_a = 0,
      // ... rest mirrors mha_fwd_kvcache ...
      "return_softmax_lse"_a = false);
```

### Patch 5 — Phase-1-only: skip the new dispatch arm and the cloned .cu

The agent's sketch adds a `run_mha_fwd_splitkv_dispatch_int4kv`
dispatch arm and a new `flash_fwd_split_hdim128_bf16_int4kv_sm80.cu`
in Phase 1. **For runbook Phase 1, both are deferred.** Phase 1 just
needs the new entry point routing back to the stock dispatch.

This keeps Phase 1's diff minimal: ~50 lines across 4 files. The
Phase 1.4 step in the runbook (clone the .cu file) and Phase 1.3
(new dispatch arm) become Phase 2 work — the moment we want a
genuinely different kernel body to route to, the dispatch arm and
the new .cu earn their existence.

### Revised Phase 1 acceptance test

```python
# After build + install, the smoke test does:
import torch
from vllm.vllm_flash_attn import flash_attn_with_kvcache
from vllm.vllm_flash_attn.flash_attn_interface import (
    flash_attn_with_int4_kvcache,
)

# Same inputs to both — Phase 1 INT4 wrapper just delegates.
q = torch.randn(1, 1, 28, 128, device="cuda", dtype=torch.bfloat16)
k = torch.randn(1, 32768, 4, 128, device="cuda", dtype=torch.bfloat16)
v = torch.randn(1, 32768, 4, 128, device="cuda", dtype=torch.bfloat16)
csl = torch.full((1,), 32768, device="cuda", dtype=torch.int32)

out_stock = flash_attn_with_kvcache(q, k, v, cache_seqlens=csl)
out_int4  = flash_attn_with_int4_kvcache(q, k, v, cache_seqlens=csl)
assert torch.equal(out_stock, out_int4), "Phase 1 parity broken"
```

If this assertion holds bit-for-bit, Phase 1 is GREEN. Then Phases
2-4 begin.

---

## What this code-read changes in the design / runbook

1. **`KERNEL_6C3C_RUNBOOK.md` Phase 1.3 / Phase 1.4** — these two
   steps (new dispatch arm + cloned .cu file) move from Phase 1 to
   the beginning of Phase 2. Phase 1 reduces to: new Python
   wrapper + new C++ entry + Flash_fwd_params extension + pybind
   registration. Smaller surface, faster cycle.
2. **`KERNEL_6C3C_RUNBOOK.md` Phase 2.1 prefix** — Phase 2 now opens
   with "clone the kernel + add the dispatch arm" (the work moved
   out of Phase 1) before the K-read modifications.
3. **No change to Phase 2 effort estimate (5 days).** The work just
   re-partitions across Phase 1/2 boundaries.
4. **New invariant for Phase 2:** the INT4 unpack + dequant inside
   the kernel MUST be numerically identical to route-B's reference
   ops in `kv_policy/int4_per_channel_kv.py`, or the cosine test
   against the existing oracle will fail silently with a ±1 LSB
   drift.
