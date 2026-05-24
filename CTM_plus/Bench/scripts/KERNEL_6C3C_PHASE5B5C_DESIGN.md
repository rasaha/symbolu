# Phase 5B/5C — vLLM native integration

> **The v1 ship blocker.** Phase 2.4.x landed algorithm + correctness +
> speed on a monkey-patched single-sequence install. Phase 5B/5C makes
> the v1 ship claim real: actual HBM savings vs stock vLLM and
> multi-batch serving. Multi-week scope. Architecture locked here
> before any code.

## Why this is the v1 ship blocker

Current state at Phase 2.4.1d (commit `b74ef90`):
- Packed-K kernel correctness ✓ (cosine 0.9999792 vs Phase 5A)
- End-to-end Qwen2.5-7B install ✓ (28.6 tok/s, 0 fallbacks)
- Faster than Phase 5A end-to-end ✓ (+12.3%)
- **HBM savings vs stock: none** (+0.387 GB overhead today)
- **Batch > 1 support: none** (sidecar is per-process)

The memory-savings claim is contingent on Phase 5C landing
(`kv_cache_dtype="int4_protected"` registration in vLLM's
CacheEngine). The multi-batch claim is contingent on Phase 5B
(native attention backend). Neither is optional for a v1 ship that
holds water.

## Scope decomposition

| | Owns |
|---|---|
| **Phase 5B** | Native vLLM attention backend, per-sequence state in vLLM metadata, batch > 1 dispatch, cache write path |
| **Phase 5C** | `kv_cache_dtype="int4_protected"` config registration, CacheEngine per-block byte cost, BlockManager integration |

5B is the plumbing; 5C is what lands the memory claim.

## Architecture target: native attention backend (NOT monkey-patch)

vLLM 0.7.x has a plug-in attention backend system: at engine init,
the backend (FlashAttention, XFormers, FlashInfer, etc.) is selected
based on hardware + `kv_cache_dtype`. Each backend provides:
- per-block byte cost calculator
- kernel dispatch for the attention call
- cache write path

**Lock:** Phase 5B adds `Int4ProtectedAttentionBackend`. Phase 5C
makes it selectable via `kv_cache_dtype="int4_protected"`.

**Why not monkey-patch:** the BlockManager allocates blocks based on
the backend's byte-cost report. Monkey-patching `forward` doesn't
change BlockManager. So the 24 GB reserve stays 24 GB. No savings.

## Five open design questions — answers locked below

### Q1. Static protect-K mask: per-sequence or per-model?

