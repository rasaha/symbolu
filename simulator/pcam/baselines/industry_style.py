"""
Industry-Style baseline controller.

A well-engineered production-style baseline combining:
- Pinned sinks: first 4-8 tokens always retained
- Recent window: last 256-512 tokens always retained
- Attention-aware: track per-block attention score (EMA)
- Ghost buffer: recently evicted blocks tracked for recall
- Adaptive budget: adjust retention by layer importance

This represents what a sophisticated software-only solution would do.
"""

from typing import List, Dict, Tuple, Optional, Set
from collections import OrderedDict, deque
from dataclasses import dataclass, field

from .base import BaselineController, ControllerConfig


@dataclass
class GhostEntry:
    """Entry in the ghost buffer."""
    block_id: int
    eviction_step: int
    last_score: float
    access_count: int


class IndustryStyleController(BaselineController):
    """
    Industry-style KV cache controller.

    Combines multiple strategies:
    1. Sink pinning: First tokens never evicted
    2. Recent window: Last N tokens always kept
    3. Attention-aware scoring: EMA of attention weights
    4. Ghost buffer: Track recently evicted blocks for potential recall
    5. Adaptive: Adjust policy based on observed patterns

    This is the hardest baseline to beat - represents a well-engineered
    production system.
    """

    def __init__(
        self,
        config: Optional[ControllerConfig] = None,
        ema_alpha: float = 0.3,
        ghost_buffer_size: int = 128,
        adaptive_threshold: float = 0.5,
    ):
        super().__init__(config)

        # EMA smoothing factor for attention scores
        self.ema_alpha = ema_alpha

        # Ghost buffer for tracking recently evicted blocks
        self.ghost_buffer_size = ghost_buffer_size
        self._ghost_buffer: OrderedDict[int, GhostEntry] = OrderedDict()

        # Adaptive threshold for recalling from ghost buffer
        self.adaptive_threshold = adaptive_threshold

        # Per-block state
        self._ema_scores: Dict[int, float] = {}
        self._access_counts: Dict[int, int] = {}
        self._last_access: Dict[int, int] = {}

        # Adaptive state
        self._recent_hit_rate: float = 0.5
        self._hit_history: deque = deque(maxlen=100)

    @property
    def name(self) -> str:
        return "industry_style"

    def get_candidates(
        self,
        query_block: int,
        k: int,
        sequence_id: int = 0,
    ) -> List[Tuple[int, float]]:
        """
        Return top-K candidates using multi-strategy selection.

        Priority order:
        1. Sinks (always included)
        2. Recent window (always included)
        3. High EMA score blocks
        4. Ghost buffer blocks with high recall score
        """
        candidates: List[Tuple[int, float]] = []
        seen: Set[int] = set()

        # 1. Sinks - highest priority
        for i in range(self.config.num_sinks):
            candidates.append((i, 1000.0))  # Very high score
            seen.add(i)

        # 2. Recent window - second priority
        recent_start = max(0, query_block - self.config.recent_window)
        for i in range(recent_start, query_block + 1):
            if i not in seen:
                distance = query_block - i
                recency_score = 100.0 / (1 + distance)  # Decay with distance
                candidates.append((i, recency_score))
                seen.add(i)

        # 3. High EMA score blocks from cache
        ema_candidates = [
            (block_id, score)
            for block_id, score in self._ema_scores.items()
            if block_id not in seen and block_id in self.state.cached_blocks
        ]
        ema_candidates.sort(key=lambda x: -x[1])

        for block_id, score in ema_candidates:
            if len(candidates) >= k:
                break
            candidates.append((block_id, score))
            seen.add(block_id)

        # 4. Check ghost buffer for potential recalls
        if len(candidates) < k:
            ghost_candidates = self._get_ghost_candidates(query_block, seen)
            for block_id, score in ghost_candidates:
                if len(candidates) >= k:
                    break
                candidates.append((block_id, score * 0.5))  # Discount ghost scores
                seen.add(block_id)

        # Sort and return
        candidates.sort(key=lambda x: -x[1])
        return candidates[:k]

    def record_access(
        self,
        query_block: int,
        accessed_blocks: List[int],
        attention_scores: Dict[int, float],
        sequence_id: int = 0,
    ) -> None:
        """
        Record access with EMA update and ghost buffer management.
        """
        hits = 0
        misses = 0

        for block_id in accessed_blocks:
            score = attention_scores.get(block_id, 0.0)

            # Update EMA score
            if block_id in self._ema_scores:
                old_score = self._ema_scores[block_id]
                self._ema_scores[block_id] = (
                    self.ema_alpha * score + (1 - self.ema_alpha) * old_score
                )
            else:
                self._ema_scores[block_id] = score

            # Update access tracking
            self._access_counts[block_id] = self._access_counts.get(block_id, 0) + 1
            self._last_access[block_id] = self._step

            # Check hit/miss
            if block_id in self.state.cached_blocks:
                hits += 1
            else:
                misses += 1
                self.state.cached_blocks.add(block_id)

                # Check if this was in ghost buffer (recall)
                if block_id in self._ghost_buffer:
                    del self._ghost_buffer[block_id]

        # Update stats
        self.state.hits += hits
        self.state.misses += misses

        # Update adaptive hit rate
        self._hit_history.append(hits / max(1, hits + misses))
        self._recent_hit_rate = sum(self._hit_history) / len(self._hit_history)

        # Handle evictions
        overflow = len(self.state.cached_blocks) - self.config.cache_capacity
        if overflow > 0:
            evicted = self.select_evictions(overflow, sequence_id)
            for block_id in evicted:
                self._move_to_ghost(block_id)
                self.state.cached_blocks.discard(block_id)

    def select_evictions(
        self,
        num_to_evict: int,
        sequence_id: int = 0,
    ) -> List[int]:
        """
        Select blocks to evict using adaptive scoring.

        Score combines:
        - Inverse EMA score (low attention = eviction candidate)
        - Recency (old blocks more likely to evict)
        - Access frequency (rarely accessed = eviction candidate)
        """
        # Calculate eviction scores for each block
        eviction_candidates = []

        for block_id in self.state.cached_blocks:
            # Skip sinks
            if self._is_sink(block_id):
                continue

            # Skip recent window
            if block_id in self._last_access:
                if self._step - self._last_access[block_id] < self.config.recent_window:
                    continue

            # Calculate eviction score (higher = more likely to evict)
            ema_score = self._ema_scores.get(block_id, 0.0)
            access_count = self._access_counts.get(block_id, 1)
            recency = self._step - self._last_access.get(block_id, 0)

            # Eviction score: low EMA, low access, high recency
            eviction_score = (
                (1 - ema_score) * 0.5 +  # Low attention
                (1 / access_count) * 0.3 +  # Low access frequency
                (recency / max(1, self._step)) * 0.2  # Old blocks
            )

            eviction_candidates.append((block_id, eviction_score))

        # Sort by eviction score (highest first = evict first)
        eviction_candidates.sort(key=lambda x: -x[1])

        evicted = []
        for block_id, _ in eviction_candidates:
            if len(evicted) >= num_to_evict:
                break
            evicted.append(block_id)
            self.state.evictions += 1

        return evicted

    def _move_to_ghost(self, block_id: int) -> None:
        """Move an evicted block to the ghost buffer."""
        entry = GhostEntry(
            block_id=block_id,
            eviction_step=self._step,
            last_score=self._ema_scores.get(block_id, 0.0),
            access_count=self._access_counts.get(block_id, 0),
        )

        # Add to ghost buffer
        self._ghost_buffer[block_id] = entry

        # Trim ghost buffer if needed
        while len(self._ghost_buffer) > self.ghost_buffer_size:
            self._ghost_buffer.popitem(last=False)  # Remove oldest

        # Clean up main state
        if block_id in self._ema_scores:
            del self._ema_scores[block_id]
        if block_id in self._access_counts:
            del self._access_counts[block_id]

    def _get_ghost_candidates(
        self,
        query_block: int,
        exclude: Set[int],
    ) -> List[Tuple[int, float]]:
        """
        Get candidate blocks from ghost buffer for potential recall.

        Returns blocks that were evicted recently but had high scores.
        """
        candidates = []

        for block_id, entry in self._ghost_buffer.items():
            if block_id in exclude:
                continue

            # Calculate recall score
            age = self._step - entry.eviction_step
            age_penalty = 1.0 / (1 + age * 0.01)

            recall_score = entry.last_score * age_penalty * (1 + entry.access_count * 0.1)

            if recall_score > self.adaptive_threshold:
                candidates.append((block_id, recall_score))

        candidates.sort(key=lambda x: -x[1])
        return candidates

    def reset(self) -> None:
        """Reset controller state."""
        super().reset()
        self._ghost_buffer.clear()
        self._ema_scores.clear()
        self._access_counts.clear()
        self._last_access.clear()
        self._recent_hit_rate = 0.5
        self._hit_history.clear()

    def get_stats(self) -> Dict:
        """Extended stats including ghost buffer and adaptive metrics."""
        stats = super().get_stats()
        stats["ghost_buffer_size"] = len(self._ghost_buffer)
        stats["recent_hit_rate"] = self._recent_hit_rate
        stats["tracked_blocks"] = len(self._ema_scores)
        return stats
