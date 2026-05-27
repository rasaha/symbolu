# Phase 6F — int4 attention kernel optimization

> **Status:** Plan-of-record only, contingent on Phase 6E outcome.
> Trigger: 6E ships and `cap/bf16` ratio at B=8 lands < 0.45×, OR 6E
> ships and the residual gap is clearly localized to inside the
> int4 attention kernel itself (`vllm::unified_attention_with_output`
> at 184 ms vs bf16's 3.2 ms in the Phase 6D profile).
>
> **One-sentence goal:** Optimize the int4_packed flash_attention
> kernel in the `vllm-flash-attn-dev` fork so it runs at speeds
> comparable to the stock bf16 `flash_fwd_splitkv_kernel`, closing
> the architectural gap that the Phase 6 writer-side work couldn't.
>
> **Why this is the right next step:** After Phase 6E eliminates the
> writer-side launch overhead, any remaining int4-vs-bf16 throughput
> gap lives inside `flash_attn_with_int4_kvcache`. Phase 6D measured
> this kernel at 184 ms for 224 calls (28 layers × 8 decode steps),
> while bf16's `flash_fwd_splitkv_kernel` runs in 1.63 ms total for
> the same workload. Per-call: int4 ≈ 825 µs, bf16 ≈ 7 µs.
> **The int4 kernel is ~118× slower than bf16 per attention forward.**
> That's the next material lever.

## Where the time goes inside the int4 kernel

From reading `flash_fwd_kernel.h` lines 900-1130 + the helper file
names (`int4_packed_load_K_block`, `int4_quant_dequant_K_block_inplace`,
`int4_packed_load_V_block`, `int4_quant_dequant_V_block_inplace`):

| Phase per kernel call | What happens | Bf16 baseline cost | Int4 cost | Extra work |
|---|---|---|---|---|
| Per-block K load | cp.async from HBM | ~1 µs (one bf16 read) | ~1.5 µs (int4 + scale + xmin + protect_bf16 + protect_slot loads) | +0.5 µs per block |
| Per-block K dequant | (none for bf16) | 0 | ~1-2 µs (group-wise dequant + protect-mask blend) | +1.5 µs per block |
| Q @ K^T GEMM | TensorOp instruction | ~1 µs | ~1 µs (same as bf16 once K is in bf16) | same |
| Softmax | partial-row softmax | <0.5 µs | <0.5 µs | same |
| Per-block V load | cp.async from HBM | ~1 µs | ~1.5 µs (int4 + scale + xmin) | +0.5 µs per block |
| Per-block V dequant | (none) | 0 | ~1-2 µs | +1.5 µs per block |
| P @ V GEMM | TensorOp instruction | ~1 µs | ~1 µs | same |
| Output accumulate | <0.5 µs | <0.5 µs | same |

For B=8, max_model_len=4096, BS=32, decoder block size kBlockN=32:
each decode step's attention processes ~ceil(cache_seqlens/kBlockN)
K/V blocks. At ~100 tokens cache_seqlens, that's ~3 blocks per layer
per step.

Expected per-call cost (Phase 6F target):
- 3 blocks × (~5 µs per block including int4 dequant overhead)
- + ~10 µs of fixed-cost kernel setup + final reduction
- = **~25 µs per call** (vs bf16's ~7 µs)

Current: ~825 µs per call. **Headroom: ~30× speedup** vs current,
but only ~3.5× faster than bf16 even at the asymptote.

So Phase 6F can probably get us to **cap/bf16 ≈ 0.3-0.5×** of bf16 in
the int4 kernel itself (vs current 0.05× = 1.63 ms / 184 ms ratio).
Combined with Phase 6E's writer fusion (the rest of the visible
overhead), the OVERALL cap/bf16 ratio could land at **~0.4-0.6×**.

## Strong hypotheses about the slowness (to verify with ncu)

The int4 kernel is implemented in `vllm-flash-attn-dev` (a fork of
the upstream Dao-AILab flash-attn). The relevant files:

- `csrc/flash_attn/src/flash_fwd_kernel.h` — main kernel template
- `csrc/flash_attn/src/int4_packed_load_K_block.cuh` (or similar) —
  the int4 K dequant + protect splice
- `csrc/flash_attn/src/int4_packed_load_V_block.cuh` (or similar)
- Probably some `int4_pack.cuh` with the packing/unpacking primitives

**H1: The int4 dequant is unfused with the K/V load.** Today the
flow is probably:
1. cp.async load int4 bytes from HBM to smem
2. Wait
3. Load scale/xmin from HBM
4. Wait
5. Dequantize int4 → bf16 in registers
6. Load protect_bf16 + protect_slot
7. Splice protected dims into the bf16 K tile
8. GEMM

If steps 1-7 don't overlap, we serialize HBM latency. The
ncu metric to verify: `gpu__time_active.avg` per step vs
`dram__bytes.avg.per_second` — if the kernel is bandwidth-bound
during int4 load but compute-idle during dequant, those phases need
overlap.

**Fix candidate:** issue cp.async for the NEXT block's int4 + scale
+ xmin BEFORE the current block's dequant runs. Pipeline depth 2
should hide HBM latency.

**H2: The protect-mask splice has bank conflicts.** The protect_slot
is a per-(h,d) index telling which protect_bf16 channel to read for
that dim. If the access pattern stride doesn't match smem bank layout,
warps serialize on smem reads.

**Fix candidate:** reorder protect_bf16 in HBM so the protect_slot
lookup is consecutive within a warp (no bank conflict).

**H3: The int4 unpack is single-issue per thread.** Dequantizing
`q = (byte >> 4*shift) & 0x0F` plus `bf16 = q * scale + xmin` is ~3
FMA instructions per pair of int4 elements. If the kernel issues
these one-at-a-time per thread, it's instruction-bound (not
bandwidth-bound).

