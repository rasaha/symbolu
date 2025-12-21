"""
Coherence Filter Provider (Enterprise)
=======================================

Enhanced filter provider that combines resonance-based filtering with
canonical matching (C × R × S) coherence diagnostics.

This provider adds coherence metadata to filter results, enabling:
- Post-generation coherence auditing
- Semantic validation beyond phonetic similarity
- Full C × R × S diagnostic visibility

Tier: Core/Substrate (Tier 1)
Authority: NONE (signal processing only)
"""

from typing import Tuple, Dict, Any, Optional, List

from symbolu.providers.interfaces.filter_provider import (
    FilterProvider,
    FilterResult,
)
from symbolu.providers.interfaces.match_provider import (
    MatchProvider,
    MatchResult,
    MatchMode,
)
from symbolu.providers.enterprise.resonance_filter import ResonanceFilterProvider
from symbolu.providers.enterprise.canonical_match import CanonicalMatchProvider


class CoherenceFilterResult(FilterResult):
    """
    Extended FilterResult with canonical matching coherence metadata.

    This adds C × R × S diagnostics to standard filter results,
    enabling post-generation coherence auditing.
    """

    @classmethod
    def from_filter_result(
        cls,
        base_result: FilterResult,
        coherence_checks: Dict[str, Any],
    ) -> "CoherenceFilterResult":
        """
        Create a CoherenceFilterResult from a base FilterResult.

        Args:
            base_result: The underlying filter result
            coherence_checks: Dictionary of canonical match diagnostics

        Returns:
            CoherenceFilterResult with coherence metadata
        """
        extended_stats = {
            **base_result.stats,
            "coherence_checks": coherence_checks,
        }
        return cls(
            filtered_texts=base_result.filtered_texts,
            scores=base_result.scores,
            stats=extended_stats,
        )


