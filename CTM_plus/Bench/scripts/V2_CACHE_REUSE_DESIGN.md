# V2 — Cache-Reuse Layer Design

> **Status:** Design + CPU prototype + CPU tests. **No GPU work, no vLLM
> integration in this iteration.** This document is the v2 production-
> hardening plan; phase-gated execution.

## TL;DR

INT4 protected optimizes **KV memory per block**. The v2 cache-reuse
layer optimizes **how many blocks are reused across requests** by
adding cache-aware request scheduling on top of vLLM's existing
block-level prefix caching.

| Layer | What it optimizes | Mechanism |
|---|---|---|
| INT4 protected (v1, shipped) | bytes per block | 4-bit quantization with 4% K-channel protection |
| **Cache-reuse (v2, this doc)** | **block reuse across requests** | **Radix-prefix index + cache-aware admission scheduling** |

The two layers are **orthogonal**: the v2 scheduler does NOT change
the `Int4ProtectedAttentionImpl` backend, does NOT change the vLLM-FA
kernel fork, and does NOT introduce a new eviction-scoring algorithm.
It sits above vLLM's scheduler and reorders the admission queue based
on predicted prefix-cache hit rate.

This is the **SGLang RadixAttention pattern**, adapted to vLLM 0.7.3
+ INT4 protected. The pattern is industry-deployed and the only
research effort here is the integration shape — not the algorithm.

## Problem statement

vLLM today admits pending requests in arrival order. Its
`PrefixCachingBlockAllocator` correctly REUSES blocks when two
admitted requests share a prefix, but it does NOT proactively
schedule the admission queue to maximize that sharing. Two common
patterns leave free wins on the table:

1. **Concurrent multi-turn chat sessions** with overlapping system
   prompts. If 30 pending requests share a 1k-token system prompt
   but arrive interleaved with non-sharing requests, vLLM may admit
   them in arrival order — causing prefix-cache misses, KV
   recomputation, and lower effective concurrency.
2. **Burst-arriving RAG queries** with the same retrieval context
   prefix. The first request populates the cache; subsequent
   requests should be admitted while the cache is warm, but vLLM
   has no admission-ordering policy that knows this.

SGLang's RadixAttention solves this at the serving layer:
- A radix tree indexes cached prefixes by token sequence.
- Pending requests are evaluated for predicted hit rate.
- Requests with high overlap with currently-cached prefixes are
  scheduled first.
- Reported impact: 2-5× cache hit rate on multi-turn chat
  workloads vs FCFS scheduling.