**Fix candidate:** use the `__nv_bfloat162` SIMD intrinsics for 2-
wide bf16 ops; vectorize the dequant.

**H4: The kernel uses MMA tiles of the wrong size for our shapes.**
Stock flash_attn picks tile sizes optimized for typical bf16
workloads. The int4 fork may not have re-tuned. With H=4, D=128, B=8,
the per-tile work is small; a too-large tile wastes SM slots.

**Fix candidate:** experiment with kBlockM=64 vs 128 in the
Kernel_traits template; re-tune for our specific shapes.

## Phase 6F method

### Profile first (the gate that justifies the work)

```bash
# On a GPU pod with bundled nsys (path: /opt/nvidia/nsight-compute/...):
export PATH="/opt/nvidia/nsight-compute/2025.1.1/host/target-linux-x64:$PATH"

# After Phase 6E ships, profile the int4_captured cell with ncu:
ncu --nvtx --nvtx-include "phase6d_step/" \
    --section ComputeWorkloadAnalysis \
    --section MemoryWorkloadAnalysis \
    --section SchedulerStats \
    --section Occupancy \
    --section SpeedOfLight \
    --section InstructionStats \
    --section WarpStateStats \
    --kernel-name regex:'flash::fwd_kernel|_int4kv|int4_packed_load' \
    --launch-skip 30 --launch-count 5 \
    --export bench_out/phase6f_profile/int4_kernel_ncu \
    --force-overwrite \
    python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell int4_captured
```

Open the .ncu-rep in Nsight Compute UI (or `ncu --import` for CLI
summary). Per kernel, check:

| ncu section | What it tells you | Phase 6F action if pathological |
|---|---|---|
| **SpeedOfLight** | % of peak compute and memory | < 30% on both → bandwidth-bound with stalls; check H1 |
| **MemoryWorkloadAnalysis** | DRAM throughput, L1/L2 hit rates | Low DRAM throughput + high latency → cp.async pipeline depth too shallow |
| **WarpStateStats** | Stall reasons (mio_throttle, lg_throttle, etc.) | `long_scoreboard` stalls → memory dependency; pipeline harder |
| **SchedulerStats** | Issue rate per warp | Low issue rate → instruction-bound; vectorize per H3 |
| **Occupancy** | Active warps per SM | < 50% → maybe register pressure; reduce per-thread state |
| **InstructionStats** | Mix of FMA/SHFL/LDS | High LDS without coalescing → bank conflicts per H2 |

