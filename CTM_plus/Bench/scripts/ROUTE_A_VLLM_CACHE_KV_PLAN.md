# Route-A vLLM `cache_kv` hook — engineering plan

**Status:** scoped, not implemented. Owner: TBD. Sized: **3-5 engineer-days CPU + ~$0.30 GPU**.

**Why this plan exists:** Route-B INT4 KIVI lives in HF transformers' `DynamicCache`. It is the **measurement vehicle** (perplexity, MMLU, generation-quality artefacts in §18-§19 are valid because route-B holds the algorithm identical to a production deployment). It is **not the deployment vehicle** — production inference runs on vLLM. The route-A hook is what moves the validated INT4 algorithm into vLLM at the `cache_kv` insertion point.

This plan also unblocks the **same** integration-shape gap CTM+ Phase 4 hit at §13.3 (the −20% tokens/sec is structural at the Evictor-ABC patching layer). Two work-tracks, one hook surface.

## What this is

A vLLM-side monkey-patch of `FlashAttentionImpl.forward`'s `cache_kv` call site that:

1. Intercepts K/V on the GPU before they're written to vLLM's paged FP16 KV tensor.
2. Compresses K/V using the **already-validated** route-B algorithm (`kv_policy/int4_per_channel_kv.py` quantize + pack), with scales/offsets per the KIVI config.
3. Stores compressed bytes in an alternate paged buffer (or the same buffer treated as INT4-packed; layout TBD).
4. On read (decode-time attention), decompresses on the GPU just-in-time and feeds FP16 K/V back into the attention math.

The algorithm path stays **bit-identical** to route-B. Only the storage layer and the call-site interception change.

## File-by-file patch surface

### Primary patch

* **`vllm/attention/backends/flash_attn.py`** — `FlashAttentionImpl.forward`, the `cache_kv` invocation block.
  Line target (vLLM 0.7.3): inside the `if kv_cache.numel() > 0:` branch, around the `ops.reshape_and_cache_flash(...)` call.
  Patch shape: wrap the call. On entry, take the (key, value) tensors from local scope (`key`, `value` of shapes `(num_tokens, num_kv_heads, head_dim)`), pass through `quantize_per_channel_int4` + `quantize_per_token_int4` + `pack_int4`, store the packed bytes via vLLM's existing block-allocator slot (alternate paged buffer at FP16 byte-rate, since 8 INT4 elements = 1 FP16 element of bytes).
* **`vllm/attention/backends/abstract.py`** — `AttentionMetadata` may need extension to carry per-layer scales (or we keep scales in a side-channel module attribute keyed by `(layer_idx, block_id)`).

### Secondary patches (read path)

* **`vllm/attention/backends/flash_attn.py`** — the prefill+decode path also reads from `kv_cache`. The decode forward kernel (`flash_attn_with_kvcache`) expects FP16 K/V tensors at compute time. Two options:
  1. **Decompress to FP16 in a torch op before the kernel call.** Lowest-risk, highest-throughput-cost. Adds two dequant kernels per attention call (one for K, one for V). Estimated cost: 5-15% on decode latency for Qwen2.5-7B (one decode kernel becomes three: dequant_K + dequant_V + attention).
  2. **Patch the FlashAttention kernel itself** to read INT4 and dequantize inline. This is the Marlin pattern; see `PHASE4_GPU_FINDINGS.md` §20.6. Higher-effort (weeks, not days), lowest-overhead. Out of scope for this plan; the option-1 dequant fallback ships first, the Marlin kernel lands as an optional follow-up.

This plan implements **option 1** (PyTorch dequant fallback). The Marlin-kernel acceleration is a separate plan; see §20.6.

### Block-allocator wiring

* **`vllm/core/block_manager_v2.py`** (or `block_manager_v1.py` depending on the engine config) — `BlockManager.allocate` and friends already manage the paged KV tensor by `(num_blocks, block_size, num_kv_heads, head_dim)`. Our INT4 path stores per-block scales/offsets that are NOT in this tensor. New side-channel: a `BlockId -> (k_scale, k_offset, v_scale, v_offset)` dict, keyed by the same block_ids vLLM's evictor sees. Lifecycle hooks on `BlockManager.free` clean up the side-channel.

