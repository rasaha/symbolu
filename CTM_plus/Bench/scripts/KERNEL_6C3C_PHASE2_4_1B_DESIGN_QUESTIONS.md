# Phase 2.4.1b — open design questions (lock before next session)

> Phase 2.4.1a is GREEN at commit `3211008`. The packed-K side
> channel pointers flow through to `params.k_packed_*_ptr` and
> `params.is_int4kv_packed` is set when all five tensor args are
> supplied. The kernel does not read them yet — that's 2.4.1b.
>
> Phase 2.4.1b is ~400-500 LOC of CUDA across `int4_packed_load.h`
> (new), `flash_fwd_kernel.h`, `flash_fwd_launch_template.h`,
> `flash.h`, `flash_api.cpp`, plus a new `.cu` instantiation file
> and the Python verify + apply scripts. The locked design lives
> in `KERNEL_6C3C_PHASE2_4_DESIGN.md`. This file captures the
> three open sub-questions worth locking BEFORE the first
> rebuild (~15-20 min per cycle, so per-iteration cost is real).

## Locked decisions (do NOT re-litigate)

From `KERNEL_6C3C_PHASE2_4_DESIGN.md`:

1. Template threading: new `bool Is_int4kv_packed = false`
   template parameter from `compute_attn_1rowblock_splitkv` →
   `compute_attn_splitkv` → `flash_fwd_splitkv_kernel` →
   `run_flash_splitkv_fwd`. Mirrors Phase 2.5's `Is_int4kv`
   propagation.
2. New dispatch arm: `run_mha_fwd_splitkv_dispatch_int4kv_packed`,
   new `.cu` file
   `flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu`, gated
   by `params.is_int4kv_packed` in `run_mha_fwd`. Mirrors Phase
   2.1's pattern.
3. SEPARATE smem regions: `sK_packed` (~8 KB) + `sScale` (~1 KB)
   + `sXmin` (~1 KB) + `sProtect_bf16` (~4 KB) + `sProtect_slot`
   (128 bytes), ALONGSIDE existing `sK` (~32 KB).
4. CUTLASS bypass for HBM load — manual `__ldg(uint4*)` v1.
   `cp.async` is a perf optimization for Phase 2.4.1c+.
5. V stays BF16 in Phase 2.4. V pack is Phase 2.6.
6. vLLM paged K cache stays alongside our sidecar in Phase 2.4.a.
   Freeing it is Phase 2.4.b.

## Three open questions (locked answers below)

### Q1. `kPackedNProtectMax`: 8 or 16?

Defines the FIXED storage width of the per-token protect channel
sidecar in the kernel's smem scratchpad. Independent of the
runtime `n_protect` count (= `params.packed_n_protect`, the
iteration bound).

| Option | Smem per K block | Vector-load alignment | Max protect_fraction |
|---|---|---|---|
| A: kPackedNProtectMax = 8  | 128 × 8  × 2 = 2 KB | 16-byte / token (1 uint4 load) | 6.25%  (8/128)  |
| B: kPackedNProtectMax = 16 | 128 × 16 × 2 = 4 KB | 32-byte / token (2 uint4 loads) | 12.5% (16/128) |

Phase 6.4 GREEN policy:
- Default: 4% (n_protect = 5)
- Safe mode: 8% (n_protect = 10)
- Above 8% not tested as a target

Option A excludes safe mode (8% needs 10 > 8). Option B keeps
both policy points viable + buys headroom.

