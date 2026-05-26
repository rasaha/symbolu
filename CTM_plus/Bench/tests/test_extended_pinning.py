"""Phase 4A CPU tests for extended pinning.

Validates ``kv_policy.extended_pinning`` against mocked vLLM
0.7.x ``BlockSpaceManager`` + ``LRUEvictor`` shapes (V1 and V2).

Acceptance gates covered (per the Phase 4A proposal):

* A1: PinSpec validates inputs (token_ids xor first_n_blocks_per_request)
* A2: PinningManager mark/unmark/is_pinned
* A3: Budget cap enforcement (pin_budget_rejections counter)
* A4: enable=False is a structural no-op
* A5: enable=True wraps allocate AND evictor on both V1 + V2 shapes
* A6: Content-based pin: matching token-prefix → block_ids pinned
* A7: Position-based pin: first_n_blocks_per_request → block_ids[:N] pinned
* A8: Evictor wrap stashes pinned candidates; pinned_evictions_avoided counted
* A9: Pool-entirely-pinned → forced_pin_evictions counted; eviction still happens
* A10: Teardown reverts wraps LIFO; idempotent
* A11: Composition with cache_aware_install — both wraps stack
* A12: stats() dict has expected keys
* A13: AST gate — no Int4ProtectedAttentionImpl references
* A14: existing test suites still pass (regression — covered by sweep)

No torch, no vllm, no GPU. Real-vLLM verification deferred to
Phase 4C.
"""

from __future__ import annotations

import ast
import collections
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

from kv_policy.extended_pinning import (
    ExtendedPinningInstall,
    PinningManager,
    PinSpec,
    _resolve_evictor,
    install_extended_pinning,
)


# ---------------------------------------------------------------- #
# Mock vLLM shapes
# ---------------------------------------------------------------- #


class _MockSequence:
    def __init__(self, seq_id: int, prompt: Sequence[int]):
        self.seq_id = seq_id
        self._prompt = list(prompt)

    def get_prompt_token_ids(self) -> List[int]:
        return list(self._prompt)


class _MockSequenceGroup:
    def __init__(
        self, request_id: str, prompt: Sequence[int],
        seq_id: Optional[int] = None,
    ):
        self.request_id = request_id
        self._seqs = [
            _MockSequence(
                seq_id=seq_id if seq_id is not None else hash(request_id) & 0x7FFFFFFF,
                prompt=prompt,
            )
        ]

    def get_seqs(self) -> List[_MockSequence]:
        return list(self._seqs)


class _MockPhysicalBlock:
    def __init__(self, block_number: int):
        self.block_number = block_number


class _MockLRUEvictor:
    """Minimal LRU evictor mimicking vLLM's shape.

    ``free_table`` is the canonical dict the install introspects.
    ``evict()`` pops the oldest entry (Python dict preserves
    insertion order in 3.7+) and returns its metadata.
    """

    def __init__(self):
        self.free_table: Dict[int, Any] = {}
        self.evict_call_count: int = 0
        # Track which block_id was returned by each evict() call so
        # tests can inspect the order.
        self.last_evicted: Optional[int] = None

    def add_to_free_pool(self, block_id: int, metadata: Any = None) -> None:
        """Test fixture: simulate vLLM dropping a block's ref-count
        to 0 (block becomes available for eviction)."""
        self.free_table[block_id] = metadata if metadata is not None else (
            f"block_{block_id}_metadata"
        )

    def evict(self):
        self.evict_call_count += 1
        if not self.free_table:
            raise RuntimeError("free_table empty — vLLM would assert here")
        # Pop the first (LRU-most) entry.
        block_id = next(iter(self.free_table))
        meta = self.free_table.pop(block_id)
        self.last_evicted = block_id
        return (block_id, meta)


class _MockGpuAllocatorV1:
    def __init__(self):
        self.evictor = _MockLRUEvictor()


class _MockGpuAllocatorV2:
    def __init__(self):
        self.evictor = _MockLRUEvictor()


