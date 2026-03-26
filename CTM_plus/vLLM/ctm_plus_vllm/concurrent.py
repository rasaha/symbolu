"""
Lock-free and concurrent data structures for CTM+ vLLM integration.

At 64+ CPU cores, coarse-grained RLock becomes a bottleneck.  This module
provides data structures that reduce lock contention on the hot path:

1. AtomicCounter      – lock-free integer counter (CAS via threading.Lock)
2. StripedLock        – fine-grained lock striping for dict-keyed structures
3. RCUDict            – read-copy-update dict: lock-free reads, COW writes
4. MPSCQueue          – multi-producer single-consumer bounded queue
5. ConcurrentBlockMap – striped block-state map for the evictor hot path

Design principles:
    - Hot path (on_block_access) should be lock-free for the common case
      (GPU hit = read block state + atomic counter increment).
    - Cold path (eviction, slow-path maintenance) may acquire write locks.
    - Python's GIL guarantees single-word reads/writes are atomic, so
      RCU-style snapshot reads are safe without memory barriers.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

V = TypeVar("V")


# =============================================================================
# AtomicCounter – lock-free integer counter
# =============================================================================

class AtomicCounter:
    """Thread-safe counter with minimal overhead.

    Uses a dedicated Lock (not RLock) for CAS-style increment.
    Much cheaper than acquiring the evictor's coarse RLock just to
    bump a stat counter.

    On CPython, ``int`` assignment is GIL-atomic, so reads without the
    lock are safe (may be slightly stale, which is acceptable for stats).
    """

    __slots__ = ("_value", "_lock")

    def __init__(self, initial: int = 0) -> None:
        self._value = initial
        self._lock = threading.Lock()

    def increment(self, delta: int = 1) -> int:
        """Increment and return the new value."""
        with self._lock:
            self._value += delta
            return self._value

    def decrement(self, delta: int = 1) -> int:
        with self._lock:
            self._value -= delta
            return self._value

    @property
    def value(self) -> int:
        """Lock-free read (GIL-atomic on CPython)."""
        return self._value

    def reset(self, new_value: int = 0) -> int:
        """Reset and return the old value."""
        with self._lock:
            old = self._value
            self._value = new_value
            return old

    def compare_and_swap(self, expected: int, desired: int) -> bool:
        """CAS operation. Returns True if swap succeeded."""
        with self._lock:
            if self._value == expected:
                self._value = desired
                return True
            return False


# =============================================================================
# AtomicStats – batch of named counters for lock-free stats tracking
# =============================================================================

class AtomicStats:
    """Collection of named AtomicCounters for stats tracking.

    Replaces ``dict[str, int]`` stats protected by a coarse lock.
    Each counter has its own lock, so concurrent increments on
    different counters never contend.
    """

    def __init__(self, *names: str) -> None:
        self._counters: Dict[str, AtomicCounter] = {
            name: AtomicCounter() for name in names
        }

    def increment(self, name: str, delta: int = 1) -> int:
        return self._counters[name].increment(delta)

    def __getitem__(self, name: str) -> int:
        return self._counters[name].value

    def snapshot(self) -> Dict[str, int]:
        """Return a consistent-ish snapshot (no global lock)."""
        return {name: c.value for name, c in self._counters.items()}

    def reset_all(self) -> Dict[str, int]:
        """Reset all counters. Returns old values."""
        return {name: c.reset() for name, c in self._counters.items()}


# =============================================================================
# StripedLock – fine-grained lock striping
# =============================================================================

class StripedLock:
    """Array of locks indexed by ``hash(key) % num_stripes``.

    Instead of one lock for the entire dict, spread contention across
    *num_stripes* independent locks.  At 64 cores with 64 stripes,
    expected contention drops to ~1 core per stripe.

    Usage::

        sl = StripedLock(64)
        with sl.lock_for(block_id):
            # protected per-block operation
    """

    __slots__ = ("_stripes", "_num_stripes")

    def __init__(self, num_stripes: int = 64) -> None:
        self._num_stripes = num_stripes
        self._stripes = [threading.Lock() for _ in range(num_stripes)]

    def lock_for(self, key: int) -> threading.Lock:
        """Return the stripe lock for *key*."""
        return self._stripes[key % self._num_stripes]

    def lock_for_keys(self, *keys: int) -> "_MultiStripeLock":
        """Acquire locks for multiple keys in a deadlock-free order."""
        indices = sorted(set(k % self._num_stripes for k in keys))
        return _MultiStripeLock([self._stripes[i] for i in indices])


class _MultiStripeLock:
    """Context manager that acquires multiple stripe locks in order."""

    __slots__ = ("_locks",)

    def __init__(self, locks: List[threading.Lock]) -> None:
        self._locks = locks

    def __enter__(self) -> "_MultiStripeLock":
        for lock in self._locks:
            lock.acquire()
        return self

    def __exit__(self, *_: Any) -> None:
        for lock in reversed(self._locks):
            lock.release()


# =============================================================================
# RCUDict – read-copy-update dictionary
# =============================================================================

class RCUDict(Generic[V]):
    """Read-copy-update dictionary for read-heavy workloads.

    Reads are lock-free: callers get a reference to the current snapshot
    dict, which is never mutated in place.

    Writes copy the entire dict, apply the mutation, then atomically
    swap the reference (a single pointer assignment, GIL-atomic).

    Best for:
        - Read-heavy workloads (>90% reads) with small-to-medium dicts
        - Scenarios where reads vastly outnumber writes

    Not ideal for:
        - Large dicts with frequent writes (copy cost)
        - Write-heavy workloads

    Concurrent writers are serialised via a write lock.
    """

    __slots__ = ("_data", "_write_lock")

    def __init__(self, initial: Optional[Dict[int, V]] = None) -> None:
        self._data: Dict[int, V] = dict(initial) if initial else {}
        self._write_lock = threading.Lock()

    # --- Lock-free read API ---

    def get(self, key: int, default: Optional[V] = None) -> Optional[V]:
        """Lock-free read."""
        return self._data.get(key, default)

    def __contains__(self, key: int) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, key: int) -> V:
        return self._data[key]

    def snapshot(self) -> Dict[int, V]:
        """Return current snapshot (shared reference, do NOT mutate)."""
        return self._data

    def keys(self) -> frozenset:
        """Return a frozen snapshot of keys."""
        return frozenset(self._data.keys())

    def values(self) -> list:
        """Return snapshot of values."""
        return list(self._data.values())

    def items(self) -> list:
        """Return snapshot of items."""
        return list(self._data.items())

    # --- Copy-on-write mutations ---

    def put(self, key: int, value: V) -> None:
        """Insert or update (copy-on-write)."""
        with self._write_lock:
            new = dict(self._data)
            new[key] = value
            self._data = new

    def remove(self, key: int) -> Optional[V]:
        """Remove key (copy-on-write). Returns removed value or None."""
        with self._write_lock:
            if key not in self._data:
                return None
            new = dict(self._data)
            val = new.pop(key)
            self._data = new
            return val

    def batch_update(self, updates: Dict[int, V]) -> None:
        """Apply multiple updates in one COW operation."""
        if not updates:
            return
        with self._write_lock:
            new = dict(self._data)
            new.update(updates)
            self._data = new

    def batch_remove(self, keys: Set[int]) -> None:
        """Remove multiple keys in one COW operation."""
        if not keys:
            return
        with self._write_lock:
            new = {k: v for k, v in self._data.items() if k not in keys}
            self._data = new

    def clear(self) -> None:
        with self._write_lock:
            self._data = {}

    def mutate(self, key: int, fn: Callable[[V], V]) -> Optional[V]:
        """Apply a function to a value (copy-on-write).

        Returns new value, or None if key not found.
        For hot-path mutations consider using ConcurrentBlockMap instead.
        """
        with self._write_lock:
            if key not in self._data:
                return None
            new = dict(self._data)
            new[key] = fn(new[key])
            self._data = new
            return new[key]


# =============================================================================
# MPSCQueue – multi-producer single-consumer bounded queue
# =============================================================================

class MPSCQueue(Generic[V]):
    """Bounded multi-producer single-consumer queue.

    Producers push items from any thread.  A single consumer drains
    the queue (typically in the slow-path maintenance thread).

    Uses a Lock for producers and a separate drain that swaps the
    internal buffer, so the consumer never blocks producers for long.
    """

    __slots__ = ("_buffer", "_lock", "_capacity")

    def __init__(self, capacity: int = 4096) -> None:
        self._buffer: List[V] = []
        self._lock = threading.Lock()
        self._capacity = capacity

    def push(self, item: V) -> bool:
        """Push item. Returns False if full (item dropped)."""
        with self._lock:
            if len(self._buffer) >= self._capacity:
                return False
            self._buffer.append(item)
            return True

    def drain(self) -> List[V]:
        """Drain all items. Returns the batch; buffer is reset."""
        with self._lock:
            batch = self._buffer
            self._buffer = []
        return batch

    def __len__(self) -> int:
        return len(self._buffer)

    @property
    def is_empty(self) -> bool:
        return len(self._buffer) == 0


# =============================================================================
# ConcurrentBlockMap – striped block-state map
# =============================================================================

class ConcurrentBlockMap(Generic[V]):
    """Dict-like map with per-stripe locking for block state.

    Unlike RCUDict (which copies the entire dict on write), this uses
    striped locks so that concurrent writes to *different* blocks never
    contend.  Reads within a stripe still need the stripe lock, but
    stripe lock hold times are sub-microsecond.

    Use this for the ``blocks: Dict[int, BlockState]`` map where both
    reads and writes are frequent and the map can be large (10k+ entries).
    """

    __slots__ = ("_shards", "_locks", "_num_shards")

    def __init__(self, num_shards: int = 64) -> None:
        self._num_shards = num_shards
        self._shards: List[Dict[int, V]] = [{} for _ in range(num_shards)]
        self._locks = [threading.Lock() for _ in range(num_shards)]

    def _shard_for(self, key: int) -> int:
        return key % self._num_shards

    def get(self, key: int) -> Optional[V]:
        s = self._shard_for(key)
        with self._locks[s]:
            return self._shards[s].get(key)

    def __contains__(self, key: int) -> bool:
        s = self._shard_for(key)
        # GIL-atomic dict lookup; lock optional for contains
        return key in self._shards[s]

    def __getitem__(self, key: int) -> V:
        s = self._shard_for(key)
        with self._locks[s]:
            return self._shards[s][key]

    def put(self, key: int, value: V) -> None:
        s = self._shard_for(key)
        with self._locks[s]:
            self._shards[s][key] = value

    def remove(self, key: int) -> Optional[V]:
        s = self._shard_for(key)
        with self._locks[s]:
            return self._shards[s].pop(key, None)

    def update_in_place(self, key: int, fn: Callable[[V], None]) -> bool:
        """Apply fn to value in-place under stripe lock.

        Returns True if key existed and fn was applied.
        This is the hot-path primitive: acquire one stripe lock,
        mutate BlockState, release.
        """
        s = self._shard_for(key)
        with self._locks[s]:
            val = self._shards[s].get(key)
            if val is None:
                return False
            fn(val)
            return True

    def __len__(self) -> int:
        return sum(len(s) for s in self._shards)

    def keys(self) -> List[int]:
        """Return snapshot of all keys (acquires each stripe briefly)."""
        result = []
        for i in range(self._num_shards):
            with self._locks[i]:
                result.extend(self._shards[i].keys())
        return result

    def values(self) -> List[V]:
        result = []
        for i in range(self._num_shards):
            with self._locks[i]:
                result.extend(self._shards[i].values())
        return result

    def items(self) -> List[Tuple[int, V]]:
        result = []
        for i in range(self._num_shards):
            with self._locks[i]:
                result.extend(self._shards[i].items())
        return result

    def snapshot(self) -> Dict[int, V]:
        """Return a merged snapshot dict (for slow-path operations)."""
        merged: Dict[int, V] = {}
        for i in range(self._num_shards):
            with self._locks[i]:
                merged.update(self._shards[i])
        return merged

    def clear(self) -> None:
        for i in range(self._num_shards):
            with self._locks[i]:
                self._shards[i].clear()


# =============================================================================
# ConcurrentSet – striped set for gpu_blocks / cpu_blocks
# =============================================================================

class ConcurrentSet:
    """Thread-safe set with striped locking.

    Optimised for the gpu_blocks / cpu_blocks membership tests in the
    evictor hot path.  ``__contains__`` is GIL-atomic on CPython so
    reads skip the lock entirely.
    """

    __slots__ = ("_shards", "_locks", "_num_shards")

    def __init__(self, num_shards: int = 16) -> None:
        self._num_shards = num_shards
        self._shards: List[Set[int]] = [set() for _ in range(num_shards)]
        self._locks = [threading.Lock() for _ in range(num_shards)]

    def _shard_for(self, key: int) -> int:
        return key % self._num_shards

    def add(self, key: int) -> None:
        s = self._shard_for(key)
        with self._locks[s]:
            self._shards[s].add(key)

    def discard(self, key: int) -> None:
        s = self._shard_for(key)
        with self._locks[s]:
            self._shards[s].discard(key)

    def remove(self, key: int) -> None:
        s = self._shard_for(key)
        with self._locks[s]:
            self._shards[s].remove(key)

    def __contains__(self, key: int) -> bool:
        # GIL-atomic set membership; no lock needed for reads
        s = self._shard_for(key)
        return key in self._shards[s]

    def __len__(self) -> int:
        return sum(len(s) for s in self._shards)

    def snapshot(self) -> Set[int]:
        """Return a merged snapshot (for slow-path operations)."""
        result: Set[int] = set()
        for i in range(self._num_shards):
            with self._locks[i]:
                result.update(self._shards[i])
        return result

    def clear(self) -> None:
        for i in range(self._num_shards):
            with self._locks[i]:
                self._shards[i].clear()
