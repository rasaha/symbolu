"""
Semantic Router
===============

Routes queries to specialized sub-models based on phoneme signature.

Key Insight:
    Different ontological layers suggest different processing needs:
    - O9_UNIFYING dominant → relationship/connection queries
    - O6_REASONING dominant → logical/analytical queries
    - O3_ACTING dominant → action/procedural queries

Instead of one giant model, route to smaller specialized models.

Computational Savings:
    - General model: 175B parameters
    - Specialized models: 7B parameters each
    - 25x parameter reduction for most queries
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Callable, Any
from enum import Enum

from symbolu.resonance import (
    analyze_phrase,
    analyze_word,
    PhraseAnalysis,
    WordVector,
    LAYER_NAMES,
)


class ModelType(Enum):
    """Types of specialized models."""
    GENERAL = "general"           # Fallback for mixed/unclear
    RELATIONSHIP = "relationship"  # O9_UNIFYING - connections, love, unity
    REASONING = "reasoning"        # O6_REASONING - logic, analysis
    ACTION = "action"             # O3_ACTING - procedures, commands
    CREATIVE = "creative"         # O2_FORMING - creation, art, structure
    REFLECTIVE = "reflective"     # O1_THINKING - contemplation, philosophy
    DIRECTIVE = "directive"       # O5_DIRECTING - guidance, commands
    TRANSCENDENT = "transcendent" # O10_ABSOLVING - abstract, spiritual


@dataclass(frozen=True)
class RoutingDecision:
    """Result of routing decision."""
    model_type: ModelType
    confidence: float  # 0.0 to 1.0
    dominant_layer: str
    layer_scores: Tuple[Tuple[str, float], ...]  # Top layers
    query_analysis: PhraseAnalysis


# Layer → Model mapping
LAYER_TO_MODEL: Dict[str, ModelType] = {
    "O1_THINKING": ModelType.REFLECTIVE,
    "O2_FORMING": ModelType.CREATIVE,
    "O3_ACTING": ModelType.ACTION,
    "O4_TAGGING": ModelType.GENERAL,  # Classification → general
    "O5_DIRECTING": ModelType.DIRECTIVE,
    "O6_REASONING": ModelType.REASONING,
    "O7_PURPOSING": ModelType.DIRECTIVE,
    "O8_META_OBSERVING": ModelType.REFLECTIVE,
    "O9_UNIFYING": ModelType.RELATIONSHIP,
    "O10_ABSOLVING": ModelType.TRANSCENDENT,
}


class SemanticRouter:
    """
    Routes queries to specialized models based on phoneme signature.

    Usage:
        router = SemanticRouter()
        decision = router.route("Love conquers all")
        # decision.model_type = ModelType.RELATIONSHIP
        # decision.confidence = 0.85

        # Now dispatch to appropriate model
        if decision.model_type == ModelType.RELATIONSHIP:
            result = relationship_model(query)
        elif decision.model_type == ModelType.REASONING:
            result = reasoning_model(query)
        ...
    """

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        fallback_model: ModelType = ModelType.GENERAL,
    ):
        """
        Initialize router.

        Args:
            confidence_threshold: Minimum dominant layer score to route
            fallback_model: Model to use when confidence is low
        """
        self.confidence_threshold = confidence_threshold
        self.fallback_model = fallback_model

    def route(self, query: str) -> RoutingDecision:
        """
        Route a query to the appropriate model.

        Args:
            query: The input query/prompt

        Returns:
            RoutingDecision with model type and confidence
        """
        # Analyze the query
        analysis = analyze_phrase(query)

        if not analysis.words:
            # Empty or all stop words
            return RoutingDecision(
                model_type=self.fallback_model,
                confidence=0.0,
                dominant_layer=LAYER_NAMES[0],
                layer_scores=(),
                query_analysis=analysis,
            )

        # Aggregate layer scores across content words
        layer_totals = [0.0] * 10
        for word_vec in analysis.words:
            for i, score in enumerate(word_vec.vector):
                layer_totals[i] += score

        # Find dominant layer using raw totals (not normalized)
        max_idx = 0
        max_total = layer_totals[0]
        for i in range(1, 10):
            if layer_totals[i] > max_total:
                max_total = layer_totals[i]
                max_idx = i

        dominant_layer = LAYER_NAMES[max_idx]

        # Calculate confidence using the best word-level dominant score
        # This preserves the differentiation seen at word level
        max_word_score = 0.0
        for word_vec in analysis.words:
            if word_vec.dominant_score > max_word_score:
                max_word_score = word_vec.dominant_score

        # Normalize for layer_scores display (but not for routing decision)
        total = sum(layer_totals)
        if total > 0:
            normalized = [s / total for s in layer_totals]
        else:
            normalized = layer_totals

        # Get top 3 layers for context
        indexed = [(LAYER_NAMES[i], normalized[i]) for i in range(10)]
        sorted_layers = sorted(indexed, key=lambda x: x[1], reverse=True)
        top_layers = tuple(sorted_layers[:3])

        # Determine model using word-level confidence
        if max_word_score < self.confidence_threshold:
            model_type = self.fallback_model
            confidence = max_word_score
        else:
            model_type = LAYER_TO_MODEL.get(dominant_layer, self.fallback_model)
            confidence = max_word_score

        return RoutingDecision(
            model_type=model_type,
            confidence=confidence,
            dominant_layer=dominant_layer,
            layer_scores=top_layers,
            query_analysis=analysis,
        )

    def route_batch(
        self,
        queries: Tuple[str, ...],
    ) -> Tuple[RoutingDecision, ...]:
        """Route multiple queries."""
        return tuple(self.route(q) for q in queries)

    def estimate_savings(
        self,
        queries: Tuple[str, ...],
        general_model_params: int = 175_000_000_000,  # 175B
        specialized_model_params: int = 7_000_000_000,  # 7B
    ) -> dict:
        """
        Estimate parameter savings from routing.

        Args:
            queries: Sample queries to analyze
            general_model_params: Parameters in general model
            specialized_model_params: Parameters in specialized models

        Returns:
            Dict with savings estimates
        """
        decisions = self.route_batch(queries)

        general_count = sum(1 for d in decisions if d.model_type == ModelType.GENERAL)
        specialized_count = len(decisions) - general_count

        # Without routing: all queries use general model
        without_routing = len(queries) * general_model_params

        # With routing: some use specialized
        with_routing = (
            general_count * general_model_params +
            specialized_count * specialized_model_params
        )

        return {
            "queries_to_general": general_count,
            "queries_to_specialized": specialized_count,
            "percent_specialized": specialized_count / len(queries) * 100 if queries else 0,
            "params_without_routing": without_routing,
            "params_with_routing": with_routing,
            "param_reduction_factor": without_routing / with_routing if with_routing > 0 else 0,
        }


class ModelRegistry:
    """
    Registry of specialized models for the router.

    Register actual model handlers and let the router dispatch to them.
    """

    def __init__(self):
        self._models: Dict[ModelType, Callable] = {}
        self._router = SemanticRouter()

    def register(self, model_type: ModelType, handler: Callable):
        """Register a model handler."""
        self._models[model_type] = handler

    def invoke(self, query: str) -> Any:
        """
        Route and invoke the appropriate model.

        Args:
            query: Input query

        Returns:
            Result from the selected model
        """
        decision = self._router.route(query)
        handler = self._models.get(decision.model_type)

        if handler is None:
            # Fallback to general if no handler registered
            handler = self._models.get(ModelType.GENERAL)

        if handler is None:
            raise RuntimeError(f"No handler for {decision.model_type}")

        return handler(query, decision)


# Example specialized model stubs
def relationship_model_stub(query: str, decision: RoutingDecision) -> str:
    """Stub for relationship-focused model."""
    return f"[RELATIONSHIP MODEL] Processing: {query}"


def reasoning_model_stub(query: str, decision: RoutingDecision) -> str:
    """Stub for reasoning-focused model."""
    return f"[REASONING MODEL] Processing: {query}"


def action_model_stub(query: str, decision: RoutingDecision) -> str:
    """Stub for action-focused model."""
    return f"[ACTION MODEL] Processing: {query}"


def create_demo_registry() -> ModelRegistry:
    """Create a demo registry with stub handlers."""
    registry = ModelRegistry()
    registry.register(ModelType.RELATIONSHIP, relationship_model_stub)
    registry.register(ModelType.REASONING, reasoning_model_stub)
    registry.register(ModelType.ACTION, action_model_stub)
    registry.register(ModelType.GENERAL, lambda q, d: f"[GENERAL MODEL] {q}")
    return registry