class _MockBlockAllocatorV2:
    """V2 CpuGpuBlockAllocator shape — exposes .gpu_allocator."""

    def __init__(self):
        self.gpu_allocator = _MockGpuAllocatorV2()


class _MockBlockManagerV1:
    """V1 block manager — gpu_allocator directly."""

    def __init__(self, block_size: int = 32):
        self.block_size = block_size
        self.gpu_allocator = _MockGpuAllocatorV1()
        self.block_tables: Dict[int, List[_MockPhysicalBlock]] = {}
        self.allocate_calls: int = 0
        self.free_calls: int = 0
        self._next_block_number: int = 1

    def allocate(self, seq_group: _MockSequenceGroup) -> None:
        self.allocate_calls += 1
        seq = seq_group.get_seqs()[0]
        tokens = seq.get_prompt_token_ids()
        n_blocks = max(1, (len(tokens) + self.block_size - 1) // self.block_size)
        blocks = []
        for _ in range(n_blocks):
            blocks.append(_MockPhysicalBlock(self._next_block_number))
            self._next_block_number += 1
        self.block_tables[seq.seq_id] = blocks

    def free(self, seq_or_seq_group: Any) -> None:
        self.free_calls += 1
        seq = (
            seq_or_seq_group
            if hasattr(seq_or_seq_group, "get_prompt_token_ids")
            else seq_or_seq_group.get_seqs()[0]
        )
        self.block_tables.pop(seq.seq_id, None)


class _MockBlockManagerV2:
    """V2 block manager — block_allocator wrapper."""

    def __init__(self, block_size: int = 32):
        self.block_size = block_size
        self.block_allocator = _MockBlockAllocatorV2()
        self.block_tables: Dict[int, List[_MockPhysicalBlock]] = {}
        self.allocate_calls: int = 0
        self.free_calls: int = 0
        self._next_block_number: int = 1

    def allocate(self, seq_group: _MockSequenceGroup) -> None:
        self.allocate_calls += 1
        seq = seq_group.get_seqs()[0]
        tokens = seq.get_prompt_token_ids()
        n_blocks = max(1, (len(tokens) + self.block_size - 1) // self.block_size)
        blocks = []
        for _ in range(n_blocks):
            blocks.append(_MockPhysicalBlock(self._next_block_number))
            self._next_block_number += 1
        self.block_tables[seq.seq_id] = blocks

    def free(self, seq_or_seq_group: Any) -> None:
        self.free_calls += 1
        seq = (
            seq_or_seq_group
            if hasattr(seq_or_seq_group, "get_prompt_token_ids")
            else seq_or_seq_group.get_seqs()[0]
        )
        self.block_tables.pop(seq.seq_id, None)


# ---------------------------------------------------------------- #
# A1: PinSpec validation
# ---------------------------------------------------------------- #


def test_pin_spec_rejects_both_fields_set():
    with pytest.raises(ValueError, match="exactly one"):
        PinSpec(name="bad", token_ids=(1, 2, 3), first_n_blocks_per_request=2)


def test_pin_spec_rejects_neither_field_set():
    with pytest.raises(ValueError, match="exactly one"):
        PinSpec(name="bad")


def test_pin_spec_rejects_empty_token_ids():
    with pytest.raises(ValueError, match="non-empty"):
        PinSpec(name="bad", token_ids=())


def test_pin_spec_rejects_zero_or_negative_first_n_blocks():
    with pytest.raises(ValueError, match=">= 1"):
        PinSpec(name="bad", first_n_blocks_per_request=0)
    with pytest.raises(ValueError, match=">= 1"):
        PinSpec(name="bad", first_n_blocks_per_request=-1)


def test_pin_spec_coerces_list_to_tuple():
    """A frozen dataclass needs hashable fields; PinSpec coerces
    sequence-typed token_ids to tuple in __post_init__."""
    spec = PinSpec(name="ok", token_ids=[1, 2, 3])
    assert spec.token_ids == (1, 2, 3)
    assert isinstance(spec.token_ids, tuple)


def test_pin_spec_accepts_valid_content_spec():
    spec = PinSpec(name="system", token_ids=(10, 20, 30))
    assert spec.name == "system"
    assert spec.token_ids == (10, 20, 30)
    assert spec.first_n_blocks_per_request is None


def test_pin_spec_accepts_valid_position_spec():
    spec = PinSpec(name="first4", first_n_blocks_per_request=4)
    assert spec.name == "first4"
    assert spec.first_n_blocks_per_request == 4
    assert spec.token_ids is None


# ---------------------------------------------------------------- #
# A2: PinningManager mark/unmark/is_pinned
# ---------------------------------------------------------------- #


def test_manager_mark_pinned_adds_block():
    pm = PinningManager(
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        max_budget_blocks=10, block_size=32,
    )
    assert not pm.is_pinned(42)
    added = pm.mark_pinned(42, spec_name="s")
    assert added is True
    assert pm.is_pinned(42)


def test_manager_mark_pinned_idempotent_per_block():
    """A block can be re-marked by the same or another spec;
    the second mark doesn't double-count or fail."""
    pm = PinningManager(
        pin_specs=[
            PinSpec(name="a", first_n_blocks_per_request=1),
            PinSpec(name="b", first_n_blocks_per_request=1),
        ],
        max_budget_blocks=10, block_size=32,
    )
    pm.mark_pinned(7, "a")
    pm.mark_pinned(7, "b")
    pm.mark_pinned(7, "a")  # repeated
    assert pm.is_pinned(7)
    # Single block in the set; multiple spec attributions.
    assert len(pm._pinned_blocks) == 1
    assert pm._block_to_specs[7] == {"a", "b"}


def test_manager_unmark_pinned_drops_block():
    pm = PinningManager(
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        max_budget_blocks=10, block_size=32,
    )
    pm.mark_pinned(99, "s")
    assert pm.is_pinned(99)
    pm.unmark_pinned(99)
    assert not pm.is_pinned(99)
    # unmarking an unpinned block is safe.
    pm.unmark_pinned(99)


# ---------------------------------------------------------------- #
# A3: Budget cap enforcement
# ---------------------------------------------------------------- #


def test_manager_budget_cap_rejects_overflow():
    pm = PinningManager(
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        max_budget_blocks=3, block_size=32,
    )
    assert pm.mark_pinned(1, "s") is True
    assert pm.mark_pinned(2, "s") is True
    assert pm.mark_pinned(3, "s") is True
    # 4th distinct block hits the cap.
    assert pm.mark_pinned(4, "s") is False
    assert not pm.is_pinned(4)
    assert pm._pin_budget_rejections == 1
    # Repeating the rejected attempt increments the counter again.
    assert pm.mark_pinned(5, "s") is False
    assert pm._pin_budget_rejections == 2
    # Existing pins survive overflow attempts.
    assert pm.is_pinned(1)
    assert pm.is_pinned(2)
    assert pm.is_pinned(3)


def test_manager_budget_cap_does_not_reject_already_pinned_block():
    """Re-marking an already-pinned block must not count as
    rejection even when the cap is reached."""
    pm = PinningManager(
        pin_specs=[PinSpec(name="a", first_n_blocks_per_request=1)],
        max_budget_blocks=2, block_size=32,
    )
    pm.mark_pinned(1, "a")
    pm.mark_pinned(2, "a")
    # Already at cap. Re-marking 1 (already pinned) succeeds.
    assert pm.mark_pinned(1, "a") is True
    assert pm._pin_budget_rejections == 0


# ---------------------------------------------------------------- #
# A4: enable=False is a structural no-op
# ---------------------------------------------------------------- #


def test_install_with_enable_false_is_no_op():
    bm = _MockBlockManagerV1()
    original_allocate = bm.allocate
    original_evict = bm.gpu_allocator.evictor.evict

    install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=False,
    )
    assert install.enabled is False
    assert install.manager is None
    # Bound methods are unchanged: their __func__ matches the class
    # method, proving no wrap was applied.
    assert bm.allocate.__func__ is _MockBlockManagerV1.allocate
    assert bm.gpu_allocator.evictor.evict.__func__ is _MockLRUEvictor.evict
    # stats() returns the minimal stub.
    assert install.stats() == {"enabled": False}


def test_install_rejects_missing_allocate():
    class _NoAllocate:
        pass

    with pytest.raises(AttributeError, match="allocate"):
        install_extended_pinning(
            block_manager=_NoAllocate(),
            pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
            enable=True,
        )


# ---------------------------------------------------------------- #
# A5: Wrap allocate AND evictor on V1 + V2
# ---------------------------------------------------------------- #


def test_install_wraps_allocate_and_evictor_v1():
    bm = _MockBlockManagerV1()
    original_allocate = bm.allocate
    original_evict = bm.gpu_allocator.evictor.evict

    install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=True,
    )
    try:
        # Both wraps applied — bound methods differ from the originals.
        assert bm.allocate is not original_allocate
        assert bm.gpu_allocator.evictor.evict is not original_evict
        assert install.evictor_path_taken == (
            "v1_block_manager.gpu_allocator.evictor"
        )
    finally:
        install.teardown()


