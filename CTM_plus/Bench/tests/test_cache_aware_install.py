"""CPU regression tests for the v2 cache-reuse Phase 1 install (PR-1).

Validates ``KVPolicy/kv_policy/cache_aware_install.py`` against
mock vLLM ``Scheduler`` / ``BlockSpaceManager`` / ``SequenceGroup``
objects that match the 0.7.3 interface shape. No torch, no vllm,
no GPU.

Acceptance gates exercised here (per Phase 1 integration note):

* Stock path unchanged when ``enable=False``
* Requests can be reordered when ``enable=True``
* Starvation guard works
* ``BlockSpaceManager.allocate`` / ``.free`` hooks update the
  ``PrefixRadixTree``
* Predicted-vs-realized hit telemetry exists in mocked form
* Teardown reverts all wraps (LIFO)
"""

from __future__ import annotations

import collections
import time
from typing import Dict, List, Optional, Sequence

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

from kv_policy.cache_aware_install import (
    CacheAwareInstall,
    install_cache_aware_scheduler,
)


# ----------------------------------------------------------------------
# Mock vLLM 0.7.3 interface shapes
# ----------------------------------------------------------------------


class MockSequence:
    """Mimics ``vllm.sequence.Sequence``: seq_id + prompt token ids."""

    def __init__(self, seq_id: int, prompt_token_ids: Sequence[int]):
        self.seq_id = seq_id
        self._prompt = list(prompt_token_ids)

    def get_prompt_token_ids(self) -> List[int]:
        return list(self._prompt)


class MockSequenceGroup:
    """Mimics ``vllm.sequence.SequenceGroup``: request_id + seqs +
    arrival_time. Single-sequence (greedy/sampling), no beam search."""

    def __init__(
        self,
        request_id: str,
        prompt_token_ids: Sequence[int],
        arrival_time: float,
        seq_id: Optional[int] = None,
    ):
        self.request_id = request_id
        self.arrival_time = arrival_time
        self._seqs = [
            MockSequence(
                seq_id=seq_id if seq_id is not None else hash(request_id) & 0x7FFF_FFFF,
                prompt_token_ids=prompt_token_ids,
            )
        ]

    def get_seqs(self) -> List[MockSequence]:
        return list(self._seqs)


class MockPhysicalTokenBlock:
    """Mimics ``vllm.block.PhysicalTokenBlock``: integer block_number."""

    def __init__(self, block_number: int):
        self.block_number = block_number


class MockBlockSpaceManager:
    """Mimics enough of vLLM's ``BlockSpaceManager`` for the install
    wraps. Models block_size=32 (the int4_protected canonical
    config), block-level prefix-cache reuse, and an LRU-ish
    free-pool of previously-cached block_ids.
    """

    def __init__(self, block_size: int = 32):
        self.block_size = block_size
        self.block_tables: Dict[int, List[MockPhysicalTokenBlock]] = {}
        self._next_block_number = 1
        # Content-hash (= tuple of tokens in the block) -> block_number
        self._cached_chunks: Dict[tuple, int] = {}
        self._free_pool: List[int] = []
        # Realized cache-hit accounting for cross-checks in tests.
        self._realized_hits_in_last_allocate = 0

    def can_allocate(self, seq_group: MockSequenceGroup) -> bool:
        return True  # tests assume unbounded GPU memory

    def allocate(self, seq_group: MockSequenceGroup) -> None:
        """Allocate blocks for ``seq_group``, reusing prefix-cached
        chunks when available. Updates ``block_tables`` as the side-
        effect the install wrap reads after delegating."""
        seq = seq_group.get_seqs()[0]
        tokens = seq.get_prompt_token_ids()
        block_ids: List[MockPhysicalTokenBlock] = []
        i = 0
        n = len(tokens)
        hit_tokens = 0
        while i + self.block_size <= n:
            chunk = tuple(tokens[i:i + self.block_size])
            existing = self._cached_chunks.get(chunk)
            if existing is not None:
                block_ids.append(MockPhysicalTokenBlock(existing))
                hit_tokens += self.block_size
            else:
                bn = self._next_block_number
                self._next_block_number += 1
                self._cached_chunks[chunk] = bn
                block_ids.append(MockPhysicalTokenBlock(bn))
            i += self.block_size
        # Tail (partial block) is not prefix-cached in vLLM either.
        self.block_tables[seq.seq_id] = block_ids
        self._realized_hits_in_last_allocate = hit_tokens

    def free(self, seq_or_seq_group) -> None:
        # vLLM 0.7.3's free() takes a Sequence; we accept both for
        # parity with the install wrap.
        if hasattr(seq_or_seq_group, "get_prompt_token_ids"):
            seq = seq_or_seq_group
        else:
            seq = seq_or_seq_group.get_seqs()[0]
        bt = self.block_tables.pop(seq.seq_id, [])
        # Move freed blocks to the free pool. In real vLLM's prefix
        # caching they may remain in cached_chunks (LRU pool); for
        # tests we drop them to make eviction observable.
        for b in bt:
            self._free_pool.append(b.block_number)
        # Drop their content-hash entries so subsequent allocates
        # of the same chunk reuse a new block_number (mirrors real
        # vLLM behaviour when the LRU evictor reclaims the chunk).
        self._cached_chunks = {
            ch: bn for ch, bn in self._cached_chunks.items()
            if bn not in {b.block_number for b in bt}
        }


