"""CPU fixture that mirrors vLLM 0.7.3's PrefixCachingBlockAllocator
protocol — built after the May 2026 GPU session surfaced seven
audit-pass misses, all in the same family: mocked unit tests pinned
per-call API shape but did not drive the cross-call invariants the
real allocator relies on.

This module:

1. Provides ``MockPrefixCachingBlockAllocator`` — a deliberately
   minimal Python simulator of the vLLM 0.7.3 allocator + evictor
   protocol that an external evictor must satisfy. It drives
   ``add → update → remove → evict → re-add`` cycles with the
   ``_cached_blocks`` invariant the production code asserts.
2. Provides seven regression tests, each pinning one of the bugs
   we caught only at GPU-execution time. Every test would have
   failed without the corresponding fix landing.

If the project grows additional vLLM-internal wrappers, follow this
module's pattern: build a CPU mock of the cross-call protocol the
wrapper is integrating against, then exercise the wrapper through
realistic operation sequences. Single-call mocks are insufficient.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


# --------------------------------------------------------------------- #
# MockPrefixCachingBlockAllocator
# --------------------------------------------------------------------- #


@dataclass
class _BlockTracker:
    """Mirror of vLLM's per-block tracking state."""
    block_id: int
    content_hash: Optional[int] = None
    refcount: int = 0


@dataclass
class MockPrefixCachingBlockAllocator:
    """CPU simulation of vLLM 0.7.3's PrefixCachingBlockAllocator
    protocol against an external evictor.

    The single most important invariant — and the one the May 2026
    GPU run kept tripping on — is:

        After ``evictor.evict()`` returns ``(block_id, content_hash)``,
        ``content_hash`` MUST be a current key of
        ``self._cached_blocks``, and ``self._cached_blocks[content_hash]
        == block_id``.

    This mock asserts that on every evict() it issues. Any wrapper
    that violates the invariant fails the test on the first divergent
    cycle, just like vLLM 0.7.3 does in production.

    Deliberately leaves out: GPU memory accounting, multiple devices,
    intermediate-tensors paths, MultiModalKwargs, copy-on-write,
    chunked prefill. The protocol surface that matters for an
    evictor wrapper is just add/update/remove/evict/__contains__/
    num_blocks plus the ``_cached_blocks`` invariant.
    """

    num_blocks: int
    block_size: int
    evictor: object  # CTMEvictorModern or any vLLM 0.7 Evictor ABC impl.

    # State that mirrors vLLM's:
    _cached_blocks: Dict[int, int] = field(default_factory=dict)  # hash -> block_id
    _block_tracker: Dict[int, _BlockTracker] = field(default_factory=dict)
    _free_block_ids: List[int] = field(default_factory=list)
    _next_hash: int = 1

    def __post_init__(self):
        # Seed the free pool with all block_ids.
        self._free_block_ids = list(range(self.num_blocks))
        self._block_tracker = {
            bid: _BlockTracker(block_id=bid)
            for bid in range(self.num_blocks)
        }

    # ---- vLLM-public allocation API --------------------------------- #

    def allocate_immutable_block(self, content_hash: int) -> int:
        """Allocate a block for content with a given content_hash.

        If the hash is already cached, increment its refcount and
        return the existing block. Otherwise, take a free block (or
        evict one), set up its tracking state, and tell the evictor.
        """
        # Cache hit: refcount up, possibly remove from evictor pool.
        if content_hash in self._cached_blocks:
            block_id = self._cached_blocks[content_hash]
            tracker = self._block_tracker[block_id]
            tracker.refcount += 1
            if block_id in self.evictor:
                # Block was evictable but is now referenced again.
                self.evictor.remove(block_id)
            return block_id

        # Cache miss: get a fresh block.
        if self._free_block_ids:
            block_id = self._free_block_ids.pop()
        else:
            block_id = self._evict_one()

        tracker = self._block_tracker[block_id]
        tracker.content_hash = content_hash
        tracker.refcount = 1
        self._cached_blocks[content_hash] = block_id
        return block_id

    def free(self, block_id: int) -> None:
        """Decrement refcount; if it drops to zero, the block becomes
        evictable (added to the evictor's pool)."""
        tracker = self._block_tracker[block_id]
        if tracker.refcount <= 0:
            raise AssertionError(
                f"free({block_id}) but refcount is already 0"
            )
        tracker.refcount -= 1
        if tracker.refcount == 0 and tracker.content_hash is not None:
            self.evictor.add(
                block_id=block_id,
                content_hash=tracker.content_hash,
                num_hashed_tokens=self.block_size,
                last_accessed=0.0,
            )

    def touch(self, block_id: int, now: float) -> None:
        """vLLM calls evictor.update on every active step."""
        self.evictor.update(block_id=block_id, last_accessed=now)

    def _evict_one(self) -> int:
        """Drive evictor.evict() and assert the cross-call invariant.
        Returns the freed block_id, ready for re-use."""
        if self.evictor.num_blocks == 0:
            raise RuntimeError(
                "MockPrefixCachingBlockAllocator: no free blocks AND "
                "evictor is empty (cache fully pinned)."
            )
        block_id, content_hash_to_evict = self.evictor.evict()

        # The vLLM 0.7.3 invariant. Every audit-pass miss in this
        # family involves either this assert or its sibling in
        # _maybe_allocate_evicted_block_id.
        assert content_hash_to_evict in self._cached_blocks, (
            f"evict() returned content_hash={content_hash_to_evict} "
            f"but it is not in self._cached_blocks "
            f"(keys: {list(self._cached_blocks.keys())[:8]}...). "
            "This is the AsyncEngineDeadError trigger from the "
            "May 2026 GPU run."
        )
        cached_block_id = self._cached_blocks[content_hash_to_evict]
        assert cached_block_id == block_id, (
            f"evict() returned block_id={block_id} but "
            f"_cached_blocks[{content_hash_to_evict}] = "
            f"{cached_block_id}. Tracking divergence."
        )

        # Real vLLM updates these on successful evict.
        del self._cached_blocks[content_hash_to_evict]
        tracker = self._block_tracker[block_id]
        tracker.content_hash = None
        tracker.refcount = 0
        return block_id

    # ---- Convenience for tests --------------------------------------- #

    def stress_admit_evict_cycles(
        self,
        num_cycles: int,
        unique_hashes: int,
        seed: int = 42,
    ) -> None:
        """Drive a randomised admit/evict workload — many cycles of
        ``allocate_immutable_block(hash)`` followed by ``free(block_id)``
        with varying hashes.

        Catches the bugs that only surface under cross-call divergence.
        Caps the live-reference set at ``num_blocks - 1`` so we never
        pin the whole cache (which would deadlock the evictor; that's
        an upstream caller bug, not a wrapper bug).
        """
        rng = random.Random(seed)
        live: List[Tuple[int, int]] = []  # (block_id, content_hash)
        max_live = max(1, self.num_blocks - 2)
        for _ in range(num_cycles):
            # Free aggressively when we're near capacity so the
            # evictor pool stays non-empty and we exercise its path.
            should_free = (
                len(live) >= max_live
                or (live and rng.random() < 0.5)
            )
            if should_free:
                idx = rng.randrange(len(live))
                bid, _h = live.pop(idx)
                self.free(bid)
            else:
                h = rng.randrange(unique_hashes)
                bid = self.allocate_immutable_block(h)
                live.append((bid, h))


