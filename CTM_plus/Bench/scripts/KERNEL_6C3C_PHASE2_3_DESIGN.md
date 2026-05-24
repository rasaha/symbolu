# Kernel 6c.3C — Phase 2.3 design brief (NO-OP transform proof)

> Output of the 2026-05-20 background code-read of
> `compute_attn_1rowblock_splitkv` in `flash_fwd_kernel.h` at SHA
> `720c948`. Documents the kernel surface Phase 2.3 modifies and
> the design choices that the actual patch will instantiate.
>
> Phase 2.3 acceptance: `verify_phase1.py` still PASS bit-equal (or
> cosine ≥ 0.9999) when `params.is_int4kv=true` and the kernel runs
> through the in-register quantize→dequant transform on the loaded
> K. Stock path (when `params.is_int4kv=false`) MUST remain
> bit-identical to before — no measurable drift on stock-FA calls.

---

## K read sites in `compute_attn_1rowblock_splitkv`

Four sites at SHA 720c948:

| # | Line | Purpose |
|---|---:|---|
| 1 | ~267 | Append_KV initial K load — before the main masking loop, in the Append_KV path only |
| 2 | ~851 | Standard initial K load — before first masking iteration; used by all code paths |
| 3 | ~929 | Main loop K reload — inside the masking loop, guarded by `if (n_block > n_block_min)` |
| 4 | ~990 | Append_KV continuation K reload — after the main masking loop completes |

All four follow the same pattern:
```cpp
FLASH_NAMESPACE::copy<...>(gmem_tiled_copy_KV, tKgK, tKsK, ...);
cute::cp_async_fence();
// ... other work ...
cute::cp_async_wait<0>();
__syncthreads();
// K is now in smem; GEMM follows
```

## Insertion point — post-load in-register transform

**Decision: insert AFTER `cp_async_wait<0>() + __syncthreads()`, BEFORE
the GEMM.** Reasoning:

- Sync is "free" — `__syncthreads()` already ensures all K data is in
  smem.
- No extra buffers — the transform reads from `tKsK`, transforms in
  registers, writes back to the same smem locations.
- Each thread owns ~256 BF16 elements of K in the smem tile (kBlockN=128 ×
  kHeadDim=128 = 16384 elements split over 128 threads). The swizzle is
  handled by the existing CUTLASS atoms, so we operate on logical
  `(seq, dim)` indices and let the CUTLASS abstractions handle the
  bank-conflict mapping.

No alternative insertion point is clearly better. The pre-load-into-temp
option requires a doubled smem footprint and an extra cp.async + sync
round; the in-register-during-copy option requires a custom copy atom
(the CUTLASS one is fixed-element-type) — that's where Phase 2.4 will
land, but Phase 2.3 stays simpler.

## Per-thread layout

For `Flash_fwd_kernel_traits<Headdim=128, kBlockM=64, kBlockN=128, kNWarps=4, false, false, bf16_t>`:

- Global K tile per block: `128 × 128 = 16384` BF16 elements
- Per-thread: ~256 BF16 elements during the HBM→smem copy
- After load, each thread's `tKsK` thread-tile partitions a subset of
  the swizzled smem K tile. CUTLASS handles indexing; we read/write
  through the existing tile abstractions, not via raw offsets.

## Scale/offset computation (the hard part)

