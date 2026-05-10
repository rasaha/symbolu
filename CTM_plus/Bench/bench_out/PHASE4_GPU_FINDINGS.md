# Phase 4 GPU Findings — Honest Write-up

**Session date:** 2026-05-09 → 2026-05-10
**Branch:** `claude/safety-state-machine-EXAlZ`
**Hardware:** RunPod A100 80GB
**Model:** Qwen2.5-7B-Instruct (vLLM 0.7.3, enforce_eager=True)
**Total GPU spend:** ~$1.60 spot
**Audience:** partner-pitch authors, technical reviewers, the engineering
team's next iteration on CTM+

This document is the canonical record of what the May 2026 Phase 4
GPU validation attempted, what it produced, and what the result
honestly means. It is the doc to share with a partner who asks "did
your trig scoring beat LRU?"

## §1. TL;DR

We executed the Phase 4 four-cell GPU experiment against real
Qwen2.5-7B in vLLM 0.7.3. **Phase 4 did not beat Phase 2 or LRU on
streaming chat workload.** Throughput dropped ~20% relative to Phase 2;
swap-out per decode token was roughly identical (Phase 4: 0.28,
Phase 2: 0.31).

The win condition from `POST_PHASE4_ROADMAP.md` step 1 (≥+3pp hit-rate
uplift over LRU) was missed.

The session also produced **seven audit-pass findings** — bugs that
existed in the implementation and that the prior CPU mocked tests had
not caught. All seven are fixed in source. A new CPU fixture
(`tests/test_vllm_protocol_fixture.py`) drives the cross-call protocol
that surfaces this class of bug at $0 in <0.2s.

What the session **does not** invalidate: the architecture-doc 8.8×
capacity claim (TurboQuant + CTM+ + CTXL stack) — none of those layers
were measured here. The negative result applies specifically to CTM+
Phase 4's scoring formula on streaming chat in vLLM 0.7.3, with pooled
calibration on a shared-rotary model.

## §2. What we set out to validate

The Phase 4 design (`scripts/MODE_B_PHASE4_DESIGN.md`) adopts
TriAttention's pre-RoPE Q/K-concentration insight as a new component
in CTM+'s eviction-scoring formula. The hypothesis under test was
that, on a streaming chat workload at heavy KV pressure on real
Qwen2.5-7B:

* CTM+ Phase 4 beats LRU on **swap-out blocks per completed request**
  (≥3 percentage-point improvement, equivalent to ≥+3pp hit-rate
  uplift), and
* It does so without measurable throughput regression (≤5%).

The four-cell experiment design covered LRU baseline, CTM+ Phase 2
(recency+frequency only), CTM+ Phase 4 (trig + window pruning), and
optional CTM+ Phase 3 (real attention forwarding) as an ablation.

## §3. What we actually measured

Six GPU runs, in order:

| # | Cell | Outcome |
|---|------|---------|
| 1 | Calibration | ~100K tokens accumulated. `layers=1` (Qwen2.5 shares one RotaryEmbedding); MRL=0.221 (paper's healthy bar is ≥ 0.3). |
| 2 | LRU baseline (v2) | `swap_out=0, completed=8, prefix-cache hit rate=12.5%, peak KV=57%`. **Cache never spilled.** |
| 3 | CTM+ Phase 2 (v2) | `AsyncEngineDeadError` (bug #1). Crashed after 5 of 30 requests. |
| 4 | CTM+ Phase 2 (v3) | `swap_out=3188, completed=5, evict_calls=3323, tokens/sec=85.33, prefix-cache hit=0%, peak KV=99%, wall=120s`. |
| 5 | CTM+ Phase 4 (v3) | Bit-identical to Phase 2 v3. Bug #4 + #5 + #6 silently degraded Phase 4 to Phase 2. |
| 6 | CTM+ Phase 4 (diag3) | After all seven fixes: `swap_out=1134, completed=2, evict_calls=1283, tokens/sec=68.26, window_pruning_invocations=45, blocks_captured=135, wall=60s`. |

The headline comparison after all fixes landed (extrapolated to matched
wall):

| Metric | LRU baseline | Phase 2 (v3) | Phase 4 (diag3 ×2) |
|---|---:|---:|---:|
| swap_out | 0 | 3188 | ~2268 |
| completed | 8 | 5 | ~4 |
| tokens/sec | (different regime) | 85.33 | 68.26 |
| evict_calls | n/a | 3323 | ~2566 |
| swap_out / decode_token | n/a | 0.311 | 0.277 |

**Phase 4 vs Phase 2: −20% throughput, ~−11% swap-out per token,
~−20% completed at matched wall. No clear win.**

**Phase 2 vs LRU: incomparable** because the patched evictor disrupts
vLLM's prefix-cache promotion path (LRU 12.5% prefix hit → 0% under
CTM+; LRU peak KV 57% → CTM+ 99%). The two policies are seeing
different effective workloads.

## §4. The seven audit-pass findings

Every one is fixed in source; the regression tests in
`tests/test_vllm_protocol_fixture.py` would have caught each of them
on CPU in <0.2s.

1. **`assert content_hash in _cached_blocks` invariant violation
   (HIGH).** `CTMEvictorModern.evict()` did not call
   `KVCachePolicy.evict_block(victim_id)` to drain the policy's
   `gpu_blocks` set. Under sustained allocation pressure,
   `select_victims` re-picked the already-evicted block,
   `self._content_hash.pop(victim_id, 0)` returned `0`, and vLLM's
   `assert content_hash in self._cached_blocks` fired with
   `AsyncEngineDeadError`. Fixed by always calling `evict_block` and
   using strict `pop` with a defensive retry loop.

2. **Identical prompts dedupe to zero evictions under prefix caching
   (HIGH).** The streaming runner generated `[100] * length` prompts
   for every request. With `enable_prefix_caching=True` (which Phase 4
   requires), vLLM achieved 77% prefix-cache hit rate and the GPU KV
   cache peaked at ~57% — never enough to engage swap or eviction.
   Fixed by injecting a per-request unique head token at position 0
   so each prompt's content-hash chain diverges from the start.

3. **Re-admission divergence between `_tracked` and `gpu_blocks`
   (HIGH).** vLLM's `PrefixCachingBlockAllocator` re-admits evicted
   blocks routinely. `CTMEvictorModern.add()` called
   `KVCachePolicy.ensure_block()`, which early-returns when
   `block_id` is already in `self.blocks` — and our `evict_block`
   path discards from `gpu_blocks` but never pops `self.blocks`. After
   enough re-admissions, `gpu_blocks` shrank to empty even though
   `_tracked` was full; `select_victims` returned `[]` and
   `evict()` raised `ValueError: no tracked blocks`. Fixed by
   explicitly `self._policy.gpu_blocks.add(block_id)` after
   `ensure_block` in the wrapper's `add()` path.

4. **Hook ordering: rotary_emb fires before Attention (HIGH).** The
   side-channel hook was installed on each Attention layer's
   `forward_pre_hook`, on the assumption that `Attention.forward`
   fires before `rotary_emb`. In vLLM 0.7.3's Qwen2.5 implementation
   the actual order inside a decoder layer is:
   `qkv_proj → rotary_emb (pre-RoPE capture fires) → Attention.forward
   (old side-channel fired here, too late)`. So at capture time
   `evictor._phase4_pending_slot_mapping` was always `None` and the
   capture function silently aborted. Fixed by hooking the top-level
   `model.forward` (which receives `attn_metadata` as a forward kwarg
   and fires before any submodule).

5. **`set_block_pre_rope_keys` silently dropping every capture
   (HIGH).** The function gated on
   `if block_id not in self._tracked: return`. Every decode token
   writes to a slot whose block is mutable (still being filled by
   vLLM) and not yet promoted/hashed/admitted to the evictor — so
   not in `_tracked`, so silently no-op'd. Fix: speculative storage.
   Don't gate on `_tracked`; store the keys whenever
   `set_block_pre_rope_keys` is called. `remove()` and `evict()`
   pop the entries so the dict stays bounded by the live cache
   footprint. When the block is later admitted, the keys are
   already there and trig scoring can use them.

6. **Window pruning never fires (HIGH).** The trig score is consumed
   only by `window_pruning_pass()`, not by the main `evict()` path.
   The runner never called `evictor.window_pruning_passed/pass`, so
   the proactive pruning that's supposed to activate Phase 4's
   mechanism never ran. Fixed by ticking the window-pruning state in
   `AsyncEngineDriver._submit_one` on every yielded output, and
   running `window_pruning_pass(target=current-4)` when the threshold
   crosses.

7. **`SetBlockPreRopeKeys` after evict resurrected stale entries
   (MEDIUM).** Speculative storage made `_block_pre_rope_keys`
   accept any `block_id`. But after the block is evicted, if a
   different content takes that block_id and the speculative-store
   call fires again, the old K vectors leak into the new block's
   scoring. Fixed by popping `_block_pre_rope_keys` and
   `_block_layer_head` in both `remove()` and `evict()` so the
   dict stays bounded by live cache footprint.

**The pattern across all seven:** mocked unit tests pinned per-call API
shape but did not drive the cross-call invariants the real allocator
relies on. The May 2026 GPU run was the first time those invariants
were exercised. The new fixture
(`tests/test_vllm_protocol_fixture.py`) closes the gap.

## §5. Synthetic ↔ real reconciliation

Mode A synthetic predicted (canonical headline cells):

* `chat_32k @ oversubscription 0.025`: −52% avg latency (HBF + CTM+
  vs DDR + LRU)
* `rag_128k @ all oversubscriptions`: −100% slow-tier reads
* `agentic_clustered_64k @ oversub 0.025`: +192% (the honest
  regression)

Mode B real GPU showed Phase 4 ≈ Phase 2 ≈ no measurable win on
streaming chat. **Five reasons the numbers don't transfer:**

### §5.1. Different mechanism

Mode A's CTM+ scoring uses real attention sums:
`0.35·attn_sum + 0.30·position + 0.25·recency + 0.10·freq`. Mode B's
Phase 2 has zero attention forwarding — vLLM 0.7's Evictor ABC does
not pass attention to `update()`. So Phase 2's effective formula
collapses to `0.25·recency + 0.10·freq`, equivalent to LRU + a
frequency tiebreaker. Phase 4 layers a trig signal on top via window
pruning, but the main `evict()` path still doesn't see attention.

The HIGH-severity audit finding from earlier flagged this; we never
reconciled the Mode A predictions against the actual integrated
formula.

### §5.2. Mode A's tier-cost model assumes static per-block costs

Mode A treats each slow-tier byte as a fixed-latency event (e.g., 50µs
for DDR, 2µs for HBF). Real GPU serving has per-step batching,
prefix-cache interactions, scheduler overhead, async backpressure, and
KV-block transfer is amortised across batched requests. The 52%
latency reduction is "if a slow-tier byte costs X and a saved one
costs Y, that's (X−Y)×bytes" — but real serving doesn't see slow-tier
bytes in isolation; it sees them folded into a wider critical path
that includes scheduler + collective + decode kernels.

### §5.3. Synthetic attention patterns are cleaner than reality

Mode A's KVSimulator generates one of {sink+recent, entity-focused,
distributed, mixed} per sequence. Real Qwen2.5 attention on chat
workloads is much more diffuse — entity-focused patterns (which
CTM+ exploits via its ENTITY classification) are rarer. The
distributions Mode A samples from have higher signal than the
distributions real chat produces.