class CoherenceFilterProvider(FilterProvider):
    """
    Enterprise filter provider with canonical matching coherence.

    This provider wraps the standard ResonanceFilterProvider and
    adds C × R × S coherence diagnostics to the results metadata.

    Use Cases:
    - Word-to-word semantic filtering (full S discrimination)
    - Post-generation coherence auditing
    - Semantic validation requiring non-phonemic grounding

    The coherence metadata follows the DESIGN.md specification:
    ```python
    result.stats["coherence_checks"] = {
        ("word_a", "word_b"): {
            "match_score": 0.687,
            "mode": "true_match",
            "components": {"C": 0.82, "R": 0.84, "S": 0.99}
        },
        ...
    }
    ```

    Attributes:
        base_filter: Underlying filter provider (default: ResonanceFilterProvider)
        match_provider: Canonical match provider for coherence checks
        compute_pairwise: Whether to compute pairwise coherence between results
    """

    def __init__(
        self,
        threshold: float = 0.5,
        compute_pairwise: bool = True,
        max_pairwise_checks: int = 20,
    ):
        """
        Initialize the coherence filter provider.

        Args:
            threshold: Minimum phoneme similarity to pass filtering
            compute_pairwise: Whether to compute pairwise coherence between results
            max_pairwise_checks: Maximum number of pairwise checks (to limit compute)
        """
        self._base_filter = ResonanceFilterProvider(threshold=threshold)
        self._match_provider = CanonicalMatchProvider()
        self._compute_pairwise = compute_pairwise
        self._max_pairwise_checks = max_pairwise_checks
        self._threshold = threshold

    def filter(
        self,
        candidates: Tuple[str, ...],
        query: str,
        top_k: int = 10,
    ) -> FilterResult:
        """
        Filter candidates with coherence diagnostics.

        Performs standard resonance filtering, then adds C × R × S
        coherence checks for:
        1. Query vs each filtered candidate
        2. Optionally, pairwise between filtered candidates

        Args:
            candidates: Tuple of candidate texts to filter
            query: Query text to compare against
            top_k: Maximum number of candidates to return

        Returns:
            FilterResult with coherence_checks in stats
        """
        # Step 1: Standard resonance filtering
        base_result = self._base_filter.filter(candidates, query, top_k)

        if not base_result.filtered_texts:
            return CoherenceFilterResult.from_filter_result(
                base_result,
                coherence_checks={
                    "query_matches": [],
                    "pairwise_matches": [],
                    "summary": {
                        "total_checks": 0,
                        "true_matches": 0,
                        "referent_mismatches": 0,
                    },
                },
            )

        # Step 2: Compute query → candidate coherence
        query_matches = self._compute_query_coherence(query, base_result.filtered_texts)

        # Step 3: Optionally compute pairwise coherence
        pairwise_matches = []
        if self._compute_pairwise and len(base_result.filtered_texts) > 1:
            pairwise_matches = self._compute_pairwise_coherence(
                base_result.filtered_texts
            )

        # Step 4: Build coherence summary
        all_matches = query_matches + pairwise_matches
        summary = {
            "total_checks": len(all_matches),
            "true_matches": sum(1 for m in all_matches if m["mode"] == "true_match"),
            "latent_matches": sum(1 for m in all_matches if m["mode"] == "latent"),
            "referent_mismatches": sum(
                1 for m in all_matches if m["mode"] == "ref_mismatch"
            ),
            "non_matches": sum(1 for m in all_matches if m["mode"] == "non_match"),
            "avg_match_score": (
                sum(m["match_score"] for m in all_matches) / len(all_matches)
                if all_matches
                else 0.0
            ),
            "avg_referent_score": (
                sum(m["S"] for m in all_matches) / len(all_matches)
                if all_matches
                else 0.0
            ),
        }

        coherence_checks = {
            "query_matches": query_matches,
            "pairwise_matches": pairwise_matches,
            "summary": summary,
        }

        return CoherenceFilterResult.from_filter_result(base_result, coherence_checks)

    def _compute_query_coherence(
        self,
        query: str,
        candidates: Tuple[str, ...],
    ) -> List[Dict[str, Any]]:
        """Compute coherence between query and each candidate."""
        results = []
        for candidate in candidates:
            match = self._match_provider.match(query, candidate)
            results.append(self._format_match(match))
        return results

    def _compute_pairwise_coherence(
        self,
        candidates: Tuple[str, ...],
    ) -> List[Dict[str, Any]]:
        """Compute pairwise coherence between candidates."""
        results = []
        pairs_checked = 0

        for i, a in enumerate(candidates):
            if pairs_checked >= self._max_pairwise_checks:
                break
            for b in candidates[i + 1 :]:
                if pairs_checked >= self._max_pairwise_checks:
                    break
                match = self._match_provider.match(a, b)
                results.append(self._format_match(match))
                pairs_checked += 1

        return results

    def _format_match(self, match: MatchResult) -> Dict[str, Any]:
        """Format a MatchResult for coherence metadata."""
        return {
            "terms": (match.term_a, match.term_b),
            "match_score": match.match_score,
            "C": match.feasibility,
            "R": match.realization,
            "S": match.referent,
            "mode": match.mode.value,
            "confidence": match.confidence,
            "is_referent_grounded": match.is_referent_grounded,
        }

    def get_threshold(self) -> float:
        """Return the filtering threshold."""
        return self._threshold

    def get_match_provider(self) -> MatchProvider:
        """Return the underlying match provider for direct access."""
        return self._match_provider


def create_coherence_filter_provider(
    threshold: float = 0.5,
    compute_pairwise: bool = True,
    max_pairwise_checks: int = 20,
) -> CoherenceFilterProvider:
    """
    Factory function to create a CoherenceFilterProvider.

    Args:
        threshold: Minimum phoneme similarity to pass filtering
        compute_pairwise: Whether to compute pairwise coherence
        max_pairwise_checks: Maximum pairwise checks (limit compute)

    Returns:
        Configured CoherenceFilterProvider instance
    """
    return CoherenceFilterProvider(
        threshold=threshold,
        compute_pairwise=compute_pairwise,
        max_pairwise_checks=max_pairwise_checks,
    )
