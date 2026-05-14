# Next session — Track B: TurboQuant ↔ vLLM integration (Tier 1 CPU prototype)

**Repository:** `rasaha/symbolu`
**Branch:** `claude/safety-state-machine-EXAlZ` (continue, or cut a new
feature branch off it).
**Status entering the session:** Phase 4 throughput closed as a
durable structural negative (v10, see `PHASE4_GPU_FINDINGS.md` §12.7–
§13.3). Algorithm-quality win (−11.1% swap_out / decode_token vs LRU)
survives across five evictor implementations. The Cython port +
fast-hooks + algorithm code are production-ready.

## Why Track B now

After v10, Phase 4 throughput is closed. The next layer of the
architecture-doc stack remains unmeasured: TurboQuant 3-bit polar
quantisation is CPU-simulated only, and its integration into vLLM's
KV-cache path has **never been built**. Without it, the architecture
doc's 8.8× capacity claim has no layer-2 validation; CTM+ Phase 4 is
layer-1 (algorithm, partial validation).

Tier 1 in this session is the **CPU prototype** of TurboQuant ↔ vLLM
KV-cache integration. Tier 2 (GPU pure-PyTorch path) and Tier 3
(Triton/CUDA kernel) are later sessions.

## Tier 1 scope (this session)

**Sized: ~1 day code + ~$0.05 GPU validation.**

Build `TurboQuantKVStore` — a CPU-prototype shim that intercepts
vLLM's `Attention.forward` cache write/read path and routes K/V
tensors through CPU compression. Latency will be catastrophic by
design (10–100× slowdown); the goal is to:

1. Prove the integration shape works against the real vLLM KV path.
2. Measure compression ratio (~7×) and cosine similarity (~0.965) on
   real Qwen2.5-7B K/V tensors (not synthetic).
3. Identify the exact hook points in vLLM (likely `cache_kv` in the
   FlashAttention backend, KV layout
   `[2, num_blocks, block_size, num_kv_heads, head_dim]` BF16/FP16).
4. Output a paragraph in `PHASE4_GPU_FINDINGS.md` §14 (new section)
   + a CPU benchmark in the bench_out artefact tree.

**Existing code to reuse (~1900 lines, math is correct, only the
vLLM-side wiring is missing):**

| File | What's there |
|---|---|
| `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_offload.py` | `PolarQuant`, `QJL`, `TurboQuantCompressor`, `TurboQuantOffloadManager` |
| `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_numba.py` | Numba JIT polar transform kernels |
| `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_cuda_ext.py` | CUDA extension stub (NOT functional, Tier 3 target) |
| `CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md` | Existing CPU benchmark: 7.15× ratio at 0.965 cosine on synthetic blocks |

## Tier 1 deliverables

1. New module `CTM_plus/KVPolicy/kv_policy/turboquant_kvstore.py` (or
   equivalent location) implementing the vLLM-side wrapper.
2. CLI flag in `run_streaming.py`: `--turboquant-kv` (off by default).
3. CPU-side regression test that pins:
   * Compression round-trip preserves K/V tensor shape and dtype.
   * Decompression cosine similarity ≥ 0.95 on synthetic + a real
     Qwen2.5-7B KV slice.
   * Per-call latency is reported in the streaming summary
     (compression_us_per_block, decompression_us_per_block).
4. `bench_out/turboquant_cpu_prototype/` artefact with one
   measurement cell on Qwen2.5-7B (chat_32k or shorter; doesn't need
   to complete — just needs to emit one round-trip with real tensors).
5. `PHASE4_GPU_FINDINGS.md` §14 with the integration-shape result,
   measured compression ratio, cosine similarity, and the exact hook
   points named.

## What NOT to do this session

* Don't try to GPU-accelerate the compression (that's Tier 2/3).
* Don't claim 8.8× combined-stack capacity. CTXL has zero runtime
  measurement; combined-stack measurement requires CTM+ ×
  TurboQuant × CTXL together.
* Don't re-run Phase 4 GPU cells. The v10 result closes that
  work-track; revisiting it requires new evidence (different vLLM
  version, different integration point, different workload), not
  more iteration on the current shape.
* Don't budget more than ~$0.05 GPU. Tier 1 is mostly a CPU + shape
  exercise.

## Open the session by asking the user

1. "Tier 1 CPU prototype scope as written (above) — does the
   measurement plan match the integration shape you want to see?"
2. "Any GPU spend constraint this session?"
3. "Should we also fold in the Phase 4 algorithm result (−11%
   swap_out/decode_token across five evictor implementations) into
   the partner pitch as a precondition to opening the Track B
   conversation, or treat them as independent?"

## File pointers (in priority order)

| Path | Why |
|---|---|
| `CTM_plus/Bench/bench_out/PHASE4_GPU_FINDINGS.md` §12.7–§13.3 | Phase 4 closure record (what survives, what moves, what stops) |
| `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_offload.py` | Reuse target for `PolarQuant` / `QJL` |
| `CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md` | CPU-only benchmark to extend |
| `CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` | Architecture doc with the 8.8× claim |
| `CTM_plus/Bench/bench_out/PARTNER_VALIDATION_NOTE.md` | Partner-shareable framing; needs a §-Phase-4-closure update folded in |
