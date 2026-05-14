# Continue CTM+ development — session N+2 prompt

**Repository:** `rasaha/symbolu`
**Branch:** `claude/safety-state-machine-EXAlZ`
**Latest commit:** `ae94bf0` (docs(phase4): v10 result + Phase 4 throughput closure + Track B handoff)

## Current state — read this before suggesting code

Read **`CTM_plus/Bench/bench_out/PHASE4_GPU_FINDINGS.md`** end-to-end first, paying attention to §12.6–§13.3 (the Cython-port + hook-shape-fix arc and the durable-negative closure). It captures the full **ten-run** GPU experiment record now, the **eight** audit-pass bug fixes (one added in v9 — `_phase4_handles` missing on the cdef class), the I1–I5 + Cython + fast-hooks engineering sequence, and the §11 py-spy diagnosis.

Key measured findings to preserve:

- **98.7–99.0% trig-override rate** across v6/v8/v9/v10: algorithm dominantly active.
- **−11.1% swap_out per decode token vs LRU** — reproduced across **five distinct evictor implementations** (v5/v6/v8/v9/v10) with bit-identical eviction outcomes. Durable algorithm result.
- **−20% tokens/sec vs LRU — structural.** Three engineering generations (I1–I5 + Cython port + monkey-patched-forward fast hooks) audit-summed at 19–38pp recovery; measured ~1pp total. The gap lives in vLLM 0.7.3 scheduler + allocator paths around an Evictor-ABC patch point, NOT in CTM+ code (py-spy: CTM+ = 1.1% of wall).
- **Cython `CTMEvictorModernC` is semantically validated** on real-model GPU (v9: swap_out / decode_token = 0.2769 bit-identical to v8). Production-ready code shape.
- **Bench tests: 278 passed, 44 skipped.** Parametrized over `[py]` and `[c]` evictor variants. All eight audit-pass bugs pinned by `tests/test_vllm_protocol_fixture.py` + the new `test_phase4_external_attr_writes_succeed_on_cdef_class` + the monkey-patch regression pair.

**Phase 4 throughput optimization is CLOSED as an engineering work-track.** Cumulative GPU spend ~$2.10. Don't iterate further on chat_32k throughput without new evidence (different vLLM version, different integration point, or partner-specific workload). See §13.3 for what survives partner-shareable, what moves with caveat, and what stops.

## Three tracks for this session

All are sized. Track B is the strongly recommended primary; C and D are alternates with specific triggers.

### Track B — TurboQuant ↔ vLLM integration, Tier 1 CPU prototype (Recommended)

**Why:** the architecture-doc 8.8× claim assumes TurboQuant × CTM+ × CTXL stacking. CTM+ Phase 4's algorithm layer is validated (−11% per-token swap, mechanism dominantly active); the throughput cost is now bounded and understood. TurboQuant is the next layer of the stack. It's CPU-simulated only (`CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md`) — the vLLM-side integration **has never been built**.