def test_install_wraps_allocate_and_evictor_v2():
    bm = _MockBlockManagerV2()
    original_allocate = bm.allocate
    original_evict = bm.block_allocator.gpu_allocator.evictor.evict

    install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=True,
    )
    try:
        assert bm.allocate is not original_allocate
        assert (
            bm.block_allocator.gpu_allocator.evictor.evict
            is not original_evict
        )
        assert install.evictor_path_taken == (
            "v2_block_allocator.gpu_allocator.evictor"
        )
    finally:
        install.teardown()


def test_resolve_evictor_returns_no_known_path_when_absent():
    """A block_manager without any of the documented paths gets
    'no_known_path' and the install completes in allocate-wrap-only
    mode (no evictor wrap applied)."""

    class _Bare:
        def allocate(self, sg): pass

    ev, path = _resolve_evictor(_Bare())
    assert ev is None
    assert path == "no_known_path"

    bm = _Bare()
    install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=True,
    )
    try:
        assert install.evictor_path_taken == "no_known_path"
        # Allocate wrap still installed (manager runs in tracking-only
        # mode).
        assert install.manager is not None
    finally:
        install.teardown()


# ---------------------------------------------------------------- #
# A6: Content-based pin marks matching block_ids
# ---------------------------------------------------------------- #