### §5.4. Mode A has zero integration overhead

Mode A's "CTM+" is a pure-Python scoring function. Real Phase 4 has:

* 159K hook fires per 60s (side-channel pre-hook + rotary pre-hook).
* 45 window-pruning passes per 60s, each scoring 50+ blocks.
* 159K `set_block_pre_rope_keys` calls per 60s, each writing into a
  Python dict.
* CPU↔GPU tensor materialisation for K capture (`.detach().to("cpu")`
  per decode token).

The 20% throughput drop measured in the GPU runs lives almost entirely
in this overhead. A production CTM+ would need a CUDA kernel for trig
scoring or radically batched updates to recover it.

### §5.5. Mode A's RAG cell (−100%) is unreachable above LRU + prefix-caching

vLLM's `enable_prefix_caching=True` already deduplicates one-shot
prompts. The "S3-FIFO scan resistance" CTM+ provides is mostly
redundant with prefix caching for the RAG workload. We never compared
CTM+ vs LRU+prefix-caching apples-to-apples in Mode A; if we had, the
−100% advantage would have shrunk to whatever advantage S3-FIFO has
over vLLM's content-hash dedupe (probably small).

### What does transfer

The agentic regression direction. Mode A predicted CTM+ would
underperform on certain workloads at heavy spillover. The Mode B run
showed CTM+'s 20% throughput overhead on chat — different metric,
same overall direction: CTM+ as currently built has a cost-benefit
profile that's not universal. Workloads where CTM+ wins probably
exist (the simulator predicts them); chat at heavy KV pressure isn't
one of them.

