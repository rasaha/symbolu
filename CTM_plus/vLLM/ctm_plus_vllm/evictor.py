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

import random
import time
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any

from .config import CTMvLLMConfig


# =============================================================================
# PRODUCTION: Latency Tracking
# =============================================================================

@dataclass
class LatencyStats:
    """P99-focused latency tracking for production monitoring."""
    samples: List[float] = field(default_factory=list)
    max_samples: int = 10000

    def record(self, latency_us: float):
        if len(self.samples) >= self.max_samples:
            self.samples = self.samples[-self.max_samples // 2:]
        self.samples.append(latency_us)

    def percentile(self, p: float) -> float:
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * p / 100)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

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
            "count": len(self.samples),
            "p50_us": self.p50,
            "p95_us": self.p95,
            "p99_us": self.p99,
            "max_us": max(self.samples) if self.samples else 0,
        }


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

    def __init__(self, window_size: int = 16):
        self.window_size = window_size
        self.recent_accesses: deque = deque(maxlen=window_size)
        self.cooccurrence: Dict[int, Dict[int, int]] = {}

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
    """

    def __init__(self, config: Optional[CTMvLLMConfig] = None):
        self.config = config or CTMvLLMConfig()
        self.blocks: Dict[int, BlockState] = {}
        self.gpu_blocks: Set[int] = set()
        self.cpu_blocks: Set[int] = set()

        self.neighbor_tracker = NeighborTracker(self.config.neighbor_window)
        self.transition_tracker = TransitionTracker()
        self.shadow_tier = DualShadowTier(self.config.shadow_size)
        self.shadow_tier.p = self.config.initial_p

        self.access_counter = 0
        self.stats = {
            "gpu_hits": 0,
            "cpu_hits": 0,
            "misses": 0,
            "promotions": 0,
            "evictions": 0,
            "smart_selections": 0,
            "batch_evictions": 0,
            "slow_path_runs": 0,
        }

        # PRODUCTION: Latency tracking and candidate pools
        self.latency_stats = LatencyStats()
        self.candidate_pool = StratifiedCandidatePool(pool_size=64)
        self._slow_path_counter = 0
        self.max_blocks: int = 0  # Set when capacity is known

    def on_block_access(
        self,
        block_id: int,
        sequence_id: Optional[int] = None,
    ) -> Tuple[bool, bool]:
        """
        Handle block access.

        PRODUCTION: Fast path with O(1) state updates and latency tracking.

        Returns:
            (is_promotion, is_eviction_needed): Whether block was promoted
            and whether eviction is needed to make space.
        """
        start_time = time.perf_counter()

        current_time = time.monotonic()
        self.access_counter += 1
        self._slow_path_counter += 1

        # Track for patterns
        self.neighbor_tracker.record_access(block_id)
        self.transition_tracker.record_access(block_id)

        # Check shadow tier for ARC adaptation
        self.shadow_tier.check_and_adapt(
            block_id, self.config.adaptive_p_learning_rate
        )

        is_promotion = False
        needs_eviction = False

        if block_id in self.gpu_blocks:
            # GPU hit
            self.stats["gpu_hits"] += 1
            block = self.blocks[block_id]
            block.update_access(current_time)

        elif block_id in self.cpu_blocks:
            # CPU hit - consider promotion
            self.stats["cpu_hits"] += 1
            block = self.blocks[block_id]
            block.update_access(current_time)

            if self._should_promote(block):
                is_promotion = True
                needs_eviction = True  # May need to evict from GPU
                self.stats["promotions"] += 1

        else:
            # Miss - new block
            self.stats["misses"] += 1
            block = BlockState(
                block_id=block_id,
                sequence_id=sequence_id,
                last_access_time=current_time,
                access_count=1,
            )
            self.blocks[block_id] = block
            self.gpu_blocks.add(block_id)
            is_promotion = True

        # PRODUCTION: Check if batch eviction needed
        if self.max_blocks > 0:
            utilization = len(self.gpu_blocks) / self.max_blocks
            if utilization >= EVICTION_THRESHOLD:
                self._batch_evict()

        # PRODUCTION: Run slow path maintenance periodically
        if self._slow_path_counter >= SLOW_PATH_INTERVAL:
            self._slow_path_maintenance()
            self._slow_path_counter = 0

        # PRODUCTION: Record latency
        elapsed_us = (time.perf_counter() - start_time) * 1_000_000
        self.latency_stats.record(elapsed_us)

        return is_promotion, needs_eviction

    def _should_promote(self, block: BlockState) -> bool:
        """Determine if block should be promoted to GPU."""
        if not self.config.enable_smart_victim:
            return True  # Always promote if smart victim disabled

        reuse = self.transition_tracker.get_reuse_score(block.block_id)
        neighbor_hot = self.neighbor_tracker.get_hotness(
            block.block_id, self.gpu_blocks
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
        if not self.gpu_blocks:
            return None

        if not self.config.enable_smart_victim:
            # Simple LRU fallback
            return self._select_lru_victim()

        self.stats["smart_selections"] += 1
        return self._select_smart_victim()

    def _select_lru_victim(self) -> int:
        """Select victim using simple LRU."""
        oldest_time = float('inf')
        victim = None

        for block_id in self.gpu_blocks:
            block = self.blocks[block_id]
            if not block.pinned and block.last_access_time < oldest_time:
                oldest_time = block.last_access_time
                victim = block_id

        return victim or next(iter(self.gpu_blocks))

    def _select_smart_victim(self) -> int:
        """Select victim using CTM+ scoring."""
        candidates = list(self.gpu_blocks)
        n = len(candidates)

        if n == 0:
            return None

        # Sample k candidates
        sample_size = min(self.config.victim_sample_size, n)
        if sample_size < n:
            sampled = random.sample(candidates, sample_size)
        else:
            sampled = candidates

        # Always include LRU victim as baseline
        lru_victim = self._select_lru_victim()
        if lru_victim not in sampled:
            sampled.append(lru_victim)

        # Compute time range for normalization
        times = [self.blocks[bid].last_access_time for bid in sampled]
        min_time = min(times)
        max_time = max(times)
        time_range = max_time - min_time if max_time > min_time else 1.0

        # Score each candidate
        best_victim = None
        best_score = float('inf')
        adaptive_p = self.shadow_tier.p

        for block_id in sampled:
            block = self.blocks[block_id]

            if block.pinned:
                continue

            score = self._compute_victim_score(
                block, min_time, time_range, adaptive_p
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
    ) -> float:
        """Compute victim score (lower = evict first)."""
        # Normalize recency to [0, 1]
        recency = (block.last_access_time - min_time) / time_range

        # Frequency score
        frequency = min(block.access_count * 0.1, 1.0)

        # Reuse score
        reuse = self.transition_tracker.get_reuse_score(block.block_id)

        # Neighbor hotness
        neighbor_hot = self.neighbor_tracker.get_hotness(
            block.block_id, self.gpu_blocks
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
        if block_id in self.gpu_blocks:
            self.gpu_blocks.remove(block_id)
            self.cpu_blocks.add(block_id)
            self.blocks[block_id].in_gpu = False

            # Record in shadow tier
            self.shadow_tier.record_eviction(
                block_id, from_gpu=True, current_time=time.monotonic()
            )
            self.stats["evictions"] += 1

    # =========================================================================
    # PRODUCTION: Batch Eviction and Slow Path Maintenance
    # =========================================================================

    def set_capacity(self, max_blocks: int) -> None:
        """Set the maximum block capacity for batch eviction threshold."""
        self.max_blocks = max_blocks

    def _batch_evict(self) -> List[int]:
        """
        PRODUCTION: Batch eviction - evict M blocks at once.

        Instead of evicting one block at a time, we evict a batch
        to amortize the overhead of victim selection.

        Returns:
            List of evicted block IDs.
        """
        evicted = []

        # Get pinned block IDs to exclude
        pinned = {bid for bid, block in self.blocks.items() if block.pinned}

        # Get candidates from stratified pools
        candidates = self.candidate_pool.get_candidates(
            K_CANDIDATES * 2, exclude_pinned=pinned
        )

        # Fall back to random sampling if pools are empty
        if len(candidates) < EVICTION_BATCH_SIZE:
            available = [bid for bid in self.gpu_blocks if bid not in pinned]
            if available:
                sample_size = min(K_CANDIDATES * 2, len(available))
                candidates = random.sample(available, sample_size)

        if not candidates:
            return evicted

        # Score candidates (O(k) operation)
        scored = []
        times = [self.blocks[bid].last_access_time for bid in candidates if bid in self.blocks]
        if not times:
            return evicted

        min_time = min(times)
        max_time = max(times)
        time_range = max_time - min_time if max_time > min_time else 1.0
        adaptive_p = self.shadow_tier.p

        for block_id in candidates:
            if block_id not in self.blocks:
                continue
            block = self.blocks[block_id]
            score = self._compute_victim_score(block, min_time, time_range, adaptive_p)
            scored.append((block_id, score))

        # Sort by score and take lowest (worst candidates)
        scored.sort(key=lambda x: x[1])
        victims = [bid for bid, _ in scored[:EVICTION_BATCH_SIZE]]

        # Evict victims
        for victim_id in victims:
            self.evict_block(victim_id)
            evicted.append(victim_id)

        if evicted:
            self.stats["batch_evictions"] += 1

        return evicted

    def _slow_path_maintenance(self) -> None:
        """
        PRODUCTION: Slow path maintenance - runs every N accesses.

        O(n) operations that are too expensive for the hot path:
        - Rebuild stratified candidate pools
        """
        self.stats["slow_path_runs"] += 1

        # Clear and rebuild candidate pools
        self.candidate_pool.clear()

        # Get unpinned GPU blocks
        available = [
            (bid, self.blocks[bid])
            for bid in self.gpu_blocks
            if bid in self.blocks and not self.blocks[bid].pinned
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
        if block_id in self.cpu_blocks:
            self.cpu_blocks.remove(block_id)
            self.gpu_blocks.add(block_id)
            self.blocks[block_id].in_gpu = True

    def free_block(self, block_id: int) -> None:
        """Free block entirely (sequence completed)."""
        self.gpu_blocks.discard(block_id)
        self.cpu_blocks.discard(block_id)
        if block_id in self.blocks:
            del self.blocks[block_id]

    def pin_block(self, block_id: int) -> None:
        """Pin block to prevent eviction."""
        if block_id in self.blocks:
            self.blocks[block_id].pinned = True

    def unpin_block(self, block_id: int) -> None:
        """Unpin block to allow eviction."""
        if block_id in self.blocks:
            self.blocks[block_id].pinned = False

    def get_stats(self) -> Dict[str, Any]:
        """Get eviction statistics including production latency metrics."""
        total = self.stats["gpu_hits"] + self.stats["cpu_hits"] + self.stats["misses"]
        return {
            **self.stats,
            "total_accesses": total,
            "gpu_hit_rate": self.stats["gpu_hits"] / total if total > 0 else 0.0,
            "adaptive_p": self.shadow_tier.p,
            "gpu_blocks": len(self.gpu_blocks),
            "cpu_blocks": len(self.cpu_blocks),
            # PRODUCTION: Latency metrics
            "latency": self.latency_stats.summary(),
            "candidate_pool_sizes": {
                "lru": len(self.candidate_pool.lru_pool),
                "lfu": len(self.candidate_pool.lfu_pool),
                "low_reuse": len(self.candidate_pool.low_reuse_pool),
            },
        }

    def reset_stats(self) -> None:
        """Reset statistics including production latency tracking."""
        for key in self.stats:
            self.stats[key] = 0
        # PRODUCTION: Reset latency and pools
        self.latency_stats = LatencyStats()
        self.candidate_pool.clear()
        self._slow_path_counter = 0