### Init / discovery

* **`vllm/engine/llm_engine.py`** or **`vllm/engine/arg_utils.py`** — accept a new engine arg `kv_cache_dtype="int4_kivi"` (mirroring the existing `kv_cache_dtype="fp8"` plumbing the FP8 path uses). The route-A install hook triggers when this value is observed.

### Discovery shim (for route-A install timing)

* The vLLM 0.7.3 `LLMEngine.__init__` constructs the model executor and worker before any KV ops run. Our patch installs after `model_executor.init_model_executor_environment` but before the first request. The CTM+ side-channel installer (`runner_vllm_streaming.py:_extract_model_from_engine`) already does the walker we need; reuse the same `model_executor → driver_worker → worker → model_runner → model` path.

## Engineer-days breakdown

| Day | Work |
|---|---|
| **Day 1** | Stand up the install scaffold. CPU-only: patch `FlashAttentionImpl.forward` with a no-op wrapper that logs entry; verify install lands at the right call site (the patch fires on every decode step). CPU-side test (faked attention impl) that the wrapper is reached. Wire `kv_cache_dtype="int4_kivi"` through `arg_utils`. |
| **Day 2** | Write the GPU compress path. On entry, take K/V; quantize + pack on the K/V's existing device (no host transit); store INT4 bytes in the alternate paged buffer. CPU-side test (faked CUDA tensors via torch.zeros on CPU) verifying shape + dtype + side-channel update. |
| **Day 3** | Write the GPU decompress path. Hook the read site (slice into the cache tensor right before the FlashAttention kernel call); dequantize via the existing `dequantize_per_channel_int4` + `dequantize_per_token_int4`. CPU-side test that read produces a tensor matching the K/V originally written within INT4 round-trip tolerance (cosine ≥ 0.98 on Qwen-shape data). |
| **Day 4** | GPU smoke run on a small open model (e.g., Qwen2.5-0.5B-Instruct, ~$0.02 wall). Verify the install survives engine startup. Single short prompt, decode 10 tokens. Verify output is coherent. |
| **Day 5** | Full chat_32k run on Qwen2.5-7B (~$0.07). Measure tokens/sec, swap_out/decode_token, and decode-step latency vs the FP8 baseline cell from `FP8_INT4_THROUGHPUT_RUNBOOK.md`. Land artefacts; update PHASE4_GPU_FINDINGS §20. |

**Total: 3-5 days CPU + $0.10-0.30 GPU.** The estimate ranges over: (a) whether vLLM's `BlockManager` cleanly exposes a hook for the side-channel scale storage (best case 3 days; if not, +1 day to subclass the allocator) and (b) whether GQA-specific stride math on K/V matches what `pack_int4` expects (best case 3 days; if not, +1 day to add a shape-adapter).

## What this WILL inherit automatically from route-B

All of the following are already validated in route-B and survive the move to route-A transparently:

* **Algorithm correctness.** The `quantize_per_channel_int4` / `quantize_per_token_int4` / `pack_int4` / `unpack_int4` ops are pure-torch and don't depend on the cache wrapper — route-A reuses them unchanged.
* **Quality numbers.** Perplexity 1.024×, MMLU −0.9pt @ 1000q, teacher-forced 96.4% next-token agreement. Route-A is the same algorithm on the same K/V tensors; quality is bit-identical.
* **Bit-packed storage.** The `INT4Block.k_packed` / `v_packed` `uint8` layout (§19.1) ports as-is to vLLM's alternate paged buffer.
* **Group + asymmetric config.** All three rescue mechanisms (per-channel scale, group=32, asymmetric scale+offset) port as parameters; no code change for them.
* **Sink-FP16 + body-INT4 (if §20.2 lands).** The cache wrapper's sink_size pass-through pattern is reused at the call-site level: first N positions skip compression, positions [N:] are quantized.

