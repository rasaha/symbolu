# Mode B Streaming Runner — Design Document (Roadmap #3)

**Status:** Phase 1 implemented (May 2026). Phase 2 (CTM+ on
modern vLLM) still gated on partner request or explicit
multi-day authorization.

**Phase 1 deliverables that landed:**

* `ctm_bench/runner_vllm_streaming.py::AsyncEngineDriver.run`
  — full implementation. Builds `AsyncEngineArgs` with
  `preemption_mode="swap"` and `enable_prefix_caching=False`,
  constructs `AsyncLLMEngine`, drives it with timed
  `engine.generate(...)` async iterations from the Pareto
  schedule, and runs a parallel asyncio task for periodic
  swap-counter sampling.
* `_read_swap_counters_from_engine` — reads
  `block_allocator.get_and_reset_swaps()` defensively. Tolerates
  three return formats (dict / 2-tuple / object with attrs)
  observed across vLLM minor versions.
* `ctm_bench/scripts/run_streaming.py` + `scripts/run_streaming.sh`
  — CLI + shell wrapper for per-cell GPU runs. Includes a
  Phase 1 pass criterion in the aggregator (swap_out_blocks > 0
  across cells; warns loudly on zero).
* 11 new unit tests covering: dict/tuple/object swap-counter
  formats, missing-attribute defaults, legacy-v0.6
  `gpu_allocator` path, `preemption_mode="swap"` propagation
  through `_build_engine_args`, scheduler-config-override
  precedence, full mocked run loop, max-wall-seconds capping.
  Total Bench tests: 158 (was 147 + 11 new).

**Phase 1 GPU-validated (May 2026):** RunPod A100 + vLLM 0.7.3
+ Qwen2.5-7B-Instruct produced **swap_out=2205 blocks,
preempt=2 events** on a single-cell smoke. vLLM scheduler log
corroborated the parser. Hyperparameters that engage swap on
this hardware: `GPU_MEM_UTIL=0.26`, `arrival_rate=6/sec`,
`max_decode_tokens=2048`, prompt-length distribution biased to
8K–30K. Full artifact: `bench_out/streaming_smoke_v4_proof.json`.
RESULTS.md §13.2 captures the multi-iteration knob-tuning that
got there (v1 64% KV no swap → v2 vLLM-refused-to-start → v3
98% KV but queue-not-preempt → v4 success).

**Phase 2 implemented (May 2026):** the CTM+ evictor patch for
modern vLLM (0.5+) lives at
`kv_policy.vllm_evictor.patch_vllm_engine_modern` and is
re-exported from `ctm_bench.runner_vllm_streaming`. The
streaming runner wires `ctm_plus_evictor=True` end-to-end
(verified by mocked-vLLM tests; GPU validation pending). See
§1.2 below for what landed and §1.3 for the GPU run procedure.

