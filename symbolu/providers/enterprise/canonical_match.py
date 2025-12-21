"""
Canonical Match Provider (Enterprise)
=====================================

Enterprise implementation of the MatchProvider interface using the
C × R × S canonical matching framework from name_resonance.

This provider computes pairwise resonance between terms:
- C (Constraint): Phonemic → ontological feasibility
- R (Realization): Phonemic → experiential strength
- S (Referent): Non-phonemic referential coherence (source-independent)

Tier: Core/Substrate (Tier 1)
Authority: NONE (signal processing only)
"""

from typing import Tuple, Dict, Any, List

from symbolu.providers.interfaces.match_provider import (
    MatchProvider,
    MatchResult,
    BatchMatchResult,
    MatchMode,
)
from symbolu.name_resonance.canonical_matcher import (
    canonical_match as _canonical_match,
    CanonicalMatchResult,
    MatchMode as InternalMatchMode,
    C_THRESHOLD,
    R_THRESHOLD,
    S_THRESHOLD,
)


def _convert_mode(internal_mode: InternalMatchMode) -> MatchMode:
    """Convert internal MatchMode to provider MatchMode."""
    return MatchMode(internal_mode.value)


def _convert_result(result: CanonicalMatchResult) -> MatchResult:
    """Convert internal CanonicalMatchResult to provider MatchResult."""
    # Build diagnostics from detailed analysis
    diagnostics: Dict[str, Any] = {
        "constraint_analysis": {
            "violations": [
                {
                    "type": v.violation_type,
                    "severity": v.severity,
                    "description": v.description,
                }
                for v in result.constraint_analysis.violations
            ],
            "dominant_layer_a": result.constraint_analysis.dominant_layer_a,
            "dominant_layer_b": result.constraint_analysis.dominant_layer_b,
            "layer_distance": result.constraint_analysis.layer_distance,
            "direction_aligned": result.constraint_analysis.direction_aligned,
        },
        "realization_analysis": {
            "experiential_similarity": result.realization_analysis.experiential_similarity,
            "phonetic_coherence": result.realization_analysis.phonetic_coherence,
            "structural_alignment": result.realization_analysis.structural_alignment,
        },
        "referent_analysis": {
            "primary_a": [c.value for c in result.referent_analysis.primary_a],
            "primary_b": [c.value for c in result.referent_analysis.primary_b],
            "secondary_a": [c.value for c in result.referent_analysis.secondary_a],
            "secondary_b": [c.value for c in result.referent_analysis.secondary_b],
            "shared_primary": [c.value for c in result.referent_analysis.shared_primary],
            "shared_secondary": [c.value for c in result.referent_analysis.shared_secondary],
            "is_grounded": result.referent_analysis.is_grounded,
            "is_unknown": result.referent_analysis.is_unknown,
        },
    }

    return MatchResult(
        match_score=result.match_score,
        feasibility=result.feasibility,
        realization=result.realization,
        referent=result.referent,
        mode=_convert_mode(result.mode),
        term_a=result.word_a,
        term_b=result.word_b,
        confidence=result.confidence,
        diagnostics=diagnostics,
    )