def test_content_pin_marks_blocks_for_matching_prefix():
    """When a request's prompt starts with the spec's token_ids,
    the first ceil(len(spec) / block_size) blocks are pinned."""
    bm = _MockBlockManagerV2(block_size=32)
    # PinSpec covers 64 tokens = 2 blocks at block_size=32.
    spec = PinSpec(name="system_prompt", token_ids=tuple(range(1000, 1064)))
    install = install_extended_pinning(
        block_manager=bm, pin_specs=[spec], enable=True, block_size=32,
    )
    try:
        # Request 1: prompt starts with the spec's tokens + a unique tail.
        sg1 = _MockSequenceGroup(
            "req1", list(range(1000, 1064)) + list(range(9000, 9032)),
        )
        bm.allocate(sg1)
        # The first 2 blocks of sg1 should be pinned.
        block_ids_1 = [
            int(b.block_number) for b in bm.block_tables[sg1.get_seqs()[0].seq_id]
        ]
        assert install.manager.is_pinned(block_ids_1[0])
        assert install.manager.is_pinned(block_ids_1[1])
        # The tail block (3rd block, holding unique tokens) is NOT
        # pinned.
        if len(block_ids_1) > 2:
            assert not install.manager.is_pinned(block_ids_1[2])

        # Request 2: prompt does NOT start with the spec's tokens.
        sg2 = _MockSequenceGroup("req2", list(range(8000, 8064)))
        bm.allocate(sg2)
        block_ids_2 = [
            int(b.block_number) for b in bm.block_tables[sg2.get_seqs()[0].seq_id]
        ]
        for bid in block_ids_2:
            assert not install.manager.is_pinned(bid), (
                "non-matching prompt should NOT be pinned"
            )
    finally:
        install.teardown()


