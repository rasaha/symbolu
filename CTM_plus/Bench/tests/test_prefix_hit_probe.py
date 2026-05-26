"""Phase 3A CPU tests for the prefix-hit probe.

Validates ``kv_policy.prefix_hit_probe.install_prefix_hit_probe``
against mock allocators that match the V1 and V2 vLLM 0.7.x
shapes plus a "no known path" fallback.

Acceptance gates exercised:

* Install + teardown wrap mechanics.
* Native-counter path (mock allocator exposes ``cache_hits``):
  counter delta is recorded per allocate.
* Cached-blocks-derived path (mock exposes ``_cached_blocks``,
  no native counter): chunk-hash matches counted per allocate.
* No-known-path fallback: wrap installs as a structural no-op;
  ``path_taken == "no_known_path"``; allocates still delegate
  cleanly to the original.
* Stats dict shape + idempotent teardown.

No torch, no vllm, no GPU. Real-vLLM verification deferred to
Phase 3C (the cell B/C bench harness needs a real H100 + vLLM
0.7.3 to confirm the attribute names this probe targets).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

from kv_policy.prefix_hit_probe import (
    PrefixHitProbe,
    _content_hash_of_chunk,
    _count_block_hits_from_cached_blocks,
    install_prefix_hit_probe,
)


# ---------------------------------------------------------------- #
# Mock vLLM allocator shapes
# ---------------------------------------------------------------- #


class _MockSequence:
    def __init__(self, prompt: List[int]):
        self._prompt = list(prompt)

    def get_prompt_token_ids(self) -> List[int]:
        return list(self._prompt)


class _MockSequenceGroup:
    def __init__(self, prompt: List[int]):
        self._seqs = [_MockSequence(prompt)]

    def get_seqs(self) -> List[_MockSequence]:
        return list(self._seqs)


class _NativeCounterAllocator:
    """V2-shaped GPU allocator that exposes ``cache_hits`` native
    counter. The probe should pick the ``native_counter`` path."""

    def __init__(self) -> None:
        self.cache_hits: int = 0

    def fake_increment_hits(self, n: int) -> None:
        self.cache_hits += n


class _CachedBlocksAllocator:
    """V2-shaped GPU allocator that exposes ``_cached_blocks`` (dict)
    but no native counter. The probe should pick the
    ``cached_blocks_derived`` path."""

    def __init__(self) -> None:
        self._cached_blocks: Dict[int, Any] = {}

    def seed_with_chunks(self, *, chunks: List[List[int]]) -> None:
        for chunk in chunks:
            self._cached_blocks[_content_hash_of_chunk(chunk)] = object()


class _UnknownShapeAllocator:
    """GPU allocator with neither counter nor _cached_blocks. Probe
    should mark path_taken='no_known_path' and structurally no-op."""
    pass


class _MockBlockAllocatorV2:
    """V2 CpuGpuBlockAllocator-shaped wrapper exposing
    ``gpu_allocator``."""

    def __init__(self, gpu: Any) -> None:
        self.gpu_allocator = gpu


class _MockBlockSpaceManagerV2:
    """V2 BlockSpaceManager-shaped mock with .allocate + .block_allocator
    pointing to a V2 wrapper."""

    def __init__(self, *, gpu: Any):
        self.block_allocator = _MockBlockAllocatorV2(gpu)
        self.allocate_calls: int = 0
        self.last_seq_group: Any = None

    def allocate(self, seq_group: Any) -> None:
        self.allocate_calls += 1
        self.last_seq_group = seq_group


class _MockBlockSpaceManagerV1:
    """V1 BlockSpaceManager-shaped mock with .allocate + .gpu_allocator
    directly (legacy path)."""

    def __init__(self, *, gpu: Any):
        self.gpu_allocator = gpu
        self.allocate_calls: int = 0

    def allocate(self, seq_group: Any) -> None:
        self.allocate_calls += 1


# ---------------------------------------------------------------- #
# install_prefix_hit_probe — mechanics
# ---------------------------------------------------------------- #


def test_install_with_enable_false_returns_no_op_probe() -> None:
    """``enable=False`` → no wrap, no measurement; stats remain at
    zero. Used by the runner when the user hasn't opted into
    ``--collect-native-prefix-hits``."""
    bm = _MockBlockSpaceManagerV2(gpu=_NativeCounterAllocator())
    original_allocate = bm.allocate
    probe = install_prefix_hit_probe(
        block_manager=bm, block_size=32, enable=False,
    )
    assert probe.path_taken == "no_known_path"
    # No wrap applied — bound method unchanged.
    assert bm.allocate.__func__ is original_allocate.__func__
    # Stats reflect uninstalled state.
    s = probe.stats()
    assert s["cache_hit_blocks"] == 0
    assert s["allocate_calls"] == 0


def test_install_rejects_missing_allocate() -> None:
    """Caller bug: passing an object without .allocate raises."""
    class _NoAllocate:
        pass
    with pytest.raises(AttributeError, match="allocate"):
        install_prefix_hit_probe(block_manager=_NoAllocate())


# ---------------------------------------------------------------- #
# Native-counter path
# ---------------------------------------------------------------- #


def test_native_counter_path_records_per_call_deltas() -> None:
    """When the allocator exposes a native counter, the probe
    snapshots it before/after each allocate and accumulates
    deltas."""
    gpu = _NativeCounterAllocator()
    gpu.cache_hits = 0
    bm = _MockBlockSpaceManagerV2(gpu=gpu)
    probe = install_prefix_hit_probe(block_manager=bm, block_size=32)
    try:
        assert probe.path_taken == "native_counter"
        assert probe.vllm_version_hint == "v2_block_allocator.gpu_allocator"
        # First allocate: vLLM "increments" the counter by 3 (simulated).
        def _allocate_then_increment(seq_group):
            gpu.fake_increment_hits(3)
        # Replace the original allocate so it increments the counter.
        # The wrap captured the previous original; we patch the
        # bm's stored original via the closure path. Simpler: just
        # call the wrap, manually increment counter inside.
        # Easier still: trigger the wrap directly and assert the
        # accumulated delta.
        gpu.cache_hits = 5   # pretend baseline is 5 (probe captured 0
                              # at install time; first .allocate's
                              # before-snapshot reads 5 → delta = 0).
        bm.allocate(_MockSequenceGroup([1, 2, 3]))
        # Counter didn't change inside .allocate (mock allocate is a
        # no-op) so delta = 0 → no hits recorded for this call.
        assert probe.cache_hit_blocks == 0
        # Manually simulate vLLM incrementing the counter inside
        # the next .allocate.
        gpu.cache_hits = 7
        bm.allocate(_MockSequenceGroup([1, 2, 3]))
        # before-snapshot for this call reads 7 (current); after-call
        # also reads 7 (mock didn't change it). So delta is still 0.
        # The native-counter path correctness depends on vLLM actually
        # incrementing the counter inside its .allocate. We can't
        # simulate that cleanly from outside the mock. Instead,
        # verify the wrap COUNTS calls and READS the counter on
        # each entry.
        assert probe.calls == 2
    finally:
        probe.teardown()


def test_native_counter_path_with_counter_increment_inside_allocate() -> None:
    """A more faithful native-counter test: the mock allocate
    increments the counter, and the probe records the delta."""

    gpu = _NativeCounterAllocator()
    gpu.cache_hits = 0

    class _BMWithCounterIncrement(_MockBlockSpaceManagerV2):
        def __init__(self, gpu: Any, increment_per_call: int):
            super().__init__(gpu=gpu)
            self._inc = increment_per_call

        def allocate(self, seq_group: Any) -> None:
            super().allocate(seq_group)
            gpu.cache_hits += self._inc

    bm = _BMWithCounterIncrement(gpu=gpu, increment_per_call=2)
    probe = install_prefix_hit_probe(block_manager=bm, block_size=32)
    try:
        assert probe.path_taken == "native_counter"
        bm.allocate(_MockSequenceGroup([1, 2, 3, 4]))
        bm.allocate(_MockSequenceGroup([5, 6, 7, 8]))
        bm.allocate(_MockSequenceGroup([9, 10, 11, 12]))
        # 3 calls × 2 increment per call = 6 blocks total.
        assert probe.cache_hit_blocks == 6
        assert probe.cache_hit_tokens == 6 * 32
        assert probe.calls == 3
    finally:
        probe.teardown()


# ---------------------------------------------------------------- #
# Cached-blocks-derived path
# ---------------------------------------------------------------- #


def test_cached_blocks_derived_path_counts_chunk_hash_matches() -> None:
    """When the allocator has no native counter but DOES expose
    ``_cached_blocks``, the probe block-chunks the prompt and
    counts how many chunks' content_hashes appear in the dict."""
    block_size = 4
    gpu = _CachedBlocksAllocator()
    # Pre-seed the cache with two specific 4-token chunks. Requests
    # whose prompts start with these chunks should be counted as
    # 1-block hits each.
    seed_chunks = [
        [11, 12, 13, 14],
        [21, 22, 23, 24],
    ]
    gpu.seed_with_chunks(chunks=seed_chunks)
    bm = _MockBlockSpaceManagerV2(gpu=gpu)
    probe = install_prefix_hit_probe(
        block_manager=bm, block_size=block_size,
    )
    try:
        assert probe.path_taken == "cached_blocks_derived"
        # Request 1: prompt's first 4-token chunk matches seed_chunks[0].
        # Second 4-token chunk is new → 1 hit.
        prompt_1 = [11, 12, 13, 14, 99, 99, 99, 99]
        bm.allocate(_MockSequenceGroup(prompt_1))
        assert probe.cache_hit_blocks == 1, probe.stats()
        # Request 2: first chunk matches seed[1], second chunk new → 1 hit.
        prompt_2 = [21, 22, 23, 24, 88, 88, 88, 88]
        bm.allocate(_MockSequenceGroup(prompt_2))
        assert probe.cache_hit_blocks == 2, probe.stats()
        # Request 3: no matching chunks → 0 additional hits.
        prompt_3 = [77, 77, 77, 77, 66, 66, 66, 66]
        bm.allocate(_MockSequenceGroup(prompt_3))
        assert probe.cache_hit_blocks == 2, probe.stats()
        # All requests increment .calls.
        assert probe.calls == 3
        # Token-count = block-count * block_size.
        assert probe.cache_hit_tokens == 2 * block_size
    finally:
        probe.teardown()


