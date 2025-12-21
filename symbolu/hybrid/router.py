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
from typing import Tuple, Optional, Dict, Callable, Any, Set
from enum import Enum
import re

from symbolu.resonance import (
    analyze_phrase,
    analyze_word,
    PhraseAnalysis,
    WordVector,
    LAYER_NAMES,
)


# Intent keyword patterns for boosting
# These augment phoneme analysis with common linguistic patterns

ACTION_PATTERNS: Set[str] = {
    "run", "execute", "start", "stop", "deploy", "install", "send", "book",
    "schedule", "create", "delete", "build", "test", "compile", "launch",
    "restart", "shutdown", "upload", "download", "push", "pull", "commit",
}

REASONING_PATTERNS: Set[str] = {
    "how", "why", "what", "explain", "analyze", "calculate", "compute",
    "derive", "prove", "solve", "understand", "theory", "logic", "reason",
    "cause", "effect", "because", "therefore", "hypothesis", "theorem",
}

RELATIONSHIP_PATTERNS: Set[str] = {
    "feel", "feeling", "emotion", "sad", "happy", "anxious", "worried",
    "lonely", "love", "hate", "friend", "family", "relationship", "hurt",
    "heart", "care", "connect", "bond", "trust", "empathy", "compassion",
}

CREATIVE_PATTERNS: Set[str] = {
    "write", "compose", "design", "create", "imagine", "paint", "draw",
    "poem", "story", "song", "art", "music", "illustration", "sketch",
    "novel", "lyrics", "melody", "artistic", "creative", "invent",
}

REFLECTIVE_PATTERNS: Set[str] = {
    "meaning", "life", "exist", "existence", "consciousness", "free",
    "will", "death", "truth", "reality", "nature", "being", "soul",
    "spirit", "philosophy", "metaphysics", "purpose", "destiny", "fate",
}


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

    # Pattern sets mapped to model types
    PATTERN_TO_MODEL: Dict[ModelType, Set[str]] = {
        ModelType.ACTION: ACTION_PATTERNS,
        ModelType.REASONING: REASONING_PATTERNS,
        ModelType.RELATIONSHIP: RELATIONSHIP_PATTERNS,
        ModelType.CREATIVE: CREATIVE_PATTERNS,
        ModelType.REFLECTIVE: REFLECTIVE_PATTERNS,
    }

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        fallback_model: ModelType = ModelType.GENERAL,
        pattern_boost: float = 0.3,
    ):
        """
        Initialize router.

        Args:
            confidence_threshold: Minimum dominant layer score to route
            fallback_model: Model to use when confidence is low
            pattern_boost: Amount to boost confidence when keyword patterns match
        """
        self.confidence_threshold = confidence_threshold
        self.fallback_model = fallback_model
        self.pattern_boost = pattern_boost

    def _detect_intent_patterns(self, query: str) -> Dict[ModelType, float]:
        """
        Detect intent patterns in the query using keyword matching.

        Args:
            query: The input query

        Returns:
            Dict mapping ModelType to match score (0.0 to 1.0)
        """
        # Tokenize query into lowercase words
        words = set(re.findall(r'\b[a-z]+\b', query.lower()))

        scores: Dict[ModelType, float] = {}

        for model_type, patterns in self.PATTERN_TO_MODEL.items():
            matches = words & patterns
            if matches:
                # Score based on number of matches and their position
                # First word matching gets extra weight (imperative detection)
                first_word = query.lower().split()[0] if query.strip() else ""
                first_word_match = first_word in patterns

                base_score = len(matches) / max(len(words), 1)
                if first_word_match:
                    base_score += 0.3  # Boost for imperative commands

                scores[model_type] = min(base_score, 1.0)

        return scores

    def route(self, query: str) -> RoutingDecision:
        """
        Route a query to the appropriate model.

        Combines phoneme layer analysis with keyword pattern detection
        for improved accuracy.

        Args:
            query: The input query/prompt

        Returns:
            RoutingDecision with model type and confidence
        """
        # Analyze the query using phoneme analysis
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
        max_word_score = 0.0
        for word_vec in analysis.words:
            if word_vec.dominant_score > max_word_score:
                max_word_score = word_vec.dominant_score

        # Normalize for layer_scores display
        total = sum(layer_totals)
        if total > 0:
            normalized = [s / total for s in layer_totals]
        else:
            normalized = layer_totals

        # Get top 3 layers for context
        indexed = [(LAYER_NAMES[i], normalized[i]) for i in range(10)]
        sorted_layers = sorted(indexed, key=lambda x: x[1], reverse=True)
        top_layers = tuple(sorted_layers[:3])

        # Detect intent patterns from keywords
        pattern_scores = self._detect_intent_patterns(query)

        # Determine model type by combining phoneme analysis with pattern matching
        phoneme_model = LAYER_TO_MODEL.get(dominant_layer, self.fallback_model)

        # If pattern detection has a strong signal, use it to override or confirm
        if pattern_scores:
            # Get the best pattern match
            best_pattern_model = max(pattern_scores, key=pattern_scores.get)
            best_pattern_score = pattern_scores[best_pattern_model]

            # Strong pattern match overrides phoneme if phoneme confidence is weak
            if best_pattern_score >= 0.2:
                # Pattern is strong enough to consider
                if max_word_score < self.confidence_threshold:
                    # Low phoneme confidence - trust pattern
                    model_type = best_pattern_model
                    confidence = min(max_word_score + best_pattern_score * self.pattern_boost, 1.0)
                elif best_pattern_model == phoneme_model:
                    # Pattern confirms phoneme - boost confidence
                    model_type = phoneme_model
                    confidence = min(max_word_score + best_pattern_score * self.pattern_boost, 1.0)
                else:
                    # Pattern and phoneme disagree - use pattern if score is high
                    if best_pattern_score >= 0.4:
                        model_type = best_pattern_model
                        confidence = min(max_word_score + best_pattern_score * self.pattern_boost, 1.0)
                    else:
                        # Stick with phoneme but note conflict
                        model_type = phoneme_model
                        confidence = max_word_score
            else:
                # Pattern too weak - use phoneme
                model_type = phoneme_model if max_word_score >= self.confidence_threshold else self.fallback_model
                confidence = max_word_score
        else:
            # No pattern matches - use pure phoneme analysis
            if max_word_score < self.confidence_threshold:
                model_type = self.fallback_model
                confidence = max_word_score
            else:
                model_type = phoneme_model
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