def test_content_pin_handles_prompt_shorter_than_spec():
    """Edge case: prompt is shorter than the spec's tokens — no
    pin."""
    bm = _MockBlockManagerV2(block_size=32)
    spec = PinSpec(name="long_system", token_ids=tuple(range(1000, 1128)))
    install = install_extended_pinning(
        block_manager=bm, pin_specs=[spec], enable=True, block_size=32,
    )
    try:
        sg = _MockSequenceGroup("short", list(range(1000, 1032)))  # only 32 tokens
        bm.allocate(sg)
        block_ids = [
            int(b.block_number) for b in bm.block_tables[sg.get_seqs()[0].seq_id]
        ]
        for bid in block_ids:
            assert not install.manager.is_pinned(bid)
    finally:
        install.teardown()


# ---------------------------------------------------------------- #
# A7: Position-based pin marks block_ids[:N]
# ---------------------------------------------------------------- #


def test_position_pin_marks_first_n_blocks_regardless_of_content():
    bm = _MockBlockManagerV2(block_size=32)
    spec = PinSpec(name="first2", first_n_blocks_per_request=2)
    install = install_extended_pinning(
        block_manager=bm, pin_specs=[spec], enable=True, block_size=32,
    )
    try:
        # Two requests with different content — both should have
        # their first 2 blocks pinned.
        sg1 = _MockSequenceGroup("req1", list(range(64)))   # 2 blocks
        sg2 = _MockSequenceGroup("req2", list(range(100, 196)))  # 3 blocks
        bm.allocate(sg1)
        bm.allocate(sg2)
        bids1 = [int(b.block_number) for b in bm.block_tables[sg1.get_seqs()[0].seq_id]]
        bids2 = [int(b.block_number) for b in bm.block_tables[sg2.get_seqs()[0].seq_id]]
        # First 2 blocks of each request are pinned.
        assert install.manager.is_pinned(bids1[0])
        assert install.manager.is_pinned(bids1[1])
        assert install.manager.is_pinned(bids2[0])
        assert install.manager.is_pinned(bids2[1])
        # If sg2 has a 3rd block, it should NOT be pinned.
        if len(bids2) > 2:
            assert not install.manager.is_pinned(bids2[2])
    finally:
        install.teardown()


def test_position_pin_handles_first_n_greater_than_blocks():
    """If first_n_blocks_per_request exceeds the seq's allocated
    blocks, pin all blocks (no error)."""
    bm = _MockBlockManagerV2(block_size=32)
    spec = PinSpec(name="first10", first_n_blocks_per_request=10)
    install = install_extended_pinning(
        block_manager=bm, pin_specs=[spec], enable=True, block_size=32,
    )
    try:
        sg = _MockSequenceGroup("req", list(range(32)))  # only 1 block
        bm.allocate(sg)
        bids = [int(b.block_number) for b in bm.block_tables[sg.get_seqs()[0].seq_id]]
        assert all(install.manager.is_pinned(b) for b in bids)
        # And no error from trying to pin past block_ids[:10].
    finally:
        install.teardown()


# ---------------------------------------------------------------- #
# A8: Evictor wrap stashes pinned candidates
# ---------------------------------------------------------------- #


