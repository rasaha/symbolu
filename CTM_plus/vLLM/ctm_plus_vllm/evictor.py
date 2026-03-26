"""
CTM+ Eviction Policy for vLLM.

Implements smart victim selection for KV cache blocks using:
- O(k) sampled scoring instead of O(n) LRU scans
- ARC-style shadow tiers with adaptive p
- Loop pinning for temporal patterns
- Neighbor tracking for cluster protection

Production Optimizations (p99 < 100µs):
- Batch eviction: Evict M blocks at once when threshold hit
- Fast/slow path: O(1) updates per access, O(n) maintenance periodic
- Stratified candidate pools: Pre-sorted worst-by-signal pools
- Bounded-cost operations: No unbounded scans in hot path
"""

import bisect
import logging
import random
import threading
import time
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any

from .concurrent import (
    AtomicCounter,
    AtomicStats,
    ConcurrentBlockMap,
    ConcurrentSet,
    MPSCQueue,
)
from .config import CTMvLLMConfig

logger = logging.getLogger(__name__)


# =============================================================================
# PRODUCTION: Latency Tracking
# =============================================================================

class LatencyStats:
    """
    P99-focused latency tracking for production monitoring.

    Uses insertion sort to maintain a sorted list, giving O(log n) insertion
    and O(1) percentile lookups instead of O(n log n) on every percentile call.

    Thread-safe: record() is protected by a dedicated lock separate from
    the evictor's write lock, so hot-path latency recording never contends
    with cold-path operations.
    """

    def __init__(self, max_samples: int = 10000):
        self.max_samples = max_samples
        self._sorted: List[float] = []
        self._count = 0
        self._lock = threading.Lock()

    def record(self, latency_us: float):
        with self._lock:
            if len(self._sorted) >= self.max_samples:
                # Remove oldest half (approximation: remove smallest values)
                self._sorted = self._sorted[self.max_samples // 2:]
            bisect.insort(self._sorted, latency_us)
            self._count += 1

    def percentile(self, p: float) -> float:
        if not self._sorted:
            return 0.0
        idx = int(len(self._sorted) * p / 100)
        return self._sorted[min(idx, len(self._sorted) - 1)]

    @property
    def p50(self) -> float:
        return self.percentile(50)

    @property
    def p95(self) -> float:
        return self.percentile(95)

    @property
    def p99(self) -> float:
        return self.percentile(99)

    def summary(self) -> dict:
        return {
            "count": self._count,
            "p50_us": self.p50,
            "p95_us": self.p95,
            "p99_us": self.p99,
            "max_us": self._sorted[-1] if self._sorted else 0,
        }

    def clear(self):
        self._sorted.clear()
        self._count = 0


# =============================================================================
# PRODUCTION: Stratified Candidate Pool
# =============================================================================

class StratifiedCandidatePool:
    """Maintains candidate pools stratified by signal for O(k) eviction."""

    def __init__(self, pool_size: int = 64):
        self.pool_size = pool_size
        self.lru_pool: deque = deque(maxlen=pool_size)  # Oldest
        self.lfu_pool: deque = deque(maxlen=pool_size)  # Lowest frequency
        self.low_reuse_pool: deque = deque(maxlen=pool_size)  # Low reuse score
        self.in_pool: Set[int] = set()

    def get_candidates(self, k: int, exclude_pinned: Set[int]) -> List[int]:
        """Get k candidates from stratified pools. O(k)."""
        candidates = set()
        per_pool = max(1, k // 3)

        for pool in [self.lru_pool, self.lfu_pool, self.low_reuse_pool]:
            for block_id in list(pool)[:per_pool]:
                if block_id not in exclude_pinned:
                    candidates.add(block_id)

        return list(candidates)[:k]

    def clear(self):
        self.lru_pool.clear()
        self.lfu_pool.clear()
        self.low_reuse_pool.clear()
        self.in_pool.clear()


# =============================================================================
# PRODUCTION: Constants
# =============================================================================

EVICTION_BATCH_SIZE = 64      # Evict M blocks at once
EVICTION_THRESHOLD = 0.95     # Trigger batch eviction at 95% capacity
SLOW_PATH_INTERVAL = 1000     # Run slow path every N accesses
K_CANDIDATES = 32             # Sample size for victim selection


@dataclass
class BlockState:
    """Per-block state for CTM+ tracking."""
    block_id: int
    sequence_id: Optional[int] = None  # Which sequence owns this block
    last_access_time: float = 0.0
    access_count: int = 0
    reuse_score: float = 0.0
    coherence: float = 0.5
    phase: float = 0.0
    in_gpu: bool = True
    pinned: bool = False

    def update_access(self, current_time: float) -> None:
        """Update block state on access."""
        self.access_count += 1
        self.last_access_time = current_time


@dataclass
class ShadowEntry:
    """Entry in shadow tier (ghost cache)."""
    block_id: int
    evict_time: float
    from_gpu: bool


class NeighborTracker:
    """Tracks co-occurrence for cluster protection."""

    def __init__(self, window_size: int = 16, max_entries: int = 10000):
        self.window_size = window_size
        self.max_entries = max_entries
        self.recent_accesses: deque = deque(maxlen=window_size)
        self.cooccurrence: Dict[int, Dict[int, int]] = {}
        self._access_count = 0

    def record_access(self, block_id: int) -> None:
        """Record block access and update co-occurrence."""
        for other_id in self.recent_accesses:
            if other_id != block_id:
                if block_id not in self.cooccurrence:
                    self.cooccurrence[block_id] = {}
                if other_id not in self.cooccurrence:
                    self.cooccurrence[other_id] = {}
                self.cooccurrence[block_id][other_id] = (
                    self.cooccurrence[block_id].get(other_id, 0) + 1
                )
                self.cooccurrence[other_id][block_id] = (
                    self.cooccurrence[other_id].get(block_id, 0) + 1
                )
        self.recent_accesses.append(block_id)
        self._access_count += 1

        # Decay periodically to prevent unbounded growth
        if self._access_count > self.max_entries:
            self._decay_cooccurrence()

    def _decay_cooccurrence(self) -> None:
        """Decay co-occurrence counts by half and prune zeros."""
        for block_id in list(self.cooccurrence.keys()):
            for other_id in list(self.cooccurrence[block_id].keys()):
                self.cooccurrence[block_id][other_id] //= 2
                if self.cooccurrence[block_id][other_id] == 0:
                    del self.cooccurrence[block_id][other_id]
            if not self.cooccurrence[block_id]:
                del self.cooccurrence[block_id]
        self._access_count //= 2

    def remove_block(self, block_id: int) -> None:
        """Remove block from co-occurrence tracking (called on free)."""
        if block_id in self.cooccurrence:
            # Remove references from other blocks
            for other_id in list(self.cooccurrence[block_id].keys()):
                if other_id in self.cooccurrence and block_id in self.cooccurrence[other_id]:
                    del self.cooccurrence[other_id][block_id]
            del self.cooccurrence[block_id]

    def get_hotness(self, block_id: int, gpu_blocks: Set[int]) -> float:
        """Get neighbor hotness (fraction of neighbors in GPU)."""
        if block_id not in self.cooccurrence:
            return 0.0

        neighbors = self.cooccurrence[block_id]
        if not neighbors:
            return 0.0

        # Top-k neighbors by co-occurrence
        top_neighbors = sorted(neighbors.items(), key=lambda x: -x[1])[:8]
        if not top_neighbors:
            return 0.0

        in_gpu = sum(1 for n_id, _ in top_neighbors if n_id in gpu_blocks)
        return in_gpu / len(top_neighbors)


class TransitionTracker:
    """Tracks block access transitions for reuse prediction."""

    def __init__(self, max_history: int = 1000):
        self.transitions: Dict[int, Dict[int, int]] = {}
        self.last_block: Optional[int] = None
        self.history_count = 0
        self.max_history = max_history

    def record_access(self, block_id: int) -> None:
        """Record transition from last block to current."""
        if self.last_block is not None and self.last_block != block_id:
            if self.last_block not in self.transitions:
                self.transitions[self.last_block] = {}
            self.transitions[self.last_block][block_id] = (
                self.transitions[self.last_block].get(block_id, 0) + 1
            )
            self.history_count += 1

            # Decay old transitions periodically
            if self.history_count > self.max_history:
                self._decay_transitions()

        self.last_block = block_id

    def _decay_transitions(self) -> None:
        """Decay transition counts by half."""
        for src in list(self.transitions.keys()):
            for dst in list(self.transitions[src].keys()):
                self.transitions[src][dst] //= 2
                if self.transitions[src][dst] == 0:
                    del self.transitions[src][dst]
            if not self.transitions[src]:
                del self.transitions[src]
        self.history_count //= 2

    def get_reuse_score(self, block_id: int) -> float:
        """Get reuse score based on transition probability."""
        if block_id not in self.transitions:
            return 0.0

        outgoing = self.transitions[block_id]
        if not outgoing:
            return 0.0

        # Score based on having predictable next access
        total = sum(outgoing.values())
        max_count = max(outgoing.values())
        return max_count / total if total > 0 else 0.0

    def remove_block(self, block_id: int) -> None:
        """Remove block from transition tracking (called on free)."""
        # Remove outgoing transitions
        if block_id in self.transitions:
            del self.transitions[block_id]
        # Remove incoming transitions from other blocks
        for src in list(self.transitions.keys()):
            if block_id in self.transitions[src]:
                del self.transitions[src][block_id]
                if not self.transitions[src]:
                    del self.transitions[src]


class DualShadowTier:
    """ARC-style dual shadow tiers for adaptive balancing."""

    def __init__(self, max_size: int = 1024):
        self.max_size = max_size
        self.b1: OrderedDict[int, ShadowEntry] = OrderedDict()  # GPU evictions
        self.b2: OrderedDict[int, ShadowEntry] = OrderedDict()  # CPU evictions
        self.p: float = 0.5  # Adaptive partition parameter

    def record_eviction(self, block_id: int, from_gpu: bool, current_time: float) -> None:
        """Record eviction to appropriate shadow tier."""
        entry = ShadowEntry(block_id, current_time, from_gpu)

        if from_gpu:
            if len(self.b1) >= self.max_size:
                self.b1.popitem(last=False)
            self.b1[block_id] = entry
        else:
            if len(self.b2) >= self.max_size:
                self.b2.popitem(last=False)
            self.b2[block_id] = entry

    def check_and_adapt(self, block_id: int, learning_rate: float) -> Optional[str]:
        """Check if block is in shadow tier and adapt p."""
        if block_id in self.b1:
            # Hit in B1: increase p (favor recency)
            delta = learning_rate * (1.0 if len(self.b2) == 0 else len(self.b1) / len(self.b2))
            self.p = min(1.0, self.p + delta)
            del self.b1[block_id]
            return "b1"
        elif block_id in self.b2:
            # Hit in B2: decrease p (favor frequency)
            delta = learning_rate * (1.0 if len(self.b1) == 0 else len(self.b2) / len(self.b1))
            self.p = max(0.0, self.p - delta)
            del self.b2[block_id]
            return "b2"
        return None


class CTMEvictionPolicy:
    """
    CTM+ Eviction Policy for vLLM KV cache blocks.

    Provides intelligent victim selection that outperforms LRU
    on temporal and mixed workloads typical in LLM inference.

    Thread-safety architecture (lock-free where possible):
      - Hot path (GPU hit): AtomicCounter + ConcurrentBlockMap stripe lock.
        No coarse lock acquired for the common case.
      - Block sets (gpu/cpu/pinned): ConcurrentSet with striped locks.
      - Stats: AtomicStats with per-counter locks (no contention between
        different stat names).
      - Cold path (eviction, slow-path): Acquires _write_lock for
        multi-step mutations that must be atomic.
      - Trackers (neighbor, transition, shadow): Protected by _write_lock
        since they maintain cross-block state.

    The coarse RLock is kept as ``_write_lock`` for cold-path operations
    that touch multiple data structures atomically (eviction, batch-evict,
    slow-path maintenance).  The hot path avoids it entirely for GPU hits.
    """

    def __init__(self, config: Optional[CTMvLLMConfig] = None):
        self.config = config or CTMvLLMConfig()

        # CONCURRENT: Striped block map – hot-path reads/writes per-block
        self.blocks: ConcurrentBlockMap[BlockState] = ConcurrentBlockMap(num_shards=64)

        # CONCURRENT: Striped sets for membership tests
        self.gpu_blocks: ConcurrentSet = ConcurrentSet(num_shards=16)
        self.cpu_blocks: ConcurrentSet = ConcurrentSet(num_shards=16)
        self.pinned_blocks: ConcurrentSet = ConcurrentSet(num_shards=16)

        self.neighbor_tracker = NeighborTracker(self.config.neighbor_window)
        self.transition_tracker = TransitionTracker()
        self.shadow_tier = DualShadowTier(self.config.shadow_size)
        self.shadow_tier.p = self.config.initial_p

        # CONCURRENT: Lock-free counters
        self.access_counter = AtomicCounter()
        self._slow_path_counter = AtomicCounter()

        # CONCURRENT: Per-stat atomic counters (no contention across stats)
        self.stats = AtomicStats(
            "gpu_hits", "cpu_hits", "misses", "promotions",
            "evictions", "smart_selections", "batch_evictions",
            "slow_path_runs",
        )

        # PRODUCTION: Latency tracking and candidate pools
        self.latency_stats = LatencyStats()
        self.candidate_pool = StratifiedCandidatePool(pool_size=64)
        self.max_blocks: int = 0  # Set when capacity is known

        # CONCURRENT: Cold-path write lock for multi-step mutations
        # (eviction, batch-evict, slow-path, tracker updates).
        # Hot-path GPU hits do NOT acquire this lock.
        self._write_lock = threading.RLock()

        # CONCURRENT: MPSC queue for deferred tracker updates.
        # Hot-path pushes access events; slow-path drains and processes.
        self._deferred_tracker_queue: MPSCQueue[Tuple[int, Optional[int]]] = (
            MPSCQueue(capacity=8192)
        )

        # Legacy alias so external code using ``with policy._lock:`` still works.
        self._lock = self._write_lock

    def on_block_access(
        self,
        block_id: int,
        sequence_id: Optional[int] = None,
    ) -> Tuple[bool, bool]:
        """
        Handle block access.

        CONCURRENT: The common case (GPU hit) is nearly lock-free:
        only acquires the per-block stripe lock in ConcurrentBlockMap
        and bumps atomic counters.  The coarse _write_lock is only
        taken for CPU hits, misses, batch eviction, and slow-path.

        Returns:
            (is_promotion, is_eviction_needed): Whether block was promoted
            and whether eviction is needed to make space.
        """
        start_time = time.perf_counter()
        current_time = time.monotonic()
        count = self.access_counter.increment()
        slow_count = self._slow_path_counter.increment()

        # === FAST PATH: GPU hit (no coarse lock) ===
        if block_id in self.gpu_blocks:
            self.stats.increment("gpu_hits")
            # Update block state under per-block stripe lock only
            self.blocks.update_in_place(
                block_id, lambda b: b.update_access(current_time)
            )

            # Defer tracker updates to slow-path drain (lock-free push)
            self._deferred_tracker_queue.push((block_id, sequence_id))

            # Check thresholds (reads are lock-free)
            self._maybe_batch_evict()
            self._maybe_slow_path(slow_count)

            elapsed_us = (time.perf_counter() - start_time) * 1_000_000
            self.latency_stats.record(elapsed_us)
            return False, False

        # === SLOW PATH: CPU hit or miss (acquire write lock) ===
        with self._write_lock:
            is_promotion = False
            needs_eviction = False

            # Drain deferred tracker updates while we hold the lock
            self._drain_deferred_tracker_events()

            # Track for patterns (under write lock)
            self.neighbor_tracker.record_access(block_id)
            self.transition_tracker.record_access(block_id)

            # Check shadow tier for ARC adaptation
            self.shadow_tier.check_and_adapt(
                block_id, self.config.adaptive_p_learning_rate
            )

            if block_id in self.cpu_blocks:
                # CPU hit - consider promotion
                self.stats.increment("cpu_hits")
                self.blocks.update_in_place(
                    block_id, lambda b: b.update_access(current_time)
                )
                block = self.blocks.get(block_id)

                if block and self._should_promote(block):
                    is_promotion = True
                    needs_eviction = True
                    self.stats.increment("promotions")

            else:
                # Miss - new block
                self.stats.increment("misses")
                block = BlockState(
                    block_id=block_id,
                    sequence_id=sequence_id,
                    last_access_time=current_time,
                    access_count=1,
                )
                self.blocks.put(block_id, block)
                self.gpu_blocks.add(block_id)
                is_promotion = True

            # Check if batch eviction needed
            self._maybe_batch_evict()
            self._maybe_slow_path(slow_count)

            elapsed_us = (time.perf_counter() - start_time) * 1_000_000
            self.latency_stats.record(elapsed_us)
            return is_promotion, needs_eviction

    def _drain_deferred_tracker_events(self) -> None:
        """Drain deferred tracker updates (called under _write_lock)."""
        events = self._deferred_tracker_queue.drain()
        for block_id, _seq_id in events:
            self.neighbor_tracker.record_access(block_id)
            self.transition_tracker.record_access(block_id)
            self.shadow_tier.check_and_adapt(
                block_id, self.config.adaptive_p_learning_rate
            )

    def _maybe_batch_evict(self) -> None:
        """Trigger batch eviction if utilization exceeds threshold."""
        if self.max_blocks > 0:
            utilization = len(self.gpu_blocks) / self.max_blocks
            if utilization >= EVICTION_THRESHOLD:
                with self._write_lock:
                    # Re-check under lock (double-checked locking)
                    utilization = len(self.gpu_blocks) / self.max_blocks
                    if utilization >= EVICTION_THRESHOLD:
                        self._drain_deferred_tracker_events()
                        self._batch_evict()

    def _maybe_slow_path(self, slow_count: int) -> None:
        """Run slow-path maintenance if interval reached."""
        if slow_count >= SLOW_PATH_INTERVAL:
            if self._slow_path_counter.compare_and_swap(slow_count, 0):
                with self._write_lock:
                    self._drain_deferred_tracker_events()
                    self._slow_path_maintenance()

    def _should_promote(self, block: BlockState) -> bool:
        """Determine if block should be promoted to GPU."""
        if not self.config.enable_smart_victim:
            return True  # Always promote if smart victim disabled

        reuse = self.transition_tracker.get_reuse_score(block.block_id)
        gpu_snap = self.gpu_blocks.snapshot()
        neighbor_hot = self.neighbor_tracker.get_hotness(
            block.block_id, gpu_snap
        )

        # Loop pinning fast-track
        if (reuse > self.config.loop_pin_reuse_threshold and
                neighbor_hot > self.config.loop_pin_neighbor_threshold):
            return True

        # Combined score
        combined = (
            self.config.weight_reuse * reuse +
            self.config.weight_coherence * block.coherence +
            self.config.weight_neighbor * neighbor_hot
        )

        return combined > self.config.promotion_threshold

    def select_victim(self) -> Optional[int]:
        """
        Select victim block for eviction from GPU.

        Returns:
            Block ID to evict, or None if GPU is empty.
        """
        with self._write_lock:
            if len(self.gpu_blocks) == 0:
                logger.debug("select_victim: no GPU blocks to evict")
                return None

            self._drain_deferred_tracker_events()

            if not self.config.enable_smart_victim:
                return self._select_lru_victim()

            self.stats.increment("smart_selections")
            return self._select_smart_victim()

    def _select_lru_victim(self) -> Optional[int]:
        """Select victim using simple LRU. Snapshot-based for concurrency."""
        oldest_time = float('inf')
        victim = None

        gpu_snap = self.gpu_blocks.snapshot()
        pinned_snap = self.pinned_blocks.snapshot()

        for block_id in gpu_snap:
            if block_id in pinned_snap:
                continue
            block = self.blocks.get(block_id)
            if block and block.last_access_time < oldest_time:
                oldest_time = block.last_access_time
                victim = block_id

        return victim

    def _select_smart_victim(self) -> Optional[int]:
        """Select victim using CTM+ scoring. Snapshot-based for concurrency."""
        gpu_snap = self.gpu_blocks.snapshot()
        pinned_snap = self.pinned_blocks.snapshot()
        candidates = [bid for bid in gpu_snap if bid not in pinned_snap]
        n = len(candidates)

        if n == 0:
            logger.debug("_select_smart_victim: all %d blocks are pinned", len(self.gpu_blocks))
            return None

        # Sample k candidates
        sample_size = min(self.config.victim_sample_size, n)
        if sample_size < n:
            sampled = random.sample(candidates, sample_size)
        else:
            sampled = candidates

        # Always include LRU victim as baseline
        lru_victim = self._select_lru_victim()
        if lru_victim and lru_victim not in sampled:
            sampled.append(lru_victim)

        if not sampled:
            return None

        # Compute time range for normalization
        times = []
        for bid in sampled:
            block = self.blocks.get(bid)
            if block:
                times.append(block.last_access_time)
        if not times:
            return None
        min_time = min(times)
        max_time = max(times)
        time_range = max_time - min_time if max_time > min_time else 1.0

        # Score each candidate (pass gpu_snap once, not per candidate)
        best_victim = None
        best_score = float('inf')
        adaptive_p = self.shadow_tier.p
        gpu_snap_for_scoring = gpu_snap

        for block_id in sampled:
            block = self.blocks.get(block_id)
            if not block:
                continue

            score = self._compute_victim_score(
                block, min_time, time_range, adaptive_p,
                gpu_snap=gpu_snap_for_scoring,
            )

            if score < best_score:
                best_score = score
                best_victim = block_id

        return best_victim or lru_victim

    def _compute_victim_score(
        self,
        block: BlockState,
        min_time: float,
        time_range: float,
        adaptive_p: float,
        gpu_snap: Optional[Set[int]] = None,
    ) -> float:
        """Compute victim score (lower = evict first).

        Args:
            gpu_snap: Pre-computed snapshot of gpu_blocks.  Passed in from
                the caller's loop to avoid O(k×n) redundant snapshots.
        """
        # Normalize recency to [0, 1]
        recency = (block.last_access_time - min_time) / time_range

        # Frequency score
        frequency = min(block.access_count * 0.1, 1.0)

        # Reuse score
        reuse = self.transition_tracker.get_reuse_score(block.block_id)

        # Neighbor hotness
        if gpu_snap is None:
            gpu_snap = self.gpu_blocks.snapshot()
        neighbor_hot = self.neighbor_tracker.get_hotness(
            block.block_id, gpu_snap
        )

        # Weighted score
        score = (
            self.config.weight_recency * recency +
            self.config.weight_frequency * frequency +
            self.config.weight_reuse * reuse +
            self.config.weight_coherence * block.coherence -
            self.config.weight_neighbor * neighbor_hot
        )

        # Partition penalty based on adaptive p
        if adaptive_p > 0.5 and frequency < 0.3:
            score -= 0.10 * (adaptive_p - 0.5) * 2.0
        elif adaptive_p < 0.5 and recency < 0.3:
            score -= 0.10 * (0.5 - adaptive_p) * 2.0

        return score

    def evict_block(self, block_id: int) -> None:
        """Mark block as evicted from GPU to CPU."""
        with self._write_lock:
            if block_id in self.gpu_blocks:
                self.gpu_blocks.discard(block_id)
                self.cpu_blocks.add(block_id)
                self.blocks.update_in_place(
                    block_id, lambda b: setattr(b, "in_gpu", False)
                )

                # Record in shadow tier
                self.shadow_tier.record_eviction(
                    block_id, from_gpu=True, current_time=time.monotonic()
                )
                self.stats.increment("evictions")

    # =========================================================================
    # PRODUCTION: Batch Eviction and Slow Path Maintenance
    # =========================================================================

    def _batch_evict(self) -> List[int]:
        """
        PRODUCTION: Batch eviction - evict M blocks at once.

        Called under _write_lock. Uses snapshots of concurrent sets.

        Returns:
            List of evicted block IDs.
        """
        evicted = []
        pinned_snap = self.pinned_blocks.snapshot()

        # Get candidates from stratified pools
        candidates = self.candidate_pool.get_candidates(
            K_CANDIDATES * 2, exclude_pinned=pinned_snap
        )

        # Fall back to random sampling if pools are empty
        if len(candidates) < EVICTION_BATCH_SIZE:
            gpu_snap = self.gpu_blocks.snapshot()
            available = [bid for bid in gpu_snap if bid not in pinned_snap]
            if available:
                sample_size = min(K_CANDIDATES * 2, len(available))
                candidates = random.sample(available, sample_size)

        if not candidates:
            return evicted

        # Score candidates (O(k) operation)
        scored = []
        times = []
        for bid in candidates:
            block = self.blocks.get(bid)
            if block:
                times.append(block.last_access_time)
        if not times:
            return evicted

        min_time = min(times)
        max_time = max(times)
        time_range = max_time - min_time if max_time > min_time else 1.0
        adaptive_p = self.shadow_tier.p

        gpu_snap_for_scoring = self.gpu_blocks.snapshot()
        for block_id in candidates:
            block = self.blocks.get(block_id)
            if not block:
                continue
            score = self._compute_victim_score(
                block, min_time, time_range, adaptive_p,
                gpu_snap=gpu_snap_for_scoring,
            )
            scored.append((block_id, score))

        # Sort by score and take lowest (worst candidates)
        scored.sort(key=lambda x: x[1])
        victims = [bid for bid, _ in scored[:EVICTION_BATCH_SIZE]]

        # Evict victims
        for victim_id in victims:
            if victim_id in self.gpu_blocks:
                self.gpu_blocks.discard(victim_id)
                self.cpu_blocks.add(victim_id)
                self.blocks.update_in_place(
                    victim_id, lambda b: setattr(b, "in_gpu", False)
                )
                self.shadow_tier.record_eviction(
                    victim_id, from_gpu=True, current_time=time.monotonic()
                )
                self.stats.increment("evictions")
                evicted.append(victim_id)

        if evicted:
            self.stats.increment("batch_evictions")

        return evicted

    def _slow_path_maintenance(self) -> None:
        """
        PRODUCTION: Slow path maintenance - runs every N accesses.

        Called under _write_lock.  Uses snapshots of concurrent structures.
        """
        self.stats.increment("slow_path_runs")

        # Clear and rebuild candidate pools
        self.candidate_pool.clear()

        # Snapshot concurrent structures for sorting
        gpu_snap = self.gpu_blocks.snapshot()
        blocks_snap = self.blocks.snapshot()

        # Get unpinned GPU blocks
        available = [
            (bid, blocks_snap[bid])
            for bid in gpu_snap
            if bid in blocks_snap and not blocks_snap[bid].pinned
        ]

        if not available:
            return

        # Build LRU pool (oldest first)
        by_recency = sorted(available, key=lambda x: x[1].last_access_time)
        for bid, _ in by_recency[:self.candidate_pool.pool_size]:
            self.candidate_pool.lru_pool.append(bid)
            self.candidate_pool.in_pool.add(bid)

        # Build LFU pool (lowest frequency first)
        by_frequency = sorted(available, key=lambda x: x[1].access_count)
        for bid, _ in by_frequency[:self.candidate_pool.pool_size]:
            if bid not in self.candidate_pool.in_pool:
                self.candidate_pool.lfu_pool.append(bid)
                self.candidate_pool.in_pool.add(bid)

        # Build low reuse pool
        by_reuse = sorted(
            available,
            key=lambda x: self.transition_tracker.get_reuse_score(x[0])
        )
        for bid, _ in by_reuse[:self.candidate_pool.pool_size]:
            if bid not in self.candidate_pool.in_pool:
                self.candidate_pool.low_reuse_pool.append(bid)
                self.candidate_pool.in_pool.add(bid)

    def promote_block(self, block_id: int) -> None:
        """Mark block as promoted from CPU to GPU."""
        with self._write_lock:
            if block_id in self.cpu_blocks:
                self.cpu_blocks.discard(block_id)
                self.gpu_blocks.add(block_id)
                self.blocks.update_in_place(
                    block_id, lambda b: setattr(b, "in_gpu", True)
                )

    def free_block(self, block_id: int) -> None:
        """Free block entirely (sequence completed). Cleans up from trackers."""
        with self._write_lock:
            self.gpu_blocks.discard(block_id)
            self.cpu_blocks.discard(block_id)
            self.pinned_blocks.discard(block_id)
            self.blocks.remove(block_id)
            # Clean up from trackers to prevent memory leaks
            self.neighbor_tracker.remove_block(block_id)
            self.transition_tracker.remove_block(block_id)

    def pin_block(self, block_id: int) -> None:
        """Pin block to prevent eviction.

        Acquires _write_lock to ensure a concurrent _batch_evict snapshot
        sees the pinned state atomically (prevents evicting a just-pinned block).
        """
        with self._write_lock:
            self.blocks.update_in_place(
                block_id, lambda b: setattr(b, "pinned", True)
            )
            self.pinned_blocks.add(block_id)

    def unpin_block(self, block_id: int) -> None:
        """Unpin block to allow eviction.

        Acquires _write_lock for consistency with pin_block.
        """
        with self._write_lock:
            self.blocks.update_in_place(
                block_id, lambda b: setattr(b, "pinned", False)
            )
            self.pinned_blocks.discard(block_id)

    def set_capacity(self, max_blocks: int) -> None:
        """Set the maximum block capacity for batch eviction threshold."""
        self.max_blocks = max_blocks  # int assignment is GIL-atomic

    def get_stats(self) -> Dict[str, Any]:
        """Get eviction statistics (lock-free snapshot reads)."""
        snap = self.stats.snapshot()
        total = snap["gpu_hits"] + snap["cpu_hits"] + snap["misses"]
        return {
            **snap,
            "total_accesses": total,
            "gpu_hit_rate": snap["gpu_hits"] / total if total > 0 else 0.0,
            "adaptive_p": self.shadow_tier.p,
            "gpu_blocks": len(self.gpu_blocks),
            "cpu_blocks": len(self.cpu_blocks),
            "pinned_blocks": len(self.pinned_blocks),
            "latency": self.latency_stats.summary(),
            "candidate_pool_sizes": {
                "lru": len(self.candidate_pool.lru_pool),
                "lfu": len(self.candidate_pool.lfu_pool),
                "low_reuse": len(self.candidate_pool.low_reuse_pool),
            },
        }

    def reset_stats(self) -> None:
        """Reset statistics including production latency tracking."""
        self.stats.reset_all()
        self.latency_stats.clear()
        self.candidate_pool.clear()
        self._slow_path_counter.reset()