> ## ⚠ HIGH-severity Phase 2 limitation (audit-pass finding)
>
> **Phase 2 as implemented does NOT run the same policy that
> produced the simulator headlines.** The evictor patch forwards
> `attention_sum=0.0` on every block update because vLLM's
> Evictor ABC doesn't expose attention through `update(block_id,
> last_accessed)`. With `attn ≡ 0`:
>
> * The 0.35·attn term in CTM+'s scoring formula zeroes out (35%
>   of the score gone).
> * Attention-EMA stays at 0 → no block is classified as ENTITY →
>   the 0.30·position term collapses to 0.30·0.1 = 0.03 constant.
> * Effective score = 0.25·recency + 0.10·frequency.
>
> That's roughly **LRU + a frequency tiebreaker**, not the CTM+
> policy that Mode A / KVSimulator / replay measured. The Mode A
> headlines (52% chat-pressure latency cut, −100% RAG slow-tier
> bytes, +192% agentic regression) ALL came from runs where
> `on_block_attention` received non-zero attention_sum.
>
> **What this means for any future Phase 2 GPU run:**
>
> 1. Expected CTM+ vs LRU delta is **small** — possibly within
>    measurement noise. A "Phase 2 finds no significant
>    difference" result would be the expected outcome of this
>    implementation, NOT evidence that CTM+'s policy doesn't
>    work on a real model.
> 2. To produce real CTM+ vs LRU evidence on modern vLLM, we
>    need a Phase 3 that hooks the model's attention output
>    path and forwards block-level attention sums to the
>    evictor. ~3-4 days of vLLM-internals + model-runner work,
>    materially more invasive than Phase 2.
> 3. The legacy vLLM 0.4 patch has the same limitation — the
>    pre-Round-4 0.4 code in `vllm_evictor.py:128-150` also
>    accepts `attention_sum` with default 0.0 and was not
>    actually wiring real attention. So **no CTM+ vLLM
>    integration we have ever shipped, on any vLLM version,
>    actually runs the simulator's policy** — including the
>    May 2026 patch-install proof on RunPod (commit `6081148`).
>    That proof showed the *integration* works; it did not
>    show that the *policy* runs end-to-end with real attention.
>
> **Honest framing for partner conversations:** simulator
> evidence remains the strongest support for the CTM+ headlines.
> Real-vLLM patch installs cleanly (verified) but doesn't
> exercise the attention-aware part of the policy. Phase 3
> (attention forwarding) is the path to producing real-model
> evidence of CTM+'s actual scoring math; it is not yet
> scoped or implemented.
>
> Phase 2 still has value — it validates the integration
> mechanism on modern vLLM and produces a clean baseline ("does
> the recency+frequency component of CTM+ alone differ from
> LRU?") — but it must not be cited as "real-model CTM+ vs LRU
> evidence." That label belongs to Phase 3.

## §1.2 Phase 2 implementation (May 2026)

What landed in `kv_policy/vllm_evictor.py`:

* **`CTMEvictorModern`** — vLLM 0.7+ Evictor ABC implementation.
  Adapts the ABC's six methods (`__contains__`, `add`, `update`,
  `remove`, `evict`, `num_blocks`) to a `KVCachePolicy` instance.
  Block-content hashes are tracked in a side dict so `evict()`
  returns the right `(block_id, content_hash)` pair. The
  KVCachePolicy uses `attention_ema_alpha=0.2` (Round 4
  production default), NOT CTMvLLMConfig's pre-Round-4 0.1.
* **`patch_vllm_engine_modern(engine)`** — walks
  `engine.engine.scheduler[0].block_manager.block_allocator
  ._allocators[GPU_DEVICE].evictor` and replaces with
  `CTMEvictorModern`. Tolerates async engines (peels `.engine`
  if needed). Raises `NotImplementedError` if the GPU allocator
  is `NaiveBlockAllocator` (i.e., `enable_prefix_caching=False`)
  with a message naming the fix; raises `RuntimeError` if the
  allocator path can't be walked (vLLM minor-version
  incompatibility).

What landed in `ctm_bench/runner_vllm_streaming.py`:

* **Phase-dependent `enable_prefix_caching`** in
  `_build_engine_args`: `False` for Phase 1 (LRU + swap path),
  `True` for Phase 2 (CTM+ + cache retention). Both phases
  keep `preemption_mode="swap"` so swap counters always
  accumulate.
* **`run()` calls `patch_vllm_engine_modern`** after engine
  construction when `ctm_plus_evictor=True`. Patch failure
  surfaces as a clear exception, not a silent no-op.

What did NOT land (honest scope):

* **Attention forwarding** (option (a) from §4.4). CTM+ scores
  on position + recency + frequency only; the 0.35 attention
  weight is effectively zero through this path. This is what
  the legacy vLLM 0.4 patch did too (the `update()` API didn't
  forward attention either) — see `vllm_evictor.py:128-150` —
  so Phase 2 matches the legacy behaviour.
* **Sink protection** is degraded. We can't tell from vLLM's
  evictor API which block holds positions 0-3 (the conventional
  sink). Synthetic position offsets in `add()` deliberately
  start at `sink_tokens` so CTM+ doesn't auto-pin every block;
  the trade-off is no real sink protection. Acceptable starter;
  worth revisiting if the GPU validation surfaces sink-eviction
  regressions.
* **GPU validation.** The CPU sandbox proves the API contract
  via mocks (8 new Phase-2 tests covering Evictor ABC
  conformance, allocator walker, prefix-caching gate,
  legacy-path rejection, re-export). The actual question
  "does CTM+ vs LRU produce different cache-retention
  outcomes on real attention" needs a GPU.

### Tests added (8 new, total 171)

* `test_ctm_evictor_modern_implements_vllm_07_evictor_abc`
* `test_ctm_evictor_modern_evict_raises_on_empty_cache`
* `test_ctm_evictor_modern_update_before_add_is_silent`
* `test_ctm_evictor_modern_remove_untracked_is_silent`
* `test_patch_vllm_engine_modern_walks_to_prefix_caching_allocator`
* `test_patch_vllm_engine_modern_raises_when_prefix_caching_off`
* `test_patch_vllm_engine_modern_handles_legacy_v06_path`
* `test_patch_vllm_engine_modern_re_exports_from_kv_policy`
* (replaces the old `test_async_engine_driver_run_phase2_raises_not_implemented`
  with `test_async_engine_driver_phase2_enables_prefix_caching`)

## §1.2.1 Phase 2 audit-pass — fixes (May 2026)

An independent audit of the Phase 2 implementation surfaced one
HIGH and three MEDIUM findings. The HIGH finding is documented
in the §1.1 callout above (no attention forwarding → CTM+ runs
as recency+frequency only). The three MEDIUM fixes shipped:

* **Engine leak on patch failure (MEDIUM #2 fix).** If
  `patch_vllm_engine_modern` raises mid-`run()` (e.g.
  `NotImplementedError` from prefix caching being off, or
  `RuntimeError` from allocator drift), the engine is now torn
  down via `shutdown_background_loop` / `shutdown` / `stop`
  before the exception propagates. Multi-cell sweeps no longer
  leak GPU memory across cells when the patch fails.
* **LRU + prefix caching baseline (MEDIUM #3 fix).**
  `enable_prefix_caching` is now an independent constructor
  arg on `AsyncEngineDriver` (and `--enable-prefix-caching`
  on the CLI). Default behaviour preserved (True iff
  `ctm_plus_evictor=True`). Partners can now run an
  apples-to-apples LRU baseline cell with prefix caching ON
  for direct comparison against a Phase 2 CTM+ cell — both
  cells decide cache retention; only the policy differs.
  Constructor explicitly rejects the impossible combination
  `ctm_plus_evictor=True + enable_prefix_caching=False`.
* **Dead modulo math (MEDIUM #4 fix).** `CTMEvictorModern.add`
  was computing `num_hashed_tokens % block_size or block_size`
  to handle a hypothetical partial-block case that vLLM's
  prefix cache never produces (partial blocks have unstable
  hashes and aren't cached). Replaced with a constant
  `block_size`.

Tests added (3 new, total 174):

* `test_async_engine_driver_phase2_patch_failure_tears_down_engine`
  — verifies the teardown chain fires when the patch raises.
* `test_async_engine_driver_explicit_prefix_caching_for_lru_baseline`
  — pins the LRU + prefix caching path for the apples-to-apples
  baseline.
* `test_async_engine_driver_rejects_ctm_plus_without_prefix_caching`
  — pins the constructor's explicit rejection of the impossible
  combination.

## §1.4 Phase 3 — attention forwarding (real attention into CTM+)

The Phase 2 audit surfaced that vLLM's Evictor ABC carries zero
attention through `update(block_id, last_accessed)`, so CTM+'s
0.35·attn term zeroes out and the policy collapses to ~LRU.
Phase 3 plumbs real attention through a separate channel.

**Three components landed in `kv_policy.vllm_evictor`:**

1. **`CTMEvictorModern.forward_block_attention(block_id,
   attention_sum)`** — out-of-band API on the evictor. Pushes
   real attention magnitude into the policy's
   `on_block_attention(...)`, separate from the Evictor ABC's
   `update()`.
2. **`AttentionAggregator`** — pure-Python state machine that
   buffers per-block attention across layers within a decode
   step, then flushes cumulative sums to the evictor on a
   controlled cadence (matches the swap-counter sampler interval).
3. **`install_attention_capture(model, aggregator, evictor)`**
   — walks the model's modules, identifies vLLM Attention layers
   by class name (`Attention` / `PagedAttention`) or duck-typing
   (`head_size` + `num_heads`), monkey-patches each layer's
   `forward` to also call the capture function. Returns the
   number of layers patched; logs a warning + returns 0 if no
   attention modules found.

Plus a pure helper:

* **`aggregate_attention_to_blocks(weights, block_table, block_size)`**
  — given a per-key attention vector + the sequence's block_table,
  returns `{block_id: attention_sum}`. Tested with synthetic
  tensors; this is the math the GPU-side capture path will
  use after the real Q@K computation.

**Streaming runner wiring:**

* `AsyncEngineDriver(phase3_attention_capture=True)` and
  `--phase3-attention` CLI flag.
* Constructor rejects `phase3_attention_capture=True` without
  `ctm_plus_evictor=True` (no evictor → nowhere to push
  attention).
* `run()` extracts the model from the engine via a
  multi-path walker (vLLM 0.5+ has the path
  `model_executor → driver_worker → worker → model_runner →
  model`; older paths tried as fallbacks), installs the
  capture hooks, and starts a parallel asyncio task that
  flushes the aggregator to the evictor on the same cadence
  as the swap-counter sampler.
* Engine teardown on patch failure preserved (audit-pass
  MEDIUM #2 fix); attention-flusher task cancellation in the
  same `finally` block.

### §1.4.1 What the GPU-side capture actually does

Per decode step, for each Attention layer:

1. Original `forward(query, key, value, kv_cache, attn_metadata)`
   runs unchanged → output correctness preserved.
2. Wrapper extracts the new query token's Q, identifies the
   sequence's block_table from `attn_metadata`, computes
   `softmax(Q @ K^T / √d_k)` against the cached keys.
3. `aggregate_attention_to_blocks` groups per-key weights into
   per-block sums.
4. `aggregator.record_block_batch({block_id: sum})`.

After all layers fire in a decode step, the parallel flusher
delivers cumulative per-block sums to
`CTMEvictorModern.forward_block_attention`, which forwards to
`KVCachePolicy.on_block_attention(attention_sum=...)`. CTM+'s
EMA + ENTITY classification + the 0.35·attn term ALL come
alive — the policy that produced the simulator headlines now
runs end-to-end.

### §1.4.2 Honest scope of what landed in this session

**CPU-tested (✓):**

* `aggregate_attention_to_blocks` math — synthetic vectors,
  partial-last-block edge case, input validation.
* `AttentionAggregator` — record / record_batch / flush /
  empty-flush / stale-evictor-error tolerance.
* `CTMEvictorModern.forward_block_attention` — non-zero
  attention demonstrably changes a block's score; untracked
  block_id is a silent no-op.
* `install_attention_capture` — finds Attention modules by
  class name, returns 0 cleanly on a model with none, fires
  the side-channel test path through the wrapped forward.
* Streaming runner constructor/argparse — `phase3_attention_capture`
  validation, `_extract_model_from_engine` multi-path walker,
  flusher task lifecycle.

**Deferred to GPU validation (✗):**

* The actual Q@K computation inside the wrapped forward. The
  current implementation has a `NotImplementedError` on the
  real-extraction branch — only the test side-channel
  (`decode_attention_weights` attribute pre-computed) flows
  through CPU-side. Real-vLLM-tensor extraction is the next
  GPU-day's work; once written, it'll exercise the same
  aggregator + evictor APIs that CPU tests already pin.

This is the same staging discipline Phase 1 used: ship the
CPU-testable scaffolding + integration plumbing first, mark
the GPU-only branch with `NotImplementedError`, validate on
real silicon when GPU access is available.

### §1.4.3 Tests added (15 new, total 189)

* `test_aggregate_attention_to_blocks_basic`
* `test_aggregate_attention_to_blocks_partial_last_block`
* `test_aggregate_attention_to_blocks_rejects_too_many_weights`
* `test_aggregate_attention_to_blocks_rejects_bad_block_size`
* `test_attention_aggregator_buffer_and_flush`
* `test_attention_aggregator_record_block_batch`
* `test_attention_aggregator_flush_empty_returns_zero`
* `test_attention_aggregator_tolerates_evictor_errors`
* `test_ctm_evictor_modern_forward_block_attention_changes_score`
* `test_ctm_evictor_modern_forward_block_attention_silent_on_untracked`
* `test_install_attention_capture_finds_attention_modules`
* `test_install_attention_capture_returns_zero_on_empty_model`
* `test_async_engine_driver_phase3_requires_phase2`
* `test_async_engine_driver_phase3_constructor_stores_flag`
* `test_extract_model_from_engine_walks_documented_paths`

### §1.4.4 Phase 3 GPU run (next session)

```bash
cd /workspace/symbolu/CTM_plus/Bench
python3 -m ctm_bench.scripts.run_streaming \
    --model /workspace/.hf_cache/qwen2.5-7b \
    --workload chat_32k --seed 42 \
    --gpu-memory-utilization 0.26 --swap-space-gb 16 \
    --arrival-rate 6.0 --arrival-alpha 1.5 \
    --max-requests 30 --max-wall-seconds 120 \
    --max-decode-tokens 2048 \
    --prompt-length-choices "8000,16000,24000,30000" \
    --ctm-plus --phase3-attention \
    --output-dir bench_out/streaming_phase3_smoke
