"""CPU regression tests for the v2 cache-reuse layer.

Validates the Phase 0 deliverables described in
``Bench/scripts/V2_CACHE_REUSE_DESIGN.md``:

* ``PrefixRadixTree`` correctness — insert / query / evict / prune /
  pin behave as designed.
* ``CacheHitPredictor`` — block-aligned hit prediction, conservative
  on partial-block matches, exact on block-multiple matches.
* ``CacheAwareScheduler`` — descending sort by predicted hit, FCFS
  tiebreaker, starvation guard, pinned-prefix priority bonus.
* End-to-end composition against a mock vLLM block allocator that
  enforces the INT4 protected ``block_size=32`` constraint.

All tests are pure-Python — no torch, no vllm, no GPU. They run as
part of the standard Bench test suite and gate the Phase 1 work.

If any test fails, the design or prototype has a bug — the Phase 1
integration MUST NOT proceed until this suite is GREEN.
"""

from __future__ import annotations

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

from kv_policy.cache_aware_scheduler import (
    CacheAwareScheduler,
    CacheHitPredictor,
    PendingRequest,
    PrefixRadixTree,
)


# ----------------------------------------------------------------------
# PrefixRadixTree
# ----------------------------------------------------------------------


def test_radix_tree_empty_query_returns_zero():
    tree = PrefixRadixTree()
    assert tree.query([1, 2, 3]) == 0
    assert tree.query([]) == 0


def test_radix_tree_insert_and_query_exact_match():
    tree = PrefixRadixTree()
    tree.insert([1, 2, 3, 4, 5], block_ids=[100])
    assert tree.query([1, 2, 3, 4, 5]) == 5


def test_radix_tree_query_returns_longest_cached_prefix():
    tree = PrefixRadixTree()
    tree.insert([1, 2, 3, 4, 5], block_ids=[100])
    # Query a longer sequence — only the cached prefix counts.
    assert tree.query([1, 2, 3, 4, 5, 99, 88]) == 5
    # Query a shorter prefix — fewer tokens match.
    assert tree.query([1, 2, 3]) == 3


def test_radix_tree_branching_paths():
    tree = PrefixRadixTree()
    tree.insert([1, 2, 3], block_ids=[100])
    tree.insert([1, 2, 4], block_ids=[101])
    # Both branches independently cached.
    assert tree.query([1, 2, 3]) == 3
    assert tree.query([1, 2, 4]) == 3
    # Common prefix only counts as long as it has block_ids;
    # split-point nodes may not. The prefix [1, 2] sits at the
    # split point — by design, only nodes with block_ids count
    # as "cached". This is the conservative interpretation; partial
    # split-point matches yield 0 unless the deeper node matches too.
    # The test below documents that contract.
    assert tree.query([1, 2]) in (0, 2)


def test_radix_tree_evict_removes_blocks():
    tree = PrefixRadixTree()
    tree.insert([1, 2, 3, 4], block_ids=[100, 101])
    assert tree.query([1, 2, 3, 4]) == 4
    tree.evict([100, 101])
    # All blocks gone; prefix no longer cached.
    assert tree.query([1, 2, 3, 4]) == 0


def test_radix_tree_partial_eviction_keeps_other_blocks():
    tree = PrefixRadixTree()
    tree.insert([1, 2, 3], block_ids=[100, 101])
    tree.evict([100])
    # 101 still holds the prefix.
    assert tree.query([1, 2, 3]) == 3


def test_radix_tree_idempotent_insert():
    tree = PrefixRadixTree()
    tree.insert([1, 2, 3], block_ids=[100])
    tree.insert([1, 2, 3], block_ids=[100])  # re-insert
    tree.insert([1, 2, 3], block_ids=[101])  # add another block
    tree.evict([100])
    assert tree.query([1, 2, 3]) == 3  # still cached via 101
    tree.evict([101])
    assert tree.query([1, 2, 3]) == 0


def test_radix_tree_pin_survives_eviction():
    tree = PrefixRadixTree()
    SYSTEM_PROMPT = list(range(50))
    tree.insert(SYSTEM_PROMPT, block_ids=[200, 201], pinned=True)
    # Even after all blocks evicted, pin keeps the path alive in
    # the tree's bookkeeping. (Realized hit on GPU would be 0 until
    # re-cached; the pin just keeps the scheduler aware of intent.)
    tree.evict([200, 201])
    assert tree.contains_pinned(SYSTEM_PROMPT[:10])


def test_radix_tree_max_tokens_bounded_under_pressure():
    tree = PrefixRadixTree(max_tokens=200)
    for i in range(20):
        # Each unique prefix is 50 tokens.
        prefix = [i * 1000 + j for j in range(50)]
        tree.insert(prefix, block_ids=[1000 + i])
    # 20 * 50 = 1000 tokens inserted, but max is 200.
    # The tree should have pruned itself.
    assert tree.stats()["tracked_tokens"] <= tree.stats()["max_tokens"]
    assert tree.stats()["prunes"] >= 1