Current Phase 2.4.1c: per-sequence (computed at prefill end from
each sequence's K magnitudes). Works for batch=1.

For multi-batch + prefix caching, blocks must be shareable across
sequences via content hash. If protect_mask differs per-sequence,
blocks are not shareable → prefix caching breaks.

| Option | Trade |
|---|---|
| A: per-sequence (current) | Best quality per-sequence; breaks prefix caching |
| B: per-model frozen at load | Sharable blocks; quality may degrade if K distribution varies per prompt |
| C: per-layer frozen at load | Same as B with finer granularity |

**Lock: B — per-model static protect mask.** Computed once via a
calibration script (Phase 5B.0) over a representative dataset
(WikiText sample). Saved as a frozen artifact.

**Quality risk mitigation:** Phase 6.4 GREEN tested per-sequence
masks. Run a Phase 6.4-style needle + lm-eval-harness sweep with
per-model mask at 4%, 6%, 8% (Phase 5B.5 — quality re-acceptance).
Lock the lowest fraction that holds 100% needle retrieval.

### Q2. Block layout: scale/xmin in-block vs out-of-band?

vLLM block_size is typically 16. Our quant group_size is 32. One
block contains < 1 group; one group spans 2 blocks. Awkward.

| Option | Cost |
|---|---|
| A: match group_size to block_size = 16 | 2× scale storage vs G=32 (still tiny: ~12% of total bytes per token) |
| B: separate out-of-band scale tensor | Adds a parallel allocation outside BlockManager — complicates eviction + prefix caching |
| C: pack scale inside each block | Variable-size blocks, mostly broken with vLLM's fixed-size paged allocator |

**Lock: A — group_size = 16 = block_size.** Match the block alignment.
2× scale storage cost is negligible.

**Per-token byte cost** at D=128, bf16, n_protect=5 (4%):

| Storage | Bytes/token | Stock (bf16) |
|---|---|---|
| K_int4 | 64 (= D/2) | 256 |
| K_scale (per-group, amortized) | 16 (= D bf16 / 16 tokens) | 0 |
| K_xmin (per-group, amortized) | 16 | 0 |
| K_protect_bf16 | 10 (= n_protect bf16) | 0 |
| V (still bf16 in 5B/5C, packed in 2.6) | 256 | 256 |
| **Per-token total** | **362 bytes** | **512 bytes** |
| **vs stock** | **0.71×** | 1.0× |

After Phase 2.6 (V packed): per-token = 64+16+16+10+64+16+16 ≈
**202 bytes** vs stock 512 = **0.40× (60% savings).**

Until 2.6, the 30% savings on K-only is real but partial.

### Q3. Cache write path

vLLM writes K/V to paged blocks during prefill and decode. Our path
needs to QUANTIZE before write.

| Option | Trade |
|---|---|
| A: write BF16, lazy-quantize on read | Quantize cost on every read = unacceptable |
| B: write quantized directly | Need scale/xmin BEFORE write, which depends on a full group |
| C: partial-group staging buffer | Maintain (group_size, D) BF16 buffer per (layer, kv_head); finalize on fill |

**Lock: C — partial-group staging buffer.**

Mechanics:
1. New K token arrives: write into staging buffer at `s_curr % G` row.
2. If `(s_curr + 1) % G == 0` (group complete): compute scale/xmin,
   quantize, write the full group to the paged INT4 cache, clear
   buffer.
3. Prefill end: if partial group remains, zero-pad to G, finalize
   (zeros are within typical K range — already validated in 2.4.1c).

Storage: 1 buffer per (layer, kv_head) = 28 layers × 4 H_kv = 112
buffers × G × D × 2 bytes = 112 × 16 × 128 × 2 = **448 KB total**.
Negligible.

### Q4. Native backend vs monkey-patch

Already answered above. Locking again here: **native backend.**

### Q5. vLLM version pinning

| Option | Pro | Con |
|---|---|---|
| A: pin to 0.7.3 (current) | Matches Phase 0 setup, all our patches anchor to 0.7.3 internals | Future vLLM upgrades require porting work |
| B: develop on 0.8+ | Forward-compatible | Reset Phase 0/1/2.x anchors on 0.8 internals = days of rework |

**Lock: A — pin to 0.7.3 for v1.** Migration to 0.8+ is post-v1.

## Sub-phase breakdown

Total estimate: **10-15 engineer-days** (2-3 calendar weeks with
iteration + integration testing). Sequenced for incremental
validation — each phase has its own acceptance gate.

### Phase 5B.0 — calibration script for static protect mask (~1 day)

Standalone Python. Loads Qwen2.5-7B, runs forward over a calibration
dataset (WikiText-103 sample, ~1k sequences), collects per-(layer,
kv_head, dim) max-abs across the dataset. Picks top-4% channels.
Saves as `qwen2_5_7b_protect_mask_4pct.pt`. No vLLM changes.

Acceptance: artifact exists, contains shape `(num_layers, H_kv, D)`
int8.

### Phase 5B.1 — partial-group staging buffer + standalone test (~1-2 days)

Implement `PartialGroupQuantizer` class. Takes K tokens one at a time,
emits packed INT4 + scales when groups complete. Standalone test
verifies bit-equivalence to `pack_k_for_phase2_4(full K)` on a
synthetic K trace.

Acceptance: round-trip test PASS — packing 4096 K tokens one-by-one
through the staging buffer produces the same packed dict as
`pack_k_for_phase2_4(K[:4096])`.

### Phase 5B.2 — Int4ProtectedAttentionBackend skeleton (~1-2 days)

Register a new attention backend class with vLLM's backend selection
machinery. Initial implementation: stub that delegates the attention
call to FlashAttention backend (i.e., zero behavioral change). Goal
is to verify vLLM PICKS UP the new backend when configured.

Acceptance: vLLM engine init log shows "Using Int4Protected backend"
when configured; smoke test still produces correct output (because
we delegate).

### Phase 5B.3 — CacheConfig + CacheEngine integration (~2-3 days)

- Patch `CacheConfig` validation to accept `kv_cache_dtype="int4_protected"`.
- Override per-block byte cost in `CacheEngine.get_cache_block_size`
  to return Phase 5B/5C per-token byte cost (362 bytes, dropping to
  202 after 2.6).
- BlockManager allocates fewer blocks at the same util → smaller reserve.

Acceptance: engine init log shows "the rest of the memory reserved
for KV Cache" drops from ~24 GiB to ~17 GiB (×0.71 ratio). Stock
behavior preserved when `kv_cache_dtype="auto"`.

### Phase 5B.4 — block-manager-aware read/write path (~2-3 days)

- Cache writes route through the staging buffer (Phase 5B.1), finalize
  groups into INT4 blocks.
- Cache reads happen inside the attention backend; backend calls our
  Phase 2.4.1b packed kernel directly using the BlockManager's
  block-table pointers.
- Multi-batch correctness test: two concurrent sequences must produce
  the same output as serial execution.

Acceptance: multi-batch smoke test PASS — needle retrieval works on
both sequences in a batch=2 run.

### Phase 5B.5 — quality re-acceptance with per-model mask (~1 day)

Re-run Phase 6.4-style needle test + lm-eval-harness sample with the
per-model frozen mask. Lock protect_fraction at the lowest value
holding 100% needle retrieval.

Acceptance: 100% needle at chosen protect_fraction; lm-eval-harness
within 5% of stock vLLM.

### Phase 5C — first-class config option (~1-2 days)

- Add to `LLM(...)` kwargs documentation.
- Add to `CacheConfig` schema.
- Top-level Python API: `LLM(model=..., kv_cache_dtype="int4_protected")`.
- Memory + throughput acceptance on full ship config (max_model_len=32k).

Acceptance: ship-config memory + throughput pass; documentation
includes the config option.

## Risk callouts

1. **vLLM internal API drift between 0.7.3 and 0.8+** —
   AttentionBackend interface, BlockManager hooks, CacheConfig
   validation. **Mitigation:** pin to 0.7.3; document migration plan.

2. **Per-model static mask quality vs per-sequence** —
   Phase 6.4 GREEN tested per-sequence. **Mitigation:** Phase 5B.5
   sweeps fractions; lock the lowest that holds.

3. **Partial-group staging buffer correctness** — off-by-one in
   finalize logic, prefill-tail partial group, races between
   prefill and decode. **Mitigation:** standalone tests in 5B.1
   before vLLM integration.

4. **BlockManager allocation accounting** — vLLM schedules based on
   per-block byte cost. Under-reporting bytes → over-commits →
   OOM. **Mitigation:** include ALL bytes (k_int4 + scales + xmins
   + protect_bf16 + V) in the byte-cost calculator.

5. **Prefix caching with per-model mask** — vLLM's prefix caching
   hashes blocks. With per-model mask, identical token prefixes
   produce identical blocks → cache hits work. With per-sequence
   mask, they don't. **Mitigation:** locked Q1 to per-model.

6. **Multi-batch dispatch in the kernel** — current packed kernel
   was verified at batch=1. **Mitigation:** Phase 5B.4 smoke test
   at batch=2 explicitly.

7. **The packed kernel reads from a contiguous (S_max, H_kv, D/2)
   sidecar; vLLM's paged cache is (num_blocks, block_size, H_kv,
   D/2)** — different layout. The kernel needs a block-table-aware
   read path. **Mitigation:** either adapt the kernel to use vLLM's
   block_table (the original FA path was designed for paged reads;
   inherit), or expose a "gather to contiguous" pre-pass. Decide
   in Phase 5B.4.

