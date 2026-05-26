# Phase 4A — vLLM 0.7.3 LRU evictor hook research note

> **Status:** Phase 4A CPU work. Documents the candidate paths the
> ``install_extended_pinning`` wrap tries when locating vLLM's LRU
> evictor + how it intercepts ``evict()``. Real-vLLM verification
> deferred to Phase 4C on a GPU pod.
>
> **Phase 4D placeholder:** when the GPU measurement lands, a
> companion ``PHASE4_EXTENDED_PINNING_FINDINGS.md`` will document
> ship-signal / inconclusive / negative findings (modeled on
> ``PHASE3_CACHE_AWARE_FINDINGS.md``). Not drafted upfront per
> Phase 4A scope.

## Why this exists

The Phase 4A install needs to filter pinned candidates out of the
LRU evictor's victim pool when vLLM faces memory pressure. There
is no public vLLM API for "this block is high-priority"; we must
monkey-patch the evictor's ``evict()`` method (or its candidate
lookup) instead.

The contract:

1. Locate the LRU evictor instance reachable from
   ``block_manager``.
2. Wrap its ``evict()`` so pinned blocks are temporarily removed
   from the candidate pool before delegating to the original.
3. Restore the stashed blocks after the eviction completes.
4. Failsafe: if the entire pool is pinned (over-pin scenario),
   restore everything + call the original anyway, incrementing
   ``forced_pin_evictions``.

## What vLLM 0.7.3 exposes (best-known shape)

vLLM 0.7.3 has the same V1/V2 block-manager split we already hit
in Phase 3C. The evictor lives at different attribute paths in
each:

### V1 block manager (``vllm/core/block_manager_v1.py``)

* ``block_manager.gpu_allocator`` is a ``BlockAllocator``.
* When ``enable_prefix_caching=True``, ``gpu_allocator`` is a
  ``PrefixCachingBlockAllocator`` (subclass).
* The evictor: ``gpu_allocator.evictor`` is an ``LRUEvictor``.
* LRUEvictor maintains ``self.free_table: Dict[block_number,
  evict_metadata]`` — content_hash → block-with-metadata.
* ``evict()`` pops the LRU-most entry and returns its metadata
  (the exact return type is vLLM-version-specific; we don't
  fabricate it, we just stash candidates and delegate).

### V2 block manager (``vllm/core/block_manager_v2.py``)

* ``block_manager.block_allocator`` is a ``CpuGpuBlockAllocator``.
* Per-device sub-allocators at
  ``block_allocator._allocators[Device.GPU]`` (dict form) OR
  exposed via a ``.gpu_allocator`` property in some 0.7.x
  variants.
* GPU sub-allocator (under prefix caching) is a
  ``PrefixCachingBlockAllocator`` with an ``evictor`` attribute.
* Evictor shape matches V1: ``free_table: Dict``, ``evict()``.

## Paths the install tries (in order)

```
_resolve_evictor(block_manager):
  1. block_manager.block_allocator.gpu_allocator.evictor    -> V2 property form
  2. block_manager.block_allocator._allocators[GPU].evictor -> V2 dict form
  3. block_manager.gpu_allocator.evictor                    -> V1 direct
  4. (none)                                                 -> "no_known_path"
```

The ``evictor_path_taken`` field in ``ExtendedPinningInstall.stats()``
reports which path matched. ``no_known_path`` means the evictor
wrap was not installed; the install completes anyway in
**allocate-wrap-only mode** (the manager still tracks pinned
blocks via the allocate wrap, but no evictions are filtered —
useful for telemetry-only measurement).

## free_table introspection

The evictor wrap reads ``evictor.free_table`` and:

1. Iterates its keys.
2. For each key the ``PinningManager`` reports as pinned, pops
   it out of ``free_table`` into a ``stashed`` dict.
3. Calls ``original_evict()`` — sees only unpinned candidates.
4. In the ``finally`` block, restores ``stashed`` back into
   ``free_table`` so future ``evict()`` calls still see them.
5. If ALL candidates were pinned, restores everything + calls
   ``original_evict()`` anyway (forced eviction; counter logged).