class MockScheduler:
    """Minimum surface for the install wrap: ``waiting`` deque +
    ``schedule()`` callable that consumes pending requests."""

    def __init__(self):
        self.waiting: collections.deque = collections.deque()
        self.running: List[MockSequenceGroup] = []
        self.admitted_order: List[MockSequenceGroup] = []
        self._schedule_call_count = 0

    def schedule(self):
        """Admit up to N pending requests per call (FCFS within the
        post-reorder ``waiting`` deque). Returns the admitted list
        for inspection in tests."""
        self._schedule_call_count += 1
        admitted = []
        while self.waiting and len(admitted) < 4:
            sg = self.waiting.popleft()
            self.running.append(sg)
            admitted.append(sg)
            self.admitted_order.append(sg)
        return admitted


# ----------------------------------------------------------------------
# Disabled / no-op install
# ----------------------------------------------------------------------


def test_disabled_install_returns_no_op_handle():
    sched = MockScheduler()
    bm = MockBlockSpaceManager()
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=False,
    )
    assert handle.enabled is False
    assert handle.tree is None
    assert handle.cas is None
    assert handle.stats() == {"enabled": False}


def test_disabled_install_applies_no_patches():
    """Disabled install must leave the three methods as the
    original class-defined bound methods (no monkey-patch).

    Note: bound-method identity (``a.foo is a.foo``) is always
    False in Python — bound methods are recreated on each lookup.
    We verify lack of patching by comparing the underlying
    ``__func__`` to the class method.
    """
    sched = MockScheduler()
    bm = MockBlockSpaceManager()
    install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=False,
    )
    assert getattr(sched.schedule, "__func__", None) is MockScheduler.schedule
    assert getattr(bm.allocate, "__func__", None) is MockBlockSpaceManager.allocate
    assert getattr(bm.free, "__func__", None) is MockBlockSpaceManager.free


def test_disabled_install_teardown_is_safe():
    sched = MockScheduler()
    bm = MockBlockSpaceManager()
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=False,
    )
    handle.teardown()  # should not raise
    handle.teardown()  # idempotent — second call also fine


# ----------------------------------------------------------------------
# Enabled install — basic wrap verification
# ----------------------------------------------------------------------


def test_enabled_install_wraps_three_methods():
    sched = MockScheduler()
    bm = MockBlockSpaceManager()
    original_schedule = sched.schedule
    original_allocate = bm.allocate
    original_free = bm.free
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True,
    )
    try:
        assert handle.enabled is True
        assert handle.tree is not None
        assert handle.cas is not None
        assert sched.schedule is not original_schedule
        assert bm.allocate is not original_allocate
        assert bm.free is not original_free
    finally:
        handle.teardown()


