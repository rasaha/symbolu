# V2 Cache-Reuse — Phase 1 Integration Note

> **Status:** Reconnaissance only. No code in this commit. This doc
> identifies the vLLM 0.7.3 surfaces the Phase 1 patch will touch
> and defines the acceptance criteria the patch must satisfy.
>
> **Phase 0 (CPU prototype + tests):** ✅ committed at `3168e94`.
> **Phase 1 (vLLM integration):** scoped below — implementation NOT
> in this commit.

## 1. vLLM 0.7.3 admission flow — files and functions

The path from user `llm.generate(...)` to actual admission:

```
LLM.generate(prompts, ...)                        # vllm/entrypoints/llm.py
  └─ LLMEngine.add_request(request_id, prompt)    # vllm/engine/llm_engine.py
       └─ self.scheduler.add_seq_group(seq_group) # appends to scheduler.waiting

[per engine step]
LLMEngine.step()
  └─ self.scheduler.schedule()                    # vllm/core/scheduler.py
       ├─ _schedule_running()                     # already-active sequences
       ├─ _schedule_prefills()                    # consumes self.waiting in order
       │    └─ self.block_manager.can_allocate(seq_group)
       │    └─ self.block_manager.allocate(seq_group)
       │         └─ PrefixCachingBlockAllocator.allocate(...)
       │              └─ _block_for_token_ids(content_hash, ...)
       │                   └─ HIT path: reuses cached block; or
       │                   └─ MISS path: allocates new block
       └─ _schedule_swapped()                     # preempted sequences
```

Key types:

| Symbol | Location | Role |
|---|---|---|
| `Scheduler` | `vllm/core/scheduler.py` | Picks runnable sequences per step |
| `Scheduler.waiting` | same | `Deque[SequenceGroup]` — FCFS admission queue |
| `Scheduler.running` | same | currently-active sequences |
| `Scheduler.swapped` | same | preempted-to-CPU sequences |
| `BlockSpaceManagerV1` / `V2` | `vllm/core/block_manager_*.py` | block lifecycle owner |
| `PrefixCachingBlockAllocator` | `vllm/core/block/prefix_caching_block.py` | content-hash → block index for prefix reuse |
| `SequenceGroup` | `vllm/sequence.py` | one request's state container; carries token ids, sampling params |

## 2. Safe reorder point

**The waiting deque is the reorder target.** `_schedule_prefills`
iterates `self.waiting` left-to-right and admits as long as
`block_manager.can_allocate(seq_group)` returns success. Reordering
`self.waiting` BEFORE this iteration changes which sequence gets
admitted first.

The intercept can land at one of three points:

| Option | Where | Trade-off |
|---|---|---|
| **A (preferred)** | Monkey-patch `Scheduler.schedule()` to reorder `self.waiting` in-place before calling the original | Minimally invasive; one method wrap; preserves vLLM's internal invariants; same pattern as the int4_protected backend installs its swap |
| B | Subclass `Scheduler` + class-swap on the engine | More surface, more version-fragility |
| C | New scheduling-policy hook | Doesn't exist in 0.7.3; would require an upstream vLLM change |

**Phase 1 uses Option A.** The wrap is:

```python
original_schedule = scheduler.schedule
def cache_aware_schedule():
    if cache_aware_enabled:
        # Reorder waiting in-place by predicted hit rate.
        reordered = cache_aware.order_admissions(list(scheduler.waiting))
        scheduler.waiting.clear()
        scheduler.waiting.extend(reordered)
    return original_schedule()
scheduler.schedule = cache_aware_schedule
```

`scheduler.waiting` is a `collections.deque` in 0.7.3; the
`clear()`+`extend()` round-trip is O(N) in queue length and
preserves identity (no SequenceGroup objects re-created).

## 3. Prefix-cache / block-manager observation point

The radix tree's source of truth is the
`PrefixCachingBlockAllocator`'s internal index. Two observable
hooks:

| Hook | What it tells us | When it fires |
|---|---|---|
| `BlockSpaceManager.allocate(seq_group)` | which blocks were newly allocated AND which were prefix-cache reused | each time a request is admitted |
| `BlockSpaceManager.free(seq)` | which blocks were released back to the allocator's free-pool | each time a request finishes or is preempted |

