# Kernel 6c.3C — Phase 2.3 insertion-point analysis

> Focused read of `compute_attn_1rowblock_splitkv` in
> `csrc/flash_attn/src/flash_fwd_kernel.h` at SHA `720c948`. Pins the
> insertion point for the in-kernel INT4 K transform.
>
> Written retroactively after Phase 2.3 / 2.5 / 3 / 4 landed GREEN, as
> an audit of the insertion-point reasoning. The 7 questions are the
> standard pre-flight checklist for any new kernel-side modification;
> this doc answers them for K, and serves as a template for Phase 2.4
> (REAL INT4 K HBM read) and any future kernel work in Phase 5+.

## 1. Where K is loaded from global memory

Three sites in `compute_attn_1rowblock_splitkv`:

| # | Line | Code path | Function |
|---|---:|---|---|
| A | 851 | Prologue, before the masking loop | First K load (`K[n_block_max-1]`) |
| B | 929 | Inside `if (n_block > n_block_min)` in the masking loop | Reload for next iteration's K |
| C | 991 | Inside `if (n_block > n_block_min)` in the non-masking loop | Reload for next iteration's K |

All three use the same atom and pattern:
```cpp
FLASH_NAMESPACE::copy<...>(gmem_tiled_copy_KV, tKgK, tKsK, tKVcKV, tKVpKV[, ...]);
cute::cp_async_fence();
```

The cp.async writes go to smem buffer `sK` (the underlying tensor that
`tKsK` is a per-thread partition of) but do **not commit** until
`cp_async_wait` runs at the top of the next consuming iteration. This
is FA's standard software-pipelined K load — the load for block N+1
is issued at the end of iteration N+1 (or in the prologue for N=max),
committed at the top of iteration N.

## 2. Where K enters registers / fragment form

K enters registers inside the qK^T GEMM calls:

| Line | Code |
|---:|---|
| 902 | `FLASH_NAMESPACE::gemm(acc_s, tSrQ, tSrK, tSsQ, tSsK, tiled_mma, smem_tiled_copy_Q, smem_tiled_copy_K, ...);` |
| 973 | Same shape, non-masking loop |

The GEMM internally:
1. Uses `smem_tiled_copy_K` (the MMA-side atom) to load smem K → `tSrK` register fragment.
2. Runs the MMA on `tSrQ`/`tSrK` → `acc_s`.

The register fragment `tSrK` is declared at line 182:
`Tensor tSrK = thr_mma.partition_fragment_B(sK);` — typed on the same
`Element` as `sK`.

**Important:** smem K is read by `smem_tiled_copy_K`, not the original
`gmem_tiled_copy_KV` that wrote it. Both atoms are typed on
`Element = Kernel_traits::Element` (`cutlass::bfloat16_t` for our
target), so they agree on the element type. The smem layout
(`SmemLayoutKV`) is swizzled for bank-conflict-free MMA loads — both
atoms understand the swizzle.

## 3. Where the qK dot path begins

The qK^T dot **consumes** K at lines 902 (masking) and 973 (non-masking).
This is the deadline: any modification to smem K must complete and
sync before these GEMM calls.

The dot is followed by softcap, mask application, and softmax — none
of which touch K.

## 4. Safe insertion point for a NO-OP K transform

**YES — there is a unique safe window:** between
`cp_async_wait<0>() + __syncthreads()` (which commits K to smem) and
the `FLASH_NAMESPACE::gemm(...)` that consumes K.

Specifically:

| Loop | Wait site | GEMM site | Transform window |
|---|---:|---:|---|
| Masking | line 882-883 | line 902 | lines 884-901 |
| Non-masking | line 960-961 | line 973 | lines 962-972 |

Inside each window, the code issues a cp.async for V (V cp.async writes
to `sV`, a *different* smem buffer, so it does not conflict with our K
transform). The cp.async is non-blocking; its writes don't commit
until the next `cp_async_wait` at the bottom of this iteration. So
the V cp.async and our K transform can run concurrently without races.

**Safety invariants at the insertion point:**

- K is committed in smem (`cp_async_wait<0>()` ran).
- All threads see the committed K (`__syncthreads()` ran).
- No other code in this window reads or writes `sK` (V cp.async writes
  to `sV`).
- After the transform, an explicit `__syncthreads()` must run before
  the GEMM so all threads see the modified smem K. (The GEMM itself
  internally syncs but we should not rely on that.)

Phase 2.3 / 2.5 chose **immediately after the wait+sync**, before the
V cp.async setup. This is the simplest placement and works for all
three K loads (the prologue load A is committed by the masking loop's
first wait; loads B and C are committed by their respective loops'
subsequent waits).

**Three K loads, two insertion points in source.** The transform fires
once per loop iteration; the loops iterate N times, transforming N K
blocks. The two source-level insertions cover all three loads at
runtime.

## 5. Type/layout preservation for CUTLASS copy atoms

**YES, both must be preserved.** The downstream consumer
(`smem_tiled_copy_K` inside the GEMM) is typed on `Element` and
assumes the swizzled `SmemLayoutKV` layout. The transform must:

1. **Preserve element type.** Read `Element` from smem, transform in
   higher-precision registers (FP32), cast back to `Element` before
   write. If we wrote a different type (e.g., uint8 packed INT4), the
   consumer would misinterpret the bits.

2. **Preserve smem layout.** Operate through the CUTLASS tensor's
   element accessor (`tKsK(i, j, k)`) which applies the swizzle for
   both reads and writes. Do NOT use raw pointer arithmetic on
   `sK.data()` — that bypasses the swizzle.

Phase 2.3's helper does both correctly: reads `Element` via
`int4_inline_to_float<Element>(tKsK(i, j, k))`, transforms in FP32,
writes `Element` via `tKsK(i, j, k) = int4_inline_from_float<Element>(x_hat)`.

