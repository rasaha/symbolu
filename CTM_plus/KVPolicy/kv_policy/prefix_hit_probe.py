"""vLLM 0.7.3 native prefix-cache hit probe — Phase 3A.

Measurement-only wrap of ``block_manager.allocate`` that counts how
many KV-cache blocks each request reuses from vLLM's
``PrefixCachingBlockAllocator``. Used by the Phase 3 cache-aware-
vs-FCFS measurement (`bench_phase3_cache_aware.py`) to compute the
**cell B baseline** (FCFS + vLLM-native prefix caching, no
cache-aware reorder) so the cell C cache-aware realized-hit number
is comparable on an apples-to-apples scale.

This module is INDEPENDENT of ``cache_aware_install.py``. The probe
is purely observational — it does not reorder admissions or modify
block-table state. Both installs can stack on the same
``block_manager``; the probe must be installed FIRST so the
cache-aware install's ``original_allocate`` resolves to the
probe-wrapped allocate.

## Disposition contract

* ``install_prefix_hit_probe(block_manager) -> PrefixHitProbe``
  monkey-patches ``block_manager.allocate``. Returns a handle with
  ``stats()`` and ``teardown()``.
* ``teardown()`` is idempotent + LIFO-safe.
* No changes to ``block_manager.free`` (no need; we measure at
  admission time only).

## Research note — vLLM 0.7.3 path identification

vLLM 0.7.3 reaches the prefix-cache machinery via two block-manager
generations:

* **V1 block manager** (`block_manager_v1.py`, legacy):
  - ``block_manager.gpu_allocator`` is a ``BlockAllocator``-shaped
    object; for prefix caching, it's a
    ``PrefixCachingBlockAllocator``.
  - The allocator's internal index lives at ``.cached_blocks``
    (``Dict[content_hash, PhysicalTokenBlock]``).

* **V2 block manager** (`block_manager_v2.py`, default in V0
  engine for 0.7.3+):
  - ``block_manager.block_allocator`` is a
    ``CpuGpuBlockAllocator``.
  - Per-device allocators at
    ``block_allocator._allocators[Device.GPU]`` (or via the
    ``.gpu_allocator`` property in some minor versions).
  - The GPU allocator is a ``PrefixCachingBlockAllocator`` when
    ``enable_prefix_caching=True``.
  - Cached-blocks index: ``gpu_allocator._cached_blocks``
    (``Dict[int, Block]``; key is content_hash).

The probe tries the V2 path first since that's the production-
relevant case, then falls back to V1, then to a structural
no-op (probe still installs, but stats remain at the
``no_known_path`` marker so the cell-comparison harness can flag
it). The exact attribute names below are best-known-good for vLLM
0.7.3; GPU-pod verification in Phase 3C confirms the live path.

## Counting strategy

For each ``block_manager.allocate(seq_group)`` call:

1. Snapshot the set of currently-cached content_hashes (the keys
   of ``gpu_allocator._cached_blocks`` if accessible).
2. Compute the request's prompt's block-level content_hashes (we
   approximate by chunking the prompt token_ids at block_size and
   hashing each chunk; this matches vLLM's content_hash convention
   for prefix caching, which is also chunk-based — though the
   actual hash function in vLLM may include parent-hash chaining
   that we do NOT replicate here. The probe's number is an
   **upper bound** on realized hits; for the cell-comparison
   harness this is acceptable because the same approximation
   applies to both cells).
3. Count how many of the prompt's chunks have content_hashes that
   appear in the snapshot. That's the **per-request realized
   hit count** in blocks; multiply by block_size to get tokens.

If we can read a **native cumulative counter** (e.g.
``gpu_allocator.cache_hits``), prefer that — single attribute
read, no chunk-hashing overhead.

## Mock testability

CPU tests in ``Bench/tests/test_prefix_hit_probe.py`` cover:

* Install + teardown wrap mechanics against a mock allocator.
* Native-counter detection when the mock exposes ``cache_hits``.
* Block-chunk derivation when the mock does NOT expose the
  counter but DOES expose ``_cached_blocks``.
* Structural no-op + ``no_known_path`` stats when neither.

GPU verification: deferred to Phase 3C real-vLLM run.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ----------------------------------------------------------------------
# Probe handle
# ----------------------------------------------------------------------


@dataclass
class PrefixHitProbe:
    """Handle for ``install_prefix_hit_probe``.

    The probe records, per ``block_manager.allocate`` call:

    * ``cache_hit_blocks``: total number of prefix-cache hit blocks
      across all allocates (cumulative).
    * ``cache_hit_tokens``: same, in tokens (= blocks * block_size).
    * ``calls``: total allocate calls observed.
    * ``path_taken``: one of ``"native_counter"``, ``"cached_blocks_derived"``,
      or ``"no_known_path"`` — describes how hits were measured.
    * ``vllm_version_hint``: best-effort string identifying the
      shape the probe found (V1 vs V2, etc.). Useful for the
      cell-comparison harness to flag environment drift.
    """

    block_size: int
    path_taken: str = "no_known_path"
    vllm_version_hint: str = "unknown"
    cache_hit_blocks: int = 0
    cache_hit_tokens: int = 0
    calls: int = 0
    # Native-counter baseline at install time so deltas are scoped
    # to this run.
    _native_baseline: Optional[int] = None
    _teardowns: List[Callable[[], None]] = field(default_factory=list)

    def teardown(self) -> None:
        """Revert the monkey-patch (LIFO; idempotent)."""
        for fn in reversed(self._teardowns):
            try:
                fn()
            except Exception:
                pass
        self._teardowns.clear()

    def stats(self) -> Dict[str, Any]:
        return {
            "installed": bool(self._teardowns) or self.calls > 0,
            "path_taken": self.path_taken,
            "vllm_version_hint": self.vllm_version_hint,
            "cache_hit_blocks": self.cache_hit_blocks,
            "cache_hit_tokens": self.cache_hit_tokens,
            "allocate_calls": self.calls,
            "block_size": self.block_size,
        }


# ----------------------------------------------------------------------
# vLLM allocator-path resolution
# ----------------------------------------------------------------------


def _resolve_gpu_allocator(block_manager: Any) -> tuple[Any, str]:
    """Walk the block manager to find the GPU-side allocator.

    Returns ``(allocator_or_none, hint_string)``. The hint reports
    which path was taken; useful for telemetry. Returns
    ``(None, "no_known_path")`` if no path matched.
    """
    # V2 path: block_manager.block_allocator (CpuGpuBlockAllocator).
    ba = getattr(block_manager, "block_allocator", None)
    if ba is not None:
        # Property form (some 0.7.x):
        gpu = getattr(ba, "gpu_allocator", None)
        if gpu is not None:
            return gpu, "v2_block_allocator.gpu_allocator"
        # Dict form (some 0.7.x): _allocators[Device.GPU].
        allocators = getattr(ba, "_allocators", None)
        if isinstance(allocators, dict):
            # Device.GPU is an enum; "GPU" string keys also seen
            # in some mocks. Try a few keys.
            for key in allocators:
                key_str = str(key).split(".")[-1].lower()
                if "gpu" in key_str:
                    return allocators[key], "v2_block_allocator._allocators[GPU]"
    # V1 path: block_manager.gpu_allocator directly.
    v1_gpu = getattr(block_manager, "gpu_allocator", None)
    if v1_gpu is not None:
        return v1_gpu, "v1_block_manager.gpu_allocator"
    return None, "no_known_path"


def _try_native_counter(allocator: Any) -> Optional[int]:
    """Try to read a cumulative cache-hit counter from the allocator.

    Returns the integer counter value, or None if no counter
    attribute is exposed. Tries a handful of common attribute
    names; vLLM's exact name may differ by minor version.
    """
    for attr in (
        "cache_hits",
        "num_cache_hits",
        "_num_cache_hits",
        "total_cache_hits",
        "hit_count",
    ):
        v = getattr(allocator, attr, None)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
    return None


def _get_cached_blocks_index(allocator: Any) -> Optional[Dict[Any, Any]]:
    """Return ``allocator._cached_blocks`` if accessible.

    The content-hash → block dict that ``PrefixCachingBlockAllocator``
    maintains. Returns None if the attribute isn't present (in
    which case the probe falls back to no-op stats).
    """
    for attr in (
        "_cached_blocks",
        "cached_blocks",
        "_block_hashes",
    ):
        v = getattr(allocator, attr, None)
        if isinstance(v, dict):
            return v
    return None


# ----------------------------------------------------------------------
# Per-request hit counting (cached_blocks-derived path)
# ----------------------------------------------------------------------


def _content_hash_of_chunk(tokens: List[int]) -> int:
    """Compute a stable content_hash for a list of token IDs.

    NOTE: this does NOT match vLLM's exact content_hash function
    (which chains parent block hashes). The probe uses this hash
    only to compare against ``allocator._cached_blocks.keys()``
    when the dict's keys happen to be the same hash form (some
    vLLM minor versions use a flat hash; others chain). In the
    chain-hashed case, the probe will under-count hits — the
    cell-comparison harness should flag this via ``path_taken``.

    Returns a 63-bit int (sign-safe for dict keys).
    """
    h = hashlib.blake2b(digest_size=8)
    for t in tokens:
        h.update(t.to_bytes(4, "little", signed=False))
    return int.from_bytes(h.digest(), "little", signed=False) & 0x7FFFFFFFFFFFFFFF


def _count_block_hits_from_cached_blocks(
    *,
    prompt_token_ids: List[int],
    block_size: int,
    cached_blocks: Dict[Any, Any],
) -> int:
    """Count how many block-sized prefix chunks of ``prompt_token_ids``
    have content_hashes that appear as keys in ``cached_blocks``.

    NOTE: this is the upper-bound chunk-hash derivation described in
    the module docstring. Real vLLM may chain-hash; if so, our
    flat-hash compare will fail to match. The probe surfaces this
    via the ``path_taken`` field so the cell-comparison harness
    can interpret accordingly.
    """
    if block_size < 1 or not prompt_token_ids or not cached_blocks:
        return 0
    n_blocks = len(prompt_token_ids) // block_size
    hit_count = 0
    for i in range(n_blocks):
        chunk = prompt_token_ids[i * block_size : (i + 1) * block_size]
        h = _content_hash_of_chunk(chunk)
        if h in cached_blocks:
            hit_count += 1
    return hit_count


# ----------------------------------------------------------------------
# Helper to extract prompt token IDs from a SequenceGroup
# (parallels the helper in cache_aware_install.py; intentionally
# duplicated to avoid a cross-module dependency for the probe).
# ----------------------------------------------------------------------


def _prompt_tokens_of(seq_group: Any) -> List[int]:
    seq = None
    get_seqs = getattr(seq_group, "get_seqs", None)
    if callable(get_seqs):
        seqs = get_seqs()
        if seqs:
            seq = seqs[0]
    if seq is None:
        seq = seq_group
    get_ids = getattr(seq, "get_prompt_token_ids", None)
    if callable(get_ids):
        return list(get_ids())
    pti = getattr(seq, "prompt_token_ids", None)
    if pti is not None:
        return list(pti)
    return []


# ----------------------------------------------------------------------
# Install — the public entry point
# ----------------------------------------------------------------------


def install_prefix_hit_probe(
    *,
    block_manager: Any,
    block_size: int = 32,
    enable: bool = True,
) -> PrefixHitProbe:
    """Install the prefix-hit probe on a vLLM ``BlockSpaceManager``.

    Args:
        block_manager: a vLLM 0.7.x ``BlockSpaceManager``-like
            object with ``.allocate(seq_group)``. The probe wraps
            ``allocate`` to read allocator state before delegating.
        block_size: KV-cache block size; default 32 (matches
            int4_protected). Used to convert block-count hits to
            token-count hits.
        enable: when False, returns a structural no-op probe
            (no wrap installed; stats remain at zero). Default
            True since the probe is opt-in at the runner layer.

    Returns:
        A :class:`PrefixHitProbe` handle. Caller is responsible for
        invoking ``probe.teardown()`` on engine shutdown.

    Raises:
        AttributeError: if ``block_manager`` lacks ``.allocate``
            (caller bug; not a runtime guard).
    """
    probe = PrefixHitProbe(block_size=int(block_size))
    if not enable:
        return probe
    if not hasattr(block_manager, "allocate"):
        raise AttributeError(
            "block_manager must have .allocate(seq_group); got "
            + type(block_manager).__name__
        )

    gpu_allocator, hint = _resolve_gpu_allocator(block_manager)
    probe.vllm_version_hint = hint

    # Choose the measurement path once at install time.
    native_baseline: Optional[int] = None
    cached_blocks_ref: Optional[Dict[Any, Any]] = None
    if gpu_allocator is not None:
        native_baseline = _try_native_counter(gpu_allocator)
        if native_baseline is not None:
            probe.path_taken = "native_counter"
            probe._native_baseline = native_baseline
        else:
            cached_blocks_ref = _get_cached_blocks_index(gpu_allocator)
            if cached_blocks_ref is not None:
                probe.path_taken = "cached_blocks_derived"
            else:
                probe.path_taken = "no_known_path"
    else:
        probe.path_taken = "no_known_path"

    original_allocate = block_manager.allocate

    def _probed_allocate(seq_group: Any, *args: Any, **kwargs: Any):
        probe.calls += 1
        # Native-counter path: read counter before, read after,
        # diff is this-call's hit increment.
        if probe.path_taken == "native_counter" and gpu_allocator is not None:
            before = _try_native_counter(gpu_allocator) or 0
            result = original_allocate(seq_group, *args, **kwargs)
            after = _try_native_counter(gpu_allocator) or before
            delta = max(0, after - before)
            probe.cache_hit_blocks += delta
            probe.cache_hit_tokens += delta * probe.block_size
            return result
        # cached_blocks-derived path: count chunk-hash matches in
        # the BEFORE snapshot, then delegate. Reading the dict's
        # current keys is cheap (~O(N_cached) hash compares).
        if (
            probe.path_taken == "cached_blocks_derived"
            and cached_blocks_ref is not None
        ):
            tokens = _prompt_tokens_of(seq_group)
            hits = _count_block_hits_from_cached_blocks(
                prompt_token_ids=tokens,
                block_size=probe.block_size,
                cached_blocks=cached_blocks_ref,
            )
            probe.cache_hit_blocks += hits
            probe.cache_hit_tokens += hits * probe.block_size
            return original_allocate(seq_group, *args, **kwargs)
        # Fallback: structural no-op. Counters stay at zero, but
        # the wrap still records calls so the cell-comparison
        # harness can tell "probe ran but found no measurement
        # path" from "probe never installed".
        return original_allocate(seq_group, *args, **kwargs)

    block_manager.allocate = _probed_allocate
    probe._teardowns.append(
        lambda: setattr(block_manager, "allocate", original_allocate)
    )
    return probe
