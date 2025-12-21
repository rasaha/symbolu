"""
Enterprise Chat Engine (Tier 2)
===============================

STL routes to specialized 7B models for generation.
25x parameter savings compared to using 175B for everything.

Use cases:
    - Specialized chat with domain expertise
    - Cost-optimized text generation
    - Explainable routing decisions

Architecture:
    Query → STL (10D) → Route Decision → 7B Specialist → Response

Performance:
    - Routing: ~100μs
    - Generation: ~500ms (depends on 7B model)
    - Cost: 25x lower than 175B
    - Accuracy: 90% routing accuracy
"""

import time
from typing import Optional, Tuple, Dict, Any, Callable, Protocol
from abc import abstractmethod

from symbolu.engine.base import BaseEngine, EngineResult, EngineCapability
from symbolu.hybrid.router import SemanticRouter, ModelType, RoutingDecision
from symbolu.hybrid.vocabulary import CustomVocabulary


class ModelHandler(Protocol):
    """Protocol for model handlers."""

    @abstractmethod
    def generate(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a response."""
        ...


class StubModelHandler:
    """
    Stub model handler for testing/demo.

    Replace with actual model implementations.
    """

    def __init__(self, model_name: str):
        self.model_name = model_name

    def generate(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a stub response."""
        return f"[{self.model_name}] Response to: {query}"


class EnterpriseChatEngine(BaseEngine):
    """
    Enterprise Tier 2: STL routes to specialized 7B models.

    Example:
        # With stub handlers (for testing)
        engine = EnterpriseChatEngine()

        # With real model handlers
        engine = EnterpriseChatEngine(
            model_handlers={
                ModelType.REASONING: ReasoningModel(),
                ModelType.CREATIVE: CreativeModel(),
                ModelType.ACTION: ActionModel(),
            }
        )

        result = engine.generate("Explain quantum physics")
        print(result.response)     # Generated text
        print(result.model_used)   # "reasoning-7b"
        print(result.stl_signal)   # Routing details
    """

    # Default model names for each type
    DEFAULT_MODEL_NAMES: Dict[ModelType, str] = {
        ModelType.REASONING: "reasoning-7b",
        ModelType.CREATIVE: "creative-7b",
        ModelType.ACTION: "action-7b",
        ModelType.RELATIONSHIP: "relationship-7b",
        ModelType.REFLECTIVE: "reflective-7b",
        ModelType.DIRECTIVE: "directive-7b",
        ModelType.TRANSCENDENT: "transcendent-7b",
        ModelType.GENERAL: "general-7b",
    }

    def __init__(
        self,
        vocabulary: Optional[CustomVocabulary] = None,
        confidence_threshold: float = 0.3,
        model_handlers: Optional[Dict[ModelType, ModelHandler]] = None,
        model_names: Optional[Dict[ModelType, str]] = None,
    ):
        """
        Initialize Enterprise Chat Engine.

        Args:
            vocabulary: Optional custom vocabulary for domain terms
            confidence_threshold: Minimum confidence for routing
            model_handlers: Map of ModelType to handler implementations
            model_names: Custom model names (for logging/tracking)
        """
        self.router = SemanticRouter(
            vocabulary=vocabulary,
            confidence_threshold=confidence_threshold,
        )
        self.vocabulary = vocabulary

        # Set up model names
        self.model_names = model_names or self.DEFAULT_MODEL_NAMES.copy()

        # Set up model handlers (stubs if not provided)
        if model_handlers:
            self.model_handlers = model_handlers
        else:
            # Create stub handlers for all model types
            self.model_handlers = {
                model_type: StubModelHandler(name)
                for model_type, name in self.model_names.items()
            }

    @property
    def tier_name(self) -> str:
        return "enterprise_chat"

    @property
    def capabilities(self) -> Tuple[EngineCapability, ...]:
        return (EngineCapability.CLASSIFY, EngineCapability.GENERATE)

    def classify(self, query: str) -> EngineResult:
        """
        Classify intent using STL.

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
            model_used=self.model_names.get(decision.model_type, "unknown"),
            stl_signal={
                "dominant_layer": decision.dominant_layer,
                "layer_scores": list(decision.layer_scores),
                "harmony": decision.query_analysis.overall_harmony,
            },
            latency_ms=elapsed_ms,
        )

    def generate(self, query: str, context: Optional[Dict[str, Any]] = None) -> EngineResult:
        """
        Generate response using STL-routed 7B model.

        Args:
            query: Input query/prompt
            context: Optional context for generation

        Returns:
            EngineResult with generated response
        """
        start = time.perf_counter()

        # Step 1: Route using STL
        decision = self.router.route(query)
        routing_time = time.perf_counter() - start

        # Step 2: Get appropriate model handler
        handler = self.model_handlers.get(decision.model_type)
        if handler is None:
            # Fall back to general
            handler = self.model_handlers.get(ModelType.GENERAL)

        if handler is None:
            return EngineResult(
                success=False,
                tier_used=self.tier_name,
                metadata={"error": f"No handler for {decision.model_type.value}"},
            )

        # Step 3: Generate response
        gen_start = time.perf_counter()

        generation_context = {
            "intent": decision.model_type.value,
            "confidence": decision.confidence,
            "dominant_layer": decision.dominant_layer,
            **(context or {}),
        }

        response = handler.generate(query, generation_context)

        gen_time = time.perf_counter() - gen_start
        total_time = (time.perf_counter() - start) * 1000

        return EngineResult(
            success=True,
            intent=decision.model_type.value,
            confidence=decision.confidence,
            response=response,
            tier_used=self.tier_name,
            model_used=self.model_names.get(decision.model_type, "unknown"),
            stl_signal={
                "dominant_layer": decision.dominant_layer,
                "layer_scores": list(decision.layer_scores),
                "harmony": decision.query_analysis.overall_harmony,
                "routing_time_ms": routing_time * 1000,
            },
            latency_ms=total_time,
            metadata={
                "generation_time_ms": gen_time * 1000,
            },
        )

    def register_handler(self, model_type: ModelType, handler: ModelHandler) -> None:
        """
        Register a model handler for a specific intent type.

        Args:
            model_type: The model type to handle
            handler: The handler implementation
        """
        self.model_handlers[model_type] = handler

    def get_routing_stats(self, queries: list) -> Dict[str, Any]:
        """
        Get routing statistics for a batch of queries.

        Args:
            queries: List of queries to analyze

        Returns:
            Dict with routing statistics
        """
        stats: Dict[str, int] = {}

        for query in queries:
            decision = self.router.route(query)
            model_name = decision.model_type.value
            stats[model_name] = stats.get(model_name, 0) + 1

        total = len(queries)
        return {
            "total_queries": total,
            "distribution": stats,
            "percentages": {k: v / total * 100 for k, v in stats.items()},
            "models_used": list(stats.keys()),
        }