```

Expected log signals if the install succeeds:

* `Phase 2: CTM+ evictor patch installed on AsyncLLMEngine`
* `Phase 3: attention capture installed on N Attention layers`
  (N should equal the model's transformer-layer count — 32 for
  Qwen 7B).
* During run: `swap_out` and `preempt` accumulate (Phase 1's
  swap path stays active under the same `preemption_mode=swap`
  config).

If `Phase 3: attention capture installed on 0 Attention layers`
fires: the model-walker can't see vLLM's attention modules.
Diagnose with:

```python
inner = engine.engine
for name, module in inner.model_executor.driver_worker.worker.model_runner.model.named_modules():
    if "ttn" in type(module).__name__.lower():
        print(name, type(module).__name__)
```

The actual Q@K-from-kv_cache extraction in
`_capture_attention_to_aggregator` is currently a
`NotImplementedError` — a Phase 3 GPU run will hit that on the
first decode step. The next session's work is filling in that
extraction against vLLM 0.7's specific kv_cache layout.

The three-cell experiment partners want to see (LRU baseline /
Phase 2 ablation / Phase 3 full CTM+) is achievable on the
same RunPod session in one ~$1 sweep once the GPU-side
extraction lands.

## §1.3 Phase 2 GPU run procedure

When ready for GPU validation, the smoke command is the same as
Phase 1 with `--ctm-plus` added (and the prompt-length /
hyperparameter regime that worked for Phase 1 v4):

```bash
cd /workspace/symbolu/CTM_plus/Bench
python3 -m ctm_bench.scripts.run_streaming \
    --model /workspace/.hf_cache/qwen2.5-7b \
    --workload chat_32k \
    --seed 42 \
    --gpu-memory-utilization 0.26 \
    --swap-space-gb 16 \
    --arrival-rate 6.0 \
    --arrival-alpha 1.5 \
    --max-requests 30 \
    --max-wall-seconds 120 \
    --max-decode-tokens 2048 \
    --prompt-length-choices "8000,16000,24000,30000" \
    --ctm-plus \
    --output-dir bench_out/streaming_phase2_smoke \
    2>&1 | tee mode_b_phase2_smoke.log