# --------------------------------------------------------------------- #
# Bug 1 + Bug 3 — the _cached_blocks invariant + evict-readmit cycles
# --------------------------------------------------------------------- #


def test_bug1_evict_returns_content_hash_in_cached_blocks():
    """vLLM 0.7.3 PrefixCachingBlockAllocator asserts
    `content_hash_to_evict in self._cached_blocks` after our evict()
    returns. The first GPU run hit this with content_hash=0 (our
    self._content_hash.pop fell through to its default).

    Without the fix in CTMEvictorModern.evict() that calls
    self._policy.evict_block(victim_id), this test fails on the
    second evict() call: select_victims re-picks the already-evicted
    block, _content_hash.pop returns 0, the assert in the mock fires.
    """
    from kv_policy.vllm_evictor import CTMEvictorModern

    evictor = CTMEvictorModern(num_blocks_capacity=64, block_size=16)
    alloc = MockPrefixCachingBlockAllocator(
        num_blocks=8, block_size=16, evictor=evictor,
    )

    # Admit 8 blocks, free all to push them into the evictor pool.
    for h in range(1, 9):
        bid = alloc.allocate_immutable_block(h)
        alloc.free(bid)
    assert evictor.num_blocks == 8

    # Now allocate 16 NEW hashes to force evictions. The mock will
    # assert the invariant on every evict.
    for h in range(100, 116):
        bid = alloc.allocate_immutable_block(h)
        alloc.free(bid)


def test_bug3_evict_readmit_keeps_tracked_aligned_with_gpu_blocks():
    """Regression for the second crash from the GPU run: after enough
    evict-readmit cycles, KVCachePolicy.gpu_blocks empties while our
    _tracked stays full, and select_victims returns []. The fix was
    to add `self._policy.gpu_blocks.add(block_id)` in the wrapper's
    add() because ensure_block early-returns when block_id is already
    in self.blocks. This drives 200 cycles and asserts the invariant
    on every one.
    """
    from kv_policy.vllm_evictor import CTMEvictorModern

    evictor = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    alloc = MockPrefixCachingBlockAllocator(
        num_blocks=16, block_size=16, evictor=evictor,
    )

    for cycle in range(200):
        # Allocate a fresh hash, free it (back into evictor).
        h = 1000 + cycle
        bid = alloc.allocate_immutable_block(h)
        alloc.free(bid)
        # Cross-call invariant must hold every cycle.
        assert evictor._tracked == evictor._policy.gpu_blocks, (
            f"cycle {cycle}: _tracked={sorted(evictor._tracked)} "
            f"vs gpu_blocks={sorted(evictor._policy.gpu_blocks)}"
        )


