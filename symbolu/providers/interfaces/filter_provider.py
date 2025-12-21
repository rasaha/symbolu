"""
Filter Provider Interface
=========================

Abstract interface for candidate filtering.
Enterprise mode uses resonance-based phoneme filtering.
Consumer mode uses attention-based semantic filtering.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, Dict, Any


@dataclass(frozen=True)
class FilterResult:
    """
    Result of candidate filtering.

    This is the standardized output from all filter providers.
    Contains the filtered candidates with their relevance scores.

    Attributes:
        filtered_texts: Tuple of filtered candidate texts (ordered by relevance)
        scores: Tuple of relevance scores for each filtered text
        stats: Implementation-specific statistics (timing, reduction ratio, etc.)
    """
    filtered_texts: Tuple[str, ...]
    scores: Tuple[float, ...]
    stats: Dict[str, Any]

    def __post_init__(self):
        if len(self.filtered_texts) != len(self.scores):
            raise ValueError(
                f"filtered_texts and scores must have same length: "
                f"{len(self.filtered_texts)} != {len(self.scores)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "filtered_texts": list(self.filtered_texts),
            "scores": list(self.scores),
            "stats": self.stats,
        }

    @property
    def count(self) -> int:
        """Return the number of filtered candidates."""
        return len(self.filtered_texts)

    def top_k(self, k: int) -> "FilterResult":
        """Return a new FilterResult with only the top k candidates."""
        if k >= len(self.filtered_texts):
            return self
        return FilterResult(
            filtered_texts=self.filtered_texts[:k],
            scores=self.scores[:k],
            stats={**self.stats, "truncated_to": k},
        )


class FilterProvider(ABC):
    """
    Abstract interface for candidate filtering.

    Filter providers reduce a set of candidates to the most relevant
    subset for a given query. Enterprise providers use phoneme resonance,
    while consumer providers use attention-based semantic similarity.
    """

    @abstractmethod
    def filter(
        self,
        candidates: Tuple[str, ...],
        query: str,
        top_k: int = 10,
    ) -> FilterResult:
        """
        Filter candidates by relevance to query.

        Args:
            candidates: Tuple of candidate texts to filter
            query: Query text to compare against
            top_k: Maximum number of candidates to return

        Returns:
            FilterResult with filtered candidates, scores, and stats
        """
        pass

    def get_threshold(self) -> float:
        """
        Return the default filtering threshold.

        Override in subclasses to provide provider-specific defaults.
        """
        return 0.5