def test_evictor_wrap_stashes_pinned_candidates():
    """When the evictor's free_table has both pinned and unpinned
    blocks, the wrap stashes the pinned ones, calls original_evict
    (which sees only unpinned), restores after."""
    bm = _MockBlockManagerV2(block_size=32)
    spec = PinSpec(name="first1", first_n_blocks_per_request=1)
    install = install_extended_pinning(
        block_manager=bm, pin_specs=[spec], enable=True, block_size=32,
    )
    try:
        # Allocate one request so block 1 is pinned (first_n=1).
        sg = _MockSequenceGroup("req1", list(range(32)))
        bm.allocate(sg)
        pinned_bid = int(bm.block_tables[sg.get_seqs()[0].seq_id][0].block_number)
        assert install.manager.is_pinned(pinned_bid)
        # Populate the evictor's free pool: pinned + unpinned blocks.
        evictor = bm.block_allocator.gpu_allocator.evictor
        evictor.add_to_free_pool(pinned_bid)        # pinned
        evictor.add_to_free_pool(99)                # unpinned
        evictor.add_to_free_pool(100)               # unpinned
        # Call evict() — wrap should pick block 99 (first unpinned)
        # because pinned_bid is stashed during the call.
        result = bm.block_allocator.gpu_allocator.evictor.evict()
        assert evictor.last_evicted == 99
        # Counters updated.
        assert install.manager._pinned_evictions_avoided == 1
        # Pinned block restored to the pool after the eviction.
        assert pinned_bid in evictor.free_table
        # Block 99 is gone (it was evicted).
        assert 99 not in evictor.free_table
    finally:
        install.teardown()


def test_evictor_wrap_per_block_pinned_evictions_counter():
    """When multiple pinned blocks are stashed in a single evict()
    call, the counter increments by the stashed count (not 1)."""
    bm = _MockBlockManagerV2(block_size=32)
    spec = PinSpec(name="first3", first_n_blocks_per_request=3)
    install = install_extended_pinning(
        block_manager=bm, pin_specs=[spec], enable=True, block_size=32,
    )
    try:
        sg = _MockSequenceGroup("req", list(range(96)))   # 3 blocks
        bm.allocate(sg)
        pinned_bids = [
            int(b.block_number)
            for b in bm.block_tables[sg.get_seqs()[0].seq_id]
        ]
        evictor = bm.block_allocator.gpu_allocator.evictor
        for bid in pinned_bids:
            evictor.add_to_free_pool(bid)
        evictor.add_to_free_pool(500)
        # One evict call should stash 3 pinned blocks → counter += 3.
        bm.block_allocator.gpu_allocator.evictor.evict()
        assert install.manager._pinned_evictions_avoided == 3
    finally:
        install.teardown()


# ---------------------------------------------------------------- #
# A9: Pool-entirely-pinned → forced_pin_evictions
# ---------------------------------------------------------------- #


def test_evictor_wrap_forced_eviction_when_all_pinned():
    """If every candidate in the free_table is pinned, the wrap
    restores all + calls original_evict (forced); the counter is
    incremented."""
    bm = _MockBlockManagerV2(block_size=32)
    spec = PinSpec(name="first2", first_n_blocks_per_request=2)
    install = install_extended_pinning(
        block_manager=bm, pin_specs=[spec], enable=True, block_size=32,
    )
    try:
        sg = _MockSequenceGroup("req", list(range(64)))  # 2 blocks
        bm.allocate(sg)
        pinned_bids = [
            int(b.block_number)
            for b in bm.block_tables[sg.get_seqs()[0].seq_id]
        ]
        evictor = bm.block_allocator.gpu_allocator.evictor
        for bid in pinned_bids:
            evictor.add_to_free_pool(bid)
        # Free pool is ENTIRELY pinned; forced eviction must happen.
        bm.block_allocator.gpu_allocator.evictor.evict()
        assert install.manager._forced_pin_evictions == 1
        # And one of the pinned blocks WAS evicted (the engine
        # has to be able to allocate; we can't refuse).
        assert evictor.last_evicted in pinned_bids
    finally:
        install.teardown()


# ---------------------------------------------------------------- #
# A10: Teardown reverts wraps LIFO; idempotent
# ---------------------------------------------------------------- #


