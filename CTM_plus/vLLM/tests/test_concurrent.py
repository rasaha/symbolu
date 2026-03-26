"""
Concurrency stress tests for CTM+ vLLM data structures.

Validates thread-safety of the lock-free fast path, striped locking,
and concurrent data structures under realistic contention scenarios.

Run: python -m pytest CTM_plus/vLLM/tests/test_concurrent.py -v
"""

import os
import random
import sys
import threading
import time
from collections import Counter
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from ctm_plus_vllm.concurrent import (
    AtomicCounter,
    AtomicStats,
    ConcurrentBlockMap,
    ConcurrentSet,
    MPSCQueue,
    RCUDict,
    StripedLock,
)
from ctm_plus_vllm.evictor import CTMEvictionPolicy, BlockState
from ctm_plus_vllm.config import CTMvLLMConfig
from ctm_plus_vllm.block_manager import CTMBlockSpaceManager


# ============================================================================
# Helpers
# ============================================================================

def run_threads(target, num_threads: int, *args) -> List[threading.Thread]:
    """Launch num_threads threads running target(*args) and wait."""
    threads = []
    barrier = threading.Barrier(num_threads)
    for _ in range(num_threads):
        t = threading.Thread(target=target, args=(barrier, *args))
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive(), "Thread did not complete in time"
    return threads


# ============================================================================
# AtomicCounter tests
# ============================================================================

class TestAtomicCounter:
    def test_single_thread_basic(self):
        c = AtomicCounter()
        assert c.value == 0
        assert c.increment() == 1
        assert c.increment(5) == 6
        assert c.decrement(2) == 4
        assert c.value == 4

    def test_compare_and_swap(self):
        c = AtomicCounter(10)
        assert c.compare_and_swap(10, 20) is True
        assert c.value == 20
        assert c.compare_and_swap(10, 30) is False  # expected doesn't match
        assert c.value == 20

    def test_concurrent_increments(self):
        """Verify no lost updates under contention."""
        c = AtomicCounter()
        num_threads = 16
        increments_per_thread = 10_000

        def worker(barrier):
            barrier.wait()
            for _ in range(increments_per_thread):
                c.increment()

        run_threads(worker, num_threads)
        assert c.value == num_threads * increments_per_thread


# ============================================================================
# AtomicStats tests
# ============================================================================

class TestAtomicStats:
    def test_concurrent_different_counters(self):
        """Concurrent increments to different counters should never contend."""
        stats = AtomicStats("hits", "misses", "evictions")
        num_threads = 8
        per_thread = 5_000

        def worker(barrier, name):
            barrier.wait()
            for _ in range(per_thread):
                stats.increment(name)

        threads = []
        barrier = threading.Barrier(num_threads * 3)
        for name in ["hits", "misses", "evictions"]:
            for _ in range(num_threads):
                t = threading.Thread(target=worker, args=(barrier, name))
                t.start()
                threads.append(t)
        for t in threads:
            t.join(timeout=30)

        snap = stats.snapshot()
        assert snap["hits"] == num_threads * per_thread
        assert snap["misses"] == num_threads * per_thread
        assert snap["evictions"] == num_threads * per_thread


# ============================================================================
# ConcurrentBlockMap tests
# ============================================================================