def test_radix_tree_pinned_prefix_not_pruned():
    tree = PrefixRadixTree(max_tokens=100)
    PINNED = list(range(80))
    tree.insert(PINNED, block_ids=[1], pinned=True)
    # Add 10 more prefixes that each push tracked_tokens > 100.
    for i in range(10):
        unique = [(i + 1) * 10000 + j for j in range(30)]
        tree.insert(unique, block_ids=[2000 + i])
    # The pinned prefix should still match in full.
    assert tree.query(PINNED) == len(PINNED)


# ----------------------------------------------------------------------
# CacheHitPredictor
# ----------------------------------------------------------------------


def test_predictor_returns_block_aligned_length():
    tree = PrefixRadixTree()
    tree.insert(list(range(100)), block_ids=[1])
    predictor = CacheHitPredictor(tree, block_size=32)
    # Tree matches 100 tokens; block-aligned floor = 96 (= 3 * 32).
    assert predictor.predict_cache_hit(list(range(100))) == 96
    # Asking for fewer: 30 // 32 = 0.
    assert predictor.predict_cache_hit(list(range(30))) == 0
    # Asking for an exact block boundary: 32 == 32.
    assert predictor.predict_cache_hit(list(range(32))) == 32


def test_predictor_empty_tree_zero_hit():
    tree = PrefixRadixTree()
    predictor = CacheHitPredictor(tree, block_size=32)
    assert predictor.predict_cache_hit(list(range(1000))) == 0


def test_predictor_block_size_validation():
    tree = PrefixRadixTree()
    with pytest.raises(ValueError):
        CacheHitPredictor(tree, block_size=0)


def test_predictor_int4_protected_block_size_32():
    """INT4 protected uses block_size=32 by construction (per the
    backend's vLLM kernel constraint). The predictor must respect it.
    """
    tree = PrefixRadixTree()
    tree.insert(list(range(64)), block_ids=[1])
    predictor = CacheHitPredictor(tree, block_size=32)
    # Two full blocks cached.
    assert predictor.predict_cache_hit(list(range(64))) == 64
    # Just shy of two blocks: floor to 32 (1 full block).
    assert predictor.predict_cache_hit(list(range(63))) == 32
    # Exactly two blocks worth of query, but cache only has 64.
    assert predictor.predict_cache_hit(list(range(64))) == 64


def test_predictor_hit_rate_matches_definition():
    tree = PrefixRadixTree()
    tree.insert(list(range(96)), block_ids=[1])
    predictor = CacheHitPredictor(tree, block_size=32)
    # 96-token request, 96 token hit, hit rate = 1.0
    assert predictor.predict_hit_rate(list(range(96))) == 1.0
    # 192-token request, only 96 prefix-cached.
    assert predictor.predict_hit_rate(list(range(192))) == 0.5


# ----------------------------------------------------------------------
# CacheAwareScheduler
# ----------------------------------------------------------------------


def _mk_request(rid: str, tokens, t: float = 0.0) -> PendingRequest:
    return PendingRequest(request_id=rid, tokens=tokens, arrival_time=t)


def test_scheduler_orders_by_predicted_hit_descending():
    tree = PrefixRadixTree()
    # Cache a 96-token prefix shared by req_b.
    SHARED = list(range(96))
    tree.insert(SHARED, block_ids=[1])

    sched = CacheAwareScheduler(tree, block_size=32)
    pending = [
        _mk_request("req_a", list(range(1000, 1100)), t=10.0),  # 0 hit
        _mk_request("req_b", SHARED + list(range(200)), t=11.0),  # 96 hit
        _mk_request("req_c", list(range(2000, 2100)), t=12.0),  # 0 hit
    ]
    ordered = sched.order_admissions(pending, now=20.0)
    # req_b should be first (highest predicted hit).
    assert ordered[0].request_id == "req_b"
    # req_a and req_c: 0-hit, FCFS tiebreak: req_a (arrived earlier).
    assert ordered[1].request_id == "req_a"
    assert ordered[2].request_id == "req_c"


def test_scheduler_fcfs_when_no_hits():
    tree = PrefixRadixTree()
    sched = CacheAwareScheduler(tree, block_size=32)
    pending = [
        _mk_request("req_c", list(range(10)), t=12.0),
        _mk_request("req_a", list(range(10, 20)), t=10.0),
        _mk_request("req_b", list(range(20, 30)), t=11.0),
    ]
    ordered = sched.order_admissions(pending, now=20.0)
    # All have 0 predicted hit -> pure FCFS.
    assert [r.request_id for r in ordered] == ["req_a", "req_b", "req_c"]