def test_teardown_reverts_both_wraps():
    bm = _MockBlockManagerV2(block_size=32)
    install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=True,
    )
    install.teardown()
    # Bound methods recovered.
    assert bm.allocate.__func__ is _MockBlockManagerV2.allocate
    assert (
        bm.block_allocator.gpu_allocator.evictor.evict.__func__
        is _MockLRUEvictor.evict
    )


def test_teardown_is_idempotent():
    bm = _MockBlockManagerV2(block_size=32)
    install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=True,
    )
    install.teardown()
    install.teardown()   # safe to call again


# ---------------------------------------------------------------- #
# A11: Composition with cache_aware_install
# ---------------------------------------------------------------- #


def test_composition_with_cache_aware_install():
    """Both installs should stack on the same block_manager;
    both wraps fire on each allocate; teardown is LIFO."""
    from kv_policy.cache_aware_install import install_cache_aware_scheduler

    bm = _MockBlockManagerV2(block_size=32)
    # MockScheduler from the cache-aware test surface — minimal
    # impl for the install's preconditions.

    class _Sched:
        def __init__(self):
            self.waiting = collections.deque()

        def schedule(self):
            return []

    sched = _Sched()

    # Install order (innermost first): extended_pinning, then
    # cache_aware. So cache_aware's wrap is OUTERMOST.
    pin_install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=True,
    )
    cas_install = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True, block_size=32,
    )
    try:
        # Submit one allocate; both wraps should fire. Verify by
        # checking the pinning manager AND the cache-aware tree
        # both updated.
        sg = _MockSequenceGroup("composed_req", list(range(64)))
        bm.allocate(sg)
        seq_id = sg.get_seqs()[0].seq_id
        assert bm.block_tables[seq_id], "allocate did not run"
        # Pinning wrap fired: first block is pinned.
        bid = int(bm.block_tables[seq_id][0].block_number)
        assert pin_install.manager.is_pinned(bid)
        # Cache-aware wrap fired: tree has the prompt inserted.
        tokens = sg.get_seqs()[0].get_prompt_token_ids()
        assert cas_install.tree.query(tokens) > 0
    finally:
        # Teardown LIFO: cache_aware first (outermost), then pinning.
        cas_install.teardown()
        pin_install.teardown()
    # After full teardown, both methods point at the originals.
    assert bm.allocate.__func__ is _MockBlockManagerV2.allocate


def test_composition_with_cache_aware_measurement_only():
    """Same as above but cache_aware in measurement_only mode —
    the schedule-reorder wrap is skipped, but allocate/free wraps
    still stack with pinning's allocate wrap."""
    from kv_policy.cache_aware_install import install_cache_aware_scheduler

    bm = _MockBlockManagerV2(block_size=32)

    class _Sched:
        def __init__(self):
            self.waiting = collections.deque()

        def schedule(self):
            return []

    sched = _Sched()

    pin_install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=True,
    )
    cas_install = install_cache_aware_scheduler(
        scheduler=sched, block_manager=bm, enable=True,
        measurement_only=True, block_size=32,
    )
    try:
        sg = _MockSequenceGroup("composed_req", list(range(64)))
        bm.allocate(sg)
        # Pinning fired.
        bid = int(bm.block_tables[sg.get_seqs()[0].seq_id][0].block_number)
        assert pin_install.manager.is_pinned(bid)
        # Cache-aware tree fired (allocate wrap is installed even in
        # measurement_only mode).
        tokens = sg.get_seqs()[0].get_prompt_token_ids()
        assert cas_install.tree.query(tokens) > 0
        # But the schedule wrap is NOT installed in measurement_only.
        assert sched.schedule.__func__ is _Sched.schedule
    finally:
        cas_install.teardown()
        pin_install.teardown()


# ---------------------------------------------------------------- #
# A12: stats() dict shape
# ---------------------------------------------------------------- #