If ``evictor.free_table`` is not a dict, the install records
``evictor_path_taken="<path>+no_free_table"`` and falls back to
allocate-wrap-only mode. Future iteration could try other
introspection strategies (e.g., walk a private list attribute,
add a ``evictor.remove()`` API) — see "Recovery options" below.

## Why stash-and-restore (not retry-and-skip)

Two strategies for filtering pinned candidates:

**Strategy A (chosen) — stash before, restore after.** The
original evict never sees pinned candidates. Single ``evict()``
call. Clean accounting.

**Strategy B (rejected) — call original, check result, retry if
pinned.** Requires PUSHING the pinned candidate back into the
pool (vLLM's exact "push back" API is version-specific) AND
risks depleting the pool through repeated pops.

Strategy A's only requirement is that ``free_table`` is mutable
(true for ``dict``). Strategy B requires knowing vLLM's full
evictor API, which we don't, especially across minor versions.

## Counter semantics

* ``pinned_evictions_avoided`` increments by ``len(stashed)`` per
  ``evict()`` call — i.e., per-pinned-block-skipped, not per-call.
  Operators reading "we protected 47 blocks across 12 evictions"
  is more informative than "12 evictions saw pinned candidates".
* ``forced_pin_evictions`` increments by 1 each time the
  pool-entirely-pinned failsafe fires. Persistent non-zero means
  the budget is set too high relative to working-set demand and
  pinning is actively hurting cache turnover.
* ``pin_budget_rejections`` increments at allocate-time when a
  new pin candidate exceeds ``max_budget_blocks``. Operators
  should size the budget so this stays near zero in steady state.

## Verification plan (Phase 4C, on GPU)

After landing Phase 4B (driver wiring + bench), Phase 4C runs the
three cells (LRU only / LRU+prefix / LRU+prefix+pinning) on
Qwen-7B + H100 + vLLM 0.7.3 with at least one ``PinSpec``
covering the shared system prompt. The first GPU smoke verifies:

1. ``stats()['evictor_path_taken']`` is one of the documented
   paths (NOT ``no_known_path``).
2. ``stats()['pinned_blocks_total']`` > 0 (the allocate wrap
   actually marked something).
3. Under memory pressure (workload large enough to force
   evictions), ``stats()['pinned_evictions_avoided']`` > 0 (the
   evictor wrap actually filtered candidates).
4. No engine crashes (LRUEvictor's invariants still hold).

If 1 returns ``no_known_path`` or ``+no_free_table``, the install
runs in allocate-wrap-only mode. Phase 4D would still produce a
finding doc — pinning is being TRACKED but not ENFORCED, which
is itself a partner-credible measurement of "is there a pinning
opportunity on this workload?" (i.e., would the evictor have
picked pinned blocks if it had been allowed to?).

## Recovery options if every path fails

If the V1/V2 paths above don't match real vLLM 0.7.3, fallback
options (in order of escalating effort):

1. **Inspect the live evictor on the GPU pod**, find the actual
   attribute names, iterate the path list above.
2. **Replace the evictor instance entirely.** Subclass
   ``LRUEvictor`` (vendoring the vLLM class) and swap it onto
   the allocator at install time. Higher coupling but bypasses
   attribute discovery.
3. **Allocate-wrap-only mode permanently.** Stop trying to
   intercept the evictor; instead, track pinned blocks via the
   allocate wrap + measure "what WOULD the evictor have done"
   via a probe. This drops the enforcement guarantee but keeps
   the measurement value. Useful as a partner story:
   "we can identify the pinning opportunity even without
   enforcing it; enforcement is a vLLM-internal patch."
4. **Patch vLLM directly.** Add a ``priority_blocks`` API
   upstream or to a vendored fork. ~50 lines of vLLM-side code.
   Out of Phase 4 scope unless 1-3 all fail.

These are NOT committed work; they are notes for the next visit.

## Module + test references

| Component | Location |
|---|---|
| Install + manager | ``KVPolicy/kv_policy/extended_pinning.py`` |
| CPU tests | ``Bench/tests/test_extended_pinning.py`` |
| Phase 3 audit precedent | ``Bench/scripts/V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md`` §"Post-closure audit fixes" |
| Phase 3 finding doc precedent | ``Bench/scripts/PHASE3_CACHE_AWARE_FINDINGS.md`` |
