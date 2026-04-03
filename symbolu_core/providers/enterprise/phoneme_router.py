"""
Phoneme Router Provider (Enterprise)
====================================

Wraps the existing SemanticRouter from symbolu/hybrid/router.py.
Provides symbolic routing based on phoneme analysis for enterprise
use cases requiring explainable, auditable routing decisions.
"""

from typing import List, Dict, Any

from symbolu_core.providers.interfaces.router_provider import (
    RouterProvider,
    RoutingDecision,
    ModelType,
)
from symbolu_core.hybrid.router import (
    SemanticRouter,
    RoutingDecision as HybridRoutingDecision,
    ModelType as HybridModelType,
)


# Map hybrid ModelType to interface ModelType
_MODEL_TYPE_MAP: Dict[HybridModelType, ModelType] = {
    HybridModelType.GENERAL: ModelType.GENERAL,
    HybridModelType.REASONING: ModelType.REASONING,
    HybridModelType.RELATIONSHIP: ModelType.RELATIONSHIP,
    HybridModelType.ACTION: ModelType.ACTION,
    HybridModelType.CREATIVE: ModelType.CREATIVE,
    HybridModelType.REFLECTIVE: ModelType.REFLECTIVE,
    HybridModelType.DIRECTIVE: ModelType.DIRECTIVE,
    HybridModelType.TRANSCENDENT: ModelType.TRANSCENDENT,
}


class PhonemeRouterProvider(RouterProvider):
    """
    Enterprise router provider using phoneme-based symbolic routing.

    This provider wraps the existing SemanticRouter and produces
    fully explainable routing decisions based on phoneme analysis.
    All decisions include a complete audit trace.

    Attributes:
        confidence_threshold: Minimum confidence for non-fallback routing
        fallback_model: Model type to use when confidence is low
    """

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        fallback_model: ModelType = ModelType.GENERAL,
    ):
        """
        Initialize the phoneme router provider.

        Args:
            confidence_threshold: Minimum dominant layer score to route
            fallback_model: Model to use when confidence is low
        """
        # Map interface ModelType back to hybrid ModelType for the underlying router
        hybrid_fallback = HybridModelType.GENERAL
        for hybrid_type, interface_type in _MODEL_TYPE_MAP.items():
            if interface_type == fallback_model:
                hybrid_fallback = hybrid_type
                break

        self._router = SemanticRouter(
            confidence_threshold=confidence_threshold,
            fallback_model=hybrid_fallback,
        )
        self._confidence_threshold = confidence_threshold
        self._fallback_model = fallback_model

    def route(self, query: str) -> RoutingDecision:
        """
        Route a query using phoneme-based analysis.

        Args:
            query: The input query/prompt

        Returns:
            RoutingDecision with model type, confidence, and audit trace
        """
        # Get decision from underlying router
        hybrid_decision = self._router.route(query)

        # Map model type
        model_type = _MODEL_TYPE_MAP.get(
            hybrid_decision.model_type, ModelType.GENERAL
        )

        # Build audit trace
        trace = self._build_trace(hybrid_decision)

        return RoutingDecision(
            model_type=model_type,
            confidence=hybrid_decision.confidence,
            dominant_layer=hybrid_decision.dominant_layer,
            layer_scores=hybrid_decision.layer_scores,
            trace=trace,
        )

    def route_batch(self, queries: List[str]) -> List[RoutingDecision]:
        """
        Batch route multiple queries.

        Args:
            queries: List of input queries

        Returns:
            List of RoutingDecision objects (one per query)
        """
        return [self.route(query) for query in queries]

    def _build_trace(self, hybrid_decision: HybridRoutingDecision) -> Dict[str, Any]:
        """
        Build an audit trace from the hybrid routing decision.

        Args:
            hybrid_decision: The underlying hybrid routing decision

        Returns:
            Dictionary with audit information
        """
        analysis = hybrid_decision.query_analysis

        # Extract word-level information for audit
        word_traces = []
        for word_vec in analysis.words:
            word_traces.append({
                "word": word_vec.word,
                "phonemes": list(word_vec.phonemes),
                "dominant_layer": word_vec.dominant_layer,
                "dominant_score": word_vec.dominant_score,
                "top_layers": list(word_vec.get_top_layers(3)),
            })

        return {
            "provider": "phoneme",
            "phrase": analysis.phrase,
            "prediction": analysis.prediction,
            "overall_harmony": analysis.overall_harmony,
            "overall_dissonance": analysis.overall_dissonance,
            "word_count": len(analysis.words),
            "words": word_traces,
            "key_resonances": [
                {
                    "word_a": r.word_a,
                    "word_b": r.word_b,
                    "similarity": r.similarity,
                    "harmonic": r.harmonic,
                }
                for r in analysis.key_resonances
            ],
        }