```

Watch for in the log:

1. vLLM engine init line should include `enable_prefix_caching=True`
   (vs Phase 1's `False`).
2. After engine init, the line:
   `Phase 2: CTM+ evictor patch installed on AsyncLLMEngine`
   (from runner_vllm_streaming logger) — confirms the patch fired.
3. During the run: `swap_out` and `preempt` should still
   accumulate (preemption_mode=swap is on). Cache hit/miss
   counters from prefix caching are visible in vLLM's metrics
   line as `GPU prefix cache hit rate`.
4. The Phase 2 vs LRU difference manifests in **which blocks
   get evicted from the cache** when full. To compare
   apples-to-apples, run two cells with the same workload +
   seed — one `--ctm-plus`, one with `--enable-prefix-caching`
   (the LRU baseline; audit-pass MEDIUM #3 fix). Both cells use
   `PrefixCachingBlockAllocator`; only the evictor differs.
   Without `--enable-prefix-caching` on the LRU cell, the
   comparison is across two scheduler regimes, NOT policies.

If the patch fails to install:

* `NotImplementedError: ... requires enable_prefix_caching=True`
  → the runner is not propagating the flag. Verify
  `--ctm-plus` is set; check `_build_engine_args` output.
* `RuntimeError: Cannot find _allocators dict` → vLLM minor
  version's allocator layout differs from 0.7.3. Inspect with
  `python3 -c "import vllm; print(vllm.__version__)"` and
  `pip show vllm` to confirm the install. Run the allocator
  probe from MODE_B_VLLM04_RUNBOOK.md §1.2 (adapted for
  modern vLLM) to inspect the actual structure.

The single-cell smoke proves the *mechanism*. Multi-cell sweep
gated on partner request.

## §1.1 Audit pass — findings + fixes (May 2026)

An independent critical-audit pass on the Phase 1 implementation
surfaced four findings. Two were **HIGH severity** — would have
silently invalidated every cell on a real GPU run by reporting
all-zero swap counters regardless of whether the swap path
engaged. All four are fixed in this commit.

### HIGH

* **Wrong parser for `block_allocator.get_and_reset_swaps()`
  return format.** vLLM 0.7's `CpuGpuBlockAllocator` returns a
  list of `(src_block_id, dst_block_id)` tuples — verified
  against `runner_vllm.py:_extract_vllm_tier_counters` and its
  pinned tests. My initial parser only handled dict / 2-tuple /
  attr-object formats; the list-of-tuples branch crashed at
  `int(swaps[0])` (treating a tuple as an int) and silently
  fell through to swap_out=0. Fix: distinguish list-of-tuples
  from list-of-ints by checking `swaps[0]` type; report
  `len(swaps)` as `swap_out_blocks` (matches the existing
  batch runner's "all swaps → DDR" convention).
* **Wrong attribute names for preemption counter.** I checked
  `num_preemption_events` and `num_cumulative_preemptions`.
  vLLM 0.7's actual attribute is `num_cumulative_preemption`
  (singular). My code never matched → `preemption_events=0`
  always. Fix: check `num_cumulative_preemption` first, then
  the alternate plural variants for forward compatibility.

### MEDIUM

* **Workload-name → prompt-length-distribution mapping
  missing.** The shell driver passed the same default
  `prompt_length_choices=256,512,1024,2048` for every workload.
  `chat_32k`, `rag_128k`, and `agentic_clustered_64k` would
  have run **identical workloads** with only a label
  difference. Fix: `prompt_lengths_for_workload()` bash
  function in `run_streaming.sh` maps each canonical workload
  to a length distribution that roughly matches its Mode A
  characteristics (chat: bimodal short + long; rag: long
  retrieval; agentic: sustained long-context).
* **No explicit engine teardown.** `AsyncLLMEngine` worker
  subprocess wasn't shut down between cells. Single-cell run
  fine; multi-cell sweep (which is what `run_streaming.sh`
  does) could leak GPU memory across cells. Fix: best-effort
  call to `engine.shutdown_background_loop()` (vLLM 0.7's
  primary teardown) → `engine.shutdown()` → `engine.stop()`
  fallback chain in the run loop's `finally` block. Awaits
  if the teardown method returns a coroutine.

### Tests added for the fixes

* `test_read_swap_counters_handles_vllm_07_list_of_tuples`
  — pins the actual format `[(1, 100), (2, 101), (3, 102)]`
  → `swap_out_blocks == 3`, mirrors the batch runner's
  `test_extract_vllm_tier_counters_uses_block_allocator_swaps`.
* `test_read_swap_counters_empty_list_means_zero` — pins the
  Phase 1 pass criterion's "no-swap-engaged" signal: empty
  list → `(0, 0, 0)`, no crash.
* `test_read_swap_counters_finds_preemption_via_alternate_attrs`
  — parametrised over `num_cumulative_preemption` (vLLM 0.7
  actual), `num_cumulative_preemptions` (plural), and
  `num_preemption_events` (alternate).
* `test_async_engine_driver_run_calls_engine_teardown` +
  `test_async_engine_driver_run_teardown_falls_back_to_shutdown`
  — verify the teardown chain calls the right method,
  including the async-coroutine path.

Total streaming-runner tests: 34 (was 29 + 5 audit-pass new).
Total Bench tests: 163 (was 158 + 5).

### Diagnostic value of the fixes

The HIGH fixes change Phase 1's behaviour on a real GPU from
"always reports zero swaps regardless of what happened" to
"reports actual swap activity if the path engages, zero if it
doesn't." Without these fixes, the Phase 1 pass criterion
(`swap_out_blocks > 0`) would have always failed silently —
producing a misleading "the swap path doesn't engage" finding
when the real story would have been "the parser is broken."

**Audience:** the engineer (possibly future-me) who will write
the code. Conservative framing throughout: every design choice
is justified against a known concrete problem from the May 2026
GPU run, not against a hypothetical concern.

## §1 What this rewrite must address

Two independent problems surfaced by the May 2026 Mode B GPU
run on vLLM 0.7 (see `MODE_B_RUNBOOK.md` §9):

**Problem A: CTM+ cannot install into modern vLLM.** vLLM 0.5+
replaced `BlockSpaceManagerV1`'s public `Evictor` ABC with
`SelfAttnBlockSpaceManager` + a private
`CpuGpuBlockAllocator._allocators` dict. The existing CTM+
patch (`KVPolicy/kv_policy/vllm_evictor.py:patch_vllm_engine`)
correctly fails fast with `NotImplementedError` on this version.
No CTM+ vs LRU comparison on modern vLLM exists today.

**Problem B: batch-mode FCFS execution does not trigger
swap/preemption.** Even with LRU, the existing runner uses
`LLM(...).generate(prompts=[...])`. The default FCFS scheduler
either admits a prompt or queues it; it never preempts running
sequences. `swap_space` engages only on preemption events, so
`block_allocator.get_and_reset_swaps()` returned zero across
every Mode B cell — counter source `vllm_0_7_no_swaps_observed`.

These problems are orthogonal and can be solved separately:

* Solving A alone → CTM+ runs on modern vLLM, but swap path
  still doesn't engage.
* Solving B alone → swap path engages for LRU, but CTM+ still
  can't be installed.
* Solving both → the validation we want.

The design below addresses both, with B as a milestone
deliverable that's independently useful (validates the swap
counters work + Mode A's tier model on real attention with LRU)
even before A lands.

## §2 Non-goals

* **No vLLM PR.** Submitting an upstream `EvictorPolicy` ABC PR
  to vLLM is the cleanest long-term outcome but would take
  months to land. Out of scope for this rewrite.
* **No multi-GPU / tensor-parallel support.** Single-GPU is
  sufficient for the validation question; TP introduces
  allocator-distribution complications that aren't on the
  critical path.
* **No production-deployable code.** This runner is a
  validation harness, not a serving stack. We do not need to
  match vLLM's production-grade error recovery, OpenAI-compatible
  API, etc. It needs to be reproducible and instrumented; it
  does not need to be a fork.

## §3 Architecture overview

```
┌─────────────────────────────────────────────────────────────┐
│ ctm_bench.runner_vllm_streaming                             │
│                                                              │
│  ┌──────────────────┐    ┌──────────────────────────────┐   │
│  │ ArrivalScheduler │───▶│ AsyncEngineDriver            │   │
│  │ (Pareto / replay)│    │ (vllm.AsyncLLMEngine wrapper)│   │
│  └──────────────────┘    └────────────┬─────────────────┘   │
│                                       │                      │
│  ┌────────────────────────────────────▼─────────────────┐   │
│  │ vllm AsyncLLMEngine                                   │   │
│  │ (configured: preemption_mode=swap, scheduler=...)     │   │
│  │                                                        │   │
│  │  ┌──────────────────────────────────────┐             │   │
│  │  │ SelfAttnBlockSpaceManager            │             │   │
│  │  │  ┌──────────────────────────────┐    │             │   │
│  │  │  │ CpuGpuBlockAllocator         │    │             │   │
│  │  │  │  _allocators[Device.GPU]: ◀──┼────┼── PATCHED   │   │
│  │  │  │   CTMAwarePrefixCachingAllocator   │             │   │
│  │  │  └──────────────────────────────┘    │             │   │
│  │  └──────────────────────────────────────┘             │   │
│  └────────────────────────────────────┬──────────────────┘   │
│                                        │                      │
│  ┌────────────────────────────────────▼─────────────────┐   │
│  │ SwapCounterSampler                                    │   │
│  │ (polls block_allocator.get_and_reset_swaps periodic-  │   │
│  │  ally, accumulates per-(workload, policy, seed) cell) │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