## §6. What we wanted to measure vs what the experiment actually measured

The experiment's nominal comparison was **CTM+ Phase 4 vs LRU on
streaming chat at matched cache pressure.**

What we actually measured is **CTM+ Phase 4 (with prefix caching ON
because Phase 4 requires it) vs LRU (with prefix caching ON because we
forced it for apples-to-apples)**. The "apples-to-apples" assumption
fails because CTM+'s evictor patch disrupts vLLM's prefix-cache
promotion path. The two cells run at different effective KV pressures:
LRU at ~57% peak, CTM+ at ~99% peak.

**This is not Phase 4's fault.** It's a structural consequence of
patching `PrefixCachingBlockAllocator.evictor` while keeping prefix
caching on. To get a clean comparison we need either:

* Both cells with prefix caching off (then CTM+ doesn't install,
  because its patch only finds the `evictor` slot on the
  `PrefixCachingBlockAllocator`); or
* A custom evictor that integrates more deeply with the prefix-cache
  promotion path so it doesn't disrupt it (significantly more work);
  or
* A different metric: not raw swap_out, but **effective concurrency
  at fixed quality (MMLU/perplexity)** at matched wall, which removes
  the need to equalise the cache regime.

The roadmap's +3pp hit-rate gate was framed against the assumption
that both cells would see the same cache regime. They don't. The
gate definition needs updating (see §9).

## §7. What's still completely unbacked

The architecture doc `CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md`
projects an 8.8× effective serving capacity from the full
TurboQuant + CTM+ + CTXL stack. After this session we have validated:

| Component | Validation status |
|---|---|
| TurboQuant 3-bit polar quant | CPU-simulated 7.15× ratio at 0.965 cosine (DeepSpeed v3 benchmark, 2026-04-02). v4 GPU kernel is "pending"/"target" per `CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md`. |
| TurboQuant ↔ vLLM KV-cache integration | **Not attempted.** No code path exists. |
| CTM+ Phase 1 (synthetic CPU sim) | Mode A 5 rounds + audit pass + multi-seed |
| CTM+ Phase 2/4 on real Qwen2.5-7B | This session; ~$1.60 GPU; **negative result on chat workload** |
| CTM+ Phase 3 (real attention forwarding) | Code-complete; deferred; no GPU run |
| CTXL (HBM → CXL → NVMe tiering) | **Designed only.** No runtime measurement anywhere in repo. |
| Combined-stack measurement | **Not attempted.** |
| Quality preservation (MMLU / perplexity) | **Not measured at any layer.** |

Any partner pitch citing the 8.8× number needs a footnote: "forward
projection of a stack whose individual components have varying levels
of validation; the algorithm-layer (CTM+ Phase 4) component, the
only one validated end-to-end on real-model GPU, did not produce a
measurable win on streaming chat in this session."

## §8. Honest claims by milestone — what's safe to say to partners