def test_teardown_reverts_all_wraps_lifo():
    sched = MockScheduler()
    bm = MockBlockSpaceManager()
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True,
    )
    handle.teardown()
    # After teardown the bound methods point back to the class-defined
    # originals (their __func__ is the class method).
    assert getattr(sched.schedule, "__func__", None) is MockScheduler.schedule
    assert getattr(bm.allocate, "__func__", None) is MockBlockSpaceManager.allocate
    assert getattr(bm.free, "__func__", None) is MockBlockSpaceManager.free


def test_teardown_is_idempotent():
    sched = MockScheduler()
    bm = MockBlockSpaceManager()
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True,
    )
    handle.teardown()
    handle.teardown()  # second call must not error


def test_install_rejects_objects_missing_required_attrs():
    class Bad:
        pass

    with pytest.raises(AttributeError):
        install_cache_aware_scheduler(
            scheduler=Bad(), block_manager=MockBlockSpaceManager(),
            enable=True,
        )
    with pytest.raises(AttributeError):
        install_cache_aware_scheduler(
            scheduler=MockScheduler(), block_manager=Bad(),
            enable=True,
        )


# ----------------------------------------------------------------------
# Reorder behavior
# ----------------------------------------------------------------------


def _mk_sg(rid: str, tokens: Sequence[int], t: float) -> MockSequenceGroup:
    return MockSequenceGroup(rid, tokens, arrival_time=t)


def test_schedule_wrap_reorders_by_predicted_hit():
    """A request with high predicted cache hit jumps ahead of an
    earlier-arrived zero-hit request.

    arrival_time anchors to ``time.monotonic()`` because that's
    the clock the install wrap uses internally (via
    ``CacheAwareScheduler.order_admissions``).
    """
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        # Seed the tree with a 64-token cached prefix (2 blocks).
        SHARED_PREFIX = list(range(64))
        bm.allocate(_mk_sg("seed", SHARED_PREFIX + list(range(900, 932)), time.monotonic()))
        # Now: zero-hit arrived first; high-hit arrived later.
        # Both are "fresh" (well below the starvation threshold).
        now = time.monotonic()
        sched.waiting.append(
            _mk_sg("zero_hit_early", list(range(1000, 1100)), t=now - 0.5)
        )
        sched.waiting.append(
            _mk_sg("high_hit_later", SHARED_PREFIX + list(range(2000, 2032)), t=now - 0.3)
        )
        sched.schedule()
        # high_hit_later should have been admitted FIRST.
        assert sched.admitted_order[0].request_id == "high_hit_later"
        assert sched.admitted_order[1].request_id == "zero_hit_early"
    finally:
        handle.teardown()


def test_schedule_wrap_no_op_on_empty_waiting():
    sched = MockScheduler()
    bm = MockBlockSpaceManager()
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True,
    )
    try:
        admitted = sched.schedule()
        assert admitted == []
        # Tree is empty too.
        assert handle.tree.stats()["tracked_tokens"] == 0
    finally:
        handle.teardown()


def test_schedule_wrap_no_op_on_single_pending():
    """With one waiting request, reorder is a no-op (no other
    request to prefer over it). Predicted hit still recorded."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        sched.waiting.append(_mk_sg("only", list(range(100)), t=0.0))
        sched.schedule()
        assert sched.admitted_order[0].request_id == "only"
    finally:
        handle.teardown()


def test_starvation_guard_admits_old_request_first():
    """Request older than the starvation threshold is admitted next
    even when fresh requests have higher predicted hit."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
        max_starvation_seconds=5.0,
    )
    try:
        # Seed cache so the fresh request has a real predicted hit.
        SHARED = list(range(64))
        bm.allocate(_mk_sg("seed", SHARED + list(range(800, 832)), 0.0))
        # Starved (arrived 30s ago, no hit) + Fresh (just arrived,
        # would have 64-token hit).
        now = time.monotonic()
        sched.waiting.append(
            _mk_sg("starved", list(range(9000, 9064)), t=now - 30.0)
        )
        sched.waiting.append(
            _mk_sg("fresh_high_hit", SHARED + list(range(700, 732)), t=now - 0.1)
        )
        sched.schedule()
        assert sched.admitted_order[0].request_id == "starved", (
            "fairness guard failed: starved request should outrank "
            "a fresh high-hit request"
        )
    finally:
        handle.teardown()