Three new runtime components, one allocator patch:

| Component | Purpose | Solves |
|---|---|---|
| `ArrivalScheduler` | Generates request arrivals with Pareto / empirical inter-arrival shapes | B (creates real preemption pressure) |
| `AsyncEngineDriver` | Wraps `AsyncLLMEngine` with `add_request` + scheduler config | B (uses async API instead of batch) |
| `SwapCounterSampler` | Periodic polling of swap counters during the run | B (captures preemption events as they happen) |
| `CTMAwarePrefixCachingAllocator` | Subclass of `CpuGpuBlockAllocator`'s GPU allocator that intercepts eviction decisions and routes them through CTM+ | A (makes CTM+ work on modern vLLM) |

## §4 Component specifications

### §4.1 `ArrivalScheduler`

```python
class ArrivalScheduler:
    """Generates per-step arrival decisions for the streaming runner.

    Two modes:
      * "pareto":   Pareto-gap inter-arrival with shape alpha.
                    Produces heavy-tailed bursts that match
                    BurstGPT-shape production traces.
      * "replay":   Reads (timestamp, prompt_length) tuples from
                    a CSV file; replays them in real-time at
                    the file's logical pace.

    Determinism: per-seed (mode "pareto") or per-CSV (mode
    "replay"). The same seed + same CSV must produce the same
    schedule in test and in production.
    """

    def __init__(
        self,
        mode: Literal["pareto", "replay"],
        seed: int,
        # Pareto-mode params:
        base_rate_per_sec: Optional[float] = None,
        alpha: Optional[float] = None,
        # Replay-mode param:
        csv_path: Optional[Path] = None,
    ): ...

    def next_arrival_delay_seconds(self) -> float: ...
    def next_prompt_length(self) -> int: ...  # may sample from a distribution
```

