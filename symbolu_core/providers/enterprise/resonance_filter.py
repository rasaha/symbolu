"""
Resonance Filter Provider (Enterprise)
======================================

Wraps the existing CandidatePreFilter from symbolu/hybrid/prefilter.py.
Provides phoneme resonance-based candidate filtering for enterprise
use cases requiring explainable, auditable filtering decisions.
"""

from typing import Tuple, Dict, Any

from symbolu_core.providers.interfaces.filter_provider import (
    FilterProvider,
    FilterResult,
)
from symbolu_core.hybrid.prefilter import CandidatePreFilter


class ResonanceFilterProvider(FilterProvider):
    """
    Enterprise filter provider using phoneme resonance.

    This provider wraps the existing CandidatePreFilter and produces
    fully explainable filtering decisions based on phoneme similarity.

    Attributes:
        threshold: Minimum phoneme similarity to pass (0.0 to 1.0)
    """

    def __init__(
        self,
        threshold: float = 0.5,
    ):
        """
        Initialize the resonance filter provider.

        Args:
            threshold: Minimum phoneme similarity to pass filtering
        """
        self._filter = CandidatePreFilter(threshold=threshold, top_k=None)
        self._threshold = threshold

    def filter(
        self,
        candidates: Tuple[str, ...],
        query: str,
        top_k: int = 10,
    ) -> FilterResult:
        """
        Filter candidates using phoneme resonance.

        Args:
            candidates: Tuple of candidate texts to filter
            query: Query text to compare against
            top_k: Maximum number of candidates to return

        Returns:
            FilterResult with filtered candidates, scores, and stats
        """
        if not candidates:
            return FilterResult(
                filtered_texts=(),
                scores=(),
                stats={
                    "provider": "resonance",
                    "threshold": self._threshold,
                    "total_candidates": 0,
                    "passed_candidates": 0,
                    "reduction_ratio": 0.0,
                },
            )

        # Get filtered candidates with scores
        scored_results = self._filter.filter(
            candidates=candidates,
            target=query,
            return_scores=True,
        )

        # Sort by score descending and apply top_k
        sorted_results = sorted(scored_results, key=lambda x: x[1], reverse=True)
        if top_k is not None and len(sorted_results) > top_k:
            sorted_results = sorted_results[:top_k]

        # Separate texts and scores
        filtered_texts = tuple(r[0] for r in sorted_results)
        scores = tuple(r[1] for r in sorted_results)

        # Build stats
        stats = {
            "provider": "resonance",
            "threshold": self._threshold,
            "query": query,
            "total_candidates": len(candidates),
            "passed_candidates": len(filtered_texts),
            "reduction_ratio": len(filtered_texts) / len(candidates) if candidates else 0.0,
            "top_k_applied": top_k,
        }

        return FilterResult(
            filtered_texts=filtered_texts,
            scores=scores,
            stats=stats,
        )

    def get_threshold(self) -> float:
        """Return the filtering threshold."""
        return self._threshold