**Decision gate:** the ncu output tells us WHICH of H1/H2/H3/H4 is
actually firing. Pick the dominant one and fix that first.

### Implement the fix (CUDA work, ~2-5 days each)

For each hypothesis, the fix is in `vllm-flash-attn-dev/csrc/flash_attn/src/`:
- H1 (load-dequant overlap): rewrite `int4_packed_load_K_block.cuh`
  to issue cp.async with deeper pipeline.
- H2 (bank conflicts): change protect_bf16 HBM layout in the writer
  (`phase5b_4c_paged_writer.py`), then update the kernel's load
  pattern to match.
- H3 (scalar dequant): vectorize using `__nv_bfloat162` intrinsics.
- H4 (tile size): expand the Kernel_traits template enum and add a
  shape-specific instantiation; update the dispatcher.

### Verify

- The 6B.3 semantic-eq gate (already in place) re-runs unchanged
  after each kernel change.
- Throughput re-bench using `bench_phase6_b4_throughput_gpu.py`.
- ncu re-profile to confirm the targeted bottleneck moved.

## Estimated effort

Highly variable by which hypothesis pans out and how deep the
optimization goes. Rough framing:

| Scope | Time | Risk |
|---|---|---|
| Profile + diagnose (one ncu session + analysis) | 0.5 day | Low |
| Fix ONE hypothesis (the dominant one) | 2-5 days CUDA dev | Medium |
| Fix multiple hypotheses iteratively | 1-2 weeks | Medium-high |
| Full kernel rewrite for SOTA int4 attention | 1-2 months | High |

**Recommendation: scope Phase 6F as "profile + fix the ONE dominant
hypothesis". Stop there.** Don't open-end the kernel work. If the
fix delivers, great; if it doesn't move the needle enough,
Phase 6G's "pivot the VC narrative to memory + algorithmic value"
path is the honest move.

## Risks

1. **The int4 kernel may be near-optimal for its design.** The fork
   was presumably tuned by someone competent. Phase 6F might
   discover the dominant cost is fundamental to int4-with-protect-
   mask, not fixable with code changes. Mitigation: the profile-first
   step is the gate. If ncu shows the kernel running at >70% SpeedOf
   Light on both compute and memory, optimization room is small;
   accept the design and update the brief.

2. **CUDA toolchain expertise gap.** This is real kernel-level CUDA
   work (cp.async pipelining, warp scheduling, smem layout). Requires
   meaningful CUDA expertise. If unavailable, the realistic move is
   to scope a contractor or wait until that expertise is on team.

3. **Maintenance burden.** Every torch / CUDA upgrade risks
   breaking the kernel. The forked `vllm-flash-attn-dev` already
   represents this commitment; Phase 6F deepens it. Mitigation:
   pin CUDA toolkit + PyTorch version explicitly; add a small CI
   job that builds the fork on every Python or CUDA upgrade.

4. **Phase 6E might already close enough of the gap.** If 6E lands
   at cap/bf16 ≥ 0.5× at B=8, 6F may be unnecessary. Always check
   the post-6E numbers before scoping 6F.

## Decision criteria — when to start Phase 6F

After Phase 6E ships, run the throughput bench. Then:

- **cap/bf16 ≥ 0.5× at B=8:** Phase 6 is complete. Update the brief,
  emphasize memory + algorithmic value, ship. Skip 6F.
- **cap/bf16 in [0.35×, 0.5×]:** Phase 6F is OPTIONAL. The product
  case is workable without it; the kernel work would be a nice-to-have.
- **cap/bf16 < 0.35×:** Phase 6F is JUSTIFIED. The gap is large enough
  to warrant kernel-level work.

## Deferred (post-6F)

- **Cross-family verification post-6F** (Mistral-7B, Llama-3.1-8B).
  Sanity check that the optimization didn't overfit to Qwen.
- **Long-context bench** (max_model_len=16K, 32K). Where int4's
  per-position memory savings compound. May be where int4 actually
  wins regardless of throughput.
- **Hopper (H100/H200) optimization.** Tensor Memory Accelerator
  (TMA) + larger register file enable kernel rewrites that aren't
  available on Ampere. Out of scope unless the customer base
  includes H100 deployments.