def test_bugs_1_and_3_at_scale_under_random_workload():
    """End-to-end stress with mixed allocate/free, drives the fixture
    through 5K cycles. Catches any remaining cross-call divergence."""
    from kv_policy.vllm_evictor import CTMEvictorModern

    evictor = CTMEvictorModern(num_blocks_capacity=256, block_size=16)
    alloc = MockPrefixCachingBlockAllocator(
        num_blocks=32, block_size=16, evictor=evictor,
    )
    alloc.stress_admit_evict_cycles(
        num_cycles=5000, unique_hashes=200, seed=137,
    )
    # Final invariant.
    assert evictor._tracked == evictor._policy.gpu_blocks


# --------------------------------------------------------------------- #
# Bug 5 — speculative storage on untracked block_ids
# --------------------------------------------------------------------- #


def test_bug5_set_block_pre_rope_keys_speculative_when_untracked():
    """The diag2 GPU run's smoking gun: 159K capture attempts, 0 blocks
    captured. set_block_pre_rope_keys gated on `block_id in
    self._tracked` and silently no-op'd. Every decode token writes
    to a mutable, not-yet-promoted block; vLLM hasn't called add()
    on it yet, so it's not tracked, so set_block_pre_rope_keys
    silently dropped. Fix: speculative storage. This test pins it.
    """
    from kv_policy.vllm_evictor import CTMEvictorModern

    evictor = CTMEvictorModern(num_blocks_capacity=64, block_size=16)
    alloc = MockPrefixCachingBlockAllocator(
        num_blocks=8, block_size=16, evictor=evictor,
    )

    # Decode-time write to a block that hasn't been promoted yet.
    # In production this is the slot vLLM is currently filling.
    speculative_block_id = 5
    assert speculative_block_id not in evictor._tracked
    evictor.set_block_pre_rope_keys(
        block_id=speculative_block_id,
        keys=[(0, [1.0, 0.0], [0.0, 1.0])],
        layer=0, head=0,
    )
    # Speculative counter ticks; key persists.
    assert evictor._phase4_set_pre_rope_keys_speculative == 1
    assert speculative_block_id in evictor._block_pre_rope_keys

    # Later vLLM promotes the block — admit it via the real path.
    bid = alloc.allocate_immutable_block(content_hash=12345)
    # Ensure we exercise the same physical block_id by freeing it
    # so it goes into the evictor's pool with the speculative keys.
    if bid != speculative_block_id:
        # The mock allocator picks free block_ids in LIFO order; on a
        # cold pool it will hand out 7, 6, 5, ... so we may need to
        # consume earlier IDs first. Drive until we get block 5.
        consumed = [bid]
        while bid != speculative_block_id and len(consumed) < 16:
            bid = alloc.allocate_immutable_block(
                content_hash=20000 + len(consumed),
            )
            consumed.append(bid)
    alloc.free(bid)
    # Speculative keys MUST still be available for trig scoring.
    assert speculative_block_id in evictor._block_pre_rope_keys

    # And on remove, GC fires.
    evictor.remove(speculative_block_id)
    assert speculative_block_id not in evictor._block_pre_rope_keys


# --------------------------------------------------------------------- #
# Bug 4 — hook ordering: rotary_emb fires BEFORE Attention.forward
# --------------------------------------------------------------------- #