For Phase 1, we wrap both with thin instrumentation that:
1. Reads the allocator state AFTER the wrapped call to learn the
   delta (newly cached prefixes; freed blocks)
2. Calls `tree.insert(...)` or `tree.evict(...)` accordingly

Allocator state surfaces in 0.7.3:

```
block_manager.block_allocator                  # BlockAllocator instance
  └─ .cached_blocks                            # content_hash -> PhysicalBlock
  └─ .evictor (LRU)                            # freed-block recycler
```

For prefix-cache hit detection at admission time, the simplest
signal is: count the SequenceGroup's prompt tokens that hash to an
existing entry in `cached_blocks` BEFORE the `allocate()` call,
and compare to the tokens that don't. The delta is the realized
cache-hit token count for that admission — exactly what the
predictor was predicting.

## 4. Tree synchronization (allocate / free events)

The Phase 1 patch wraps these two BlockSpaceManager methods
(monkey-patch, same wrap pattern as the scheduler):

```python
original_allocate = block_manager.allocate
def cache_aware_allocate(seq_group):
    # Compute realized cache hits for telemetry.
    realized_hit = _count_prefix_cached_tokens(seq_group)
    result = original_allocate(seq_group)
    # Sync tree with the new admission's blocks.
    tree.insert(
        seq_group.get_seqs()[0].get_prompt_token_ids(),
        block_ids=_block_ids_for(seq_group),
    )
    cache_aware.record_realized_hit(seq_group.request_id, realized_hit)
    return result
block_manager.allocate = cache_aware_allocate

original_free = block_manager.free
def cache_aware_free(seq):
    blocks_being_freed = _block_ids_for(seq)
    result = original_free(seq)
    tree.evict(blocks_being_freed)
    return result
block_manager.free = cache_aware_free
```

The two helpers (`_count_prefix_cached_tokens`, `_block_ids_for`)
are pure-read inspections of vLLM's allocator + seq state; no
shared mutable side-effects.

## 5. Fairness / streaming / cancellation impact

Three operational concerns the Phase 1 patch must not break:

### 5.1 Fairness — bounded by the starvation guard

Reordering by predicted hit rate creates a **starvation risk** if a
steady stream of high-hit requests keeps pushing older
low-hit requests further back. The Phase 0 prototype already has
a fairness guard: `max_starvation_seconds=30s` default. Any
request whose age in `waiting` exceeds this threshold is admitted
next regardless of hit rate, in FCFS order among the starved set.

The guard is tested in
`test_scheduler_starvation_guard_kicks_in`. Phase 1 must keep
this on by default.

### 5.2 Streaming order — unaffected

vLLM streams tokens per-sequence-group within `Scheduler.running`,
not per the original arrival order. The admission queue is
separate from the streaming queue. Once a sequence is admitted,
it streams its tokens in generation order regardless of how it
got there. **Reordering admission has zero impact on
within-request streaming order.**

### 5.3 Cancellation semantics — unaffected

`LLMEngine.abort_request(request_id)` finds the sequence by
`request_id` and removes it from whichever queue it's in
(`waiting`, `running`, or `swapped`). The reorder operation
preserves SequenceGroup object identity — we just permute the
deque. Cancellation lookup remains O(N) on `waiting` regardless
of order. **No change to abort behavior.**

Edge case: if a request is reordered to the BACK of `waiting` by
the cache-aware policy and then aborted before admission, it's
still findable by `request_id`. The abort path's existing search
isn't position-dependent.

## 6. Minimal Phase 1 patch — scope

**File surface (proposed; not committed in this note):**

```
KVPolicy/kv_policy/cache_aware_install.py        # new (~150 LOC)
Bench/ctm_bench/runner_vllm_streaming.py         # ~30-LOC plumbing
Bench/ctm_bench/scripts/run_streaming.py         # 1 new CLI flag
Bench/tests/test_cache_aware_install.py          # CPU smoke against
                                                 #   a mock scheduler
```

**Contract:**

