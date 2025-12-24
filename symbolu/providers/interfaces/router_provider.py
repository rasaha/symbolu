"""
Router Provider Interface
=========================

Abstract interface for query routing.
Enterprise mode uses phoneme-based symbolic routing.
Consumer mode uses trained classifier routing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Dict, Any


class ModelType(Enum):
    """
    Types of specialized models for query routing.

    Each type corresponds to a different processing approach
    based on the nature of the query.
    """
    GENERAL = "general"            # Fallback for mixed/unclear queries
    REASONING = "reasoning"        # O6_REASONING - logic, analysis
    RELATIONSHIP = "relationship"  # O9_UNIFYING - connections, love, unity
    ACTION = "action"              # O3_ACTING - procedures, commands
    CREATIVE = "creative"          # O2_FORMING - creation, art, structure
    REFLECTIVE = "reflective"      # O1_THINKING - contemplation, philosophy
    DIRECTIVE = "directive"        # O5_DIRECTING - guidance, commands
    TRANSCENDENT = "transcendent"  # O10_ABSOLVING - abstract, spiritual


@dataclass(frozen=True)
class RoutingDecision:
    """
    Result of a routing decision.

    This is the standardized output from all router providers.
    The governance layer receives this regardless of which provider
    (enterprise or consumer) produced it.

    Attributes:
        model_type: The type of specialized model to route to
        confidence: Confidence score for the routing decision (0.0 to 1.0)
        dominant_layer: The dominant ontological layer (e.g., "O7_REASONING")
        layer_scores: Top layers with their scores
        trace: Implementation-specific trace info for debugging/auditing
    """
    model_type: ModelType
    confidence: float
    dominant_layer: str
    layer_scores: Tuple[Tuple[str, float], ...]
    trace: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model_type": self.model_type.value,
            "confidence": self.confidence,
            "dominant_layer": self.dominant_layer,
            "layer_scores": list(self.layer_scores),
            "trace": self.trace,
        }


class RouterProvider(ABC):
    """
    Abstract interface for query routing.

    Router providers analyze input queries and determine the appropriate
    model type for processing. Enterprise providers use symbolic analysis
    (phonemes), while consumer providers use trained classifiers.
    """

    @abstractmethod
    def route(self, query: str) -> RoutingDecision:
        """
        Route a query to the appropriate model type.

        Args:
            query: The input query/prompt

        Returns:
            RoutingDecision with model type and confidence
        """
        pass

    @abstractmethod
    def route_batch(self, queries: List[str]) -> List[RoutingDecision]:
        """
        Batch route multiple queries.

        Args:
            queries: List of input queries

        Returns:
            List of RoutingDecision objects (one per query)
        """
        pass

    def get_supported_model_types(self) -> List[ModelType]:
        """
        Return the list of model types this router can route to.

        Default implementation returns all model types.
        Providers may override to restrict supported types.
        """
        return list(ModelType)