**Sized:** ~1 day code + ~$0.05 GPU. Expected output: measured compression ratio + cosine similarity on real Qwen2.5-7B KV blocks, exact hook points named, throughput cost characterised (will be catastrophic by design at Tier 1 — that's expected).

**Existing code to reuse (~1900 lines, math is correct):**

- `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_offload.py` — `PolarQuant`, `QJL`, `TurboQuantCompressor`, `TurboQuantOffloadManager`
- `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_numba.py` — JIT polar transform kernels
- `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_cuda_ext.py` — CUDA stub (NOT functional; Tier 3 target)

**Integration shape (the gap):**

- vLLM's `Attention.forward` in `vllm/attention/layer.py` calls `cache_kv` (FlashAttention backend) on write
- KV cache layout: `[2, num_blocks, block_size, num_kv_heads, head_dim]` BF16/FP16 on GPU
- Tier 1 routes K/V tensors through CPU compression → decompression on read
- Latency will slow inference 10–100× by design

**Start here:**

1. Read the `PolarQuant` + `TurboQuantCompressor` round-trip in `turboquant_offload.py` (focus on `compress`/`decompress` signatures + tensor-shape expectations).
2. Read `vllm/attention/layer.py` `Attention.forward` to identify the cache-write hook point. The flash-attn backend's `cache_kv` call is the natural insertion point.
3. New module: `CTM_plus/KVPolicy/kv_policy/turboquant_kvstore.py` implementing the vLLM-side wrapper that compresses on write, decompresses on read, and tracks per-call compression metrics.
4. New CLI flag: `--turboquant-kv` in `run_streaming.py`. Off by default. When on, installs the wrapper alongside (or in place of) the CTM+ evictor patch.
5. CPU regression tests pinning: round-trip preserves shape + dtype; decompression cosine similarity ≥ 0.95 on synthetic + a real Qwen2.5-7B KV slice; per-call latency reported in the streaming summary as `compression_us_per_block` / `decompression_us_per_block`.
6. One Tier-1 measurement cell on Qwen2.5-7B + chat_32k (or shorter; doesn't need to complete — just needs to emit a round-trip on real tensors). Artefact in `bench_out/turboquant_cpu_prototype/`.
7. New `PHASE4_GPU_FINDINGS.md` §14 (or a fresh `TURBOQUANT_INTEGRATION_FINDINGS.md`) with the integration-shape result, measured compression ratio, cosine similarity, and the exact hook points.

**Validation criterion:** measured compression ratio ≥ 5× at cosine similarity ≥ 0.95 on real Qwen2.5-7B KV blocks, with the exact vLLM hook points documented. **Honest framing post-Tier 1:** "TurboQuant compresses real Qwen2.5-7B KV blocks at X× ratio / Y cosine similarity through a working vLLM-integration shape. End-to-end inference cost is structurally bounded by CPU transit (Tier 2 is the GPU port)."

**Tier 2 (next session after Tier 1, ~3–5 days code + ~$0.20 GPU):** re-implement TurboQuant's polar transform in pure PyTorch ops (`torch.atan2`, `torch.cos`, `torch.sin`, `torch.bucketize` for bit-packing). Runs on GPU without CUDA. 5–10× slower than a hand-rolled kernel but real GPU code, deployable shape.

**Tier 3 (future, ~2–4 weeks):** Triton or CUDA kernel. What `turboquant_cuda_ext.py` stub was meant to be. Production-ready. NOT for this session.

**Do NOT, even after Tier 2, claim 8.8× combined-stack capacity.** That requires CTM+ × TurboQuant × CTXL together. CTXL has zero runtime measurement. Honest framing post-Tier-2: "TurboQuant × CTM+ combined: measured X× memory at Y% throughput cost on Qwen2.5-7B. CTXL tiering layer remains projection only."

### Track C — Decision-quality measurement on `agentic_clustered_64k` or `rag_128k`

**Why:** v5/v9/v10 all ran chat_32k and produced `swap_in_blocks = 0` — no re-references to evicted blocks within the 60s budget. This means our −11% swap_out / decode_token result proves we evict *fewer* blocks per useful token, but does NOT directly prove we evict the *right* blocks. A workload where `swap_in > 0` lets us measure decision quality directly (re-reference miss rate, hit rate, etc.).

**Sized:** ~$0.10 GPU + ~half-day plumbing (the workload generators exist in Mode A; the harness flag exists in `run_streaming.py`). Output: a `agentic_clustered_64k` or `rag_128k` cell with measured `swap_in` counters + a decision-quality metric (e.g. wrong-evictions / total-evictions, or swap_in_blocks-not-from-evictor / swap_in_blocks-total).

**Trigger:** prefer this over Track B if a partner specifically asks "but did you evict the RIGHT blocks?" or if the partner workload is agentic/RAG-heavy. Otherwise Track B is more strategic (closes the next-layer validation gap).

**Validation criterion:** report the swap_in_blocks distribution split between "from CTM+ evictor's pool" and "from native LRU + prefix-cache promotion" on a workload where `swap_in > 0`. If CTM+'s evictor underperforms LRU on decision quality at re-reference, that's a more damaging result than the current −20% throughput. If it outperforms, that strengthens the algorithm pitch independent of throughput.

### Track D — Re-architect the integration point (deferred)

**Why:** §13.3 names the structural ceiling: vLLM 0.7.3's `PrefixCachingBlockAllocator.evictor` patching disrupts the prefix-cache promotion path. A deeper integration that doesn't go through evictor patching could close the 20% throughput cost. Three candidates: subclass `CpuGpuBlockAllocator`, intercept at `BlockTable` / `KVCacheManager`, or land an upstream vLLM PR adding a public `EvictorPolicy` abstraction.

**Sized:** 2–3 weeks of engineering + meaningful GPU spend. High effort, uncertain payoff. **Defer unless a partner specifically requests chat-throughput parity AND commits to scoping** — otherwise it's research-grade engineering without a clear customer.

## Recommended starting point

**Start with Track B (TurboQuant Tier 1 CPU prototype).** Reasons:

1. Phase 4 throughput is closed; iterating further wastes time. Track B opens the next-layer validation gap on the architecture-doc stack.
2. Tier 1 is contained: math already works (CPU benchmark exists), gap is purely the vLLM-side wiring. ~1 day of focused work.
3. After Tier 1 + Tier 2 (next session), we have "TurboQuant × CTM+ combined: X× memory at Y% throughput cost on Qwen2.5-7B." That's a real two-layer-validated stack claim.
4. Track C is a single-workload-pivot move that doesn't structurally change the engineering picture. Useful if a partner asks; not a first-mover.
5. Track D is deferred by default.

**Switch to Track C if:** partner conversation is agentic / RAG-heavy and they specifically want decision-quality evidence.
**Switch to Track D if:** partner specifically wants chat-throughput parity and commits to scoping the integration rewrite.

## What to NOT do

- **Don't iterate on Phase 4 throughput.** Three engineering generations are closed. New work requires new evidence (different vLLM version, different integration point, different workload class), not more leaf-level optimization.
- **Don't update the architecture-doc 8.8× claim** without measured combined-stack data. The downgrade banner in `CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` is the current honest framing.
- **Don't claim TurboQuant × CTM+ stack effects** after Tier 1 alone. Tier 1 is CPU shim, can't show real combined-stack throughput. Honest framing: "integration shape works; compression ratio measured; throughput cost characterised but expected to be catastrophic at Tier 1."
- **Don't re-run another chat_32k cell** without a hypothesis that distinguishes from v5/v6/v8/v9/v10. We have enough data on that workload.
- **Don't add a CUDA kernel** for TurboQuant (Tier 3). Tier 2 PyTorch-ops first is the right intermediate.
- **Don't extend the Cython port** to `KVCachePolicy.select_victims` / `score_block` etc. unless v10 results are revisited under a different workload. The current Cython surface is at the boundary the §11 profile justifies.

## File pointers for fast onboarding

| Path | Purpose |
|---|---|
| `CTM_plus/Bench/bench_out/PHASE4_GPU_FINDINGS.md` | Canonical session record §1 TL;DR + §11 profile + §12.6/§12.7/§12.8/§13.3 (the Cython + fast-hooks + closure arc) |
| `CTM_plus/Bench/bench_out/PARTNER_VALIDATION_NOTE.md` | Partner-shareable framing with Phase 4 v3–v10 + closure |
| `CTM_plus/Bench/scripts/POST_PHASE4_ROADMAP.md` | 7-step roadmap; Step 1 now marked closed; Steps 2–6 reference the unmeasured layers |
| `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_offload.py` | **Track B reuse target** — PolarQuant + QJL + offload manager |
| `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_numba.py` | Track B reuse — Numba JIT polar kernels |
| `CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md` | Existing CPU-only TurboQuant benchmark (7.15× / 0.965 cosine on synthetic) |
| `CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` | Architecture-doc with the 8.8× claim + the honest-scope downgrade banner |
| `CTM_plus/KVPolicy/kv_policy/vllm_evictor.py` | `CTMEvictorModern` / `CTMEvictorModernC` — production-ready code shape (NOT a Track B target; Phase 4 is closed) |
| `CTM_plus/KVPolicy/kv_policy/_ctm_evictor.pyx` | Cython source for the C variant. Build: `cd CTM_plus/KVPolicy && python3 setup.py build_ext --inplace` |
| `CTM_plus/KVPolicy/kv_policy/triattention.py` | Phase 4 hooks + `_wrap_module_forward` helper (fast-hooks path). Production-ready. |
| `CTM_plus/Bench/tests/test_vllm_protocol_fixture.py` | CPU fixture pinning Evictor ABC + cdef-class attr-set contract + monkey-patch contract — must keep green |
| `CTM_plus/Bench/scripts/run_v9.sh`, `run_v10.sh` | Reference GPU batch entry points; mirror their shape if a Track B GPU cell is needed |

## Open the session by asking the user

1. "Which track — B (TurboQuant Tier 1 CPU prototype, recommended), C (decision-quality on agentic/RAG), or D (integration re-architecture)?"
2. "GPU spend budget? Track B Tier 1 needs ~$0.05 for one Qwen2.5-7B round-trip cell; code-only is fine if you want to defer the cell to Tier 2."
3. "Any partner-specific input that should redirect — workload class, model class, vLLM version constraint, deployment timeline?"