def test_count_block_hits_handles_short_prompts() -> None:
    """Edge cases for the chunk-hit derivation helper."""
    # Empty prompt → 0 hits.
    assert _count_block_hits_from_cached_blocks(
        prompt_token_ids=[], block_size=4, cached_blocks={1: object()},
    ) == 0
    # Prompt shorter than block_size → 0 hits (tail isn't a full block).
    assert _count_block_hits_from_cached_blocks(
        prompt_token_ids=[1, 2], block_size=4, cached_blocks={1: object()},
    ) == 0
    # Empty cache → 0 hits.
    assert _count_block_hits_from_cached_blocks(
        prompt_token_ids=[1, 2, 3, 4], block_size=4, cached_blocks={},
    ) == 0


# ---------------------------------------------------------------- #
# No-known-path fallback
# ---------------------------------------------------------------- #


def test_no_known_path_installs_as_structural_no_op() -> None:
    """When neither native counter nor cached_blocks accessor is
    found, the probe still installs (wraps allocate) but counters
    stay at zero. The cell-comparison harness uses path_taken to
    flag this."""
    bm = _MockBlockSpaceManagerV2(gpu=_UnknownShapeAllocator())
    probe = install_prefix_hit_probe(block_manager=bm, block_size=32)
    try:
        assert probe.path_taken == "no_known_path"
        bm.allocate(_MockSequenceGroup([1, 2, 3]))
        bm.allocate(_MockSequenceGroup([4, 5, 6]))
        # Allocates still delegate; calls still counted.
        assert bm.allocate_calls == 2
        assert probe.calls == 2
        # But no hit measurement is possible on this shape.
        assert probe.cache_hit_blocks == 0
    finally:
        probe.teardown()


