"""
H2O (Heavy Hitters Oracle) baseline controller.

Based on the H2O paper: tracks accumulated attention mass per block
and evicts blocks with lowest cumulative attention.
"""

from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from .base import BaselineController, ControllerConfig


class H2OController(BaselineController):
    """
    H2O (Heavy Hitters Oracle) eviction policy.

    Tracks cumulative attention scores for each block.
    Evicts blocks with lowest accumulated attention mass.

    This represents the state-of-the-art academic baseline.
    """

    def __init__(
        self,
        config: Optional[ControllerConfig] = None,
        decay_rate: float = 0.99,
    ):
        super().__init__(config)
        self.decay_rate = decay_rate

        # Cumulative attention mass per block
        self._attention_mass: Dict[int, float] = defaultdict(float)

        # Access count per block
        self._access_counts: Dict[int, int] = defaultdict(int)

    @property
    def name(self) -> str:
        return "h2o"

    def get_candidates(
        self,
        query_block: int,
        k: int,
        sequence_id: int = 0,
    ) -> List[Tuple[int, float]]:
        """
        Return top-K blocks by accumulated attention mass.

        Heavy hitters (blocks with high cumulative attention)
        are prioritized as candidates.
        """
        candidates = []

        # Always include sinks (highest priority)
        for i in range(self.config.num_sinks):
            candidates.append((i, float('inf')))

        # Always include recent window
        for i in range(max(0, query_block - self.config.recent_window), query_block + 1):
            if i >= self.config.num_sinks:
                # Recent blocks get boosted score
                base_score = self._attention_mass.get(i, 0.0)
                distance = query_block - i
                recency_boost = 1.0 / (1 + distance * 0.1)
                candidates.append((i, base_score + recency_boost))

        # Add heavy hitters
        sorted_by_mass = sorted(
            self._attention_mass.items(),
            key=lambda x: -x[1]
        )

        for block_id, mass in sorted_by_mass:
            if block_id not in [c[0] for c in candidates]:
                candidates.append((block_id, mass))
                if len(candidates) >= k * 2:  # Get extra for deduplication
                    break

        # Sort by score and return top k
        candidates.sort(key=lambda x: -x[1])

        # Deduplicate while preserving order
        seen = set()
        unique_candidates = []
        for block_id, score in candidates:
            if block_id not in seen:
                seen.add(block_id)
                unique_candidates.append((block_id, score))
                if len(unique_candidates) >= k:
                    break

        return unique_candidates

    def record_access(
        self,
        query_block: int,
        accessed_blocks: List[int],
        attention_scores: Dict[int, float],
        sequence_id: int = 0,
    ) -> None:
        """
        Accumulate attention mass for accessed blocks.

        Also applies decay to maintain recency bias.
        """
        # Apply decay to all existing scores
        for block_id in self._attention_mass:
            self._attention_mass[block_id] *= self.decay_rate

        # Accumulate attention for accessed blocks
        for block_id in accessed_blocks:
            score = attention_scores.get(block_id, 0.0)
            self._attention_mass[block_id] += score
            self._access_counts[block_id] += 1

            if block_id in self.state.cached_blocks:
                self.state.hits += 1
            else:
                self.state.misses += 1
                self.state.cached_blocks.add(block_id)

        # Check for evictions
        overflow = len(self.state.cached_blocks) - self.config.cache_capacity
        if overflow > 0:
            evicted = self.select_evictions(overflow, sequence_id)
            for block_id in evicted:
                self.state.cached_blocks.discard(block_id)

    def select_evictions(
        self,
        num_to_evict: int,
        sequence_id: int = 0,
    ) -> List[int]:
        """
        Evict blocks with lowest accumulated attention mass.
        """
        # Get cached blocks sorted by attention mass (ascending)
        eviction_candidates = [
            (block_id, self._attention_mass.get(block_id, 0.0))
            for block_id in self.state.cached_blocks
            if not self._is_sink(block_id)
        ]
        eviction_candidates.sort(key=lambda x: x[1])

        evicted = []
        for block_id, _ in eviction_candidates:
            if len(evicted) >= num_to_evict:
                break
            evicted.append(block_id)
            self.state.evictions += 1

            # Clear attention mass for evicted blocks
            if block_id in self._attention_mass:
                del self._attention_mass[block_id]

        return evicted

    def reset(self) -> None:
        """Reset controller state."""
        super().reset()
        self._attention_mass.clear()
        self._access_counts.clear()

    def get_stats(self) -> Dict:
        """Extended stats including attention distribution."""
        stats = super().get_stats()
        stats["heavy_hitters"] = len([
            m for m in self._attention_mass.values() if m > 0.1
        ])
        return stats