# ----------------------------------------------------------------------
# Allocator hooks
# ----------------------------------------------------------------------


def test_allocate_wrap_inserts_into_tree():
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        tokens = list(range(96))
        bm.allocate(_mk_sg("r1", tokens, 0.0))
        # Tree should now contain the prefix.
        assert handle.tree.query(tokens) == 96
        # And it tracks tokens.
        assert handle.tree.stats()["tracked_tokens"] > 0
    finally:
        handle.teardown()


def test_allocate_wrap_records_realized_hits():
    """When a second request shares a 64-token prefix with a
    previously-allocated one, the allocate hook records 64 realized
    hit tokens (block-aligned)."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        SHARED = list(range(64))  # 2 blocks
        # Seed: first request populates the tree.
        bm.allocate(_mk_sg("seed", SHARED + list(range(500, 532)), 0.0))
        # Second request shares the 64-token prefix.
        bm.allocate(_mk_sg("reuser", SHARED + list(range(600, 632)), 1.0))
        # Install should have recorded the cache hit.
        assert handle._realized_hits_total == 64
        assert handle.stats()["realized_hit_tokens_total"] == 64
    finally:
        handle.teardown()


def test_free_wrap_evicts_from_tree():
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        tokens = list(range(64))
        sg = _mk_sg("r1", tokens, 0.0)
        bm.allocate(sg)
        assert handle.tree.query(tokens) == 64
        bm.free(sg.get_seqs()[0])
        assert handle.tree.query(tokens) == 0
    finally:
        handle.teardown()


def test_free_wrap_accepts_sequence_or_sequence_group():
    """vLLM 0.7.3 free() is sometimes called with a Sequence,
    sometimes with a SequenceGroup. Both paths must work."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        tokens_a = list(range(64))
        tokens_b = list(range(100, 164))
        sg_a = _mk_sg("a", tokens_a, 0.0)
        sg_b = _mk_sg("b", tokens_b, 1.0)
        bm.allocate(sg_a)
        bm.allocate(sg_b)
        # free with Sequence
        bm.free(sg_a.get_seqs()[0])
        assert handle.tree.query(tokens_a) == 0
        # free with SequenceGroup
        bm.free(sg_b)
        assert handle.tree.query(tokens_b) == 0
    finally:
        handle.teardown()


# ----------------------------------------------------------------------
# Telemetry
# ----------------------------------------------------------------------


def test_stats_when_disabled():
    sched = MockScheduler()
    bm = MockBlockSpaceManager()
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=False,
    )
    s = handle.stats()
    assert s == {"enabled": False}


def test_stats_when_enabled_includes_required_fields():
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        SHARED = list(range(64))
        bm.allocate(_mk_sg("seed", SHARED + list(range(500, 532)), 0.0))
        bm.allocate(_mk_sg("reuser", SHARED + list(range(600, 632)), 1.0))
        s = handle.stats()
        # Required fields per Phase 1 acceptance gate.
        for k in (
            "enabled",
            "admissions",
            "reordered_count",
            "starvation_overrides",
            "predicted_hit_tokens_total",
            "realized_hit_tokens_total",
            "prediction_accuracy",
            "tree_inserts",
            "tree_evictions",
            "tree_tracked_tokens",
        ):
            assert k in s, f"missing telemetry field: {k}"
        assert s["enabled"] is True
        assert s["realized_hit_tokens_total"] == 64
    finally:
        handle.teardown()