**Tests required:**

* Determinism per seed (pareto mode)
* Bursty-distribution property: max gap > uniform-Bernoulli max gap
* Replay-mode round-trips a CSV exactly
* Mode validation rejects mixing pareto-only + replay-only kwargs

### §4.2 `AsyncEngineDriver`

```python
class AsyncEngineDriver:
    """Drives an AsyncLLMEngine with timed `add_request` calls.

    Critical config the constructor MUST set:
      * `preemption_mode="swap"` on the scheduler config so
        swap_space actually engages on preemption events.
      * `swap_space=NN` (default 8 GB; configurable for
        --heavy-spillover analog).
      * `enforce_eager=True` so kernel-launch overhead doesn't
        skew per-token timing measurements.

    The driver's run loop:
      1. Loop over scheduled arrivals from ArrivalScheduler.
      2. For each arrival, call `engine.add_request(...)` with
         a unique request_id.
      3. Sleep for the inter-arrival delay.
      4. Concurrently, periodically pump engine.step() and
         drain finished outputs.
      5. SwapCounterSampler runs on a separate task,
         independently sampling counter deltas.
    """

    def __init__(
        self,
        model: str,
        gpu_memory_utilization: float,
        swap_space_gb: int,
        seed: int,
        scheduler_config_overrides: Optional[Dict[str, Any]] = None,
    ): ...

    async def run(
        self,
        scheduler: ArrivalScheduler,
        sampler: SwapCounterSampler,
        max_requests: int,
        max_wall_seconds: float,
    ) -> RunResult: ...
```