def test_v1_path_resolution() -> None:
    """V1 block-manager shape: ``.gpu_allocator`` directly on the
    manager, not via ``.block_allocator``."""
    gpu = _NativeCounterAllocator()
    bm = _MockBlockSpaceManagerV1(gpu=gpu)
    probe = install_prefix_hit_probe(block_manager=bm, block_size=32)
    try:
        assert probe.path_taken == "native_counter"
        assert probe.vllm_version_hint == "v1_block_manager.gpu_allocator"
    finally:
        probe.teardown()


# ---------------------------------------------------------------- #
# Teardown + stats
# ---------------------------------------------------------------- #


def test_teardown_reverts_allocate_wrap() -> None:
    bm = _MockBlockSpaceManagerV2(gpu=_NativeCounterAllocator())
    original = bm.allocate
    probe = install_prefix_hit_probe(block_manager=bm, block_size=32)
    # After install the bound method changes.
    assert bm.allocate is not original
    probe.teardown()
    # Bound-method identity recovers — verify via __func__ on the
    # restored method.
    assert bm.allocate.__func__ is _MockBlockSpaceManagerV2.allocate


def test_teardown_is_idempotent() -> None:
    bm = _MockBlockSpaceManagerV2(gpu=_NativeCounterAllocator())
    probe = install_prefix_hit_probe(block_manager=bm, block_size=32)
    probe.teardown()
    probe.teardown()  # safe to call again


def test_stats_dict_has_expected_keys() -> None:
    bm = _MockBlockSpaceManagerV2(gpu=_NativeCounterAllocator())
    probe = install_prefix_hit_probe(block_manager=bm, block_size=32)
    try:
        s = probe.stats()
        for key in (
            "installed", "path_taken", "vllm_version_hint",
            "cache_hit_blocks", "cache_hit_tokens",
            "allocate_calls", "block_size",
        ):
            assert key in s, key
    finally:
        probe.teardown()


def test_content_hash_of_chunk_is_deterministic() -> None:
    """Same chunk → same hash; different chunks → different hashes
    (with overwhelming probability)."""
    h1 = _content_hash_of_chunk([1, 2, 3, 4])
    h2 = _content_hash_of_chunk([1, 2, 3, 4])
    h3 = _content_hash_of_chunk([1, 2, 3, 5])
    assert h1 == h2
    assert h1 != h3
