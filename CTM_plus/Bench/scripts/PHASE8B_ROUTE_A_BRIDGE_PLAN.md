# Phase 8b — Route-A Days 4-5 + bridge plan

> **Status:** scaffold + composition test landed; awaiting GPU pod for
> the smoke run. This doc is the engineering plan for the next pod
> session and the bridge-completion roadmap.

## TL;DR (read this first)

The audit said "Route-A is dequant-only and does NOT wire attention
through to the Phase 4 evictor." That was 80% right and 20% wrong.

* **80% right:** Route-A's `_wrap_attention_forward_with_kv_rewrite`
  (int4_cache_kv_route_a.py:527-590) only rewrites K/V. It does not
  itself call `evictor.forward_block_attention`.
* **20% wrong:** A SEPARATE wrapper installed alongside route-A —
  `install_attention_capture` (vllm_evictor.py:1691-1797) — already
  computes per-block attention sums and pushes them to
  `AttentionAggregator`, which `_run_attention_flusher`
  (runner_vllm_streaming.py:830-855) periodically flushes to the
  evictor's `forward_block_attention`. **The "bridge" infrastructure
  exists.** It has just never been verified composing with route-A
  on the same model, on GPU, end-to-end.

So the bridge work is **mostly verification**, not new architecture.

## Critical clarification: Phase 3 vs Phase 4 are mutex

Reading `runner_vllm_streaming.py:601-606` surfaced a finding the
audit didn't have: **`--phase3-attention` and `--phase4-trig-calibration`
are explicitly mutually exclusive in the runner** (`ValueError` thrown
at engine init). The framing is "competing hypotheses; run in separate
cells of the four-cell experiment".

These two signal pipelines do different things:

| Phase | What it captures | How it reaches scoring |
|---|---|---|
| **Phase 3 (attention forwarding)** | Manual softmax(Q·K^T / √d) of the decode-step query against cached keys, summed per block | `forward_block_attention` → `policy.on_block_attention` → the 0.35*attn term in `score_block` |
| **Phase 4 (trig scoring)** | Pre-RoPE K vectors + per-layer Q-center stats → S_trig + S_norm | `_block_trig_score` cache → trig-blend re-rank inside `evict()` (separate code path from `on_block_attention`) |

The audit framed both as "what makes the bridge work." That conflated
two independent levers:
* The **bridge** (close the -20% Python-dispatch tax) needs Phase 3,
  because Phase 3 is what feeds the empty `on_block_attention` slot
  that vLLM's Evictor-ABC `update()` zeros out.
* The **algorithm win** (-11% swap_out in v5) came from Phase 4 trig.
  Per-layer recalibration may preserve or amplify it.

**Implication for 8a:** rather than ONE cell with both phases, 8a runs
THREM as separate cells of the four-cell layout:
- Cell 2 = `--ctm-plus --phase3-attention` (bridge cell)
- Cell 3 = `--ctm-plus --phase4-trig-calibration <path>` (algorithm cell)
- Cell 4 = `--ctm-plus --phase4-trig-calibration <path> --int4-kv-route-a` (combined-stack; Phase 4 trig is the empirically stronger algorithm so the combined cell uses it)

This composition is enforced by the runner's mutex; it's also the
cleanest scientific design.

## What this phase delivers

| Artefact | Where | Status |
|---|---|---|
| CPU composition regression test | `Bench/tests/test_route_a_phase3_composition.py` | LANDED — runs once torch is available; locks the install order + asserts zero double-quantization |
| GPU smoke script (Days 4 + 5) | `Bench/scripts/phase8b_route_a_gpu_smoke.sh` | LANDED — runs on pod |
| 8a remeasurement scaffold | `Bench/scripts/phase8a_remeasure.sh` + `PHASE8A_REMEASUREMENT_SCAFFOLD.md` | LANDED but **gated** behind Day 5b green |
| Per-layer recalibration prerequisite | `PHASE8A_REMEASUREMENT_SCAFFOLD.md` §"Per-layer recalibration" | DOCUMENTED — to run BEFORE 8a |

## Bridge architecture, as it stands