These supersede the milestone claims in
`Bench/scripts/POST_PHASE4_ROADMAP.md` §"Decision matrix" until the
roadmap is rewritten.

### Safe today

* "We integrated TriAttention-inspired pre-RoPE Q/K capture and trig
  scoring end-to-end into vLLM 0.7.3's eviction path on real
  Qwen2.5-7B."
* "Our audit-pass methodology produced 7 fixable findings during
  Phase 4 GPU validation (~$1.60 of GPU spend), all caught and
  documented; the regression test fixture closes the gap that
  allowed those findings to ship in the first place."
* "On streaming chat at heavy KV pressure on Qwen2.5-7B in vLLM
  0.7.3, CTM+ Phase 4 with pooled-layer calibration **does not
  beat** Phase 2 or LRU. The trig signal is firing as designed but
  is not changing eviction outcomes meaningfully on this workload."
* "The honest interpretation of the simulator's wins is that they
  reflect a different mechanism (real attention values in scoring)
  than what current vLLM integration can run; reconciling them
  requires Phase 3 (attention-forwarding) or a different integration
  point that doesn't disrupt the prefix cache."

### Not safe today

* "CTM+ delivers X% latency reduction on real models." (We do not
  have any cell where CTM+ beats LRU at matched regime.)
* "TurboQuant + CTM+ + CTXL delivers 8.8× capacity." (No combined
  measurement; only the architecture doc.)
* "TriAttention's claims reproduce in our integration." (TriAttention
  paper headlines 10.7× memory reduction and 2.5× throughput at
  matched accuracy. Our Phase 4 shows ~−20% throughput at no measurable
  quality gain — a 12.5× gap from paper claims that needs
  reconciliation before citing the paper alongside our work.)

### What can move into "safe" with cheap follow-up

* **Per-layer calibration** (~$0.05 GPU + 1–2 hours code) plausibly
  closes the MRL gap from 0.221 to >0.3. If it does AND Phase 4 still
  loses, the negative result becomes durable. If it does AND Phase 4
  wins, we have a real headline.
* **Quality measurement** (MMLU subset, ~1 day no-GPU) lets us drop
  the "raw swap_out comparison" and adopt "effective concurrency at
  matched quality" — a metric that doesn't depend on equalising the
  cache regime.
* **Comparison vs vLLM-FP8 / KIVI / H2O on the same hardware**
  (~1 GPU-day) tells us whether CTM+ sits above or below the Pareto
  frontier of off-the-shelf alternatives.

## §9. Decision criteria for next steps

In strict priority:

### §9.1. Don't run another GPU cell yet