class CanonicalMatchProvider(MatchProvider):
    """
    Enterprise match provider using the C × R × S canonical matching framework.

    This provider wraps the canonical_match function from name_resonance
    and provides the full MatchProvider interface for STL integration.

    The formula: MATCH = C × R × S

    Where:
    - C = Constraint feasibility (phonemic → ontology)
    - R = Realization strength (phonemic → experience)
    - S = Referential coherence (NON-phonemic, source-independent)

    Key Properties:
    - Deterministic: Same inputs always produce identical outputs
    - Explainable: Full diagnostic trace for every match
    - Source-independent: S provides non-phonemic validation axis
    - Zero authority: Signal processing only, no governance decisions

    Attributes:
        c_threshold: Threshold for "high" constraint score
        r_threshold: Threshold for "high" realization score
        s_threshold: Threshold for referent coherence
    """

    def __init__(
        self,
        c_threshold: float = C_THRESHOLD,
        r_threshold: float = R_THRESHOLD,
        s_threshold: float = S_THRESHOLD,
    ):
        """
        Initialize the canonical match provider.

        Args:
            c_threshold: Threshold for "high" constraint score (default 0.6)
            r_threshold: Threshold for "high" realization score (default 0.5)
            s_threshold: Threshold for referent coherence (default 0.2)
        """
        self._c_threshold = c_threshold
        self._r_threshold = r_threshold
        self._s_threshold = s_threshold

    def match(self, term_a: str, term_b: str) -> MatchResult:
        """
        Compute canonical match between two terms.

        MATCH = C × R × S

        Args:
            term_a: First term
            term_b: Second term

        Returns:
            MatchResult with score, components, and diagnostics
        """
        internal_result = _canonical_match(term_a, term_b)
        return _convert_result(internal_result)

    def match_batch(
        self,
        pairs: List[Tuple[str, str]],
    ) -> BatchMatchResult:
        """
        Batch match multiple term pairs.

        Args:
            pairs: List of (term_a, term_b) tuples

        Returns:
            BatchMatchResult with all pairwise results, sorted by score
        """
        results = []
        for term_a, term_b in pairs:
            result = self.match(term_a, term_b)
            results.append(result)

        # Sort by match score descending
        sorted_results = sorted(results, key=lambda r: r.match_score, reverse=True)

        stats = {
            "provider": "canonical_match",
            "total_pairs": len(pairs),
            "true_matches": sum(1 for r in results if r.mode == MatchMode.TRUE_MATCH),
            "latent_matches": sum(1 for r in results if r.mode == MatchMode.LATENT),
            "referent_mismatches": sum(1 for r in results if r.mode == MatchMode.REFERENT_MISMATCH),
            "non_matches": sum(1 for r in results if r.mode == MatchMode.NON_MATCH),
            "distorted": sum(1 for r in results if r.mode == MatchMode.DISTORTED),
            "avg_score": sum(r.match_score for r in results) / len(results) if results else 0.0,
            "thresholds": self.get_thresholds(),
        }

        return BatchMatchResult(
            results=tuple(sorted_results),
            stats=stats,
        )

    def match_one_to_many(
        self,
        query: str,
        candidates: Tuple[str, ...],
        top_k: int = 10,
    ) -> BatchMatchResult:
        """
        Match a query term against multiple candidates.

        Args:
            query: The query term
            candidates: Tuple of candidate terms to match against
            top_k: Maximum number of results to return

        Returns:
            BatchMatchResult sorted by match score (descending)
        """
        pairs = [(query, candidate) for candidate in candidates]
        result = self.match_batch(pairs)

        # Apply top_k limit
        if top_k is not None and len(result.results) > top_k:
            result = result.top_k(top_k)

        # Update stats with query info
        stats = {
            **result.stats,
            "query": query,
            "candidate_count": len(candidates),
            "top_k": top_k,
        }

        return BatchMatchResult(
            results=result.results,
            stats=stats,
        )

    def get_thresholds(self) -> Dict[str, float]:
        """
        Return the threshold configuration.

        Returns:
            Dict with C_THRESHOLD, R_THRESHOLD, S_THRESHOLD
        """
        return {
            "C_THRESHOLD": self._c_threshold,
            "R_THRESHOLD": self._r_threshold,
            "S_THRESHOLD": self._s_threshold,
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def create_canonical_match_provider(
    c_threshold: float = C_THRESHOLD,
    r_threshold: float = R_THRESHOLD,
    s_threshold: float = S_THRESHOLD,
) -> CanonicalMatchProvider:
    """
    Factory function to create a CanonicalMatchProvider.

    Args:
        c_threshold: Threshold for "high" constraint score
        r_threshold: Threshold for "high" realization score
        s_threshold: Threshold for referent coherence

    Returns:
        Configured CanonicalMatchProvider instance
    """
    return CanonicalMatchProvider(
        c_threshold=c_threshold,
        r_threshold=r_threshold,
        s_threshold=s_threshold,
    )