```
  vLLM Attention.forward(query, key, value, kv_cache, attn_metadata)
        ↑
  install_attention_capture wraps it (capture_forward)
        ↑
  install_int4_cache_kv_route_a wraps THAT (route_a_forward)
        ↑
  vLLM model code calls route_a_forward(q, k, v, ...)

  Call sequence at runtime, per layer per decode step:

  1. route_a_forward receives (q, k, v, kv_cache, attn_metadata).
  2. It calls manager.round_trip_kv(k, v) → returns (k_int4, v_int4).
  3. It calls capture_forward(q, k_int4, v_int4, kv_cache,
     attn_metadata).
  4. capture_forward calls original Attention.forward(q, k_int4,
     v_int4, ...) — vLLM's real attention runs on the int4
     round-tripped K/V. The model produces correct (but lossy) output.
  5. capture_forward calls _capture_attention_to_aggregator(args,
     kwargs, head_dim, aggregator). The aggregator's
     record_block_attention buffers per-block sums.
  6. Returns up the stack.

  Asynchronously, every sample_interval_seconds:

  7. _run_attention_flusher calls aggregator.flush_to_evictor(evictor).
  8. flush_to_evictor iterates the buffer; for each block_id, calls
     evictor.forward_block_attention(block_id, attention_sum).
  9. The evictor's CTMEvictorModern.forward_block_attention calls
     policy.on_block_attention, which feeds the EMA / entity
     classification path.
 10. Subsequent evict() calls score blocks using the now-non-zero
     attention signal — Phase 4's eviction is finally
     attention-driven.
```

The chain has no architectural holes. The verification gaps are:

* **Step 5** uses `decode_attention_weights` (a test side-channel)
  on CPU. On GPU, the real path computes manual attention from
  args[1] (key) and args[4].block_tables (the attention metadata
  from vLLM). This GPU path has never been exercised — that's
  what Day 5b's "bridge composition cell" smokes out.
* **Step 8** flushes only when blocks_flushed > 0 — if the
  aggregator's record path silently no-ops (vLLM 0.7.x's
  `decode_attention_weights` field doesn't exist on the real GPU
  attn_metadata object), forward_block_attention will be called
  zero times and the evictor will see attention_sum=0 (the audit
  status quo). The smoke script's `fba_nonzero` assertion is what
  catches this.

## Day 4 — install verification (small model)

Confirms route-A's `_looks_like_attention` class-name heuristic
matches the real vLLM Attention class on the pinned vLLM version.
Qwen2.5-0.5B-Instruct is enough; we just need any decode step to
fire so `forward_calls` increments.

**Pass:** `int4_route_a_stats.forward_calls > 0` in
`bench_out/PHASE8B_GPU/day4_install_smoke.json`.

**Fail:** the class-name heuristic missed. Inspect
`kv_policy.int4_cache_kv_route_a:_looks_like_attention` — the
vLLM version probably renamed Attention → AttentionImpl or moved
it under a backend namespace. Fix: add a substring match or
a backend-specific case before continuing.

## Day 5a — route-A only

Throughput + quality re-validation of the §20.3 dequant_fallback
cell. Qwen2.5-7B chat_32k, 30 concurrent, 60s wall. Optional
MMLU 200q gated on `RUN_MMLU=1` (extra ~$0.05).

**Compare to:** §19.4 (perplexity 1.024×, MMLU −0.9pt @ 1000q)
and the FP8 baseline cell from `FP8_INT4_THROUGHPUT_RUNBOOK.md`.

## Day 5b — BRIDGE COMPOSITION CELL ⭐ key result