8. **V cache still BF16 in 5B/5C** — 30% savings on K-only.
   Until Phase 2.6, the ship claim is "30% smaller KV than stock."
   Honest framing. **Mitigation:** clear in marketing materials;
   2.6 lands the rest.

## Acceptance criteria

### Phase 5B GREEN
1. Engine init log shows `Int4ProtectedAttentionBackend` selected when configured.
2. KV reserve drops from ~24 GiB to ~17 GiB (×0.71).
3. Multi-batch (batch=2) smoke test PASS.
4. 0 fallbacks in decode.
5. Phase 2.4.1d single-batch tests still PASS (no regression).

### Phase 5C GREEN
1. `LLM(model="Qwen/Qwen2.5-7B-Instruct", kv_cache_dtype="int4_protected")` works as a first-class config.
2. At max_model_len=32768, KV reserve ≤ 8 GiB (vs stock ~24 GiB at same gpu_memory_utilization).
3. Phase 6.4-style needle test at chosen protect_fraction: 100% retrieval.
4. lm-eval-harness sample within 5% of stock vLLM.
5. Throughput on multi-batch workload ≥ 50% of stock vLLM (full parity is Phase 6 perf work).

## What does NOT land in 5B/5C

Per the locked v1 scope:
- Pre-RoPE quantization (out of scope across all of 6c.3C)
- FP4/NVFP4 alternative
- Multi-model support (Qwen2.5-7B only for v1; Llama/Phi/etc. are Phase 7+)
- Speculative decoding
- FA3/Hopper instantiations
- Throughput parity with stock vLLM at all scales (5B targets ≥ 50%; full parity is Phase 6)
- V packing (Phase 2.6)
- Tensor parallelism (single-GPU only for v1)