**Phase 2.4 (REAL INT4 HBM read) will need to break one or both.** That
phase loads packed uint8 from HBM into smem, then dequants to Element
before the GEMM reads. The smem layout has to either (a) stay
Element-typed (dequant happens in-register during a manual load, write
Element to smem) or (b) become a different layout matching the packed
uint8 (custom MMA-side atom). Option (a) keeps the existing GEMM atom
unchanged and is the simpler v1 path.

## 6. Compile-time flag / params field for gating

**Use a compile-time template parameter, not a runtime params field.**

After Phase 2.5, the gate is `template <... bool Is_int4kv = false>`
plumbed through:

```
run_mha_fwd_splitkv_dispatch       -> Is_int4kv=false (default)
run_mha_fwd_splitkv_dispatch_int4kv -> Is_int4kv=true
  → run_flash_splitkv_fwd<..., Is_int4kv>
    → flash_fwd_splitkv_kernel<..., Is_int4kv>
      → compute_attn_splitkv<..., Is_int4kv>
        → compute_attn_1rowblock_splitkv<..., Is_int4kv>
```

Inside the kernel: `if constexpr (Is_int4kv && ...)` gates the
transform. When `Is_int4kv == false`, the transform code (and its
smem scratchpad allocation) is eliminated by the compiler entirely.

Why template > runtime gate:

- **Static `__shared__` allocations are committed at kernel launch**,
  not at runtime branches. A runtime gate would still pay the smem
  cost (occupancy hit) on every call. Phase 2.3 ate a +19% kernel
  latency regression on stock FA from this; Phase 2.5 fixed it by
  switching to template gating.
- **Runtime branches consume registers** even when the branch is not
  taken (the branch logic needs registers for the condition).
  `if constexpr` doesn't.
- **nvcc fully eliminates `if constexpr` false branches.** The
  compiled kernel for the stock path is byte-identical to a kernel
  without the transform code present.

The `params.is_int4kv` field still exists (Phase 1 added it, Phase 2.2
plumbed it through `Int4KvDispatchGuard`'s thread-local) but is now
informational only — the template parameter carries the dispatch
decision. The field can be useful for kernel-internal assertions or
debug logging.

## 7. Bit-equivalence acceptance test

Two distinct tests for two distinct paths:

### Stock FP16 path (`Is_int4kv=false`)

**Test:** kernel output before and after Phase 2.3 must be
bit-identical for `flash_attn_with_kvcache` calls.

**How:** `smoke_test_fa_install.sh` checks FA p50 microbench against
the 2026-05-20 baseline (67.3 μs @ S=16k, ±10% threshold) AND cell-A
throughput (28.4 tok/s @ S=32k, ±5% threshold). After Phase 2.5,
both restored to baseline (66.7 μs and 28.44 tok/s respectively).

A stricter byte-for-byte test would be `torch.equal(out_pre, out_post)`
on a fixed seed, comparing pre-Phase-2.3 captured output to the current
build's output. Not currently in the harness; would be a good addition
for any kernel modification that claims "stock path untouched".

### INT4 path (`Is_int4kv=true`)

**Test:** CUDA helper output must match the PyTorch route-B
reference (`kv_policy/int4_per_channel_kv.py::quantize_per_channel_int4`
+ `dequantize_per_channel_int4`) within ~1e-5 cosine. The absolute
cosine vs raw FP16 is whatever the algorithm produces on the
distribution — for random Gaussian Qwen2.5-7B shapes, ~0.9968.

**How:**
- `verify_phase2_3.py` measures CUDA cosine vs raw FP16 FA on
  Qwen2.5-7B shapes (B=1, H_q=28, H_kv=4, D=128, S_kv=16384) at fixed
  seed. Gate: cosine ≥ 0.995, max-abs ≤ 1e-2.
- `diagnose_phase2_3_drift.py` measures PyTorch reference cosine vs
  raw FP16 FA on the same input. Confirms CUDA cosine ≈ PyTorch
  reference cosine (within ~1e-5). If they differ materially, CUDA
  has a bug; if they agree, the gate needs to track the algorithm
  floor, not aspirational targets.

**Important: the absolute cosine vs FP16 is NOT a meaningful gate by
itself.** The algorithm itself has a floor that varies with the K
distribution. The meaningful gate is "CUDA matches the PyTorch
reference" — i.e., the implementation reproduces the algorithm
faithfully. The PyTorch reference's cosine vs FP16 sets the upper
bound on what the algorithm can deliver; CUDA's job is just to match
that bound, not exceed it.

The original Phase 2.3 design brief specified cosine ≥ 0.9999, which
turned out to be wrong by 30× (algorithm floor on random Gaussian is
0.9968). This was caught by the diagnostic on the first verify run.
Gate was relaxed to 0.995, Phase 2.3 lands GREEN.

## Summary

| Question | Answer |
|---|---|
| 1. K load sites | Lines 851, 929, 991 (cp.async tKgK → tKsK) |
| 2. K register entry | Lines 902, 973 (inside `gemm(...)` via `smem_tiled_copy_K` → `tSrK`) |
| 3. qK dot start | Lines 902, 973 |
| 4. Safe transform window | Yes — between wait+sync and gemm, two source-level insertion points (lines 884 and 962) |
| 5. Type/layout preservation | YES — must write `Element` back via the swizzled `tKsK(i,j,k)` accessor |
| 6. Gate | `template <bool Is_int4kv>` + `if constexpr` (Phase 2.5+); NOT a runtime params field |
| 7. Acceptance | Stock: `smoke_test_fa_install.sh` baseline match. INT4: cosine ≥ 0.995 vs raw FP16 AND ≈ PyTorch reference (within 1e-5) |
