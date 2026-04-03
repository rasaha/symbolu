"""
Enterprise Search Engine (Tier 1)
=================================

Pure STL engine for search, classification, and filtering.
No LLM - fastest and cheapest option.

Use cases:
    - Intent classification
    - Document filtering/retrieval
    - Candidate pre-filtering
    - Audit trail generation

Performance:
    - Latency: ~100μs per query
    - Cost: Free (no API calls)
    - Accuracy: ~90% for intent classification
"""

import time
from typing import Optional, Tuple, List, Dict, Any

from symbolu_core.engine.base import BaseEngine, EngineResult, EngineCapability
from symbolu_core.hybrid.router import SemanticRouter, RoutingDecision
from symbolu_core.hybrid.vocabulary import CustomVocabulary
from symbolu_core.resonance import analyze_phrase, compare_words


class EnterpriseSearchEngine(BaseEngine):
    """
    Enterprise Tier 1: Pure STL for search/classification.

    No LLM involvement - purely symbolic processing.

    Example:
        engine = EnterpriseSearchEngine()

        # Classification
        result = engine.classify("Deploy the K8s cluster")
        print(result.intent)      # "action"
        print(result.confidence)  # 0.9

        # Search/ranking
        result = engine.search(
            query="quantum physics",
            candidates=["Chemistry basics", "Quantum mechanics", "Biology"]
        )
        print(result.metadata["ranked"])  # ["Quantum mechanics", ...]
    """

    def __init__(
        self,
        vocabulary: Optional[CustomVocabulary] = None,
        confidence_threshold: float = 0.3,
    ):
        """
        Initialize Enterprise Search Engine.

        Args:
            vocabulary: Optional custom vocabulary for domain terms
            confidence_threshold: Minimum confidence for classification
        """
        self.router = SemanticRouter(
            vocabulary=vocabulary,
            confidence_threshold=confidence_threshold,
        )
        self.vocabulary = vocabulary

    @property
    def tier_name(self) -> str:
        return "enterprise_search"

    @property
    def capabilities(self) -> Tuple[EngineCapability, ...]:
        return (EngineCapability.CLASSIFY, EngineCapability.SEARCH)

    def classify(self, query: str) -> EngineResult:
        """
        Classify intent using pure STL.

        Args:
            query: Input text to classify

        Returns:
            EngineResult with intent and confidence
        """
        start = time.perf_counter()

        decision = self.router.route(query)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return EngineResult(
            success=True,
            intent=decision.model_type.value,
            confidence=decision.confidence,
            tier_used=self.tier_name,
            stl_signal={
                "dominant_layer": decision.dominant_layer,
                "layer_scores": list(decision.layer_scores),
                "word_count": len(decision.query_analysis.words),
                "harmony": decision.query_analysis.overall_harmony,
            },
            latency_ms=elapsed_ms,
            metadata={
                "model_type": decision.model_type.value,
                "routing_trace": decision.trace if hasattr(decision, 'trace') else None,
            },
        )

    def search(
        self,
        query: str,
        candidates: List[str],
        top_k: Optional[int] = None,
    ) -> EngineResult:
        """
        Rank candidates by phoneme resonance with query.

        Uses STL's phoneme similarity for ranking.

        Args:
            query: Search query
            candidates: List of candidate documents/items
            top_k: Number of top results to return (default: all)

        Returns:
            EngineResult with ranked candidates in metadata
        """
        start = time.perf_counter()

        # Analyze query
        query_analysis = analyze_phrase(query)

        if not query_analysis.words:
            return EngineResult(
                success=False,
                tier_used=self.tier_name,
                metadata={"error": "Query has no content words"},
            )

        # Score each candidate by resonance with query
        scored_candidates = []
        for candidate in candidates:
            candidate_analysis = analyze_phrase(candidate)

            if not candidate_analysis.words:
                scored_candidates.append((candidate, 0.0))
                continue

            # Compute average resonance between query and candidate words
            total_resonance = 0.0
            comparisons = 0

            for q_word in query_analysis.words:
                for c_word in candidate_analysis.words:
                    resonance = compare_words(q_word.word, c_word.word)
                    total_resonance += resonance.similarity
                    comparisons += 1

            avg_resonance = total_resonance / comparisons if comparisons > 0 else 0.0
            scored_candidates.append((candidate, avg_resonance))

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Apply top_k if specified
        if top_k is not None:
            scored_candidates = scored_candidates[:top_k]

        elapsed_ms = (time.perf_counter() - start) * 1000

        return EngineResult(
            success=True,
            tier_used=self.tier_name,
            latency_ms=elapsed_ms,
            metadata={
                "ranked": [c[0] for c in scored_candidates],
                "scores": {c[0]: c[1] for c in scored_candidates},
                "query_words": [w.word for w in query_analysis.words],
            },
        )

    def filter_by_intent(
        self,
        candidates: List[str],
        target_intent: str,
        min_confidence: float = 0.5,
    ) -> EngineResult:
        """
        Filter candidates to only those matching a target intent.

        Args:
            candidates: List of candidate texts
            target_intent: Target intent to filter for
            min_confidence: Minimum confidence to include

        Returns:
            EngineResult with filtered candidates in metadata
        """
        start = time.perf_counter()

        filtered = []
        for candidate in candidates:
            result = self.classify(candidate)
            if result.intent == target_intent and result.confidence >= min_confidence:
                filtered.append({
                    "text": candidate,
                    "confidence": result.confidence,
                })

        elapsed_ms = (time.perf_counter() - start) * 1000

        return EngineResult(
            success=True,
            tier_used=self.tier_name,
            latency_ms=elapsed_ms,
            metadata={
                "filtered": filtered,
                "target_intent": target_intent,
                "count": len(filtered),
                "total_candidates": len(candidates),
            },
        )

    def batch_classify(self, queries: List[str]) -> List[EngineResult]:
        """
        Classify multiple queries efficiently.

        Args:
            queries: List of queries to classify

        Returns:
            List of EngineResults
        """
        return [self.classify(q) for q in queries]