def test_stats_has_expected_keys_when_enabled():
    bm = _MockBlockManagerV2(block_size=32)
    install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[
            PinSpec(name="system", token_ids=(1, 2, 3)),
            PinSpec(name="first2", first_n_blocks_per_request=2),
        ],
        enable=True,
    )
    try:
        s = install.stats()
        expected = {
            "enabled",
            "pinned_blocks_total",
            "pin_specs_count",
            "pinned_evictions_avoided",
            "pin_budget_rejections",
            "forced_pin_evictions",
            "pinned_memory_overhead_bytes",
            "per_spec_pinned_blocks",
            "evictor_path_taken",
        }
        missing = expected - set(s.keys())
        assert not missing, f"stats() missing keys: {missing}"
        assert s["enabled"] is True
        assert s["pin_specs_count"] == 2
    finally:
        install.teardown()


def test_stats_per_spec_attribution():
    """When a block is pinned by multiple specs, per_spec_pinned_blocks
    reports each spec's count separately."""
    bm = _MockBlockManagerV2(block_size=32)
    # spec_a is content-based (matches the prompt); spec_b is
    # position-based (always pins first 1 block) — both will mark
    # the same block.
    install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[
            PinSpec(name="spec_a", token_ids=tuple(range(32))),
            PinSpec(name="spec_b", first_n_blocks_per_request=1),
        ],
        enable=True, block_size=32,
    )
    try:
        sg = _MockSequenceGroup("req", list(range(32)))
        bm.allocate(sg)
        s = install.stats()
        # Same block counted by BOTH specs.
        assert s["per_spec_pinned_blocks"]["spec_a"] == 1
        assert s["per_spec_pinned_blocks"]["spec_b"] == 1
        # But pinned_blocks_total is 1 (only one distinct block_id).
        assert s["pinned_blocks_total"] == 1
    finally:
        install.teardown()


def test_stats_memory_overhead_bytes_calculation():
    bm = _MockBlockManagerV2(block_size=32)
    install = install_extended_pinning(
        block_manager=bm,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=2)],
        enable=True, block_size=32,
    )
    try:
        sg = _MockSequenceGroup("req", list(range(64)))  # 2 blocks
        bm.allocate(sg)
        s = install.stats()
        # 2 blocks * 32 tokens/block * 2 bytes/token (bf16) = 128 bytes
        assert s["pinned_memory_overhead_bytes"] == 2 * 32 * 2
    finally:
        install.teardown()


# ---------------------------------------------------------------- #
# A13: AST gate — no Int4ProtectedAttentionImpl / kernel symbols
# ---------------------------------------------------------------- #


def test_extended_pinning_source_does_not_reference_int4_protected():
    """AST-based gate: extended_pinning.py's executable code must
    not import or reference Int4ProtectedAttentionImpl, the
    vendored vLLM-flash-attn fork, or other shipped int4_protected
    components."""
    src_path = Path(
        "/home/user/symbolu/CTM_plus/KVPolicy/kv_policy/extended_pinning.py"
    )
    src = src_path.read_text()
    tree = ast.parse(src)
    forbidden = {
        "Int4ProtectedAttentionImpl",
        "Int4ProtectedLLM",
        "phase5b_backend_install",
        "phase5b_4c_paged_writer",
        "phase5b_streaming_quantizer",
        "vllm_flash_attn_int4",
        "int4_protected_k_cache",
        "int4_fused_attention_kernel",
        "int4_fused_attention_sketch",
    }
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for piece in node.module.split("."):
                    referenced.add(piece)
            for alias in node.names:
                referenced.add(alias.name)
                referenced.add(alias.name.split(".")[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for piece in alias.name.split("."):
                    referenced.add(piece)
    overlap = forbidden & referenced
    assert not overlap, (
        f"extended_pinning.py references forbidden symbols {overlap} — "
        "Phase 4 must not touch the int4_protected stack."
    )


# ---------------------------------------------------------------- #
# A14 is exercised by the broader regression sweep, not here.
# ---------------------------------------------------------------- #
