# Phase 5C v1 ship report — measured bf16 / fp8 / int4_protected

Final benchmark numbers locking the v1 ship claims. Source:
`bench_phase5c_v1.py` run on a single 80 GiB H100/A100-class device at
`gpu_memory_utilization=0.5`, Qwen2.5-7B-Instruct, max_model_len=4096.

## TL;DR — three-way comparison

| Backend | Cuda blocks | Max concurrency | Decode tok/s/seq | Output quality vs bf16 |
|---|---|---|---|---|
| **bf16** (stock) | 27934 | 109.12× | 83.8 | (baseline) |
| **fp8** (vLLM E4M3) | 56120 | 219.22× | 64.7 (77%) | 6-16% prefix overlap, 0 identical |
| **int4_proto** | 28060 | **219.22×** | 17.0 (20%) | **33-100% overlap, 3/6 IDENTICAL** |

**Headline:** int4_protected delivers **the same 2× memory-capacity gain as FP8** with **dramatically higher output fidelity** (3 of 6 prompts produce **bit-identical greedy decode** vs bf16; mean common-prefix ratio 82%). FP8 by contrast diverges from bf16 within 6-16% of the output — none of its outputs match.

The throughput gap (int4 at 20% of bf16's decode tok/s/seq, **serialized**) is the v1 known cost — dominated by per-token Python overhead in `PagedKVWriter.write` and a small-S kernel workaround that does an extra bf16 K/V cp.async per attention block. Phase 6 perf polish closes most of it (see "Deferred" below).

## Memory math

The "max concurrency" metric is the v1 ship-story number — how many sequences of `max_model_len` can fit in KV cache at the given memory budget.

| Backend | num_blocks × block_size = total slots | Slots / max_model_len = max_concurrency |
|---|---|---|
| bf16        | 27934 × 16 =   446,944 | / 4096 = **109.12×** |
| fp8         | 56120 × 16 =   897,920 | / 4096 = **219.22×** |
| int4_proto  | 28060 × 32 =   897,920 | / 4096 = **219.22×** |

Note: int4_proto reaches the same total-slot count as fp8 via **2× block_size (32 vs 16)** since the kernel's `kInt4GroupSize=32` constexpr forces that. Same effective concurrency, different paging granularity.

## Quality breakdown (per-prompt char-level vs bf16)

The fixture (6 prompts × 3 length tiers × 2 each) at `max_tokens=64`:

| Prompt | fp8 vs bf16 | int4_proto vs bf16 |
|---|---|---|
| 1 (short Q&A) | 31 / 247 chars (12.6%) | **275 / 275 (100%) IDENTICAL** |
| 2 (one-sentence fact) | 14 / 92 (15.2%) | **345 / 345 (100%) IDENTICAL** |
| 3 (passage Q&A) | 33 / 204 (16.2%) | 155 / 189 (82.0%) |
| 4 (passage Q&A) | 7 / 54 (13.0%) | **253 / 253 (100%) IDENTICAL** |
| 5 (long summary) | 12 / 203 (5.9%) | 154 / 203 (75.9%) |
| 6 (technical Q&A) | 27 / 307 (8.8%) | 104 / 315 (33.0%) |
| **Mean** | **11.9%** | **82.0%** |
| **Identical to bf16** | **0 / 6** | **3 / 6** |

**FP8 diverges from bf16 within the first 10-30 characters on every prompt.** int4_protected preserves the **complete output** on half the corpus and tracks bf16 closely on the rest.

This is the surprising-but-real finding: vLLM's FP8 KV cache is **noisier than a 4-bit quantizer that protects 4% of channels at full precision**. The protect-K mechanism (outlier channels stored as bf16) recovers far more attention fidelity than uniform 8-bit quantization.

## Per-prompt latency (serialized, batch=1)

| Prompt | bf16 (s) | fp8 (s) | int4_proto (s) |
|---|---|---|---|
| 1 (in=5, out=64)   | 0.770 | 0.871 | 2.682 |
| 2 (in=10, out=64)  | 0.741 | 0.243 (out=19) | 2.421 |
| 3 (in=98, out=64)  | 0.648 (out=55) | 0.863 | 2.350 (out=48) |
| 4 (in=84, out=64)  | 0.640 (out=55) | 0.200 (out=15) | 2.495 (out=55) |
| 5 (in=564, out=64) | 0.515 (out=41) | 1.249 | 4.629 (out=41) |
| 6 (in=504, out=64) | 0.776 | 1.057 | 5.167 |
| **Wall total** | **4.09** | **4.48** | **19.74** |

Stops short of max_tokens on a few prompts because the model emitted EOS — this is normal greedy-decode behavior. FP8's early stops (prompts 2 and 4) are because XFormers backend on FP8 produced different greedy outputs that hit EOS earlier.

**int4_proto serial-decode latency is ~5× bf16 per prompt.** Where the time goes:
- Python loop inside `PagedKVWriter.write` quantizing each token sequentially.
- Per-step gather of paged blocks + hybrid K-tail splice (small CUDA ops, but each one is a Python→CUDA call with launch overhead).
- The bf16 K/V backing populate (also a small per-step op).

The packed kernel itself is FASTER than Phase 5A's kernel (Phase 2.4.1b measurement showed 46% faster per-call). The latency cost is **entirely Python-side bookkeeping**, not GPU work. Phase 6 perf polish (vectorize the writer) targets this.

## Stat sanity (int4_proto fallback rates)

```
prefill_calls:         196
decode_calls_packed:  9240
decode_calls_fallback:   0
write_path_calls:     9408
write_path_fallback:     0
spec_decode_calls:       0
```

**0 fallbacks across 9408 writes and 9240 packed decode calls.** The backend was on the packed path for the entire benchmark.

## Ship configuration (locked)

```python
import kv_policy.int4_protected
from vllm import LLM, SamplingParams

llm = LLM(
    model="Qwen/Qwen2.5-7B-Instruct",
    kv_cache_dtype="int4_protected",
    block_size=32,
    max_model_len=4096,
)
```

Requires:
- vllm-flash-attn dev build patched through Phase 2.6.2.
- Calibrated protect_mask at `$PROTECT_MASK_PATH` (default `/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt`).
- `kv_policy` package on `PYTHONPATH`.

See `PHASE5C_USAGE.md` for the full installation + troubleshooting guide.

## Honest trade-offs

| | bf16 | fp8 | int4_protected |
|---|---|---|---|
| KV memory | 1.0× (baseline) | 0.50× | **0.50×** |
| Max concurrent sequences | 1.0× | 2.0× | **2.0×** |
| Per-sequence decode tok/s | 1.0× | 0.77× | **0.20×** (v1 Python overhead) |
| Greedy output fidelity vs bf16 | 1.00 | ~0.12 prefix overlap, 0 IDENTICAL | **~0.82 prefix overlap, 50% IDENTICAL** |
| Setup complexity | none | `kv_cache_dtype="fp8"` | `import kv_policy.int4_protected` + 2 LLM kwargs |
| Hardware support | universal | needs FP8 path (some GPUs) | sm80 (A100/H100/etc.) |

**The v1 pitch in one sentence:** int4_protected matches FP8's memory efficiency while preserving most of bf16's output behavior — at the v1 cost of ~5× slower per-sequence decode (Phase 6 closes this).

## Deferred to Phase 6 perf polish

Two concrete optimizations that would close the throughput gap:

1. **Vectorize `PagedKVWriter.write`.** Current implementation is `for t in range(T): ...` Python loop touching CUDA per token. A batched implementation that computes all quant + nibble-pack ops on (T, H, D) tensors at once should give ~5-10× write-path speedup. The math is already vectorizable — V quant is already done batch-style in numpy/torch; only the per-token slot indexing into `kv_cache` + `protect_ext` + `v_scale_ext` needs to be vectorized. Estimated ~1 day.

2. **Kernel cp.async-skip patch.** Wrap the K and V `cp.async` sites in `flash_fwd_kernel.h` with `if constexpr (!Is_int4kv_packed)`. Eliminates a wasted bf16 K/V HBM load per attention block AND removes the 224 MB bf16 backing buffer we added as a small-S workaround. Estimated ~1-2 hrs CUDA work + recompile.

Together these would bring int4_protected's decode tok/s/seq close to fp8's, with int4_protected's much higher fidelity.

Multi-batch (Phase 5B.6) would unlock the real win: int4_protected can run **2× the concurrent sequences** as bf16 at the same memory, so aggregate throughput in a high-concurrency server would exceed bf16 even at v1's per-sequence latency. Out of v1 scope (batch=1 invariant), but the memory-side win is what makes it worth doing.
