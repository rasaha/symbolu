# Phase 6D — measured profile summary

Captured 2026-05-27 on Qwen-2.5-7B-Instruct + A100-80GB + vLLM 0.7.3
(forked vllm-flash-attn). Workload: B=8, prompt repeated, max_tokens=8.
Methodology: torch.profiler (nsys not available on this pod's
inference-only venv).

## Cells

| Cell | Mode | Wall time | agg_tps | Total CUDA time |
|---|---|---|---|---|
| int4_eager   | `Int4ProtectedLLM(..., enforce_eager=True)` | 1.371s | 46.7 tok/s | **1133.5 ms** |
| bf16_eager   | `LLM(..., dtype=bfloat16, enforce_eager=True)` | 0.159s | 403.6 tok/s | **467.4 ms** |
| (bf16_stock) | `LLM(..., dtype=bfloat16)` (graphs ON, default) | 0.158s | 405 tok/s | 296.1 ms (mostly hidden) |

**int4_eager / bf16_eager = 2.43× total CUDA time** (apples-to-apples;
both eager so torch.profiler sees all kernels).

## Bucket-level diff (from `analyze_phase6d_profile.py`)

```
Bucket              | int4 ms  | bf16 ms  | delta    | int4 share
----------------------------------------------------------------------
other               |  690.63  |  233.79  | +456.84  |   60.9%
mem_other           |  192.06  |    1.05  | +191.02  |   16.9%
graph_overhead      |   16.44  |    0.27  |  +16.17  |    1.5%
protect_splice      |    2.37  |    0.00  |   +2.37  |    0.2%
model_other         |  117.55  |  117.32  |   +0.23  |   10.4%
gemm_tc             |  111.27  |  111.05  |   +0.22  |    9.8%
main_attn_kernel    |    3.20  |    3.20  |    0.00  |    0.3%
kv_write            |    0.00  |    0.73  |   -0.73  |    0.0%
```

`model_other` (RMSNorm, rotary, silu, etc.) + `gemm_tc` (linear layer GEMMs) are within 0.5 ms — confirms identical model workload across cells (sanity check OK).

**All 666 ms of gap is in `other` + `mem_other` + `graph_overhead` — the writer's per-decode-step op chain.**

## Top int4_eager kernels (writer-side overhead detail)

| Self CUDA ms | Calls | Op | What it is |
|---|---|---|---|
| 184.95 | 224 | `vllm::unified_attention_with_output` | The attention wrapper (includes int4 kernel + Python arg prep) |
| 100.86 | 680 | `aten::mm` | Linear layer GEMM (same as bf16) |
| 43.09 | **5944** | `aten::index` | Writer slot-pool indexing — DOMINANT writer op |
| 40.39 | 84 | `ampere_bf16_s16816gemm_..._256x128_ldg8_...` | Linear GEMM (same as bf16) |
| 35.47 | 204 | `ampere_bf16_s16816gemm_..._64x64_sliced1x2_...` | Linear GEMM (same as bf16) |
| 30.19 | **11356** | `aten::copy_` | Dtype/buffer copies in writer |
| 25.58 | **4732** | `aten::index_put_` | Writer scatter writes (pool updates) |
| 25.41 | **11360** | `aten::to`/`_to_copy` | Dtype conversions in splice/quant helpers |
| 18.16 | 2828 | `index_elementwise_kernel<128,4,...>` | Writer indexing internals |
| 17.05 | 3108 | `index_elementwise_kernel<128,4,...>` (variant) | Writer indexing internals |
| 16.65 | 196 | `ampere_s16816gemm_bf16_128x64_...` | Linear GEMM (same as bf16) |
| 11.44 | 1568 | `aten::nonzero` | Writer's active-mask filtering |
| 10.41 | 224 | `aten::addmm` | Linear bias add (same as bf16) |
| 9.25 | 224 | `aten::_unique2` | Slot dedup |
| 8.49 | 4256 | `Memcpy DtoH` | **Host syncs (eager-only; graphs eliminate)** |
| 7.75 | 2268 | `aten::__and__` / `bitwise_and` | Active mask boolean ops |
| 7.43 | 2072 | `bitwise_and elementwise_kernel` | Bitwise mask kernel |
| 7.00 | 1036 | `aten::amax` | V quantization scale calc |
| 6.94 | 2156 | `aten::where` | Conditional masking (splice + block-full) |
| 6.73 | 1036 | `aten::amin` | V quantization xmin calc |
| 5.90 | 2072 | `aten::div` | V/K quantization (x-xmin)/scale |
| 5.89 | 2275 | `aten::sub` | V/K quantization x-xmin |
| 5.83 | 224 | `cub::DeviceRadixSortSingleTileKernel` | Sort for unique |
| 5.42 | 2688 | `aten::item` | **CPU syncs** |
| 5.42 | 2688 | `aten::_local_scalar_dense` | **CPU syncs (mirror of item)** |
| 4.96 | 616 | `reduce_kernel` (MaxNan) | Reduction for amax |

## Top bf16_eager kernels (for comparison)

| Self CUDA ms | Calls | Op |
|---|---|---|
| 100.65 | 680 | `aten::mm` |
| 41.59 | 233 | `ampere_bf16_s16816gemm_..._64x64_sliced1x2_...` |
| 40.42 | 84 | `ampere_bf16_s16816gemm_..._256x128_ldg8_...` |
| 19.08 | 224 | `ampere_s16816gemm_bf16_128x64_...` |
| 10.41 | 28 | `aten::addmm` |
| 8.59 | 224 | `cutlass::Kernel2<...wmma_tensorop...>` |
| 5.66 | 252 | `vllm::act_and_mul_kernel` |
| 5.66 | 224 | `_C::silu_and_mul` |
| 5.97 | 224 | `ampere_bf16_s16816gemm_..._64x64_ldg8_relu_...` |
| 5.16 | 28 | `ampere_bf16_s16816gemm_..._256x128_ldg8_relu_...` |
| **3.20** | **224** | **`vllm::unified_attention_with_output`** ← **57× faster than int4's same op** |
| 2.23 | 448 | `_C::fused_add_rms_norm` |
| 1.63 | 196 | **`flash::flash_fwd_splitkv_kernel`** ← the actual flash attention compute |
| 1.34 | 224 | `vllm::rotary_embedding_kernel` |
| 0.77 | 28 | `flash::flash_fwd_kernel` (varlen, used during prefill) |

**The entire bf16 attention path runs in ~5 ms across all 28 layers × 8 decode steps.** The int4 attention path runs in ~185 ms for the same work — 37× the time, mostly Python wrapper + arg prep + writer ops, NOT the kernel itself.

## Phase 6E target (from this data)

Fuse the writer's per-decode-step op chain — specifically the `aten::index`, `aten::copy_`, `aten::index_put_`, `aten::to`, `aten::nonzero`, `aten::_unique2`, `aten::__and__`, `aten::amax`/`amin`, `aten::where`, `aten::div`/`sub`, and the small elementwise kernels — into 1-2 custom CUDA kernels.

Projected savings: ~200-280 ms of the current 666 ms gap → int4 captured B=8 throughput 174 → 250-300 tok/s → cap/bf16 ratio 0.30× → ~0.45-0.50×.

The remaining ~300-400 ms is the int4 attention wrapper's intrinsic overhead and the small fraction of the int4 kernel itself that's slower than bf16's `flash_fwd_splitkv_kernel`. Closing that further would require kernel-internal optimization (Phase 6F+ scope).

See `PHASE_6E_WRITER_FUSION_DESIGN.md` for the full implementation plan.