`--ctm-plus --phase3-attention --int4-kv-route-a` together, same
workload as 5a. (Phase 4 trig is mutex-excluded here — this cell
tests the Phase 3 path which is what closes the audit's gap.)
The five assertions in the smoke script collectively prove the bridge:

1. `int4_route_a_stats.forward_calls > 0` — route-A fires
2. `attention_aggregator_stats.samples_recorded > 0` — capture
   wrapper extracts attention from GPU args
3. `attention_aggregator_stats.blocks_flushed > 0` — flush
   reaches the buffer-to-evictor path
4. `ctm_evictor_stats.forward_block_attention_calls > 0` — the
   evictor's API is called
5. `ctm_evictor_stats.forward_block_attention_nonzero_sum_calls
   > 0` — **the attention sum is non-zero**, the audit's gap is closed

If (5) fails but (4) passes, the GPU attention extraction in
`_capture_attention_to_aggregator` returns zeros — probably
because the real vLLM attn_metadata structure has moved between
versions. This is the per-layer recalibration sister-problem and
is fixable but requires GPU iteration.

## Per-layer recalibration (sister-problem to the bridge)

Audit §3 flagged that v5 used pooled-layer calibration (MRL=0.221,
below the method's ≥0.3 bar). Per-layer recalibration landed
POST-findings. The 8a remeasurement MUST run with per-layer
calibration to produce a partner-credible number.

The recalibration is **independent of the bridge** (it's about
the trig signal that feeds `score_block`, not about
forward_block_attention). It's listed in the 8a scaffold's
prerequisite checklist.

## Logging hooks needed for Day 5b's assertions

The smoke script reads:

```
result['int4_route_a_stats']['forward_calls']
result['attention_aggregator_stats']['samples_recorded']
result['attention_aggregator_stats']['blocks_flushed']
result['ctm_evictor_stats']['forward_block_attention_calls']
result['ctm_evictor_stats']['forward_block_attention_nonzero_sum_calls']
```

`int4_route_a_stats` and `attention_aggregator_stats` are
already emitted (runner_vllm_streaming.py:1212-1316).

`ctm_evictor_stats.forward_block_attention_calls` and
`forward_block_attention_nonzero_sum_calls` are **the only new
logging hook** the bridge needs. One counter increment in
`CTMEvictorModern.forward_block_attention` (vllm_evictor.py:874-905)
and one when `attention_sum > 0.0`. Wire as part of Day 5b prep
on the pod — trivial, but DON'T skip; otherwise the smoke
script's assertion fails on the harness, not on the actual bridge.

## Day 5c — preliminary throughput-vs-LRU delta

Quick sanity (~30s wall) to see whether the integration-tax delta
moved. **Used as a preliminary signal only** — the proper 8a
remeasurement (with prefix-caching and matched-budget handling)
comes later.

## When Day 5b is green, what happens next

1. Run per-layer recalibration on Qwen2.5-7B (one-shot, ~$0.05).
   Output: per-layer scales JSON consumed by the evictor.
2. Open `PHASE8A_REMEASUREMENT_SCAFFOLD.md`, set the recalibration
   path, set the prefix-caching policy (disabled or matched-budget),
   and run `phase8a_remeasure.sh`.
3. The 8a result is the partner-shareable number. Only then update
   the VC brief.

## Risks remaining after Day 5b

* **vLLM version drift.** If the pod's vLLM version isn't 0.7.3,
  the install paths (line numbers, attn_metadata field names) may
  not match. The smoke script asserts `vllm.__version__ ==
  '0.7.3'`; the operator must adjust if the pod has 0.7.4+.
* **GQA stride math.** Qwen2.5-7B has num_kv_heads=4 vs
  num_attention_heads=28. The route-A 2-D reshape uses
  num_kv_heads — if that's misdetected, K/V is reshaped with the
  wrong stride and quality silently degrades. Test 5a's MMLU
  catches this; if MMLU drops > 2pt vs the §19.4 baseline,
  inspect `_detect_num_kv_heads` output.
* **Cross-request scale sharing.** Audit open question 4 from
  `ROUTE_A_VLLM_CACHE_KV_PLAN.md`. The dequant_fallback path
  doesn't expose this risk (no persistent scale storage); the
  fused_v2 path does. Day 5 stays on dequant_fallback.

## Bridge work that REMAINS open after Day 5b is green

* **Forward-attention frequency tuning.** The flusher runs at
  `sample_interval_seconds` cadence (~once/sec). For a 60s
  workload that's only ~60 flushes — coarse for an evictor that
  scores ~3000× / 60s. The 8a remeasurement may want a tighter
  cadence; tune after the first 8a number is in.
* **forward_block_attention semantics for prefix caching.** When
  block reuse happens, the same block_id may receive
  forward_block_attention from multiple sequences within one
  flush window. Current behaviour: sums accumulate. Whether that's
  the right semantics for prefix caching is an 8a question, not
  an 8b question.

## File anchors

| Symbol | File:line | Role |
|---|---|---|
| `_wrap_attention_forward_with_kv_rewrite` | `int4_cache_kv_route_a.py:527-590` | Route-A's K/V interception |
| `install_int4_cache_kv_route_a` | `int4_cache_kv_route_a.py:921-1059` | Route-A install entry point |
| `AttentionAggregator` | `vllm_evictor.py:1547-1645` | Phase 3 capture buffer |
| `install_attention_capture` | `vllm_evictor.py:1691-1797` | Phase 3 capture install |
| `_capture_attention_to_aggregator` | `vllm_evictor.py:1844-` | GPU attention extraction |
| `CTMEvictorModern.forward_block_attention` | `vllm_evictor.py:874-905` | Bridge sink (the call the audit's gap was about) |
| `_run_attention_flusher` | `runner_vllm_streaming.py:830-855` | Periodic flush loop |
| `AsyncEngineDriver.__init__` (route-A install) | `runner_vllm_streaming.py:1004-1098` | Where capture + route-A get installed together |