Smem cost: +2 KB for Option B is in the noise vs the ~94 KB
total budget on the packed path (under A100's 99 KB max).

**Lock: B. kPackedNProtectMax = 16.**

Rationale: preserves safe-mode option without a future code
change; +2 KB smem is negligible vs 99 KB budget; 2 uint4 loads
per token is fine.

### Q2. Pad `k_protect_bf16` in Python to kPackedNProtectMax, or runtime-strided element loads in the kernel?

With Q1.B locked, the Python-side `k_protect_bf16` at Phase 2.4.0
is shaped `(1, S, H, n_protect=5)` but the kernel wants to
vector-load 16 elements per token.

| Option | Python change | Kernel load |
|---|---|---|
| A: Pad in Python      | `phase2_4_packed_kv.py`: define `PHASE2_4_N_PROTECT_MAX = 16`, allocate `k_protect_bf16` at full width, zero-fill unused slots | `__ldg(uint4*)` clean 16-byte vector loads, 2 per token at 1 thread per token |
| B: Runtime-strided    | `phase2_4_packed_kv.py` unchanged | Per-element `__ldg(uint16_t*)` × runtime `n_protect`, ≈5 loads/thread |

Sidecar memory impact of Option A: at S=32k, padding n_protect
from 5 to 16 grows `k_protect_bf16` from 0.072 GB → 0.23 GB.
Total sidecar 0.65 → 0.81 GB. Still within design doc's Phase
2.4.a budget.

Round-trip test impact of Option A:
`verify_phase2_4_packed_kv.py` still passes unchanged —
`unpack_k_from_phase2_4` iterates the valid protect indices via
`protect_slot`, ignoring zero-padded slots.

**Lock: A. Pad in Python at `PHASE2_4_N_PROTECT_MAX = 16`.**

Rationale: one-line Python change vs runtime-stride loop in CUDA;
clean vector loads in the helper; sidecar grow ~0.16 GB at S=32k
is well within the 2.5 GB total Phase 2.4.a budget.

### Q3. Scale + xmin storage: BF16 or FP32?

Phase 5A's path computes per-group `scale = (max - min) / 15.0f`
in FP32 in-register every kernel call. Phase 2.4 computes the
same in FP32 once at pack time (Python), stores to HBM, kernel
re-reads.

BF16 storage:
- 7-bit mantissa → ~0.008 relative precision
- For typical Gaussian K with scale ≈ 0.27, per-element dequant
  drift is up to ~q · 0.008 · scale ≈ 0.032 at q=15 (≈ 1 LSB
  at scale=0.27)
- Cumulative cosine impact vs Phase 5A: ~0.999-0.9995 range —
  the 0.9995 gate is tight, not robust

FP32 storage:
- 23-bit mantissa → bit-exact match to Phase 5A's in-flight FP32
- Cosine impact: ≈ 1.0 vs Phase 5A
- Cost: 2× the scale + xmin bytes (0.114 GB total vs 0.057 GB
  at S=32k, 28 layers) — sidecar grows ~0.06 GB, still trivial

The locked design (`KERNEL_6C3C_PHASE2_4_DESIGN.md`, Risk #3)
explicitly chose BF16 default with FP32 as documented Plan B
("if FP16 scale is insufficient, fall back to FP32 scale at 4×
the scale-bytes cost — still negligible").

**Lock: BF16 default; FP32 fallback wired as a one-line patcher
flip if cosine misses 0.9995 on first build.**

Rationale: honors the locked design's choice. The BF16 → FP32
fallback is mechanically a one-line change in both
`phase2_4_packed_kv.py` (cast scale/xmin to FP32 not BF16) and
`int4_packed_load.h` (`__bfloat162float` → `*(float*)` reinterpret).
If first-build cosine ≥ 0.9995 → ship BF16. If 0.999 ≤ cos <
0.9995 → flip to FP32 and rebuild (~15-20 min, one round). If
cos < 0.999 → real bug, not BF16 precision.

## Files to create / modify in Phase 2.4.1b

In the dev tree at `/workspace/dev/vllm-flash-attn-dev`:

| File | Action | Approx LOC |
|---|---|---|
| `csrc/flash_attn/src/int4_packed_load.h` | NEW | ~280 (helper: load + unpack + dequant + protect blend) |
| `csrc/flash_attn/src/flash_fwd_kernel.h` | MODIFY | +60 (template param + smem decl + 3 K-load site gates) |
| `csrc/flash_attn/src/flash_fwd_launch_template.h` | MODIFY | +40 (template + dispatch + smem-budget) |
| `csrc/flash_attn/src/flash.h` | MODIFY | +1 (fwd decl) |
| `csrc/flash_attn/flash_api.cpp` | MODIFY | +5 (run_mha_fwd packed branch) |
| `csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu` | NEW | ~10 (instantiation only) |

In `CTM_plus/`:

| File | Action |
|---|---|
| `KVPolicy/kv_policy/phase2_4_packed_kv.py` | MODIFY: define `PHASE2_4_N_PROTECT_MAX = 16`, pad `k_protect_bf16` to it (Q1.B + Q2.A) |
| `Bench/scripts/apply_phase2_4_1b_patches.py` | NEW: idempotent patcher, sentinel-string detection |
| `Bench/scripts/apply_phase2_4_1b.sh` | NEW: orchestrator (patch → rebuild → install → verify) |
| `Bench/scripts/verify_phase2_4_1b.py` | NEW: cosine ≥ 0.9995 vs Phase 5A on Qwen2.5-7B shapes |

## Helper structure (`int4_packed_load.h`)

Single entry point. Caller adds trailing `__syncthreads()`.

```cpp
template <typename Kernel_traits, int kGroupSize, int kPackedNProtectMax,
          typename EngineK, typename LayoutK,
          typename EngineC, typename LayoutC>
__device__ __forceinline__ void int4_packed_load_K_block(
    cute::Tensor<EngineK, LayoutK>       &tKsK,            // OUT: smem K (bf16)
    cute::Tensor<EngineC, LayoutC> const &tKVcKV,          // IN:  (n, d) identity
    // per-K-block HBM source pointers (caller computes via params):
    const uint8_t       *k_packed_block,                   // (kBlockN, D/2)        for (n_block, bidh)
    const __nv_bfloat16 *k_scale_block,                    // (kNGroups, D)
    const __nv_bfloat16 *k_xmin_block,                     // (kNGroups, D)
    const __nv_bfloat16 *k_protect_block,                  // (kBlockN, kPackedNProtectMax)
    const int8_t        *smem_protect_slot,                // (D), pre-staged once per kernel
    int runtime_n_protect,                                 // <= kPackedNProtectMax
    // smem scratch (from OptionalPackedScratch):
    uint8_t       *smem_packed,                            // (kBlockN, D/2)
    __nv_bfloat16 *smem_scale,                             // (kNGroups, D)
    __nv_bfloat16 *smem_xmin,                              // (kNGroups, D)
    __nv_bfloat16 *smem_protect                            // (kBlockN, kPackedNProtectMax)
);
```

Phases inside the helper:

1. Cooperative `__ldg(uint4*)` of packed K into `smem_packed`
   (1 thread per token, 4 × 16-byte loads each at D/2=64).
2. Cooperative `__ldg(uint4*)` of scales + xmins (~64 vector
   loads each, distributed via stride loop).
3. Cooperative `__ldg(uint4*)` of `k_protect_bf16` (1 thread per
   token, 2 × 16-byte loads each at kPackedNProtectMax=16,
   D=128).
4. `__syncthreads()` — all four buffers committed.
5. Per-thread fragment iteration: for each (i0, i1, i2) in tKsK,
   look up (n, d) via `tKVcKV`; if `smem_protect_slot[d] >= 0`
   and slot < `runtime_n_protect`, read
   `smem_protect[n,slot]`; else unpack `smem_packed[n,d/2]`
   nibble (high if d odd, low if d even), look up
   `smem_scale[g,d]` + `smem_xmin[g,d]` (g = n / kGroupSize),
   dequant to BF16; write to `tKsK(i0, i1, i2)`.
6. Caller's trailing `__syncthreads()` before the GEMM consumes
   the modified smem K.

Caller-computed per-K-block HBM base pointers (in
`compute_attn_1rowblock_splitkv` near the existing K cp.async
sites):

```cpp
const int block_token_start = n_block * Kernel_traits::kBlockN;
const auto *k_packed_block =
    reinterpret_cast<const uint8_t*>(params.k_packed_int4_ptr)
    + (size_t)block_token_start * params.h_k * (Kernel_traits::kHeadDim / 2)
    + (size_t)bidh * (Kernel_traits::kHeadDim / 2);
// scale/xmin: groups-strided. group_start = block_token_start / kGroupSize.
// protect_bf16: tokens-strided with kPackedNProtectMax slots/token.
// (bidb = 0 — Phase 2.4 v1 is batch=1 per Phase 5A scope.)
```

The `smem_protect_slot` array is loaded ONCE at the top of
`compute_attn_1rowblock_splitkv` from
`params.k_packed_protect_slot_ptr` (which is `(H_kv, D) int8`),
sliced to `bidh`. Stays constant across all K blocks for a given
threadblock.

## Smem layout (`OptionalPackedScratch<Is_int4kv_packed, ...>`)

Mirrors Phase 2.5's `OptionalInt4Scratch` pattern: primary
template empty (1 byte) when `Is_int4kv_packed=false`; partial
specialization true carries five buffers.

```cpp
template <bool Has, int kPackedKBytes, int kScaleElems, int kXminElems,
          int kProtectElems, int kProtectSlotBytes>
struct OptionalPackedScratch {};   // primary empty when Has=false

template <int kPackedKBytes, int kScaleElems, int kXminElems,
          int kProtectElems, int kProtectSlotBytes>
struct OptionalPackedScratch<true, kPackedKBytes, kScaleElems,
                             kXminElems, kProtectElems, kProtectSlotBytes> {
    uint8_t       k_packed[kPackedKBytes];          // 8 KB at kBlockN=128, D=128
    __nv_bfloat16 scale[kScaleElems];               // 1 KB at kNGroups=4, D=128
    __nv_bfloat16 xmin[kXminElems];                 // 1 KB
    __nv_bfloat16 protect[kProtectElems];           // 4 KB at kBlockN=128, kPackedNProtectMax=16
    int8_t        protect_slot[kProtectSlotBytes];  // 128 bytes at D=128
};
```

Total additional smem on packed path: 8 + 1 + 1 + 4 + 0.125 ≈
14.2 KB per block. On top of stock FA's ~80 KB → ~94 KB total.
Within A100's 99 KB max. The launcher needs
`cudaFuncSetAttribute(kernel, cudaFuncAttributeMaxDynamicSharedMemorySize, 99 * 1024)`
on the packed-kernel variant (FA's existing path already does
this for the int4 variants; verify the call sees the larger size
through the template chain when `Is_int4kv_packed=true`).

## Patcher anchor strategy

Patcher uses sentinel-string detection for idempotency, mirroring
Phase 2.5's `_exactly_once` pattern:

| Anchor surface | File | "Already applied" sentinel |
|---|---|---|
| compute_attn_1rowblock_splitkv template | flash_fwd_kernel.h | `bool Is_int4kv_packed = false` in template |
| compute_attn_splitkv template | flash_fwd_kernel.h | same |
| OptionalPackedScratch decl | flash_fwd_kernel.h | `OptionalPackedScratch<Is_int4kv_packed,` |
| 3 K-load site replacements | flash_fwd_kernel.h | `int4_packed_load_K_block` call |
| flash_fwd_splitkv_kernel DEFINE | flash_fwd_launch_template.h | `bool Is_int4kv_packed` in macro |
| run_flash_splitkv_fwd template + instantiation | flash_fwd_launch_template.h | `Is_int4kv_packed` in template / instantiation |
| run_mha_fwd_splitkv_dispatch_int4kv_packed | flash_fwd_launch_template.h | function name |
| run_mha_fwd packed branch | flash_api.cpp | `params.is_int4kv_packed` branch |
| forward decl | flash.h | `run_mha_fwd_splitkv_dispatch_int4kv_packed` name |
| new helper header | int4_packed_load.h | file existence + `int4_packed_load_K_block` symbol |
| new .cu instantiation | flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu | file existence |

## Build budget

`flash_fwd_kernel.h` is included by ~14 splitkv .cu translation
units. Touching it triggers a cold rebuild of all of them. Plus
the new .cu file. Plus `flash_api.cpp`.

- Cold rebuild: ~15-20 min on the A100 pod
  (`TORCH_CUDA_ARCH_LIST=8.0`, `MAX_JOBS=16`, `NVCC_THREADS=2`).
- Incremental same — `flash_fwd_kernel.h` is the hot include.

Session budget: one full rebuild for the first try, plus 1-2
iteration rebuilds for cosine fixup or Q3 BF16→FP32 fallback.
Total session-time estimate: 1.5-2.5 hours including verify
cycles.

## Verify gate

`verify_phase2_4_1b.py`:

1. Loads Qwen2.5-7B-shaped synthetic K (B=1, S=16k, H_kv=4,
   D=128) on CUDA.
2. Runs `flash_attn_with_int4_kvcache(q, k_cache=k_bf16,
   v_cache=v_bf16, ..., protect_mask=mask, n_protect=...)` —
   the Phase 5A/4 path. Capture `ref_out`.
3. Packs the same K via `pack_k_for_phase2_4` (Phase 2.4.0
   Python).
4. Runs `flash_attn_with_int4_kvcache(q, k_cache=k_bf16,
   v_cache=v_bf16, ..., k_packed_int4=..., k_packed_scale=...,
   k_packed_xmin=..., k_packed_protect_bf16=...,
   k_packed_protect_slot=..., packed_group_size=32,
   packed_n_protect=...)` — the Phase 2.4.1b packed path.
   Capture `packed_out`.
5. Gate: `cosine(ref_out, packed_out) >= 0.9995`.

If cosine ∈ [0.9990, 0.9995): suspect BF16-scale drift, flip
Q3 to FP32, rebuild, retry.

If cosine < 0.9990: real bug. Diagnose path:
- Read back smem K via a debug print after the unpack helper.
- Compare to `unpack_k_from_phase2_4(packed)` from Python on
  the same input.
- Find the first mismatching (n, d) and trace the dequant
  arithmetic.

## Acceptance for Phase 2.4.1b GREEN

1. `verify_phase2_4_1b.py` PASS — cosine ≥ 0.9995.
2. `verify_phase4.py` still PASS — Phase 4 non-packed path
   unchanged (template gating isolates).
3. `verify_phase5a_smoke.py` still PASS — end-to-end vLLM
   decode still routes through native kernel with no fallback.
4. Stock vLLM throughput unchanged at p50 ≈ 67 μs (no template
   gate leakage into stock kernel).

## What unlocks after Phase 2.4.1b GREEN

| Phase | Adds |
|---|---|
| Phase 2.4.1c | Python install integration — `Phase2_4PackedCache` that drops the FP16 sidecar and feeds packed kwargs from `phase5a_native_install.py` |
| Phase 2.4.2 | Memory measurement — verify K sidecar bytes drop from 1.84 GB → 0.81 GB at S=32k (with kPackedNProtectMax=16 padding) |
| Phase 2.4.b | Free vLLM paged K cache — the actual HBM savings vs stock |
| Phase 2.6 | Mirror for V cache |

## Out of scope for 2.4.1b (explicitly)

- `cp.async` for the packed-K HBM load (perf — Phase 2.4.1c or
  later)
- V cache packing (Phase 2.6)
- Freeing the vLLM paged K cache (Phase 2.4.b)
- Multi-batch dispatch (Phase 5B)
- FP4/NVFP4 or alternative quant schemes
- FP32 scale storage shipping by default (revisit only if first
  build misses 0.9995)
