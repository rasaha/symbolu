"""
Base class for baseline controllers.

All baselines implement the same interface for fair comparison.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass, field


@dataclass
class ControllerConfig:
    """Configuration for baseline controllers."""
    # Cache capacity (number of blocks)
    cache_capacity: int = 256

    # Number of sink blocks to pin
    num_sinks: int = 4

    # Recent window size (blocks)
    recent_window: int = 32

    # Top-K candidates to return
    top_k: int = 256


@dataclass
class ControllerState:
    """State tracked by a controller."""
    # Currently cached block IDs
    cached_blocks: Set[int] = field(default_factory=set)

    # Block access history for LRU
    access_order: List[int] = field(default_factory=list)

    # Block scores (interpretation varies by controller)
    block_scores: Dict[int, float] = field(default_factory=dict)

    # Statistics
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class BaselineController(ABC):
    """
    Abstract base class for baseline KV cache controllers.

    All baselines must implement:
    - get_candidates: Return top-K candidate blocks for attention
    - record_access: Record which blocks were actually accessed
    - select_evictions: Select blocks to evict when cache is full
    """

    def __init__(self, config: Optional[ControllerConfig] = None):
        self.config = config or ControllerConfig()
        self.state = ControllerState()
        self._step = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """Controller name for reporting."""
        pass

    @abstractmethod
    def get_candidates(
        self,
        query_block: int,
        k: int,
        sequence_id: int = 0,
    ) -> List[Tuple[int, float]]:
        """
        Get top-K candidate blocks for this query.

        Args:
            query_block: Current query block ID
            k: Number of candidates to return
            sequence_id: Sequence ID (for multi-tenant)

        Returns:
            List of (block_id, score) tuples, sorted by score descending
        """
        pass

    @abstractmethod
    def record_access(
        self,
        query_block: int,
        accessed_blocks: List[int],
        attention_scores: Dict[int, float],
        sequence_id: int = 0,
    ) -> None:
        """
        Record which blocks were accessed and their attention scores.

        This is called after actual attention computation to update
        the controller's internal state.

        Args:
            query_block: Query block ID
            accessed_blocks: Blocks that were actually accessed
            attention_scores: Block ID -> attention weight
            sequence_id: Sequence ID
        """
        pass

    @abstractmethod
    def select_evictions(
        self,
        num_to_evict: int,
        sequence_id: int = 0,
    ) -> List[int]:
        """
        Select blocks to evict from cache.

        Args:
            num_to_evict: Number of blocks to evict
            sequence_id: Sequence ID

        Returns:
            List of block IDs to evict
        """
        pass

    def step(self) -> None:
        """Advance one step."""
        self._step += 1

    def reset(self) -> None:
        """Reset controller state."""
        self.state = ControllerState()
        self._step = 0

    def get_stats(self) -> Dict:
        """Get controller statistics."""
        total = self.state.hits + self.state.misses
        return {
            "name": self.name,
            "hits": self.state.hits,
            "misses": self.state.misses,
            "hit_rate": self.state.hits / total if total > 0 else 0.0,
            "evictions": self.state.evictions,
            "cached_blocks": len(self.state.cached_blocks),
        }

    def _is_sink(self, block_id: int) -> bool:
        """Check if block is a sink (should never be evicted)."""
        return block_id < self.config.num_sinks

    def _is_recent(self, block_id: int, current_block: int) -> bool:
        """Check if block is in recent window."""
        return block_id >= current_block - self.config.recent_window