class TestConcurrentBlockMap:
    def test_basic_operations(self):
        m = ConcurrentBlockMap[str](num_shards=4)
        m.put(1, "a")
        m.put(2, "b")
        assert m.get(1) == "a"
        assert 2 in m
        assert 3 not in m
        assert len(m) == 2
        m.remove(1)
        assert m.get(1) is None
        assert len(m) == 1

    def test_update_in_place(self):
        m = ConcurrentBlockMap[BlockState](num_shards=4)
        bs = BlockState(block_id=42, access_count=0)
        m.put(42, bs)
        m.update_in_place(42, lambda b: b.update_access(1.0))
        assert m.get(42).access_count == 1
        assert m.get(42).last_access_time == 1.0

    def test_concurrent_put_get(self):
        """Concurrent writers and readers on different keys."""
        m = ConcurrentBlockMap[int](num_shards=16)
        num_threads = 16
        keys_per_thread = 1_000
        errors = []

        def writer(barrier, tid):
            barrier.wait()
            try:
                for i in range(keys_per_thread):
                    key = tid * keys_per_thread + i
                    m.put(key, key * 2)
            except Exception as e:
                errors.append(e)

        def reader(barrier, tid):
            barrier.wait()
            try:
                for i in range(keys_per_thread):
                    key = tid * keys_per_thread + i
                    val = m.get(key)
                    if val is not None and val != key * 2:
                        errors.append(f"Corruption: key={key}, val={val}")
            except Exception as e:
                errors.append(e)

        # Run writers
        barrier = threading.Barrier(num_threads)
        threads = []
        for tid in range(num_threads):
            t = threading.Thread(target=writer, args=(barrier, tid))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Writer errors: {errors}"
        assert len(m) == num_threads * keys_per_thread

        # Run readers
        barrier2 = threading.Barrier(num_threads)
        threads2 = []
        for tid in range(num_threads):
            t = threading.Thread(target=reader, args=(barrier2, tid))
            t.start()
            threads2.append(t)
        for t in threads2:
            t.join(timeout=30)

        assert not errors, f"Reader errors: {errors}"

    def test_concurrent_update_in_place(self):
        """Many threads updating the same key's state concurrently."""
        m = ConcurrentBlockMap[BlockState](num_shards=4)
        bs = BlockState(block_id=1, access_count=0)
        m.put(1, bs)

        num_threads = 16
        per_thread = 1_000

        def worker(barrier):
            barrier.wait()
            for _ in range(per_thread):
                m.update_in_place(1, lambda b: setattr(
                    b, "access_count", b.access_count + 1
                ))

        run_threads(worker, num_threads)
        assert m.get(1).access_count == num_threads * per_thread


# ============================================================================
# ConcurrentSet tests
# ============================================================================

class TestConcurrentSet:
    def test_concurrent_add_discard(self):
        s = ConcurrentSet(num_shards=8)
        num_threads = 16
        per_thread = 2_000
        errors = []

        def adder(barrier):
            barrier.wait()
            for i in range(per_thread):
                s.add(i)

        def remover(barrier):
            barrier.wait()
            for i in range(per_thread):
                s.discard(i)

        # Add from many threads
        run_threads(adder, num_threads)
        assert len(s) == per_thread  # Deduplicated

        # Remove from many threads
        run_threads(remover, num_threads)
        assert len(s) == 0


# ============================================================================
# RCUDict tests
# ============================================================================

class TestRCUDict:
    def test_concurrent_read_write(self):
        """Readers should never see partial state."""
        d = RCUDict[str]()
        num_writers = 4
        num_readers = 12
        iterations = 2_000
        errors = []

        def writer(barrier, tid):
            barrier.wait()
            for i in range(iterations):
                d.put(i, f"v{tid}_{i}")

        def reader(barrier, _tid):
            barrier.wait()
            for _ in range(iterations):
                # Snapshot read: should be a valid dict at all times
                snap = d.snapshot()
                for k, v in snap.items():
                    if not isinstance(v, str):
                        errors.append(f"type error: {k}={v}")

        barrier = threading.Barrier(num_writers + num_readers)
        threads = []
        for tid in range(num_writers):
            t = threading.Thread(target=writer, args=(barrier, tid))
            t.start()
            threads.append(t)
        for tid in range(num_readers):
            t = threading.Thread(target=reader, args=(barrier, tid))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=30)

        assert not errors


# ============================================================================
# MPSCQueue tests
# ============================================================================

class TestMPSCQueue:
    def test_multi_producer_single_consumer(self):
        """All pushed items should be drained exactly once."""
        q = MPSCQueue[int](capacity=100_000)
        num_producers = 8
        per_producer = 5_000

        def producer(barrier, pid):
            barrier.wait()
            for i in range(per_producer):
                q.push(pid * per_producer + i)

        barrier = threading.Barrier(num_producers)
        threads = []
        for pid in range(num_producers):
            t = threading.Thread(target=producer, args=(barrier, pid))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=30)

        all_items = q.drain()
        assert len(all_items) == num_producers * per_producer
        # No duplicates
        assert len(set(all_items)) == len(all_items)