The v2 cache-reuse layer ports this pattern, adapted to vLLM 0.7.3
and the INT4 protected backend's block-size constraint.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  v2 Cache-Aware Scheduler (NEW — this design)                   │
│  ─────────────────────────────────────────                      │
│    - PrefixRadixTree (token sequence → block_id index)          │
│    - CacheHitPredictor (predicted hit rate per pending request) │
│    - AdmissionPolicy (queue reorder + pinning)                  │
│    - Telemetry (predicted-vs-realized hit rate)                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │ "admit this request next"
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  vLLM AsyncLLMEngine 0.7.3 (UNCHANGED)                          │
│    - PrefixCachingBlockAllocator (block-level cache, LRU)       │
│    - Int4ProtectedAttentionImpl backend (UNCHANGED)             │
│    - vllm-flash-attn int4 kernel fork (UNCHANGED)               │
└─────────────────────────────────────────────────────────────────┘
```

The scheduler queries vLLM for the set of currently-cached prefixes
(observable via `BlockManager` introspection), maintains its own
radix index over those prefixes, and rewrites the admission order
on each scheduling tick.

## Component design

### 1. PrefixRadixTree

Radix tree mapping `token_sequence → block_id_set`. Each node holds:

- The token sequence segment (delta from parent)
- The set of `block_id`s that hold this prefix's tokens
- Last-access timestamp (for LRU pruning)
- Pin flag (for system-prompt pinning)
- Child pointers (radix-branch by next-token)

Operations:

| Op | Args | Complexity | Notes |
|---|---|---|---|
| `insert(tokens, block_ids)` | observed cached prefix | O(L) in tokens | called when vLLM reports new immutable blocks |
| `query(tokens) -> int` | candidate request prefix | O(L) | returns longest cached prefix length |
| `evict(block_ids)` | freed blocks | O(blocks affected) | called when vLLM evicts blocks |
| `pin(tokens)` | system prompt | O(L) | marks prefix as not-LRU-evictable |
| `prune_lru(target_size)` | max tokens | O(tree size) | bounded periodic maintenance |

Memory bound: configurable max-tokens-tracked (default: 4× the
GPU's KV capacity in tokens). LRU-prune on every `evict` callback
when above target.

### 2. CacheHitPredictor

Given a candidate request's token prefix, returns predicted
cache-hit length:

```python
def predict_cache_hit(self, request_tokens: List[int]) -> int:
    """Number of leading tokens predicted to be cache-hits."""
    matched_length = self.tree.query(request_tokens)
    # Align to block_size: cache hits are in block-sized chunks.
    return (matched_length // self.block_size) * self.block_size
```

Block-alignment is critical: vLLM's prefix cache works at block
granularity (block_size=32 for INT4 protected). Partial-block
matches don't count.

### 3. AdmissionPolicy

Given the radix tree state + the pending queue, return the
admission order:

```python
def order_admissions(self, pending: List[Request]) -> List[Request]:
    """Reorder by predicted hit rate (descending), then FCFS
    within ties to preserve fairness."""
    scored = [
        (-self.predictor.predict_cache_hit(req.tokens),
         req.arrival_time,
         req)
        for req in pending
    ]
    scored.sort()
    return [req for _, _, req in scored]
```

The negation on the first sort key gives descending order on
predicted hits. `arrival_time` as the tiebreaker preserves FCFS
within equal-hit groups.

**Fairness guard:** any request whose age > `max_starvation_seconds`
is admitted next regardless of predicted hit rate. Prevents
indefinite deferral when many high-hit requests keep arriving.

### 4. Pinning

Configurable list of "always-pinned" prefixes (typically the
deployment's system prompts):

```python
scheduler.pin_system_prompt(tokenizer.encode(SYSTEM_PROMPT))
```

Pinned prefixes are never LRU-pruned from the tree. They also get
a +∞ priority bonus during admission ordering (a request matching
a pinned prefix is admitted before any non-pinned-matching
request, regardless of hit length).

### 5. Telemetry

The scheduler reports:

| Metric | Meaning |
|---|---|
| `predicted_hits_total` | sum of predicted hit tokens across admissions |
| `realized_hits_total` | sum of actual block-reuse tokens (from vLLM's allocator stats) |
| `prediction_accuracy` | realized / predicted (target: >0.85) |
| `mean_hit_rate` | realized_hits / total_prompt_tokens |
| `admissions_reordered` | count of admissions where the chosen request was not the FCFS pick |
| `starvation_overrides` | count of fairness-guard activations |
| `tree_size_tokens` | current tree size for memory monitoring |

These land in the streaming-runner summary JSON alongside the
existing `int4_route_a_stats` and `attention_aggregator_stats`.

## Integration with INT4 protected

**No changes to the INT4 protected backend.** Specifically:

| Component | Status under v2 |
|---|---|
| `Int4ProtectedAttentionImpl` | unchanged |
| Forked vllm-flash-attn int4 kernel | unchanged |
| Protected-channel splice logic | unchanged |
| `block_size=32` requirement | accommodated (scheduler block-aligns predictions) |
| Sink-FP16 protection | unchanged |

The scheduler is a serving-layer feature. The kernel + backend are
quantization-layer features. They compose because they decide
different things.

**Composition test (CPU):** the v2 scheduler is tested against a
mock vLLM block allocator that simulates the INT4 protected
backend's block_size constraint. No real GPU work needed for the
correctness gate.

## Implementation phases

| Phase | Scope | Effort | GPU $ |
|---|---|---|---|
| **Phase 0** (this commit) | Design doc + CPU prototype + CPU tests | 1-2 days | 0 |
| Phase 1 | vLLM integration: hook into `AsyncLLMEngine` admission queue | 3-5 days | ~$0.10 smoke |
| Phase 2 | Telemetry plumbing into streaming runner summary | 1-2 days | 0 (rides on existing infra) |
| Phase 3 | GPU validation on chat_32k workload (target: 2× hit rate vs FCFS) | 2-3 days | ~$0.30 |
| Phase 4 | System-prompt pinning API + partner-facing config | 2 days | ~$0.05 |
| **Total to ship** | **~10-15 engineer-days + ~$0.45 GPU** | | |

This commit lands **Phase 0 only**. Subsequent phases are gated on
this design being reviewed and the CPU tests being green.

## Phase 0 — CPU verification spec

The CPU prototype must satisfy:

1. **`PrefixRadixTree` correctness**
   - Insert + query round-trip preserves token sequences
   - Insert + evict + query reflects post-eviction state
   - LRU prune respects pinned prefixes
   - Tree size stays bounded under repeated insert+evict cycles

2. **`CacheHitPredictor` accuracy**
   - Block-aligned matches return exact block-aligned lengths
   - Partial-block matches return the floor (block-aligned) length
   - Empty tree returns 0
   - Pinned prefix always reports full hit (regardless of LRU state)

3. **`AdmissionPolicy` correctness**
   - Descending sort by predicted hit
   - FCFS tiebreaker within equal-hit groups
   - Starvation guard: request older than threshold admitted next

4. **Composition with mock INT4 protected vLLM**
   - Mock allocator with `block_size=32`
   - Scheduler emits admission order
   - Mock vLLM admits in order, reports realized hits
   - `prediction_accuracy >= 0.85` on synthetic chat_32k-shaped
     traces

All four gates are GPU-free. They run in the existing
`Bench/tests/` suite with `pytest`.

## GPU validation spec (Phase 3, gated on Phase 0 + 1 + 2)

Once integrated, the v2 scheduler is validated against the same
chat_32k workload used in the INT4 protected Tier A:

| Cell | Configuration | Measurement |
|---|---|---|
| Baseline | INT4 protected + vLLM default FCFS | hit rate, TPS, completed requests |
| v2 | INT4 protected + v2 cache-aware scheduler | hit rate (target: ≥2× baseline), TPS (target: no regression) |
| v2 + pinning | + system prompt pinned | hit rate on system-prompt-bearing requests (target: ≥0.95) |

Gates for Phase 3 GREEN:
- Cache hit rate at least 2× baseline on multi-turn chat
- TPS within ±5% of baseline (cache wins offset scheduling
  overhead)
- No regression on INT4 protected's existing measurements (needle
  retrieval, bit-identical greedy)

If any cell fails, the scheduler is retired from the v2 roadmap;
the INT4 protected backend ships without it.

## Risk analysis

| Risk | Mitigation |
|---|---|
| Radix tree memory grows unbounded under sustained load | Bounded LRU prune; configurable max-tokens; reported in telemetry |
| Tree falls out of sync with vLLM's actual cache state | All inserts/evictions are callback-driven from vLLM's allocator events, not periodic polling |
| Scheduler overhead exceeds cache-hit savings | Bench measures wall-clock per admission decision; budget <100µs/decision |
| Starvation under heavy hit-rate optimization | Fairness guard with configurable `max_starvation_seconds` (default 30s) |
| Composition with INT4 protected breaks | CPU composition test against mock backend; Phase 3 GPU verification |
| Tokenizer mismatch between scheduler and vLLM | Scheduler uses vLLM's tokenizer directly; no parallel tokenization |
| Disagreement with vLLM's own scheduler | The v2 scheduler runs BEFORE vLLM's scheduler in the admission flow. It chooses which request to enqueue; vLLM still handles within-request scheduling, preemption, etc. |

## Out of scope (for v2)

* **Distributed cache coordination** across multiple GPU nodes — different problem, requires shared-state design
* **Cross-model prefix sharing** — same prompt across different models would need model-specific tokenization; not in v2
* **KV migration** between GPU and disk/CXL — different layer entirely
* **Inventing new eviction algorithms** — explicitly out per Phase 4 retirement; v2 uses vLLM's existing LRU + block-level prefix caching
* **Modifying the INT4 protected backend** — orthogonal layer
* **Custom radix attention kernel** — we reuse SGLang-style scheduling, not their attention kernel

## File layout

```
CTM_plus/
├── Bench/scripts/V2_CACHE_REUSE_DESIGN.md          ← this doc
├── KVPolicy/kv_policy/cache_aware_scheduler.py     ← Phase 0 CPU prototype
└── Bench/tests/test_cache_aware_scheduler.py       ← Phase 0 CPU tests
```

## References

- SGLang RadixAttention: https://github.com/sgl-project/sglang
  (the radix-tree-based prefix-aware scheduling pattern this design
  ports to vLLM)
- vLLM PrefixCachingBlockAllocator: existing block-level prefix
  cache; the substrate this scheduler runs on top of
- INT4 protected backend: `INT4_PROTECTED_VC_BRIEF.md` —
  the quantization layer this composes with
- Phase 4 KV eviction retirement: `PHASE8_RETIREMENT.md` — what
  this design deliberately does NOT do (no attention-based scoring,
  no custom eviction algorithm)

## Open questions

1. **Block_size mismatch handling.** vLLM defaults to block_size=16;
   INT4 protected forces block_size=32. The scheduler should query
   the active backend's block_size at install time, not hard-code.
2. **Multi-tenant pinning.** If multiple deployments share the same
   GPU pool, system-prompt pinning policies may conflict. v2 ships
   single-tenant; multi-tenant is a v3 question.
3. **Adaptive `max_starvation_seconds`.** Fixed 30s may be wrong
   for some workloads. Phase 4 of v2 can add adaptive tuning if
   Phase 3 measurements show starvation issues.

None of these block Phase 0.
