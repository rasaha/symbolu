# Phase 3A — vLLM 0.7.3 native prefix-cache hit counter: research note

> **Status:** Phase 3A CPU work. Documents the paths the
> ``PrefixHitProbe`` tries when reading vLLM's native prefix-cache
> hit telemetry. Real-vLLM verification deferred to Phase 3C on a
> GPU pod.

## Why this exists

The Phase 3 cache-aware-vs-FCFS measurement compares three cells:

| Cell | `--cache-aware-scheduling` | `--enable-prefix-caching` |
|---|---|---|
| A — sanity | OFF | OFF |
| B — stock vLLM | OFF | **ON** |
| C — proposal | **ON** | **ON** |

For cells B and C to compare on the same metric, **both** need a
realized-prefix-hit count from vLLM's allocator state. Our PR-1
cache-aware install tracks hits in **our** radix tree, which only
exists in cell C. Cell B needs an independent measurement that
reads vLLM's allocator directly.

The probe is a measurement-only wrap of
``block_manager.allocate`` that:
1. Reads vLLM's per-call cache-hit state.
2. Sums across the workload.
3. Does NOT reorder admissions or modify block-table state.

It can compose with the PR-1 cache-aware install (innermost in
the call chain; cache-aware wraps over the probe wraps over the
original allocate) so cells B and C use the same measurement
machinery.

## What vLLM 0.7.3 exposes (best-known shape)

vLLM 0.7.3 has two block-manager generations live in-tree:

### V1 block manager (`vllm/core/block_manager_v1.py`)

Legacy path. Used by older configs / smaller models in 0.7.x.

* ``block_manager.gpu_allocator`` is a ``BlockAllocator`` instance.
* When prefix caching is enabled, the GPU allocator is a
  ``PrefixCachingBlockAllocator``.
* The allocator maintains ``self.cached_blocks: Dict[content_hash,
  PhysicalTokenBlock]``.
* Native hit counter: ``self.cache_hits`` (cumulative int, increments
  on each prefix-cache-hit allocation).
* Free-pool: ``self.evictor`` (LRUEvictor).

### V2 block manager (`vllm/core/block_manager_v2.py`)

Production path for vLLM 0.7.3 V0 engine. The shape that crashed
PR-2 (`BlockTable` wrapper, not `List[PhysicalTokenBlock]`).

* ``block_manager.block_allocator`` is a ``CpuGpuBlockAllocator``.
* The CpuGpu allocator owns per-device allocators:
  * ``CpuGpuBlockAllocator._allocators: Dict[Device, BlockAllocator]``
    or via a ``gpu_allocator`` property in some minor versions.
* The GPU allocator under prefix caching is a
  ``PrefixCachingBlockAllocator``.
* The PrefixCachingBlockAllocator maintains
  ``self._cached_blocks: Dict[int, Block]``.
* Native hit counter: best-known attribute is also ``self.cache_hits``
  (introduced in earlier 0.6.x and carried through 0.7.x). Some
  versions also expose ``self._num_cache_hits`` (private) or
  ``self.total_cache_hits``.

## Paths the probe tries (in order)

The probe resolves the GPU allocator first, then tries to find a
counter on it, then falls back to dict-keys derivation.

```
_resolve_gpu_allocator(block_manager):
  1. block_manager.block_allocator.gpu_allocator      -> V2 (property form)
  2. block_manager.block_allocator._allocators[GPU]   -> V2 (dict form)
  3. block_manager.gpu_allocator                       -> V1
  4. (none)                                            -> "no_known_path"

_try_native_counter(allocator):
  1. allocator.cache_hits        (canonical 0.7.x)
  2. allocator.num_cache_hits    (alt 0.6.x carry-over)
  3. allocator._num_cache_hits   (private; some versions)
  4. allocator.total_cache_hits  (alt; some forks)
  5. allocator.hit_count         (uncommon; defensive)

_get_cached_blocks_index(allocator):
  1. allocator._cached_blocks    (canonical)
  2. allocator.cached_blocks     (V1 path)
  3. allocator._block_hashes     (defensive fallback)
```