# ============================================================================
# CTMEvictionPolicy concurrency stress tests
# ============================================================================

class TestEvictorConcurrency:
    """Stress tests for the refactored lock-free evictor."""

    def _make_evictor(self, capacity: int = 1000) -> CTMEvictionPolicy:
        policy = CTMEvictionPolicy(CTMvLLMConfig())
        policy.set_capacity(capacity)
        return policy

    def test_concurrent_gpu_hits(self):
        """Many threads hitting the same GPU blocks concurrently.

        This exercises the lock-free fast path.
        """
        policy = self._make_evictor(500)

        # Pre-populate 100 blocks
        for i in range(100):
            policy.on_block_access(i, sequence_id=1)

        num_threads = 16
        per_thread = 5_000
        errors = []

        def worker(barrier):
            barrier.wait()
            rng = random.Random(threading.get_ident())
            try:
                for _ in range(per_thread):
                    bid = rng.randint(0, 99)
                    policy.on_block_access(bid, sequence_id=1)
            except Exception as e:
                errors.append(e)

        run_threads(worker, num_threads)

        assert not errors, f"Errors: {errors}"
        stats = policy.get_stats()
        expected_total = 100 + num_threads * per_thread
        assert stats["total_accesses"] == expected_total, (
            f"Expected {expected_total}, got {stats['total_accesses']}"
        )

    def test_concurrent_access_and_eviction(self):
        """Concurrent accesses causing evictions under memory pressure."""
        policy = self._make_evictor(100)

        num_threads = 8
        per_thread = 2_000
        errors = []

        def worker(barrier, tid):
            barrier.wait()
            rng = random.Random(tid)
            try:
                for _ in range(per_thread):
                    bid = rng.randint(0, 999)
                    policy.on_block_access(bid, sequence_id=tid)
            except Exception as e:
                errors.append(e)

        barrier = threading.Barrier(num_threads)
        threads = []
        for tid in range(num_threads):
            t = threading.Thread(target=worker, args=(barrier, tid))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Errors: {errors}"
        stats = policy.get_stats()
        assert stats["total_accesses"] == num_threads * per_thread

    def test_concurrent_access_and_free(self):
        """Concurrent accesses + block frees (sequence completion)."""
        policy = self._make_evictor(500)

        # Pre-populate
        for i in range(200):
            policy.on_block_access(i, sequence_id=i // 10)

        errors = []

        def accessor(barrier):
            barrier.wait()
            rng = random.Random(1)
            try:
                for _ in range(3_000):
                    bid = rng.randint(0, 199)
                    policy.on_block_access(bid, sequence_id=1)
            except Exception as e:
                errors.append(e)

        def freer(barrier):
            barrier.wait()
            try:
                for bid in range(0, 200, 2):  # Free even blocks
                    policy.free_block(bid)
                    time.sleep(0.0001)  # Stagger frees
            except Exception as e:
                errors.append(e)

        barrier = threading.Barrier(3)
        threads = [
            threading.Thread(target=accessor, args=(barrier,)),
            threading.Thread(target=accessor, args=(barrier,)),
            threading.Thread(target=freer, args=(barrier,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Errors: {errors}"

    def test_concurrent_pin_unpin(self):
        """Concurrent pin/unpin should not corrupt pinned_blocks set."""
        policy = self._make_evictor(500)

        for i in range(100):
            policy.on_block_access(i, sequence_id=1)

        errors = []

        def pinner(barrier):
            barrier.wait()
            try:
                for bid in range(100):
                    policy.pin_block(bid)
            except Exception as e:
                errors.append(e)

        def unpinner(barrier):
            barrier.wait()
            try:
                for bid in range(100):
                    policy.unpin_block(bid)
            except Exception as e:
                errors.append(e)

        barrier = threading.Barrier(4)
        threads = [
            threading.Thread(target=pinner, args=(barrier,)),
            threading.Thread(target=pinner, args=(barrier,)),
            threading.Thread(target=unpinner, args=(barrier,)),
            threading.Thread(target=unpinner, args=(barrier,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors

    def test_concurrent_select_victim(self):
        """Concurrent victim selection under contention."""
        policy = self._make_evictor(500)

        for i in range(200):
            policy.on_block_access(i, sequence_id=1)

        errors = []
        victims = []
        lock = threading.Lock()

        def selector(barrier):
            barrier.wait()
            try:
                for _ in range(100):
                    v = policy.select_victim()
                    if v is not None:
                        with lock:
                            victims.append(v)
            except Exception as e:
                errors.append(e)

        run_threads(selector, 8)

        assert not errors
        assert len(victims) > 0, "Should have selected some victims"

    def test_stats_consistency(self):
        """Stats should be consistent after concurrent operations."""
        policy = self._make_evictor(1000)

        num_threads = 8
        per_thread = 5_000

        def worker(barrier, tid):
            rng = random.Random(tid)
            barrier.wait()
            for _ in range(per_thread):
                bid = rng.randint(0, 499)
                policy.on_block_access(bid, sequence_id=tid)

        barrier = threading.Barrier(num_threads)
        threads = []
        for tid in range(num_threads):
            t = threading.Thread(target=worker, args=(barrier, tid))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=30)

        stats = policy.get_stats()
        total = stats["gpu_hits"] + stats["cpu_hits"] + stats["misses"]
        assert total == stats["total_accesses"]
        assert total == num_threads * per_thread


# ============================================================================
# BlockManager concurrency stress test
# ============================================================================

class TestBlockManagerConcurrency:
    def test_concurrent_allocate_access_free(self):
        """Full lifecycle under concurrent access."""
        mgr = CTMBlockSpaceManager(
            block_size=16,
            num_gpu_blocks=100,
            num_cpu_blocks=200,
        )
        errors = []

        def lifecycle(barrier, seq_id):
            barrier.wait()
            try:
                blocks = mgr.allocate(seq_id, 5)
                for _ in range(50):
                    mgr.access(seq_id)
                mgr.free(seq_id)
            except Exception as e:
                errors.append(e)

        num_seqs = 16
        barrier = threading.Barrier(num_seqs)
        threads = []
        for sid in range(num_seqs):
            t = threading.Thread(target=lifecycle, args=(barrier, sid))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Errors: {errors}"


# ============================================================================
# Throughput benchmark (not a correctness test, for comparison)
# ============================================================================

class TestThroughputBenchmark:
    def test_hot_path_throughput(self):
        """Measure GPU-hit throughput to validate lock-free benefit."""
        policy = CTMEvictionPolicy(CTMvLLMConfig())
        policy.set_capacity(10_000)

        # Pre-populate
        for i in range(1000):
            policy.on_block_access(i, sequence_id=1)

        # Single-thread baseline
        num_ops = 50_000
        start = time.perf_counter()
        for i in range(num_ops):
            policy.on_block_access(i % 1000, sequence_id=1)
        single_elapsed = time.perf_counter() - start
        single_rate = num_ops / single_elapsed

        # Multi-thread
        num_threads = 4
        per_thread = num_ops // num_threads

        def worker(barrier):
            barrier.wait()
            rng = random.Random(threading.get_ident())
            for _ in range(per_thread):
                policy.on_block_access(rng.randint(0, 999), sequence_id=1)

        start = time.perf_counter()
        run_threads(worker, num_threads)
        multi_elapsed = time.perf_counter() - start
        multi_rate = num_ops / multi_elapsed

        print(f"\n  Single-thread: {single_rate:,.0f} ops/sec")
        print(f"  Multi-thread ({num_threads}t): {multi_rate:,.0f} ops/sec")
        print(f"  Scaling: {multi_rate / single_rate:.2f}x")

        # Just verify it completes without errors; true scaling
        # is limited by Python's GIL but contention should be low
        assert single_rate > 0
        assert multi_rate > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
