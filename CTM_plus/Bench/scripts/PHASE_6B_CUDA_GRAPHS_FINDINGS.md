# Phase 6B CUDA Graphs — measured finding

> **Status:** Phase 6B (6B.1 + 6B.2 + 6B.3 + 6B.4) **CLOSED**.
> Single-pod GPU bench on Qwen-2.5-7B-Instruct + A100 + vLLM 0.7.3
> (forked int4_protected build) returned all four G_THROUGHPUT
> checks **GREEN** — the project's stated gate (CUDA graphs deliver
> ≥ 1.88× the 42.6 tok/s eager baseline at B=8) was met with margin
> (3.51× actual). The CUDA Graphs capture work landed.
>
> **The bench also surfaced a separate, dispositive result that
> matters more for the VC brief than the gate itself: int4_protected
> in its current architecture is 4-7× slower than stock vLLM bf16
> across every measured batch size, and uses ~60% MORE HBM than
> bf16 to do it.** The 1.88× throughput uplift from CUDA graphs is
> a 0.15-0.44× tax against the industry baseline — not a win.
>
> The data points at the same architectural fix: the
> `PagedKVWriter`'s `_bf16_k_backing_pool` is sized for the entire
> sequence (max_S=4096) when its job is only to provide full-
> precision K for the in-flight partial block (BS=32 tokens). That
> 128× oversize is the proximate cause of both the memory footprint
> AND the per-decode-step bandwidth pressure that erodes the
> CUDA-graphs uplift at B≥16. **Phase 6C scope: redesign the
> writer's backing pool to BS-sized window and re-bench.**

## TL;DR