1. **Feature flag off by default.** New CLI flag
   `--cache-aware-scheduling` (default `False`); new
   `AsyncEngineDriver(..., cache_aware_scheduling: bool = False)`
   parameter. With the flag off, the install function returns
   immediately and the patch is a no-op. With it on, the install
   wraps `scheduler.schedule`, `block_manager.allocate`, and
   `block_manager.free` exactly once at engine init.

2. **Reorder pending admissions only.** The patch only touches the
   admission queue. It does NOT touch:
   - `Scheduler.running` (active sequences)
   - `Scheduler.swapped` (preempted sequences)
   - Per-sequence token generation
   - Sampling
   - Streaming output

3. **No change to `Int4ProtectedAttentionImpl`.** The patch lives
   at the scheduler layer. The int4 backend doesn't know it
   exists. Composition works because the two layers decide
   different things (which request to admit vs how to store the
   admitted request's KV).

4. **No kernel changes.** The vendored `vllm-flash-attn` fork at
   SHA `720c948` + int4 path is untouched.

5. **Telemetry — predicted vs realized hit rate.** New fields in
   `StreamingRunCellResult`:

   ```
   cache_aware_scheduler_stats: dict
     ├─ admissions
     ├─ reordered_count
     ├─ starvation_overrides
     ├─ predicted_hit_tokens_total       # from order_admissions calls
     ├─ realized_hit_tokens_total        # from cache_aware_allocate hook
     ├─ prediction_accuracy              # realized / predicted (target: >= 0.85)
     ├─ mean_hit_rate                    # realized_hits / total_prompt_tokens
     └─ tree_size_tokens                 # for memory monitoring
   ```

   Plumbed through `runner_vllm_streaming.py` the same way
   `int4_route_a_stats` and `attention_aggregator_stats` are
   today.

## 7. Phase 1 acceptance criteria

Phase 1 GREEN requires **all** of:

| # | Gate | How verified |
|---|---|---|
| 1 | vLLM starts with flag ON | engine init completes; one short generate(); exit 0 |
| 2 | vLLM starts with flag OFF (regression) | same as today's behavior; full Bench test suite passes |
| 3 | Requests complete correctly with flag ON | 5-prompt smoke produces non-empty output for each request |
| 4 | Scheduler ordering applied | telemetry shows `reordered_count > 0` on a workload with shared prefixes (multi-turn chat shape, 6+ requests sharing a system prompt) |
| 5 | No starvation | `starvation_overrides` is the right ballpark (>0 when the workload has both high-hit and low-hit requests with long waits; 0 under typical workloads); no individual request stays in `waiting` past `max_starvation_seconds` |
| 6 | Prefix-hit telemetry emitted | `streaming_summary.json` contains a populated `cache_aware_scheduler_stats` dict |
| 7 | Stock path byte-identical when disabled | Phase 1 must include a regression test: run a fixed prompt 5x with flag ON vs OFF; the OFF outputs must match the pre-Phase-1 baseline outputs byte-for-byte |
| 8 | Allocator events received | smoke test confirms tree's `inserts` and `evictions` counters > 0 after one workload |
| 9 | Prediction accuracy bounded | `prediction_accuracy >= 0.85` on a chat-shaped workload (matches the Phase 0 CPU composition gate) |
| 10 | No regression on int4_protected Tier A results | run a single int4_protected needle cell with the flag OFF; result must match the brief's claims |

Gates 1, 2, 7, 8 are correctness; gates 3-6, 9-10 are
functional. Phase 1 GREEN means all ten pass.

## What Phase 1 explicitly does NOT do

* **No GPU-scale measurement.** That's Phase 3.
* **No system-prompt pinning CLI.** That's Phase 4.
* **No upstream vLLM PR.** The install is a monkey-patch (same
  pattern as int4_protected and route-A); upstreaming is a
  separate engineering track.
* **No int4_protected backend changes.** Orthogonality contract
  per Section 6 of the v2 design doc.
* **No new eviction algorithm.** Phase 4 trig retirement is still
  in force; the scheduler uses vLLM's existing block-level LRU +
  prefix caching as the substrate. The scheduler decides admission
  order; it does not decide eviction.
* **No VC brief edits.** v2 stays as roadmap, not headline.
* **No claim about combined-stack throughput / quality.** That's
  Phase 3 measurement output, not Phase 1 deliverable.

## Open questions for Phase 1 implementation

These won't block the patch but should be decided when work
starts:

1. **`SequenceGroup` ID lifetime for telemetry attribution.** To
   compute realized hit rate per admission, the
   `cache_aware_allocate` hook must remember each request_id's
   predicted hit (from `order_admissions`) and subtract realized
   on free. Simple dict; bounded by active requests; cleared on
   `complete`.

2. **vLLM 0.7.3 V0 engine vs V1 engine.** This work targets V0.
   The V1 path has a different scheduler shape. If/when the team
   ports to V1 (Tier 2 v2 item per the brief), Phase 1's
   monkey-patch needs a parallel V1 implementation. Not in scope
   here.

3. **Tokenizer access.** The radix tree indexes by token IDs (not
   strings). The scheduler must see the same token IDs vLLM does.
   We use `seq_group.get_seqs()[0].get_prompt_token_ids()` —
   already-tokenized by vLLM, no parallel tokenization.

4. **`max_starvation_seconds` default.** Phase 0 prototype uses
   30s. Real workloads may want different defaults (10s for
   latency-sensitive, 60s for throughput-bound). Phase 1 ships
   30s; Phase 3 measurement can tune.

5. **Tree memory bound default.** Phase 0 prototype uses 1M
   tokens. At ~57 KB/token in bf16, that's ~57 GB — well above
   any realistic GPU cache footprint, so the tree is the lighter
   data structure. Phase 1 ships 1M; revisit if profiling shows
   tree overhead is non-trivial.

## Effort + risk recap

| Item | Effort | Risk |
|---|---:|---|
| `install_cache_aware_scheduler` + the three monkey-patches | 2 days | low; same pattern as existing installs |
| Telemetry plumbing through the streaming runner | 1 day | low; rides on existing `int4_route_a_stats` infra |
| CPU smoke test (mock scheduler) | 0.5 day | low |
| Smoke GPU run with flag ON (single prompt, single needle bucket) | 0.5 day + ~$0.05 GPU | low |
| Stock-path regression test with flag OFF | 0.5 day + ~$0.05 GPU | low |
| **Total Phase 1** | **~4-5 days + ~$0.10 GPU** | **low** |

Risk profile is low because:
- All hooks are wraps of existing methods; no new threading or async
- The fairness guard already exists in Phase 0
- The orthogonality contract with int4_protected is mechanically enforced (we never call into the backend)
- The CPU prototype's 24 tests cover all the policy logic

## Recommendation

The Phase 1 patch is scoped, the risks are bounded, and the
acceptance criteria are concrete. Approve Phase 1 implementation
when ready; the reconnaissance answers all six questions in the
brief.

If approved, Phase 1 lands in two PRs:
1. `install_cache_aware_scheduler` + tests (PR-1, CPU-only)
2. Streaming-runner telemetry + smoke verification (PR-2, GPU
   needed for gates 4, 5, 6)

## PR-2 status (post-implementation, CPU phase)

**CPU plumbing landed.** What's in:
* `AsyncEngineDriver(cache_aware_scheduling: bool = False,
  cache_aware_max_starvation_seconds: float = 30.0)` constructor
  args.
* `install_cache_aware_scheduler` hooked into the engine init in
  `runner_vllm_streaming.run()` after engine construction and
  after the route-A INT4 install block (same `try / except
  BaseException → best-effort engine teardown` pattern). Lives at
  the scheduler layer; orthogonal to `Int4ProtectedAttentionImpl`,
  the vendored vllm-flash-attn fork, CTM+ evictor, and route-A
  INT4.
* `StreamingRunCellResult.cache_aware_scheduler_stats: Dict[str,
  Any]` populated at end-of-run from
  `CacheAwareInstall.stats()`. Empty dict when flag OFF;
  populated with the canonical 9-key dict when flag ON.
* CLI flag `--cache-aware-scheduling` (+
  `--cache-aware-max-starvation-seconds`) on `run_streaming.py`,
  plumbed through to the driver.
* Teardown wired into the existing finally block, LIFO order:
  cache-aware-scheduler → route-A INT4 → attention flusher →
  engine shutdown.
* CPU test suite `Bench/tests/test_cache_aware_runner_plumbing.py`
  with 8 tests covering:
  - constructor default (flag OFF) regression
  - constructor accepts flag ON + custom max-starvation
  - dataclass field present + default
  - flag-OFF install branch not entered (bound-method identity
    check on the engine's scheduler / block_manager methods)
  - flag-ON install populates stats with the canonical key set
  - max-starvation override plumbs through to `CacheAwareScheduler`
  - install-failure path invokes engine shutdown
  - `--help` output lists both new flags (subprocess smoke)

Acceptance-gate status (per §7):

| Gate | Status | Evidence |
|---|---|---|
| 1. vLLM starts with flag ON | **mocked GREEN** | `test_run_flag_on_installs_and_populates_stats` (real-vLLM still pending GPU pod) |
| 2. vLLM starts with flag OFF (regression) | **mocked GREEN** | `test_run_flag_off_does_not_install` + 313-test CPU sweep no-regression |
| 3. Requests complete correctly with flag ON | **pending GPU** | gate B2 |
| 4. Scheduler ordering applied | **pending GPU** | gate B4 |
| 5. No starvation | **pending GPU** | gate B7 |
| 6. Prefix-hit telemetry emitted | **pending GPU** | gate B3 |
| 7. Stock path byte-identical when disabled | **structurally GREEN** | flag-OFF path has zero patches applied (bound-method identity check); full byte-identical regression still pending GPU pod |
| 8. Allocator events received | **pending GPU** | gate B5 |
| 9. Prediction accuracy bounded | **pending GPU** | gate B6 |
| 10. No regression on int4_protected Tier A | **pending GPU** | gate C2 |

What's pending on a GPU pod:
* One Qwen-7B chat-shaped smoke with `--cache-aware-scheduling`
  to exercise gates 3-6, 8, 9.
* One int4_protected needle cell with flag OFF to exercise
  gate 10 (`verify_phase5b_5_needle.py` on Qwen-7B seed=44 —
  must match the brief's 15/15 result).

Pre-existing argparse `%` bug fix (collateral, not in scope):
three help strings in `run_streaming.py` had unescaped `%` chars
(`20% Python`, `62% trig_changed_pick`, `20% throughput`, `15%
_call_impl`) that broke `python -m … --help` because argparse
percent-formats action help. Doubled to `%%` so `--help` works
again — needed for the new CLI smoke test.

### V2 block-manager shape fix (post-first-GPU-smoke)

PR-1's recon assumed `block_manager.block_tables[seq_id]` is
`List[PhysicalTokenBlock]` (V1 block manager). vLLM 0.7.3's V0
engine actually uses a V2 block manager whose `block_tables[seq_id]`
is a `BlockTable` wrapper object — exposes `.physical_block_ids`
and `.blocks` but is **not directly iterable**.

The first GPU smoke attempt surfaced this:

```
File ".../kv_policy/cache_aware_install.py:197", in _block_ids_for_seq
    return [int(getattr(b, "block_number", b)) for b in bt]
TypeError: 'BlockTable' object is not iterable
```

Fix: `_block_ids_for_seq` in `cache_aware_install.py` now tries
three accessor patterns in order — `.physical_block_ids` (V2
canonical), `.blocks` (V2 alt), direct iteration (V1 + mocks)
— and returns `[]` on unknown shapes rather than crashing the
engine loop.

CPU regression coverage: `MockBlockTableV2` +
`MockBlockSpaceManagerV2` in `test_cache_aware_install.py` (4 new
tests, including a sanity check that the V2 mock raises
`TypeError` on iteration to match real vLLM). With those tests in
place this regression can't slip back in.

Lesson: the CPU mock-vs-real-vLLM surface drift is a real risk
of CPU-first verification. The orthogonality + monkey-patch
pattern is robust to it (the wrap stays a structural no-op when
the helper returns `[]`), but the helper itself has to know the
real interface shape. Future installs should mirror this fix
pattern: try canonical → alt → iterate → fail-safe.
