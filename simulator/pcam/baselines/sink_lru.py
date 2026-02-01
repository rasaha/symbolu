"""
Sink+LRU baseline controller.

The simplest reasonable baseline:
- Pin first K tokens (sinks) - never evict
- Use LRU for everything else
"""

from typing import List, Dict, Tuple, Optional
from collections import OrderedDict

from .base import BaselineController, ControllerConfig


class SinkLRUController(BaselineController):
    """
    Sink+LRU eviction policy.

    Sinks are always retained. Other blocks are evicted LRU.
    This is the simplest reasonable baseline for comparison.
    """

    def __init__(self, config: Optional[ControllerConfig] = None):
        super().__init__(config)
        # OrderedDict for LRU tracking (most recent at end)
        self._lru_order: OrderedDict[int, float] = OrderedDict()

    @property
    def name(self) -> str:
        return "sink_lru"

    def get_candidates(
        self,
        query_block: int,
        k: int,
        sequence_id: int = 0,
    ) -> List[Tuple[int, float]]:
        """
        Return candidates based on recency.

        For Sink+LRU, we return:
        1. All sink blocks
        2. Recent window blocks
        3. Most recently used blocks to fill k
        """
        candidates = []

        # Always include sinks
        for i in range(self.config.num_sinks):
            candidates.append((i, 1.0))  # Score 1.0 for sinks

        # Include recent window
        for i in range(max(0, query_block - self.config.recent_window), query_block + 1):
            if i >= self.config.num_sinks:  # Don't double-count sinks
                distance = query_block - i
                score = 1.0 / (1 + distance)  # Decay with distance
                candidates.append((i, score))

        # Fill remaining with most recently used
        if len(candidates) < k:
            recent_blocks = list(reversed(self._lru_order.keys()))
            for block_id in recent_blocks:
                if block_id not in [c[0] for c in candidates]:
                    candidates.append((block_id, self._lru_order.get(block_id, 0.0)))
                    if len(candidates) >= k:
                        break

        # Sort by score and return top k
        candidates.sort(key=lambda x: -x[1])
        return candidates[:k]

    def record_access(
        self,
        query_block: int,
        accessed_blocks: List[int],
        attention_scores: Dict[int, float],
        sequence_id: int = 0,
    ) -> None:
        """Record block accesses for LRU ordering."""
        for block_id in accessed_blocks:
            # Move to end (most recently used)
            if block_id in self._lru_order:
                self._lru_order.move_to_end(block_id)
                self.state.hits += 1
            else:
                self.state.misses += 1

            self._lru_order[block_id] = attention_scores.get(block_id, 0.0)
            self.state.cached_blocks.add(block_id)

        # Check if we need to evict
        overflow = len(self._lru_order) - self.config.cache_capacity
        if overflow > 0:
            evicted = self.select_evictions(overflow, sequence_id)
            for block_id in evicted:
                del self._lru_order[block_id]
                self.state.cached_blocks.discard(block_id)

    def select_evictions(
        self,
        num_to_evict: int,
        sequence_id: int = 0,
    ) -> List[int]:
        """
        Select LRU blocks to evict (excluding sinks).
        """
        evicted = []
        for block_id in list(self._lru_order.keys()):
            if len(evicted) >= num_to_evict:
                break
            if not self._is_sink(block_id):
                evicted.append(block_id)
                self.state.evictions += 1

        return evicted

    def reset(self) -> None:
        """Reset controller state."""
        super().reset()
        self._lru_order.clear()