## Suggested sequencing

5B.0 → 5B.1 → 5B.2 → 5B.3 → 5B.4 → 5B.5 → 5C

Each phase has its own acceptance gate, so the project ships
incremental value. If Phase 5B.3 (CacheEngine) hits an unfixable
0.7.3 limitation, we can replan without losing 5B.0-5B.2 work.

## Open questions to resolve before Phase 5B.0 starts

1. **Calibration dataset choice.** WikiText-103 is the default but
   may not represent serving workloads. Options:
   - WikiText-103 sample (1k sequences, ~5 min compute)
   - lm-eval-harness MMLU prompts (more diverse, ~30 min compute)
   - Mix of both
   Recommendation: start with WikiText (cheapest); revisit if 5B.5
   quality test fails.

2. **Calibration prompt count and length.** More prompts → tighter
   per-channel statistics, but diminishing returns past ~1k. Lock
   at 1k prompts × 512 tokens initially.

3. **Mask sparsity granularity.** Currently top-4% per (layer, h_kv).
   Could be per-(layer, h_kv, head_group) for GQA. Lock at
   per-(layer, h_kv) — matches the existing Phase 4 / Phase 5A code.

## What this doc does NOT lock

- Implementation language for the staging buffer (PyTorch vs
  CUDA/Triton). Start with PyTorch in 5B.1; iterate.
- Exact CacheEngine hook surface (TBD when reading vLLM 0.7.3 source).
- vLLM API surface for backend registration (TBD when reading vLLM
  0.7.3 source).

These are 5B.2/5B.3 implementation decisions, not pre-flight design
locks.