## What this WILL NOT automatically inherit from route-B

* **HF DynamicCache semantics.** Route-B subclasses HF's `DynamicCache` and benefits from its lifecycle (`update`, `crop`, `to_legacy_cache`). Route-A re-implements those semantics against vLLM's `BlockManager`; the API surfaces differ. **Estimated day 1-2 of the engineer-day budget.**
* **Decode-step S=1 special case.** Route-B handles the decode-step `S=1` case naturally because `DynamicCache.update` concatenates new K/V with existing K/V on the seq axis before the next forward. vLLM doesn't — each decode-step `cache_kv` call writes one block, scales/offsets get computed PER block independently. This matters for group quant: at S=1, group_size becomes irrelevant (one position == one group); the per-block scale IS the per-token scale. Working as intended, just needs a check.
* **Cross-request isolation.** Route-B has one cache per request; vLLM shares the paged buffer across requests. Scales/offsets must be keyed by `block_id`, not `request_id`, so block reuse (prefix caching) works correctly. The CTM+ Phase 4 evictor also keys by block_id; the two should compose without surprises, but the integration test cell in `FP8_INT4_THROUGHPUT_RUNBOOK.md` §4 (Cell B' — FP8 + CTM+) is the smoke-test pattern.

## What CTM+ Phase 4 gets out of this

The route-A hook is the **same hook the CTM+ Phase 4 −20% tokens/sec gap needs.** Per §13.3, that gap is structural at the Evictor-ABC patching layer — a deeper integration point (the `cache_kv` site we patch here) bypasses it entirely. So implementing this hook for the INT4 work simultaneously:

* Closes the §13.3 −20% throughput cost for CTM+ Phase 4 — the algorithm-quality −11.1% swap_out/decode_token win was already partner-shareable; this lifts the asterisk.
* Makes the **combined-stack** CTM+ × INT4 × vLLM operating point a single command, not three glued harnesses. The combined number is the partner-relevant one.

So: 3-5 engineer-days closes **two** validation gaps the VC brief currently flags. ROI is high.

## What this plan does NOT cover

* **Marlin-style fused unpack-attend kernel.** Separate plan; see `PHASE4_GPU_FINDINGS.md` §20.6. The fallback in this plan is the option-1 PyTorch dequant; the kernel work optimizes the fallback away.
* **vLLM upstream PR.** This plan installs as a monkey-patch (same pattern as the CTM+ Phase 4 evictor install). An upstream PR is a separate ~5-day effort with code-review iteration; not in the seed-stage 3-5-day estimate.
* **CTXL tiering integration.** CTXL is a separate work-track (weeks); coordinating with route-A is a downstream design problem.

## Open questions (for day 1)

1. Does vLLM 0.7.3's `BlockManager` expose a clean lifecycle hook for the side-channel scale storage, or do we need to subclass the allocator? (Probably subclass; vLLM's BlockManager doesn't have register-callbacks.)
2. Does `flash_attn_with_kvcache` expect K/V at FP16 specifically, or does it auto-cast from BF16? (Probably FP16-specific on Ampere; the dequant target dtype matches the kv_cache tensor's dtype.)
3. Is the page_size = block_size assumption (16 tokens/block by default in vLLM 0.7+) compatible with KIVI's group_size=32 along the seq axis? (No — we'd need group_size=16 or smaller, OR we'd group across two adjacent vLLM blocks. The simpler answer is group_size=block_size; route-B's group_size=32 gives 1 group per block at vLLM defaults if we move to block_size=32, or 2 blocks per group at block_size=16 with a constraint that blocks are always allocated in pairs. **The block_size=32 path is cleaner; verify on day 1.**)
4. How does prefix caching interact with the scale side-channel? (Block IDs are shared across requests when prefix matches; scales must also be shared. Verify that the scale is deterministic from the K/V tensor — yes, dynamic per-block max-based scaling is deterministic — so the same K/V always produces the same scale and prefix-cache hits are safe.)