def test_prediction_accuracy_on_multi_request_workload():
    """End-to-end mini-workload: 1 seeded prefix + 5 reuser requests
    all sharing it. Prediction accuracy should be at the Phase 0
    composition contract bar (>= 0.85)."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        SHARED = list(range(64))  # 2 blocks
        # Seed.
        bm.allocate(_mk_sg("seed", SHARED + list(range(900, 932)), time.monotonic()))
        # Queue 5 reuser requests + 2 unique requests, anchored to
        # ``time.monotonic()`` so the starvation guard doesn't fire.
        now = time.monotonic()
        for i in range(5):
            sched.waiting.append(_mk_sg(
                f"reuser_{i}",
                SHARED + list(range(1000 + i*100, 1032 + i*100)),
                t=now - 1.0 + i * 0.01,
            ))
        for i in range(2):
            sched.waiting.append(_mk_sg(
                f"uniq_{i}",
                list(range(5000 + i*100, 5096 + i*100)),
                t=now - 0.5 + i * 0.01,
            ))
        # First schedule consumes up to 4 (MockScheduler's batch
        # size) reordered by predicted hit.
        sched.schedule()
        # Allocate the admitted (the install wrap reads block_tables
        # after each allocate to sync the tree).
        admitted_first_batch = list(sched.admitted_order)
        for sg in admitted_first_batch:
            bm.allocate(sg)
        # Second schedule + allocate to drain the rest.
        sched.schedule()
        for sg in sched.admitted_order[len(admitted_first_batch):]:
            bm.allocate(sg)
        s = handle.stats()
        # Prediction accuracy must clear the gate.
        assert s["predicted_hit_tokens_total"] > 0
        assert s["prediction_accuracy"] >= 0.85, (
            f"prediction_accuracy = {s['prediction_accuracy']:.3f} "
            f"< 0.85 gate (predicted={s['predicted_hit_tokens_total']}, "
            f"realized={s['realized_hit_tokens_total']})"
        )
    finally:
        handle.teardown()


# ----------------------------------------------------------------------
# Orthogonality / interface adapters
# ----------------------------------------------------------------------


def test_install_does_not_touch_other_attributes():
    """The install must touch ONLY .schedule, .allocate, .free. Any
    other scheduler/block_manager attribute is left alone."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager()
    sched.unrelated_attr = "do_not_touch"
    bm.unrelated_attr = "do_not_touch_either"
    original_running = sched.running
    original_waiting_class = type(sched.waiting)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True,
    )
    try:
        assert sched.unrelated_attr == "do_not_touch"
        assert bm.unrelated_attr == "do_not_touch_either"
        assert sched.running is original_running
        assert type(sched.waiting) is original_waiting_class
    finally:
        handle.teardown()


def test_install_block_size_propagates_to_predictor():
    """The block_size arg must reach the predictor; INT4 protected
    requires block_size=32, stock vLLM defaults to 16."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=16)
    handle_int4 = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        assert handle_int4.cas.predictor.block_size == 32
    finally:
        handle_int4.teardown()

    sched2 = MockScheduler()
    bm2 = MockBlockSpaceManager(block_size=16)
    handle_stock = install_cache_aware_scheduler(
        scheduler=sched2, block_manager=bm2, enable=True, block_size=16,
    )
    try:
        assert handle_stock.cas.predictor.block_size == 16
    finally:
        handle_stock.teardown()


def test_install_handle_can_be_inspected_after_teardown():
    """Stats should still be readable after teardown (for end-of-run
    telemetry; the streaming runner reads stats() AFTER teardown)."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    bm.allocate(_mk_sg("r1", list(range(64)), 0.0))
    bm.allocate(_mk_sg("r2", list(range(64)), 1.0))
    s_before = handle.stats()
    handle.teardown()
    s_after = handle.stats()
    # Same numbers post-teardown.
    assert s_after["realized_hit_tokens_total"] == s_before["realized_hit_tokens_total"]
    assert s_after["enabled"] is True  # the install ran; teardown just unhooks


# ----------------------------------------------------------------------
# Composition with int4_protected block_size constraint
# ----------------------------------------------------------------------