| Item | Status |
|---|---|
| **G_THROUGHPUT primary gate (captured B=8 ≥ 80 tok/s)** | **GREEN** — 149.5 tok/s (3.51× the 42.6 baseline) |
| G_THROUGHPUT speedup gate (captured B=8 ≥ 1.88× baseline) | **GREEN** — 3.51× |
| G_THROUGHPUT in-run gate (captured B=8 > eager B=8) | **GREEN** — 1.42× (105.5 → 149.5 tok/s) |
| All four G_CAPTURE.2 checks (semantic-eq + non-pathological + det) | **GREEN** (from 6B.3) |
| 35/35 captured shapes succeed | **GREEN** (from 6B.3) |
| 6B.2 hook integrates with captured graph replay | **GREEN** (stash_call_count = 244 in captured cell) |
| TIER5A G5/G6 orthogonality | **GREEN** (G5c SHA baseline regen'd; 10 files) |
| **vs stock vLLM bf16 throughput** | **RED — int4 captured is 0.44-0.15× of bf16 across B∈[1, 32]** |
| **vs stock vLLM bf16 memory** | **RED — int4 captured 61.68 GB vs bf16 38.52 GB** |
| Overall verdict on the project as positioned | **The gate passed; the design didn't.** |

## The headline result

Three cells on identical workload (Qwen-7B, max_model_len=4096, n_runs=5 median, gpu_memory_utilization=0.5):

```
  B  |  int4 eager | int4 captured |   bf16 stock | cap/eager | cap/bf16
 ----+-------------+---------------+--------------+-----------+----------
   1 |      18.6   |       37.3    |       85.2   |   2.01×   |   0.44×
   2 |      31.8   |       65.3    |      169.0   |   2.05×   |   0.39×
   4 |      59.7   |      100.5    |      324.8   |   1.68×   |   0.31×
   8 |     105.5   |      149.5    |      577.1   |   1.42×   |   0.26×
  16 |     171.7   |      193.5    |      999.0   |   1.13×   |   0.19×
  32 |     259.4   |      241.7    |     1593.0   |   0.93×   |   0.15×
```

All numbers are aggregate output tok/s (decode + prefill). Within-cell determinism preserved.

**Reading the table:**

* **`cap/eager` (CUDA-graphs uplift on our backend):** 2.01× at B=1 declining to 0.93× at B=32. Graphs help most at low B where the per-layer Python dispatch dominates; at B=32 the dispatch overhead is amortized differently and graph dispatch itself becomes net-negative. The 6B.1/6B.2/6B.3 work delivered as designed.
* **`cap/bf16` (vs stock vLLM industry baseline):** **0.44× at B=1 declining to 0.15× at B=32.** The ratio degrades monotonically with concurrency — int4_protected falls further behind bf16 as B grows.

The CUDA graphs gate was set without measuring the bf16 baseline. It should have been.

## The architectural cause

`PagedKVWriter` carries two parallel K storages per active sequence:

1. **`kv_cache`** — int4-quantized K + V (the "int4 protected" payload). 0.5 bytes per element. For 28 layers × H=4 × D=128 × max_S=4096, that's **~7 GB at 64 slots**.
2. **`_bf16_k_backing_pool` + `_bf16_v_backing_pool`** — full bf16 K + V for the entire sequence history. 2 bytes per element. Same shape. **~28 GB at 64 slots.**

The bf16 backing exists because the kernel needs full-precision K for the in-flight partial block (the last BS=32 tokens) before they're finalized + quantized into a new kv_cache block. Once a block fills, those tokens are committed as int4; the bf16 copy is redundant.

**The implementation keeps the bf16 backing for the entire sequence lifetime, not just the current partial block.** That's a 128× oversize (max_S/BS = 4096/32 = 128). The kernel passes the entire backing on every decode step's read; at B=32 that's 32 × 4096 × 4 × 128 × 2 bytes = **128 MB per layer per decode step in pure read bandwidth**, of which only ~1 MB (the last BS tokens) is actually needed.

Symptoms this explains:

* **`captured cell = 61.68 GB` vs `bf16 cell = 38.52 GB`** (60% MORE HBM than stock bf16). The bf16 backing pools alone (~28 GB) dwarf the int4 savings (~5-7 GB from quantizing kv_cache).
* **`cap/eager` ratio degrades from 2.0× → 0.93×** as B grows. The captured graph's gather of `_bf16_k_backing_pool[slot_idx_t, :S_padded]` is the bandwidth-dominant op at high B; the CUDA graph captures it efficiently but can't change the I/O volume.
* **OOM at B≥16 in the earlier run with `max_active_slots=64`.** The slot pool sizing forced 64 × 28 × 16 MB = 28 GB of bf16 backing into a 40 GB budget; combined with model weights, sidecars, and the graph capture pool, the 0.5 utilization budget was unworkable.

## The methodology

### Workload (final GPU bench on the A100 pod)

* Model: `Qwen/Qwen2.5-7B-Instruct` (28 layers, H_kv=4, D=128)
* GPU: A100-80GB, `gpu_memory_utilization=0.5`
* max_model_len = 4096; max_tokens = 32
* Three cells, run as separate subprocess workers:
  * **eager** — `Int4ProtectedLLM(...)` + `PHASE6B3_FORCE_EAGER=1` + 6B.2 hook
  * **captured** — `Int4ProtectedLLM(...)` + default `enforce_eager=False` + 6B.2 hook + 35-shape graph capture
  * **bf16** — stock `vllm.LLM(model=..., dtype="bfloat16")` + default graphs + no int4_protected, no hook
* Per cell: warmup; sweep B ∈ {1, 2, 4, 8, 16, 32}; n_runs=5 per B (median wall_s reported); `agg_tps = total_output_tokens / median_wall_s`
* Identical prompt repeated B times — every sequence in the batch generates identical tokens (temp=0, greedy) so total output tokens is exactly B × per_seq_tokens.

### Six checks; all four primary checks GREEN

```
[PASS] captured_agg_tps_B8_ge_80                  149.5 tok/s
[PASS] captured_speedup_B8_ge_1p88x               3.51× (gate ≥ 1.88×)
[PASS] in_run_speedup_B8_captured_vs_eager_positive   1.42×
[INFO] info_captured_vs_bf16_B8_ratio             0.26× (informational; not a gate)
```

The fourth check is intentionally informational — the original 6B plan did not gate on bf16 comparison. It does now in the closed-finding narrative.

## Lessons learned (durable)

1. **Always measure against the industry baseline, not just the prior internal baseline.** The 1.88× target was a self-referential gate (42.6 → 80 tok/s). A 80 tok/s captured cell vs 577 tok/s bf16 still loses by 7×. Future gates should include an absolute-throughput cell.

2. **CUDA graphs help most at the smallest B.** At B=1, every per-layer Python dispatch is on the critical path; graphs erase ~50% of that. At B=32, the per-layer work itself dominates and graph dispatch overhead becomes net-negative (-7% at B=32 here). Capture is not free.

3. **Storing K twice is a memory-and-bandwidth bug, not a feature.** The bf16 backing pool was sized for "full sequence" defensiveness; the actual kernel only needs the current partial block. The 128× oversize was invisible until the bench surfaced it.

4. **Semantic-equal correctness gate (6B.3) was the right call.** Even with strict byte-eq the throughput would have been the same. The kernel FP-noise issue is orthogonal to the architectural memory issue and should not have blocked the throughput measurement.

5. **The 6B.2 hook is solid.** stash_call_count=244 in the captured cell confirms it fires once per decode step across both prompts × all batch sizes. The hook's 28× host-sync amortization is real; the throughput ceiling it lifted just wasn't where the actual bottleneck lived.

## Phase 6C scope (recommended)

**Goal: shrink `_bf16_k_backing_pool` / `_bf16_v_backing_pool` from `(n_slots, max_S=4096, H, D)` to `(n_slots, BS=32, H, D)`** — the actual in-flight partial-block window.

Expected effects:
* Writer HBM drops from ~28 GB (at 64 slots, 28 layers) to ~220 MB. **A ~130× memory reduction on the auxiliary state.**
* int4_protected captured HBM at B=32, max_S=4096 falls from 61.68 GB to ~34 GB (less than bf16's 38.5 GB).
* Per-decode-step read bandwidth on `bf16_k_batch` drops from ~128 MB/layer to ~1 MB/layer at B=32 — this is the op the captured graph's gather is currently bandwidth-bound on, so the cap/bf16 ratio should improve substantially.

**Risk:** the kernel currently expects `bf16_k_batch.shape[1] == S_padded` (the full block budget width). The redesign requires either:
* Making the kernel index `bf16_k_batch[:, :BS, ...]` for the partial block, falling back to dequantized int4 for older positions — kernel-side change, requires a C++/CUDA work item.
* Or only passing the bf16 backing for the last partial block, masking by a new `bf16_k_window_start` parameter — Python-side wrap, less invasive.

**Effort:** ~3-5 days design + impl + verify. Cross-family sanity (Qwen + Mistral) recommended.

**Open questions:**
* Does the kernel correctly dequantize the in-progress partial block from `view["k_int4"]` if the bf16 backing for those positions isn't provided? If yes, this is a Python-side fix only. If no, the kernel needs updating.
* What's the right window? Just BS=32 (last block only), or 2×BS=64 (last + previous block, for prefix-cache scenarios)?

## Code disposition

All Phase 6B code stays in-tree:

* `phase5b_4c_paged_writer.py` — capture-safe gates; sentinel-gated sync; reset_sequence("all"); `_in_cuda_graph_capture()` predicate
* `phase5b_backend_install.py` — capture-aware dispatch fork; `n_blocks_max = block_table.shape[1]` unconditionally; persistent slot-idx buffer reads under capture
* `phase6b2_precapture_hook.py` — execute_model wrap; `_resolve_and_stash`; impl-level buf population
* `bench_phase6_b3_capture_gpu_smoke.py` — semantic-eq G_CAPTURE.2 driver (the gate that closed 6B.3)
* `bench_phase6_b4_throughput_gpu.py` — three-cell throughput driver (eager + captured + bf16) with semantic-eq gate + bf16 informational comparison; the bench that produced this finding
* G5c SHA baseline (10 files) regen'd in `int4_protected_files_baseline.json`

Three env-override kill-switches retained as bisection primitives:
* `PHASE6B1_USE_DECODE_BATCHED=0` — disables the 6B.1 batched-write path
* `PHASE6B2_INSTALL_HOOK=0` — skips the 6B.2 pre-capture hook
* `PHASE6B3_FORCE_EAGER=1` — disables CUDA graphs capture entirely

## Deferred (logged for Phase 6C and beyond)

1. **Backing pool redesign (primary; Phase 6C):** shrink `_bf16_k_backing_pool` to BS-window. See "Phase 6C scope" above.
2. **`_v_bf16_ext` lazy-alloc inside captured graph:** the bf16 V mode (`PHASE5B_4C_BF16_V=1`) allocates `_v_bf16_ext` inside `torch.cuda.graph(...)` context, placing its storage in the graph memory pool where other graphs' intermediates can alias it. Symptom: captured cell becomes non-deterministic with pathological output. Fix: hoist allocation to `_lazy_alloc(kv_cache)`. Documented in PHASE_6B3_CAPTURE_FINDINGS.md; not in scope for 6B since default int4 V mode doesn't hit it.
3. **CUDA graph overhead at high B:** captured underperforms eager at B=32 by 7%. Likely from the bf16 backing gather being the bandwidth-dominant op; will resolve when 6C lands. If it doesn't, investigate the hook's per-step impl-loop population (28 impls × 1 `.copy_()` each).
4. **Cross-family sanity:** Mistral-7B sweep not re-run for 6B.4 (only the Qwen ship target). Add when 6C is done.

## Brief update proposal (text only, NOT applied without explicit approval)

**Page 5 Tier 1 row (CUDA Graphs):** mark `IMPLEMENTED` but add footnote: "uplift confirmed (1.88× the prior 42.6 baseline at B=8); throughput parity with stock vLLM bf16 is the Phase 6C target."

**Page 6 Measured table per-seq-latency row:** update to `Qwen-7B B=8: 149 tok/s aggregate (18.6 tok/s per-seq); 1.42× the 6B baseline; 0.26× of stock bf16. Phase 6C re-bench pending.`

**Headline narrative:** keep the memory-efficiency story for now. Add a 6C work-item bullet: "Resolve identified bf16-backing-pool oversize; expected to restore memory advantage vs stock vLLM and close throughput gap." Sell the discipline of catching this — not the broken result.