`path_taken` reports which path the install resolved:

* ``native_counter`` — best path; per-call counter delta gives an
  exact realized-hit count.
* ``cached_blocks_derived`` — fallback; chunk-hash the prompt and
  count keys in `_cached_blocks` that match. **Approximate** — see
  caveat below.
* ``no_known_path`` — neither resolution succeeded. The probe
  installs as a structural no-op and the cell-comparison harness
  should flag this in the per-cell JSON.

`vllm_version_hint` reports which allocator-resolution step
matched. Useful when a vLLM minor-version bump changes the API.

## Caveat — the cached_blocks-derived path

The fallback path hashes prompt chunks of size `block_size` and
checks whether the resulting hashes appear in the allocator's
`_cached_blocks` dict. **This is not vLLM's exact content_hash
function.** vLLM (>=0.5) chains each block's hash with its parent
block's hash to encode position, so two prompts with the same
first chunk but different second chunks produce different
content_hashes for blocks 2+ even though their token sequences
are identical. Our flat blake2b chunk hash does not chain.

Consequences:

* **First block:** flat-hash and chain-hash agree (no parent), so
  the probe correctly reports first-block hits.
* **Subsequent blocks:** flat-hash may under- or over-count
  relative to vLLM. On a chat-shaped workload with a long shared
  system prompt, the under-count is the realistic failure mode.

If the GPU smoke in Phase 3C lands on the `cached_blocks_derived`
path, the cell-comparison harness should:

1. Treat the probe number as an **upper bound** on realized hits
   for the first block, **lower bound** for subsequent blocks.
2. Cross-check by computing the same chunks in **both** cells B
   and C using the **same probe**, so any systematic bias is
   identical in both cells and cancels in the B/C comparison.

This is acceptable for the Phase 3 measurement goal: "is C
meaningfully better than B?" relies on the **ratio**, not the
absolute hit count.

## Verification plan (Phase 3C)

On the GPU pod with vLLM 0.7.3 installed:

1. Run the cell-B smoke from the Phase 3B harness.
2. Verify `streaming_summary.json` contains
   `native_prefix_hit_stats.path_taken == "native_counter"`.
3. If `path_taken == "cached_blocks_derived"`, the probe's
   counter values are approximate per the caveat above; flag in
   the cell-comparison JSON.
4. If `path_taken == "no_known_path"`, ask vLLM-internals
   questions (which version are we on; which attribute names are
   current). Most likely cause: vLLM version drift since this
   research note was written. Iterate the probe's attribute list.

## Recovery if every path fails

If GPU verification finds **all paths fail**, fallback options:

1. **Patch vLLM directly.** Add a small instrumentation hook to
   the ``PrefixCachingBlockAllocator.allocate_or_get_cached_block``
   path. ~10-15 lines; we vendor vLLM-fa already so vendoring the
   block-manager path is marginally more code than precedent.
2. **Use vLLM's metrics framework.** vLLM exposes Prometheus-style
   counters via ``LLMEngine.do_log_stats()``. There may be a
   ``vllm:prefix_cache_hit_rate`` Prometheus gauge in 0.7+; if so,
   read from that instead of the allocator directly.
3. **Approximate via block-count delta.** Track
   ``len(block_allocator.all_block_ids)`` (or analogous total-blocks-
   allocated counter) before and after. The delta tells us
   "blocks newly allocated"; cache hits = expected blocks - delta.
   Approximate but always-available.

These are not in Phase 3A scope; they're contingencies.

## References

* Code: `KVPolicy/kv_policy/prefix_hit_probe.py`
* CPU tests: `Bench/tests/test_prefix_hit_probe.py`
* Phase 3 design: `V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md`
* PR-2 retrospective on V1-vs-V2 BlockTable shape:
  `V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md` §"V2 block-manager
  shape fix (post-first-GPU-smoke)"
