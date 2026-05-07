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
4. The Phase 2 vs Phase 1 difference manifests in **which
   blocks get evicted from the cache** when full. To compare
   against LRU, run two cells with the same workload + seed —
   one with `--ctm-plus`, one without — and compare swap
   counters and cache hit rates.

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