For group_size_k=32 along the seq axis with kBlockN=128, each K block
has **4 groups**. Scale tensor shape: `(4, H_kv, D=128)`. For the v1
NO-OP transform, scales are **computed from the loaded K** (not read
from HBM — that's Phase 2.5+).

Two-pass cooperative reduction:

**Pass 1: per-group max-abs.** Each thread scans its 256-elem register
fragment, computes local max-abs per group, then cooperatively reduces
across the threadblock via `__shfl_xor_sync` for the warp-level part +
smem scratchpad for cross-warp. Per the brief, the existing FA
`Softmax` operator (line 851) implements similar cooperative max/sum;
adapt its reduce-max logic to reduce-max-abs.

**Pass 2: quantize + dequant.** Read group scale + offset from smem
scratchpad, apply `quant = round((x - offset) / scale * (2^4-1))`
clipped to int4 range, then `dequant = quant / (2^4-1) * scale + offset`.
Write back to tKsK.

The rounding convention must match `kv_policy/int4_per_channel_kv.py`
(specifically the `quantize_per_channel_int4` / `pack_int4` ops)
or the cosine vs the existing oracle drifts at ±1 LSB. The asymmetric
quant path uses `(x - min) / (max - min) * 15`, clip, round to int4;
dequant reverses. Need to match this exactly.

## Gating: runtime `if` vs `if constexpr`

**Decision: runtime `if (params.is_int4kv)` for v1.** The condition is
uniform across the threadblock (same flag for all threads), so:

- Modern nvcc applies CSE and constant-folding for uniform branches —
  effectively no overhead when `params.is_int4kv=false` (the stock path)
- No need to plumb a template parameter through the launcher chain
- Defer template gating to v2 when HBM layout differs (Phase 2.5+
  reads packed uint8 from a different storage; that needs a separate
  kernel instantiation, hence template gating)

## What to borrow from the existing FA codebase

The codebase has no direct INT4/FP8/INT8 quantize patterns in this
specific kernel. Patterns to adapt:

- **`FLASH_NAMESPACE::convert_type<Element>(...)`** (~line 873) —
  in-place tensor-level type casting; adapt for the register-level
  quantize/dequant operations.
- **`FLASH_NAMESPACE::Softmax`** (referenced at line 851; implemented
  in `flash_attn_common.h` or a sibling) — cooperative max/sum
  reductions. Adapt max → max-abs for the per-group scale computation
  in Pass 1.
- **Existing `__syncthreads()` placement** between cp.async wait and
  GEMM — the transform sits in the gap between these two anchors;
  no additional sync needed.

## Acceptance and validation

> **Corrected after first verify run (commit df67260).** The original
> claim — "drift is far less than BF16 precision, expect cosine ≥
> 0.9999" — was empirically WRONG. The route-B asymmetric INT4
> quant/dequant algorithm with group_size=32 has an *intrinsic* drift
> floor of ~0.9968 cosine on attention output (Qwen2.5-7B shapes, B=1,
> H_q=28, H_kv=4, D=128, S=16k). `diagnose_phase2_3_drift.py` proves
> this by running PyTorch's `quantize_per_channel_int4` +
> `dequantize_per_channel_int4` on the same K and feeding it through
> stock FA — the resulting cosine vs raw K is 0.99682, essentially
> identical to what the CUDA helper produces (0.99684, matching to
> within ~1e-5).
>
> Per-element K drift is ~0.065 mean (real, ~0.27 INT4 LSB at the
> Gaussian scale); softmax + V-dot averages it down to ~8e-4 mean on
> the attention output. **The protect-K sidecar in Phase 4 is what
> closes the remaining ~0.003 gap** — bare INT4 K (no protect) does
> not get to FP16 quality, consistent with the §20.4.3 algorithm
> needing the top-~4% magnitude channels in higher precision.

Phase 2.3 acceptance is `verify_phase2_3.py` PASS:
- **cosine ≥ 0.995** (was 0.9999 — see above for why the original
  threshold was wrong)
- **max-abs ≤ 1e-2** (unchanged; algorithm hits ~3.9e-3)

`verify_phase1.py` stays pinned at strict bit-equality and is EXPECTED
to fail post-2.3 (the int4 path now does real numerical work). To
regression-check the stock FA path, run `smoke_test_fa_install.sh`.

If verify_phase2_3.py drifts beyond the new threshold, the diagnosis is
one of:
- Rounding convention mismatch (must mirror route-B's exact op)
- Per-group reduction is wrong (reading wrong group's scale)
- Smem write/read race (need an extra sync we didn't notice)
- CUDA drift bigger than the algorithm floor — run
  `diagnose_phase2_3_drift.py` to confirm the algorithm baseline and
  isolate.

## Effort estimate for Phase 2.3

Realistic estimate from this brief:

- **Day 1:** wire the gating + add the cooperative max-abs reduction
  + verify the reduction produces same values as a host-side
  reference.
- **Day 2:** add the quantize/dequant register ops with route-B's
  rounding convention + verify against a host-side equivalent.
- **Day 3:** integrate into `compute_attn_1rowblock_splitkv` at all
  4 K read sites + run verify_phase1.py + iterate on drift.

Total ~3 engineer-days of focused CUDA work. The hard parts are (a)
matching route-B's int4 rounding exactly, and (b) the cooperative
max-abs reduction.

## Files to modify in Phase 2.3

- `csrc/flash_attn/src/flash_fwd_kernel.h` — add the conditional
  transform at the 4 K read sites in `compute_attn_1rowblock_splitkv`.
  ~50-100 lines per site (mostly the cooperative reduction + per-thread
  fragment iteration).
- Possibly `csrc/common/` — helper inline functions for the
  group-wise reduce-max-abs and quant/dequant register ops, to
  avoid 4× code duplication.

No new files; everything happens in the existing kernel.

## What this brief does NOT cover

- Phase 2.4 (REAL INT4 K HBM read with packed uint8) — separate
  design work; the HBM layout changes and a custom copy atom may
  be needed.
- Phase 4 (protected-K BF16 sidecar blend) — requires reading the
  protected channels' FP16 values from a parallel HBM tensor and
  blending with the dequant'd INT4 K. Adds another sync point.
- V cache transform — Phase 2.3 only handles K. V follows in
  Phase 3 (per the runbook).