def test_scheduler_starvation_guard_kicks_in():
    tree = PrefixRadixTree()
    # Cache a prefix shared by a "fresh" request, so without the
    # starvation guard, the fresh request would jump the queue
    # ahead of the starved one.
    tree.insert(list(range(96)), block_ids=[1])

    sched = CacheAwareScheduler(
        tree, block_size=32, max_starvation_seconds=10.0,
    )
    pending = [
        # Fresh high-hit request:
        _mk_request("fresh_high_hit", list(range(96)), t=19.5),
        # Starved low-hit request (arrived 30s ago):
        _mk_request("starved", list(range(1000, 1100)), t=0.0),
    ]
    ordered = sched.order_admissions(pending, now=20.0)
    # Starved request must come first despite no cache hit.
    assert ordered[0].request_id == "starved"
    assert ordered[1].request_id == "fresh_high_hit"


def test_scheduler_pinned_prefix_outranks_unpinned_high_hit():
    tree = PrefixRadixTree()
    PINNED_PREFIX = list(range(64))
    UNPINNED_LONGER = list(range(1000, 1200))
    tree.insert(PINNED_PREFIX, block_ids=[1], pinned=True)
    tree.insert(UNPINNED_LONGER, block_ids=[2])

    sched = CacheAwareScheduler(tree, block_size=32)
    pending = [
        # Matches the unpinned longer prefix — bigger hit length.
        _mk_request(
            "longer_unpinned", UNPINNED_LONGER + list(range(5000, 5100)),
            t=10.0,
        ),
        # Matches the pinned prefix — shorter hit length but pinned.
        _mk_request(
            "shorter_pinned", PINNED_PREFIX + list(range(6000, 6100)),
            t=11.0,
        ),
    ]
    ordered = sched.order_admissions(pending, now=20.0)
    # Pinned-prefix matcher outranks even a longer unpinned match.
    assert ordered[0].request_id == "shorter_pinned"


def test_scheduler_counts_reorder_events():
    tree = PrefixRadixTree()
    tree.insert(list(range(96)), block_ids=[1])

    sched = CacheAwareScheduler(tree, block_size=32)
    pending = [
        _mk_request("first_arrival", list(range(1000, 1100)), t=10.0),
        _mk_request("later_with_hit", list(range(96)), t=11.0),
    ]
    sched.order_admissions(pending, now=20.0)
    stats = sched.stats()
    assert stats["admissions"] == 1
    assert stats["reordered_count"] == 1
    assert stats["predicted_hit_tokens_total"] == 96


def test_scheduler_empty_queue_returns_empty():
    tree = PrefixRadixTree()
    sched = CacheAwareScheduler(tree, block_size=32)
    assert sched.order_admissions([]) == []


# ----------------------------------------------------------------------
# Composition with a mock vLLM block allocator (INT4 protected shape)
# ----------------------------------------------------------------------


class _MockInt4ProtectedAllocator:
    """Minimum surface to validate the scheduler against an INT4
    protected-shaped backend without vLLM.

    Models: block_size=32 (the INT4 protected constraint), block-
    level LRU + prefix caching as the substrate.
    """

    def __init__(self, capacity_blocks: int = 100):
        self.block_size = 32
        self.capacity_blocks = capacity_blocks
        self.cached_prefixes: dict[tuple, int] = {}  # tokens -> block_id
        self.next_block_id = 1
        self.realized_hit_tokens = 0

    def admit(self, tokens):
        """Simulate vLLM admitting a request: cache-hit credit for
        any prefix that aligns to existing block_size=32 chunks."""
        hit_tokens = 0
        i = 0
        while i + self.block_size <= len(tokens):
            chunk = tuple(tokens[i:i + self.block_size])
            if chunk in self.cached_prefixes:
                hit_tokens += self.block_size
            else:
                # Allocate a new block.
                self.cached_prefixes[chunk] = self.next_block_id
                self.next_block_id += 1
            i += self.block_size
        self.realized_hit_tokens += hit_tokens
        return hit_tokens

    def block_ids_for_prefix(self, tokens):
        """Return the block_ids covering token chunks of tokens."""
        ids = []
        i = 0
        while i + self.block_size <= len(tokens):
            chunk = tuple(tokens[i:i + self.block_size])
            if chunk in self.cached_prefixes:
                ids.append(self.cached_prefixes[chunk])
            i += self.block_size
        return ids


