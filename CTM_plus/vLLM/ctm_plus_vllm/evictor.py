"""
CTM+ Eviction Policy for vLLM.

Implements smart victim selection for KV cache blocks using:
- O(k) sampled scoring instead of O(n) LRU scans
- ARC-style shadow tiers with adaptive p
- Loop pinning for temporal patterns
- Neighbor tracking for cluster protection
"""

import random
import time
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any

from .config import CTMvLLMConfig


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
        }

    def on_block_access(
        self,
        block_id: int,
        sequence_id: Optional[int] = None,
    ) -> Tuple[bool, bool]:
        """
        Handle block access.

        Returns:
            (is_promotion, is_eviction_needed): Whether block was promoted
            and whether eviction is needed to make space.
        """
        current_time = time.monotonic()
        self.access_counter += 1

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
        """Get eviction statistics."""
        total = self.stats["gpu_hits"] + self.stats["cpu_hits"] + self.stats["misses"]
        return {
            **self.stats,
            "total_accesses": total,
            "gpu_hit_rate": self.stats["gpu_hits"] / total if total > 0 else 0.0,
            "adaptive_p": self.shadow_tier.p,
            "gpu_blocks": len(self.gpu_blocks),
            "cpu_blocks": len(self.cpu_blocks),
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        for key in self.stats:
            self.stats[key] = 0