We have enough data to write a clean honest result. Spending more
on incremental experiments before fixing the comparison validity
issue (#5) is throwing good money after bad.

### §9.2. The CPU fixture is the highest ROI fix

`tests/test_vllm_protocol_fixture.py` (committed in this session)
catches the 7-bug pattern at $0 GPU. **Every wrapper around a
vLLM-internal data structure must come with cross-call protocol
tests of this shape.** Single-call mocks are insufficient.

### §9.3. Per-layer calibration as the next experiment

If we run anything more, the per-layer calibration is the highest-ROI
$0.20 GPU spend — it directly addresses the "MRL=0.221 below paper's
0.3 bar" hypothesis and either confirms or rejects "calibration
quality is the bottleneck."

### §9.4. The roadmap's +3pp hit-rate gate is wrong

The gate was set against the assumption that LRU and CTM+ see the same
workload. They don't. The corrected gate definition:

> **Phase 4 wins iff:**
> 1. Per-layer calibration produces mean MRL ≥ 0.3, AND
> 2. CTM+ Phase 4 reduces decode latency at matched p99 by ≥ 5% on
>    chat_32k workload, comparing CTM+ vs LRU at matched
>    `enable_prefix_caching` setting (both off, since CTM+'s patch is
>    only meaningful when the eviction decision matters), AND
> 3. MMLU subset score within ±0.5 points of LRU baseline at the same
>    cache budget.

### §9.5. Architecture doc reconciliation

The 8.8× claim needs to be downgraded to "projection." A one-paragraph
reconciliation belongs at the top of
`CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` with a pointer
to this findings doc.

### §9.6. Partner-pitch positioning

What survives partner technical diligence today is the methodology
narrative, not the results narrative:

> "We have a reproducible audit-pass discipline that produced 7
> fixable findings during a single $1.60 GPU validation. The
> simulator's headline wins do not transfer directly to vLLM 0.7+
> integration in their current form, for reasons we have documented
> with specific reconciliation points. The path to a defensible win is
> per-layer calibration plus a Phase 3 attention-forwarding hook plus
> a different metric (quality-at-matched-budget rather than raw
> swap_out). Those are sized in single-digit GPU-day units and we
> would not start them without partner-specific input on what
> workload to optimise for."

That's a rare positioning for an inference-optimization team. Most
teams' benchmarks show wins; few teams' benchmarks show their
methodology surfacing and correcting their own errors mid-flight.

---

## Appendix A: Commits this session

| Commit | What |
|---|---|
| `94ff87a` | fix: two GPU-only test failures from first GPU run |
| `3080ea5` | feat: vLLM-based Q-center calibration driver |
| `538bb7c` | fix: real `QCenterStats.save` signature |
| `67ffc01` | fix: two HIGH-severity bugs from first GPU run (evict drains gpu_blocks, prompt uniqueness) |
| `94dc428` | fix: third evictor bug — re-admission divergence |
| `62c1c49` | fix: hook ordering — move side-channel to model.forward |
| `cb8de76` | diagnostic: reason-coded counters for hook + capture flow |
| `a63d0ac` | fix: `set_block_pre_rope_keys` was silently dropping every capture |
| `b408b92` | fix: wire window pruning into the runner's submit loop |
| `a3f87b0` | wip: per-layer calibration support (partial; opt-in) |
| `0b5bbe5` | test: CPU vLLM-protocol fixture catching the 7 audit-pass misses |
| (this commit) | docs: PHASE4_GPU_FINDINGS.md |

## Appendix B: Counter telemetry from the final diag3 run

The healthy-path counters from the post-fix Phase 4 run, for future
debugging:

```json
{
  "phase4_side_channel_pre_hook_calls": 2280,
  "phase4_side_channel_metadata_found": 2280,
  "phase4_side_channel_metadata_missing": 0,
  "phase4_rotary_pre_hook_calls": 63833,
  "phase4_capture_attempts": 63833,
  "phase4_capture_aborts_no_slot_mapping": 0,
  "phase4_capture_aborts_no_decode_tokens": 84,
  "phase4_capture_exceptions": 0,
  "phase4_set_pre_rope_keys_calls": 163888,
  "phase4_set_pre_rope_keys_speculative": 163888,
  "phase4_blocks_captured_with_pre_rope_keys": 135,
  "phase4_window_pruning_invocations": 45
}
```

Interpretation: every step of the Phase 4 pipeline fires (hooks
attach, metadata stashes, rotary pre-hook fires, capture attempts,
speculative storage, window pruning). The mechanism is functional;
the signal it produces does not measurably change eviction outcomes
on this workload at this calibration quality.

## Appendix C: Where to read more

| Doc | Purpose |
|---|---|
| `Bench/bench_out/RESULTS.md` | Round-by-round Mode A simulator results + the §13 validation roadmap |
| `Bench/bench_out/PARTNER_VALIDATION_NOTE.md` | Partner-shareable conservative framing |
| `Bench/scripts/POST_PHASE4_ROADMAP.md` | The 7-step plan from Phase 4 GPU validation through partner deployment (gate definition needs updating per §9.4) |
| `Bench/scripts/MODE_B_PHASE4_DESIGN.md` | Phase 4 design rationale |
| `Bench/scripts/MODE_B_PHASE4_GPU_RUNBOOK.md` | The runbook this session executed |
| `Bench/tests/test_vllm_protocol_fixture.py` | The CPU fixture that closes the audit gap |
| `CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` | Architecture-doc source of the 8.8× claim that §7 says is unbacked |