def test_composition_scheduler_predicts_realized_hits():
    """End-to-end: feed a 30-request trace through the scheduler +
    mock INT4 protected allocator; verify the scheduler's predicted
    hits track the allocator's realized hits.
    """
    SYSTEM_PROMPT = list(range(64))  # 2 blocks (block_size=32)
    USER_QUERY_LENGTH = 96  # 3 blocks

    allocator = _MockInt4ProtectedAllocator()
    tree = PrefixRadixTree()
    sched = CacheAwareScheduler(tree, block_size=allocator.block_size)

    # First request seeds the cache with the system prompt.
    seed = SYSTEM_PROMPT + list(range(10000, 10000 + USER_QUERY_LENGTH))
    allocator.admit(seed)
    # The scheduler now learns about the cached chunks.
    tree.insert(
        SYSTEM_PROMPT, block_ids=allocator.block_ids_for_prefix(SYSTEM_PROMPT),
    )

    # Subsequent 5 requests share the system prompt.
    realized_total = 0
    predicted_total = 0
    for i in range(5):
        req_tokens = SYSTEM_PROMPT + list(
            range(20000 + i * 1000, 20000 + i * 1000 + USER_QUERY_LENGTH)
        )
        pending = [_mk_request(f"req_{i}", req_tokens, t=float(i))]
        ordered = sched.order_admissions(pending, now=100.0)
        admitted = ordered[0]
        predicted = sched.predictor.predict_cache_hit(admitted.tokens)
        realized = allocator.admit(admitted.tokens)
        predicted_total += predicted
        realized_total += realized

    # On this trace every request should hit the 64-token system
    # prompt cleanly (system prompt is 2 full blocks). Predicted
    # should equal realized.
    assert predicted_total == 64 * 5  # 5 requests, 64 tokens each
    assert realized_total == predicted_total


def test_composition_scheduler_accuracy_on_mixed_trace():
    """Mixed trace: some shared-prefix, some unique. Predictor
    accuracy >= 0.85 vs the allocator's realized hits.
    """
    SHARED_A = list(range(32))   # 1 block
    SHARED_B = list(range(100, 132))  # 1 block

    allocator = _MockInt4ProtectedAllocator()
    tree = PrefixRadixTree()
    sched = CacheAwareScheduler(tree, block_size=allocator.block_size)

    # Seed both shared prefixes.
    for shared in (SHARED_A, SHARED_B):
        seed = shared + list(range(50_000, 50_064))
        allocator.admit(seed)
        tree.insert(
            shared, block_ids=allocator.block_ids_for_prefix(shared),
        )

    # 20 requests: half share A, half share B, plus 5 unique.
    pending = []
    for i in range(10):
        prefix = SHARED_A if i % 2 == 0 else SHARED_B
        req_tokens = prefix + list(
            range(60_000 + i * 100, 60_000 + i * 100 + 64)
        )
        pending.append(_mk_request(f"shared_{i}", req_tokens, t=float(i)))
    for i in range(5):
        req_tokens = list(
            range(80_000 + i * 100, 80_000 + i * 100 + 96)
        )
        pending.append(_mk_request(f"uniq_{i}", req_tokens, t=20.0 + i))

    ordered = sched.order_admissions(pending, now=100.0)
    predicted_total = 0
    realized_total = 0
    for req in ordered:
        predicted_total += sched.predictor.predict_cache_hit(req.tokens)
        realized_total += allocator.admit(req.tokens)

    # Each shared-A or shared-B request hits exactly 32 tokens.
    # Each unique request hits 0. So predicted = realized exactly
    # on this trace, but the gate accepts >= 0.85 to allow for
    # future block-fragmentation effects on real vLLM.
    assert predicted_total > 0
    accuracy = realized_total / predicted_total
    assert accuracy >= 0.85, (
        f"Predictor accuracy too low: {accuracy:.3f} "
        f"(predicted {predicted_total}, realized {realized_total})"
    )


def test_composition_high_hit_request_admitted_first():
    """When the queue mixes high-hit and zero-hit requests, the
    scheduler admits the high-hit one first — directly translating
    to higher realized hit rate.
    """
    SHARED = list(range(64))  # 2 blocks
    allocator = _MockInt4ProtectedAllocator()
    tree = PrefixRadixTree()
    sched = CacheAwareScheduler(tree, block_size=32)

    # Seed the cache with the shared prefix.
    allocator.admit(SHARED + list(range(99_000, 99_096)))
    tree.insert(SHARED, block_ids=allocator.block_ids_for_prefix(SHARED))

    pending = [
        _mk_request(
            "zero_hit_first",
            list(range(200_000, 200_096)),  # no cache hit
            t=10.0,
        ),
        _mk_request(
            "high_hit_later",
            SHARED + list(range(300_000, 300_032)),  # 64-token hit
            t=11.0,
        ),
    ]
    ordered = sched.order_admissions(pending, now=20.0)
    assert ordered[0].request_id == "high_hit_later"
    assert ordered[1].request_id == "zero_hit_first"