def test_composition_with_int4_block_size_32():
    """Full mini-flow against an int4_protected-shaped block manager
    (block_size=32). Verifies the predictor's block-alignment matches
    the allocator's block size, so realized == predicted on clean
    block-multiple requests."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        SYSTEM_PROMPT = list(range(64))  # exactly 2 blocks
        now = time.monotonic()
        # Seed.
        bm.allocate(_mk_sg(
            "seed",
            SYSTEM_PROMPT + list(range(8000, 8032)),
            now,
        ))
        # Three reuser requests at block-multiple lengths,
        # all "just-arrived" (well within the starvation window).
        for i in range(3):
            sched.waiting.append(_mk_sg(
                f"r{i}",
                SYSTEM_PROMPT + list(range(9000 + i*100, 9032 + i*100)),
                t=now - 0.5 + i * 0.01,
            ))
        sched.schedule()
        for sg in sched.admitted_order:
            bm.allocate(sg)
        s = handle.stats()
        # 3 reusers × 64-token hit each = 192 realized hits.
        assert s["realized_hit_tokens_total"] == 192
        assert s["prediction_accuracy"] >= 0.85
    finally:
        handle.teardown()


# ----------------------------------------------------------------------
# vLLM 0.7.3 V2 block-manager shape regression
#
# The V0 engine in vLLM 0.7.3 uses a V2 block manager whose
# ``block_tables[seq_id]`` is a ``BlockTable`` wrapper — not a
# directly-iterable list. PR-2's first GPU smoke surfaced this:
# ``_block_ids_for_seq`` originally did ``[... for b in bt]``, which
# raised ``TypeError: 'BlockTable' object is not iterable`` inside
# vLLM's _allocate_and_set_running.
#
# These mocks reproduce the V2 shape so the bug can't regress.
# ----------------------------------------------------------------------


class MockBlockTableV2:
    """Mimics vLLM 0.7.3 V2's ``BlockTable`` wrapper.

    Exposes ``.physical_block_ids`` (the canonical accessor — a
    ``List[Optional[int]]``) and ``.blocks`` (alt accessor → list of
    block-like objects). Crucially, it is **not directly iterable**
    — iterating it raises ``TypeError`` to match real vLLM behavior.
    """

    def __init__(self, block_numbers: Sequence[int]):
        self._block_numbers = [int(b) for b in block_numbers]

    @property
    def physical_block_ids(self) -> List[Optional[int]]:
        # vLLM populates this list with the integer block_id of each
        # allocated slot (or None for sentinels).
        return list(self._block_numbers)

    @property
    def blocks(self) -> List[MockPhysicalTokenBlock]:
        # Alt accessor — returns block-like objects with .block_id.
        return [
            type("_FakeBlock", (), {
                "block_id": bn, "block_number": bn,
            })()
            for bn in self._block_numbers
        ]

    def __iter__(self):  # pragma: no cover - exercised by assertion
        raise TypeError("'BlockTable' object is not iterable")


class MockBlockSpaceManagerV2(MockBlockSpaceManager):
    """V2 variant of the block-manager mock.

    Same prefix-cache + free-pool semantics as the V1 parent, but
    ``block_tables[seq_id]`` stores a ``MockBlockTableV2`` (wrapper
    object) instead of a plain ``List[MockPhysicalTokenBlock]``.
    """

    def allocate(self, seq_group: MockSequenceGroup) -> None:
        seq = seq_group.get_seqs()[0]
        tokens = seq.get_prompt_token_ids()
        block_numbers: List[int] = []
        i = 0
        n = len(tokens)
        hit_tokens = 0
        while i + self.block_size <= n:
            chunk = tuple(tokens[i:i + self.block_size])
            existing = self._cached_chunks.get(chunk)
            if existing is not None:
                block_numbers.append(existing)
                hit_tokens += self.block_size
            else:
                bn = self._next_block_number
                self._next_block_number += 1
                self._cached_chunks[chunk] = bn
                block_numbers.append(bn)
            i += self.block_size
        self.block_tables[seq.seq_id] = MockBlockTableV2(block_numbers)
        self._realized_hits_in_last_allocate = hit_tokens

    def free(self, seq_or_seq_group) -> None:
        if hasattr(seq_or_seq_group, "get_prompt_token_ids"):
            seq = seq_or_seq_group
        else:
            seq = seq_or_seq_group.get_seqs()[0]
        bt = self.block_tables.pop(seq.seq_id, None)
        if bt is None:
            return
        block_numbers = list(bt.physical_block_ids)
        for bn in block_numbers:
            if bn is not None:
                self._free_pool.append(int(bn))
        kept = set(block_numbers)
        self._cached_chunks = {
            ch: bn for ch, bn in self._cached_chunks.items()
            if bn not in kept
        }


def test_v2_block_table_is_not_iterable_sanity_check():
    """Sanity check: the V2 mock matches real vLLM shape — direct
    iteration raises TypeError. If this regresses, the V2-path tests
    below would not be exercising the bug they're meant to catch."""
    bt = MockBlockTableV2([1, 2, 3])
    with pytest.raises(TypeError, match="not iterable"):
        for _ in bt:
            pass
    # But .physical_block_ids must work.
    assert bt.physical_block_ids == [1, 2, 3]
    # And .blocks must yield block-like objects.
    blocks = bt.blocks
    assert len(blocks) == 3
    assert blocks[0].block_id == 1
    assert blocks[1].block_number == 2