def test_bug4_side_channel_set_before_rotary_fires_in_real_call_order():
    """Mirrors the actual Qwen2.5 vLLM call order:

        model.forward(input_ids, positions, kv_caches, attn_metadata)
            -> qkv_proj(hidden_states) [pre-RoPE Q,K,V]
            -> rotary_emb(positions, q, k) [<-- pre-RoPE capture fires]
            -> Attention.forward(...) [<-- old side-channel fired HERE]

    The first GPU run hooked Attention.forward — too late, since
    rotary already fired. Fix: hook the top-level model.forward,
    which fires before any submodule. This test reproduces that
    ordering and asserts the side-channel is set when rotary fires.
    Without the fix it fails at the snapshot assertion.
    """
    pytest.importorskip("torch")
    import torch
    from kv_policy.triattention import install_attn_metadata_side_channel
    from kv_policy.vllm_evictor import CTMEvictorModern

    captured_state: Dict[str, object] = {}

    class RotaryEmb(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class Attention(torch.nn.Module):
        def forward(self, q, k, v, kv_cache, attn_metadata):
            return q

    class FakeQwen2Model(torch.nn.Module):
        """Mimics the Qwen2 vLLM model's forward flow: rotary_emb is
        called BEFORE Attention from inside the model.forward."""

        def __init__(self):
            super().__init__()
            self.rotary_emb = RotaryEmb()
            self.attn = Attention()

        def forward(self, input_ids, positions, kv_caches, attn_metadata):
            q = torch.zeros((3, 8))
            k = torch.zeros((3, 8))
            v = torch.zeros((3, 8))
            # Real call order: rotary first (pre-RoPE point).
            q, k = self.rotary_emb(positions, q, k)
            # Then Attention.
            self.attn(q, k, v, None, attn_metadata)
            return input_ids

    class FakeMeta:
        slot_mapping = torch.tensor([0, 16, 32])
        num_decode_tokens = 3

    evictor = CTMEvictorModern(num_blocks_capacity=64, block_size=16)
    model = FakeQwen2Model()
    n_hooks = install_attn_metadata_side_channel(
        model=model, evictor=evictor,
    )
    assert n_hooks == 1

    def snapshot_at_rotary(module, args):
        captured_state["slot_mapping"] = (
            evictor._phase4_pending_slot_mapping
        )
        captured_state["num_decode_tokens"] = (
            evictor._phase4_pending_num_decode_tokens
        )

    model.rotary_emb.register_forward_pre_hook(snapshot_at_rotary)

    input_ids = torch.zeros((3,), dtype=torch.long)
    positions = torch.zeros((3,), dtype=torch.long)
    model(input_ids, positions, None, FakeMeta())

    # The side-channel MUST be visible at the moment rotary fires.
    # Without the fix (hooks on Attention only), this is None.
    assert captured_state["slot_mapping"] is not None, (
        "side-channel was None when rotary fired — would yield "
        "phase4_blocks_captured_with_pre_rope_keys=0 in production."
    )
    assert captured_state["num_decode_tokens"] == 3


# --------------------------------------------------------------------- #
# Bug 6 — window pruning integration with the runner
# --------------------------------------------------------------------- #


def test_bug6_window_pruning_fires_when_decode_tokens_tick():
    """The diag2 run had 159K captures but
    phase4_window_pruning_invocations=0 because the runner never
    called window_pruning_passed/pass. The fix wired both calls
    into AsyncEngineDriver._submit_one. This test pins the
    contract on the evictor itself: once enough decode tokens
    accumulate, window_pruning_passed returns True and
    window_pruning_pass actually runs.
    """
    from kv_policy.triattention import TrigScorer, QCenterStats
    from kv_policy.vllm_evictor import CTMEvictorModern

    stats = QCenterStats.from_lists(
        model_name="x", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=4,
        e_q_real=[[[0.5, 0.5]]],
        e_q_imag=[[[0.5, 0.5]]],
        e_q_norm=[[[1.0, 1.0]]],
    )
    evictor = CTMEvictorModern(
        num_blocks_capacity=128, block_size=16,
        trig_scorer=TrigScorer(stats=stats),
        window_pruning_interval=128,
    )

    # Admit enough blocks for pruning to have candidates.
    for bid in range(20):
        evictor.add(
            block_id=bid, content_hash=bid * 100,
            num_hashed_tokens=16, last_accessed=0.0,
        )
        evictor.set_block_pre_rope_keys(
            block_id=bid,
            keys=[(0, [0.5, 0.5], [0.5, 0.5])],
            layer=0, head=0,
        )

    # Tick decode tokens below the threshold — must NOT fire.
    for _ in range(127):
        assert evictor.window_pruning_passed(decode_tokens_emitted=1) is False
    # The 128th tick crosses the threshold — must fire.
    assert evictor.window_pruning_passed(decode_tokens_emitted=1) is True

    # And window_pruning_pass actually evicts.
    target = max(0, len(evictor._tracked) - 4)
    n_evicted = evictor.window_pruning_pass(target_blocks=target)
    assert n_evicted == 4
    assert evictor.window_pruning_invocations == 1


# --------------------------------------------------------------------- #
# Bug 7 — under non-trivial trig stats, Phase 4 evicts a different
# block than Phase 2
# --------------------------------------------------------------------- #


def test_bug7_phase4_picks_different_victim_than_phase2_under_meaningful_trig():
    """Phase 4 was bit-identical to Phase 2 for two GPU runs because
    the trig signal had no path to influence eviction (the
    window_pruning_pass call was never made, then the speculative
    storage gate was missing, then the runner didn't tick the
    state). Even with all those fixes, if the trig signal is
    constant across blocks it can't change decisions.

    This test sets up a meaningful gradient: blocks differ in their
    captured K vectors so trig scores differ, and asserts that
    window_pruning_pass evicts the LOWEST trig-scoring blocks,
    which is what Phase 4 is supposed to do differently from
    Phase 2's recency-only ordering.
    """
    from kv_policy.triattention import TrigScorer, QCenterStats
    from kv_policy.vllm_evictor import CTMEvictorModern

    stats = QCenterStats.from_lists(
        model_name="x", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=4,
        e_q_real=[[[1.0, 0.0]]],
        e_q_imag=[[[0.0, 0.0]]],
        e_q_norm=[[[1.0, 1.0]]],
    )
    evictor = CTMEvictorModern(
        num_blocks_capacity=64, block_size=16,
        trig_scorer=TrigScorer(stats=stats),
    )

    # Block 1's K aligns with the Q-center -> high trig score (kept).
    # Block 2's K is anti-aligned -> low trig score (evict-first).
    # Block 3 in between.
    aligned_k = [(0, [1.0, 0.0], [0.0, 0.0])]
    anti_aligned_k = [(0, [-1.0, 0.0], [0.0, 0.0])]
    middle_k = [(0, [0.0, 0.0], [0.0, 0.0])]

    for bid in range(1, 4):
        evictor.add(
            block_id=bid, content_hash=bid * 100,
            num_hashed_tokens=16, last_accessed=float(bid),
        )
    evictor.set_block_pre_rope_keys(1, aligned_k, layer=0, head=0)
    evictor.set_block_pre_rope_keys(2, anti_aligned_k, layer=0, head=0)
    evictor.set_block_pre_rope_keys(3, middle_k, layer=0, head=0)

    score_1 = evictor.trig_score_block(1)
    score_2 = evictor.trig_score_block(2)
    score_3 = evictor.trig_score_block(3)
    assert score_1 is not None and score_2 is not None and score_3 is not None
    assert score_1 != score_2, (
        "trig scores for differently-aligned K vectors are equal — "
        "TrigScorer is not actually using the Q-center stats."
    )

    # Window pruning must evict the lowest-scoring block first.
    initial = set(evictor._tracked)
    n_evicted = evictor.window_pruning_pass(target_blocks=2)
    assert n_evicted == 1
    surviving = set(evictor._tracked)
    evicted = initial - surviving
    assert len(evicted) == 1
    evicted_id = next(iter(evicted))
    scores = {1: score_1, 2: score_2, 3: score_3}
    assert scores[evicted_id] == min(scores.values()), (
        f"window_pruning evicted block {evicted_id} with score "
        f"{scores[evicted_id]}, but the minimum was "
        f"{min(scores.values())}. Pruning isn't ordered by trig "
        "score — Phase 4's mechanism is broken."
    )


# --------------------------------------------------------------------- #
# Bug 2 — workload-level: identical prompts collapse memory pressure
# under prefix caching
# --------------------------------------------------------------------- #


def test_bug2_identical_prompts_dedupe_to_zero_evictions_under_prefix_cache():
    """The first re-run had swap_out=0 across every cell because the
    runner generated `[100] * length` prompts identically across all
    30 requests. With prefix caching on, vLLM dedupes them to a
    single shared prefix → no memory pressure → no evictions. The
    fix injects a per-request unique head token. This test pins
    that contract: identical hashes hit cache, unique hashes force
    evictions.
    """
    from kv_policy.vllm_evictor import CTMEvictorModern

    # Identical-prompt regime: every allocation hits the same hash.
    evictor_dup = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    alloc_dup = MockPrefixCachingBlockAllocator(
        num_blocks=8, block_size=16, evictor=evictor_dup,
    )
    for _ in range(30):
        bid = alloc_dup.allocate_immutable_block(content_hash=42)
        alloc_dup.free(bid)
    # All 30 requests deduped to the same physical block. Zero
    # evictions because the cache never filled.
    assert len(alloc_dup._cached_blocks) == 1
    # Evictor sees exactly one entry, the deduped block.
    assert evictor_dup.num_blocks == 1

    # Unique-prefix regime: every prompt has a different head, so
    # each allocates a fresh block, forcing evictions.
    evictor_unique = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    alloc_unique = MockPrefixCachingBlockAllocator(
        num_blocks=8, block_size=16, evictor=evictor_unique,
    )
    n_evictions = 0
    for h in range(30):
        if not alloc_unique._free_block_ids and evictor_unique.num_blocks > 0:
            n_evictions += 1
        bid = alloc_unique.allocate_immutable_block(content_hash=h)
        alloc_unique.free(bid)
    assert n_evictions > 0, (
        "unique prompts did not force any evictions — the workload "
        "harness isn't engaging the eviction path."
    )
    # Many distinct hashes admitted.
    assert len(alloc_unique._cached_blocks) >= 8


# --------------------------------------------------------------------- #
# Meta-test: the fixture itself catches malformed evictors.
# --------------------------------------------------------------------- #


def test_fixture_actually_catches_a_broken_evictor():
    """Sanity check that MockPrefixCachingBlockAllocator's invariant
    asserts fire on a deliberately-broken evictor.

    The class below mimics the May 2026 GPU bug exactly: evict()
    returns (block_id, 0) when the block was already popped from
    its content-hash dict on a prior call.
    """
    class BrokenEvictor:
        """First evict() returns the real (block_id, content_hash);
        subsequent calls return (block_id, 0) — exactly the May 2026
        GPU bug where self._content_hash.pop(victim_id, 0) fell through
        to its default after select_victims re-picked an already-popped
        victim."""

        def __init__(self):
            self.tracked: Dict[int, int] = {}  # block_id -> content_hash
            self.evict_count = 0

        def __contains__(self, bid):
            return bid in self.tracked

        @property
        def num_blocks(self):
            return len(self.tracked)

        def add(self, block_id, content_hash, num_hashed_tokens, last_accessed):
            self.tracked[block_id] = content_hash

        def update(self, block_id, last_accessed):
            pass

        def remove(self, block_id):
            self.tracked.pop(block_id, None)

        def evict(self):
            self.evict_count += 1
            if not self.tracked:
                raise ValueError("empty")
            bid = next(iter(self.tracked))
            real_hash = self.tracked.pop(bid)
            content_hash = 0 if self.evict_count > 1 else real_hash
            return (bid, content_hash)

    alloc = MockPrefixCachingBlockAllocator(
        num_blocks=4, block_size=16, evictor=BrokenEvictor(),
    )
    # Admit 4 blocks, free them all.
    for h in (1, 2, 3, 4):
        bid = alloc.allocate_immutable_block(h * 100)
        alloc.free(bid)

    # First eviction works (returns the real hash).
    alloc._evict_one()

    # Second eviction returns content_hash=0; the fixture's assert
    # MUST fire.
    with pytest.raises(AssertionError, match="not in self._cached_blocks"):
        alloc._evict_one()


# --------------------------------------------------------------------- #
# Phase 4 outcome-improvement follow-up tests (post May-2026 negative
# result). These pin three changes intended to turn Phase 4 from
# "fires but doesn't change outcomes" into "fires and shifts the
# eviction sequence":
#
#   1. trig_score is blended into the main evict() path, not just
#      window_pruning_pass.
#   2. Per-layer call-counter indexing in install_pre_rope_capture
#      so shared-rotary models (Qwen2.5 / Llama / Mistral) get
#      per-layer stats instead of layer-pooled.
#   3. capture_every_n subsamples the speculative-storage work to
#      cut overhead.
# --------------------------------------------------------------------- #


def _build_phase4_evictor_with_two_distinct_trig_scores(
    trig_score_weight: float,
):
    """Helper: admit three blocks where the empirically-measured
    trig scores (under this Q-center setup + future-offsets default)
    split into "more-important" and "less-important" groups. We
    measure scores via trig_score_block before constructing the
    test scenario rather than assuming a sign convention — the
    paper's score formula combines s_trig (signed) and s_norm
    (positive), and the sign of the result depends on the (ω_f,
    delta) interaction in s_trig.
    """
    from kv_policy.triattention import TrigScorer, QCenterStats
    from kv_policy.vllm_evictor import CTMEvictorModern

    stats = QCenterStats.from_lists(
        model_name="x", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=4,
        e_q_real=[[[1.0, 0.0]]],
        e_q_imag=[[[0.0, 0.0]]],
        e_q_norm=[[[1.0, 1.0]]],
    )
    evictor = CTMEvictorModern(
        num_blocks_capacity=128, block_size=16,
        trig_scorer=TrigScorer(stats=stats),
        trig_score_weight=trig_score_weight,
    )
    for bid in (1, 2, 3):
        evictor.add(
            block_id=bid, content_hash=bid * 100,
            num_hashed_tokens=16, last_accessed=0.0,
        )
    evictor.set_block_pre_rope_keys(
        1, keys=[(0, [1.0, 0.0], [0.0, 0.0])], layer=0, head=0,
    )
    evictor.set_block_pre_rope_keys(
        2, keys=[(0, [-1.0, 0.0], [0.0, 0.0])], layer=0, head=0,
    )
    evictor.set_block_pre_rope_keys(
        3, keys=[(0, [-1.0, 0.0], [0.0, 0.0])], layer=0, head=0,
    )
    s1 = evictor.trig_score_block(1)
    s2 = evictor.trig_score_block(2)
    s3 = evictor.trig_score_block(3)
    return evictor, {1: s1, 2: s2, 3: s3}


def test_trig_blend_in_evict_picks_lowest_blended_score():
    """The May 2026 GPU run had trig firing but only via window
    pruning (~45 calls / 60s) — the main evict() ran ~3000× and
    was untouched. This test pins the new behavior: trig signal
    feeds the per-call evict() decision via blended scoring.
    Convention (empirical from the trig formula): higher trig
    score = more important, so we want the LOWEST blended score
    (base + w*trig) evicted first. Verify by computing the
    expected blended ranking and asserting evict() agrees.
    """
    evictor, scores = (
        _build_phase4_evictor_with_two_distinct_trig_scores(10.0)
    )
    # All blocks have the same base (no recency differentiation),
    # so blend ordering is determined entirely by trig: lowest
    # trig → first to evict.
    expected_victim = min(scores, key=lambda bid: scores[bid])

    victim_id, _ = evictor.evict()
    assert victim_id == expected_victim, (
        f"blend picked block {victim_id} (trig={scores[victim_id]}); "
        f"expected block {expected_victim} (trig={scores[expected_victim]}). "
        "All blocks tied on base score, so the lowest trig should win."
    )
    assert evictor._phase4_trig_blend_evict_calls >= 1


def test_trig_blend_can_override_base_ordering_with_strong_weight():
    """Stronger property: a high enough trig_score_weight forces
    the blend to follow trig ordering even when base ordering
    points the other way. We bump recency on the
    minimum-trig block to make base want to keep it; trig should
    still drive the eviction decision.
    """
    evictor, scores = (
        _build_phase4_evictor_with_two_distinct_trig_scores(100.0)
    )
    min_trig_block = min(scores, key=lambda bid: scores[bid])

    # Bump recency on the min-trig block so base-only would prefer
    # to KEEP it. Many updates → high last_access_step → high
    # recency contribution → high base score → last to be evicted
    # under base-only.
    for _ in range(100):
        evictor.update(block_id=min_trig_block, last_accessed=1.0)

    # With dominant trig_score_weight, the blend must still pick
    # the min-trig block (low importance overrides high recency).
    victim_id, _ = evictor.evict()
    assert victim_id == min_trig_block, (
        f"strong-trig blend picked {victim_id}; expected "
        f"{min_trig_block} (lowest trig). The trig signal must be "
        "strong enough to override base ordering."
    )


def test_trig_blend_falls_back_when_no_keys_captured():
    """When no blocks have captured K (cold start, or
    capture_every_n misses, or an early eviction before any
    capture), trig contribution = 0 and the evict() pick is
    determined solely by base scoring. Pinned via the diagnostic
    counter — without trig info, the blend code MUST count zero
    trig-driven pick changes."""
    from kv_policy.triattention import TrigScorer, QCenterStats
    from kv_policy.vllm_evictor import CTMEvictorModern

    stats = QCenterStats.from_lists(
        model_name="x", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=4,
        e_q_real=[[[1.0, 0.0]]],
        e_q_imag=[[[0.0, 0.0]]],
        e_q_norm=[[[1.0, 1.0]]],
    )
    evictor = CTMEvictorModern(
        num_blocks_capacity=64, block_size=16,
        trig_scorer=TrigScorer(stats=stats),
        trig_score_weight=10.0,
    )
    # No set_block_pre_rope_keys calls — no captured K anywhere.
    for bid in (1, 2, 3):
        evictor.add(
            block_id=bid, content_hash=bid * 100,
            num_hashed_tokens=16, last_accessed=0.0,
        )
    # Multiple evicts — trig must never change the pick.
    while evictor.num_blocks > 0:
        evictor.evict()
    # The blend ran (counter ticked) but with all trig scores
    # None it must have kept the base-only ordering throughout.
    assert getattr(evictor, "_phase4_trig_changed_pick", 0) == 0
    assert evictor._phase4_trig_blend_evict_calls > 0


def test_install_pre_rope_capture_call_counter_indexing():
    """Per-layer indexing on a shared-rotary model: one rotary_emb
    module fires N times per model.forward (once per layer); the
    pre-hook uses a counter to attribute each firing to the correct
    layer. Pinned via a snapshot of the layer_idx the capture
    function sees on each call.
    """
    pytest.importorskip("torch")
    import torch
    from kv_policy.triattention import (
        install_attn_metadata_side_channel,
        install_pre_rope_capture,
    )
    from kv_policy.vllm_evictor import CTMEvictorModern

    seen_layers: List[int] = []

    class RotaryEmb(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class FakeLlamaModel(torch.nn.Module):
        """Mimics Qwen2/Llama: ONE shared rotary_emb, fired N times
        per model.forward."""

        def __init__(self, n_layers: int):
            super().__init__()
            self.rotary_emb = RotaryEmb()
            self.n_layers = n_layers

        def forward(self, input_ids, positions, kv_caches, attn_metadata):
            q = torch.zeros((1, 4))
            k = torch.zeros((1, 4))
            for _ in range(self.n_layers):
                self.rotary_emb(positions, q, k)
            return input_ids

    class FakeMeta:
        slot_mapping = torch.tensor([0])
        num_decode_tokens = 1

    evictor = CTMEvictorModern(num_blocks_capacity=64, block_size=16)
    model = FakeLlamaModel(n_layers=4)
    install_attn_metadata_side_channel(model=model, evictor=evictor)
    n_hooked = install_pre_rope_capture(
        model=model, evictor=evictor,
        num_layers=4,
        layer_for_scoring=2,  # capture from layer 2 specifically
    )
    assert n_hooked == 1  # one rotary_emb module hooked

    # Snapshot which layer_idx the capture sees on each firing.
    original_capture = None
    from kv_policy import triattention as ta_mod
    original_capture = ta_mod._capture_pre_rope_k_to_evictor

    def spy(*, inputs, evictor, layer, head, inferred_head_dim):
        seen_layers.append(layer)

    ta_mod._capture_pre_rope_k_to_evictor = spy
    try:
        model(
            torch.zeros((1,), dtype=torch.long),
            torch.zeros((1,), dtype=torch.long),
            None,
            FakeMeta(),
        )
    finally:
        ta_mod._capture_pre_rope_k_to_evictor = original_capture

    # Capture only fires on the target layer; with layer_for_scoring=2
    # and call-counter indexing across 4 layers per forward, exactly
    # one capture call should land on layer 2.
    assert seen_layers == [2]


def test_install_pre_rope_capture_per_module_indexing_unchanged():
    """Backwards compat: when num_layers == n_rotary_modules (or
    None), behavior matches the original per-module indexing.
    Pinned because the call-counter path is opt-in.
    """
    pytest.importorskip("torch")
    import torch
    from kv_policy.triattention import install_pre_rope_capture
    from kv_policy.vllm_evictor import CTMEvictorModern

    class RotaryEmb(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class FakeMultiRotaryModel(torch.nn.Module):
        """Mimics an unusual model where each layer has its OWN
        rotary_emb. Per-module indexing must apply here."""

        def __init__(self, n_layers: int):
            super().__init__()
            self.rotaries = torch.nn.ModuleList(
                [RotaryEmb() for _ in range(n_layers)]
            )

    evictor = CTMEvictorModern(num_blocks_capacity=64, block_size=16)
    model = FakeMultiRotaryModel(n_layers=3)
    n = install_pre_rope_capture(
        model=model, evictor=evictor,
        num_layers=None,  # auto = n_modules = 3
    )
    assert n == 3


def test_install_pre_rope_capture_subsample_knob():
    """capture_every_n subsamples the speculative-storage work.
    With N=4, only every 4th rotary firing at the target layer
    runs capture. The other 3 are skipped (counted in
    _phase4_capture_subsample_skips).
    """
    pytest.importorskip("torch")
    import torch
    from kv_policy.triattention import (
        install_attn_metadata_side_channel,
        install_pre_rope_capture,
    )
    from kv_policy.vllm_evictor import CTMEvictorModern

    class RotaryEmb(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class FakeModel(torch.nn.Module):
        def __init__(self, n_layers: int):
            super().__init__()
            self.rotary_emb = RotaryEmb()
            self.n_layers = n_layers

        def forward(self, input_ids, positions, kv_caches, attn_metadata):
            q = torch.zeros((1, 4))
            k = torch.zeros((1, 4))
            for _ in range(self.n_layers):
                self.rotary_emb(positions, q, k)
            return input_ids

    class FakeMeta:
        slot_mapping = torch.tensor([0])
        num_decode_tokens = 1

    evictor = CTMEvictorModern(num_blocks_capacity=64, block_size=16)
    model = FakeModel(n_layers=2)
    install_attn_metadata_side_channel(model=model, evictor=evictor)
    install_pre_rope_capture(
        model=model, evictor=evictor,
        num_layers=2, layer_for_scoring=1,  # target layer = 1
        capture_every_n=4,
    )

    # Drive 8 forwards. Each forward fires rotary 2× (layers 0 and 1).
    # Capture only runs at layer 1 (4 attempts across 8 forwards).
    # With capture_every_n=4, the first 3 of those 4 are skipped;
    # only the 4th invokes the capture function.
    for _ in range(8):
        model(
            torch.zeros((1,), dtype=torch.long),
            torch.zeros((1,), dtype=torch.long),
            None,
            FakeMeta(),
        )
    # 8 forwards × 2 layers = 16 rotary calls. 8 hit the target
    # layer (layer 1). Of those 8, capture_every_n=4 means only 2
    # actually run (the 4th and 8th).
    skips = getattr(evictor, "_phase4_capture_subsample_skips", 0)
    assert skips == 6, (
        f"expected 6 subsample skips (8 target-layer firings - 2 "
        f"actual captures); got {skips}"
    )


def test_calibrate_q_centers_uses_call_counter_indexing_when_num_layers_set():
    """Calibration sister of the runtime per-layer test: pass
    num_layers > n_rotary_modules to opt into call-counter
    indexing during calibration. The resulting QCenterStats has
    the requested num_layers, not n_modules.
    """
    pytest.importorskip("torch")
    import torch
    from kv_policy.triattention import calibrate_q_centers

    captures: List[int] = []

    class RotaryEmb(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class FakeModel(torch.nn.Module):
        def __init__(self, n_layers: int):
            super().__init__()
            self.rotary_emb = RotaryEmb()
            self.n_layers = n_layers

        def forward(self, input_ids=None):
            positions = torch.zeros((1,), dtype=torch.long)
            for _ in range(self.n_layers):
                q = torch.zeros((1, 4))
                k = torch.zeros((1, 4))
                self.rotary_emb(positions, q, k)
            return torch.zeros(1)

    model = FakeModel(n_layers=4)

    def driver(m):
        for _ in range(2):
            m()  # 2 forwards × 4 layers = 8 rotary calls

    stats = calibrate_q_centers(
        model=model, forward_callable=driver,
        model_name="fake-llama-style",
        num_heads=1, head_dim=4, num_kv_heads=1,
        num_layers=4,
        max_tokens=10_000,
    )
    assert stats.num_layers == 4
    # All four per-layer stats slots populated (each layer should
    # have absorbed 2 firings). Assert non-empty arrays.
    assert len(stats.e_q_real) == 4
    for layer_idx in range(4):
        assert len(stats.e_q_real[layer_idx]) == 1  # num_heads


def test_calibrate_q_centers_rejects_call_counter_with_multiple_modules():
    """Sanity guard: call-counter indexing only makes sense on
    shared-rotary models. If we asked for num_layers > n_modules
    AND there are multiple modules, that's a configuration error;
    raise rather than silently mis-attribute."""
    pytest.importorskip("torch")
    import torch
    from kv_policy.triattention import calibrate_q_centers

    class RotaryEmb(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class FakeModel(torch.nn.Module):
        def __init__(self, n_modules: int):
            super().__init__()
            self.rotaries = torch.nn.ModuleList(
                [RotaryEmb() for _ in range(n_modules)]
            )

    with pytest.raises(ValueError, match="exactly one shared"):
        calibrate_q_centers(
            model=FakeModel(n_modules=3),
            forward_callable=lambda m: None,
            model_name="x",
            num_heads=1, head_dim=4, num_kv_heads=1,
            num_layers=10,  # > 3, but n_modules=3, so error
            max_tokens=1000,
        )