**Open questions for implementation:**

* AsyncLLMEngine vs LLMEngine + manual step loop. AsyncLLMEngine
  is simpler but its public API may not expose `engine.step()`
  callable from external code. Verify before committing.
* `preemption_mode="swap"` may need to be set via
  `EngineArgs(...)` rather than mutated post-construction.
* On vLLM 0.7+ the scheduler config layout has changed at least
  twice. Pin a specific minor version (0.7.2 or 0.7.3) for the
  initial implementation; widen the band only after the patch
  passes tests.

### §4.3 `SwapCounterSampler`

```python
class SwapCounterSampler:
    """Polls `block_allocator.get_and_reset_swaps()` periodically
    and accumulates per-cell totals.

    Why periodic vs end-of-run sampling:
      get_and_reset_swaps() resets the counter, so a single
      end-of-run call captures only the LAST window's swap
      events (whatever happened since the previous reset
      somewhere inside vLLM, which may be unpredictable).
      Periodic sampling at a known interval gives us a
      reliable sum.

    The sampler runs as an asyncio task in parallel with the
    AsyncEngineDriver run loop.
    """

    def __init__(
        self,
        engine: Any,  # AsyncLLMEngine
        sample_interval_seconds: float = 0.1,
    ): ...

    async def run_until_stopped(self) -> None: ...
    def stop(self) -> None: ...
    def totals(self) -> Dict[str, int]:
        """Cumulative swap_in / swap_out / blocks_swapped across
        the entire run."""
```

**Tests required:**

* Counter accumulation is correct across resets
* Sampler stops cleanly on stop() call
* Sampler tolerates the engine being torn down during a sample

### §4.4 `CTMAwarePrefixCachingAllocator`

This is the most invasive component and the riskiest part of
the rewrite. The plan:

1. **Identify the actual eviction decision point** in vLLM 0.7's
   `CpuGpuBlockAllocator`. Read the source for
   `allocate_or_get_cached_block`, `free`, and the eviction path
   the prefix cache uses. The decision typically lives inside the
   `Evictor` class on the GPU allocator (vLLM's own LRU evictor)
   — what we want is a parallel implementation that scores
   blocks via CTM+ instead.

2. **Subclass the GPU allocator's evictor** rather than the whole
   block allocator. vLLM 0.7's allocator factory uses an
   `evictor` argument; if it's exposed (even via private name),
   we substitute it. If not, we monkey-patch the allocator class
   on the engine after construction.

3. **Forward block-attention updates** from vLLM's hidden state
   into CTM+'s scoring math. CTM+ needs `on_block_attention(
   block_id, attention_sum, ...)` calls. vLLM does not natively
   emit these; we'd need to instrument the attention output
   path. Two options:
   - (a) Hook into the model's forward pass via a forward-hook
     mechanism. Heavy and may interact with CUDA graph capture.
   - (b) Skip the attention signal entirely; have CTM+ score
     using only position + recency + frequency (omit the 0.35
     attention weight). Loses some of CTM+'s edge but eliminates
     the most invasive integration.

   **Recommended:** start with (b) for the initial implementation;
   add (a) as a follow-up if (b) underperforms.

4. **Test against vLLM's own LRU baseline** to confirm the
   eviction decisions actually flow through the patched evictor
   (not silently bypassed by some internal fast path).

**Risks:**

* vLLM may re-architect the allocator again in 0.8+. We need to
  test against multiple minor versions and document the
  compatibility matrix.
* Prefix caching interacts with eviction in non-obvious ways.
  CTM+ may need to be aware of which blocks are part of a
  prefix-cache shared subtree to avoid evicting them and
  invalidating the cache for many sequences.
* `enforce_eager=True` is fine for benchmarking but a real
  partner stack may want CUDA graph capture, which is sensitive
  to allocator behaviour.

## §5 Phased delivery plan

Gated on partner request OR explicit user authorization for
multi-day work.

### Phase 1 — B-only validation (1–1.5 days)

* Implement `ArrivalScheduler` (Pareto mode), `AsyncEngineDriver`,
  `SwapCounterSampler`.
* Run LRU-only on chat / RAG / agentic_clustered.
* Validate that swap counters now go above zero.
* Cross-check the resulting tier-model calibration against Mode A.
* Write up as RESULTS.md §13 (Mode B real-swap validation, LRU
  baseline).

**Phase-1 deliverable signature:** the swap path engages, swap
counters > 0, and the LRU tier-cost numbers match Mode A's LRU
predictions within a documented calibration band. If they
disagree, that's a real finding to surface.

**Phase-1 cost:** 1–1.5 days code + ~1 GPU-day for sweeps.

### Phase 2 — A integration (1.5–2 days, after Phase 1 succeeds)

* Implement `CTMAwarePrefixCachingAllocator` (option (b) — score
  without attention initially).
* Run CTM+ vs LRU head-to-head on the four canonical workloads
  through the streaming runner.
* If CTM+ underperforms LRU on workloads where Mode A predicts
  CTM+ should win (RAG especially), revisit option (a) — wire
  attention through the allocator.
* Write up as RESULTS.md §14 (real-model CTM+ vs LRU on
  modern vLLM).

**Phase-2 deliverable signature:** CTM+ vs LRU comparison on a
modern vLLM serving stack with real attention pressure. The
result may go either way; the conservative framing carries
through — we report what we measure.

**Phase-2 cost:** 1.5–2 days code + ~1 GPU-day for sweeps + per-
vLLM-version regression maintenance ongoing.

## §6 What this design does and does not commit to

**Does commit:**

* The streaming runner is a separate module
  (`runner_vllm_streaming.py`); the existing `runner_vllm.py`
  remains the canonical batch-mode runner for vLLM 0.4 and for
  cases where preemption pressure is not needed.
* Phase 1 ships before Phase 2; the LRU swap-counter validation
  is an independently useful artifact.
* Tests cover the contract before any vLLM-specific code is
  written — pure-Python ArrivalScheduler / SwapCounterSampler
  state can be tested without a GPU.
* Honest reporting of disagreements between Mode A predictions
  and Mode B measurements; no papering over.

**Does not commit:**

* That the rewrite will succeed in producing CTM+ wins. Phase 2
  may surface that CTM+'s scoring math, when run on real
  attention through real vLLM eviction events, doesn't
  reproduce the simulator's predictions. That would be a
  meaningful finding on its own.
* That the rewrite will be portable across vLLM 0.7, 0.8, 0.9
  without per-version maintenance. The whole reason Problem A
  exists is that vLLM has re-architected the allocator twice
  already; the maintenance cost is real.
* That this rewrite is the right thing for partners to deploy
  in production. It is a *validation harness* — measuring CTM+
  through it tells us whether the policy works; it is not a
  productionized integration that partners would ship.

## §7 Decision log + open questions

Decisions made:
- Phase 1 (B alone) before Phase 2 (B + A) — independently
  useful artifact, lower risk.
- Subclass the evictor, not the whole allocator, for minimum
  patch surface.
- Start without attention forwarding; add only if needed.
- Pin a specific vLLM minor version initially; widen later.

Open questions (require code-reading or experimentation to
resolve):
- Does vLLM 0.7's `AsyncLLMEngine` expose `engine.step()` for
  external pumping, or is the run loop required to be internal?
- What's the minimum-invasiveness way to set
  `preemption_mode="swap"` — `EngineArgs` constructor arg, env
  var, scheduler config override?
- Does the GPU allocator's evictor field have a stable name
  across 0.7.x patch releases? Verify on 0.7.2 and 0.7.3.
- Prefix caching + custom evictor: does vLLM short-circuit
  eviction for blocks in shared prefix subtrees? If so, we'd
  need to detect that to avoid CTM+ being silently bypassed.

These open questions belong in the implementation prompt for
the next session; the design is fixed enough to start coding
once partner authorization arrives.