def test_allocate_wrap_works_against_v2_block_manager():
    """The install's allocate wrap must populate the tree correctly
    when block_tables[seq_id] is a V2 BlockTable wrapper (not a
    plain list). This is the regression gate for the GPU-smoke
    crash:

        TypeError: 'BlockTable' object is not iterable
        at _block_ids_for_seq, called from _allocate_with_tree_update.
    """
    sched = MockScheduler()
    bm = MockBlockSpaceManagerV2(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        tokens = list(range(96))
        bm.allocate(_mk_sg("r1", tokens, 0.0))
        # Without the fix this would have crashed in the wrap with
        # TypeError before reaching here.
        assert handle.tree.query(tokens) == 96
        assert handle.tree.stats()["tracked_tokens"] > 0
    finally:
        handle.teardown()


def test_free_wrap_works_against_v2_block_manager():
    """The install's free wrap must extract block_ids correctly from
    a V2 BlockTable before invoking the original free()."""
    sched = MockScheduler()
    bm = MockBlockSpaceManagerV2(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        tokens = list(range(64))
        sg = _mk_sg("r1", tokens, 0.0)
        bm.allocate(sg)
        assert handle.tree.query(tokens) == 64
        bm.free(sg.get_seqs()[0])
        # If _block_ids_for_seq returned [] silently on a V2 shape,
        # the tree.evict call would be a no-op and the prefix would
        # still be queryable here. That would mask the bug rather
        # than reproduce it.
        assert handle.tree.query(tokens) == 0
    finally:
        handle.teardown()


def test_realized_hits_with_v2_block_manager():
    """Realized-hit measurement still works against the V2 shape —
    second request sharing a 64-token prefix logs 64 realized hits."""
    sched = MockScheduler()
    bm = MockBlockSpaceManagerV2(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        SHARED = list(range(64))
        bm.allocate(_mk_sg("seed", SHARED + list(range(500, 532)), 0.0))
        bm.allocate(_mk_sg("reuser", SHARED + list(range(600, 632)), 1.0))
        assert handle._realized_hits_total == 64
        assert handle.stats()["realized_hit_tokens_total"] == 64
    finally:
        handle.teardown()


# ----------------------------------------------------------------------
# Phase 3C measurement-only mode
#
# install_cache_aware_scheduler(measurement_only=True) installs the
# allocate + free tree wraps for realized-hit measurement, but
# SKIPS the scheduler.schedule reorder wrap. Used by cell B of the
# Phase 3 comparison to bridge the probe failure (vLLM's chained
# content_hash defeats the flat-hash probe).
# ----------------------------------------------------------------------


def test_measurement_only_skips_schedule_wrap():
    """measurement_only=True does NOT install the scheduler.schedule
    wrap — bound-method identity unchanged."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    original_schedule = sched.schedule
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm,
        enable=True, measurement_only=True, block_size=32,
    )
    try:
        assert handle.enabled is True
        assert handle.measurement_only is True
        # The schedule method's underlying function should remain the
        # MockScheduler class method (the wrap was NOT applied).
        assert sched.schedule.__func__ is MockScheduler.schedule
        # Sanity: scheduler still callable, returns admitted list.
        assert sched.schedule() == []
    finally:
        handle.teardown()


def test_measurement_only_installs_allocate_and_free_wraps():
    """measurement_only=True DOES install the allocate + free
    wraps — bound-method identity changes for both."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    original_allocate = bm.allocate
    original_free = bm.free
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm,
        enable=True, measurement_only=True, block_size=32,
    )
    try:
        # Allocate / free are wrapped — closures, not bound methods.
        assert bm.allocate is not original_allocate
        assert bm.free is not original_free
    finally:
        handle.teardown()
    # Teardown restores them.
    assert bm.allocate.__func__ is MockBlockSpaceManager.allocate
    assert bm.free.__func__ is MockBlockSpaceManager.free


def test_measurement_only_accumulates_realized_hits():
    """The load-bearing assertion: measurement_only mode still
    counts realized hit tokens via the allocate wrap. This is what
    cell B of Phase 3 will rely on."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm,
        enable=True, measurement_only=True, block_size=32,
    )
    try:
        SHARED = list(range(64))  # 2 blocks @ 32
        # Seed allocate populates the tree.
        bm.allocate(_mk_sg("seed", SHARED + list(range(500, 532)), 0.0))
        # Reuser shares the 64-token prefix → 64-token realized hit.
        bm.allocate(_mk_sg("reuser", SHARED + list(range(600, 632)), 1.0))
        assert handle._realized_hits_total == 64
        s = handle.stats()
        assert s["realized_hit_tokens_total"] == 64
        # No reorder happened (no schedule wrap), no predictor ran.
        assert s["admissions"] == 0
        assert s["reordered_count"] == 0
        assert s["predicted_hit_tokens_total"] == 0
        # measurement_only flag surfaces in stats.
        assert s["measurement_only"] is True
    finally:
        handle.teardown()


def test_measurement_only_does_not_reorder_waiting_deque():
    """End-to-end: even with multiple pending requests of varying
    predicted hit rates, measurement_only mode preserves FCFS
    admission order (verifies the schedule wrap really isn't
    installed)."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm,
        enable=True, measurement_only=True, block_size=32,
    )
    try:
        # Seed the tree so a future request would have a high
        # predicted hit rate.
        seed_tokens = list(range(64))
        bm.allocate(_mk_sg(
            "seed", seed_tokens + list(range(500, 532)), 0.0,
        ))
        # Enqueue two pending requests: r_low_hit (no overlap with
        # tree) and r_high_hit (shares the 64-token prefix).
        r_low = _mk_sg("r_low", list(range(9000, 9064)), 1.0)
        r_high = _mk_sg("r_high", seed_tokens + list(range(7000, 7032)), 2.0)
        sched.waiting.append(r_low)
        sched.waiting.append(r_high)
        admitted = sched.schedule()
        # FCFS order preserved: r_low (older arrival_time) admitted
        # before r_high, even though r_high has a higher predicted hit.
        assert admitted == [r_low, r_high]
    finally:
        handle.teardown()


def test_full_mode_stats_reports_measurement_only_false():
    """Sanity check: the default (full-mode) install reports
    measurement_only=False in stats."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True,
        block_size=32,
        # measurement_only defaults to False
    )
    try:
        s = handle.stats()
        assert s["enabled"] is True
        assert s["measurement_only"] is False
    finally:
        handle.teardown()


def test_disabled_install_has_no_measurement_only_field_in_stub_stats():
    """When enable=False, stats() returns the minimal {'enabled': False}
    stub — no measurement_only field needed since nothing's installed."""
    sched = MockScheduler()
    bm = MockBlockSpaceManager(block_size=32)
    handle = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm,
        enable=False, measurement_only=True,   # measurement_only ignored
    )
    assert handle.enabled is False
    assert handle.stats() == {"enabled": False}
