"""
Base Engine Classes
===================

Abstract base classes for all engine tiers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum


class EngineCapability(Enum):
    """Capabilities an engine can have."""
    CLASSIFY = "classify"       # Intent classification
    SEARCH = "search"           # Document retrieval
    GENERATE = "generate"       # Text generation
    EMBED = "embed"             # Embedding generation


@dataclass
class EngineResult:
    """
    Unified result from any engine operation.

    Attributes:
        success: Whether the operation succeeded
        intent: Classified intent (if applicable)
        confidence: Confidence score (0.0 to 1.0)
        response: Generated text response (if applicable)
        model_used: Which model handled the request
        tier_used: Which tier processed the request
        stl_signal: STL analysis details
        semantic_signal: 768D embedding details (if used)
        latency_ms: Processing time in milliseconds
        metadata: Additional operation-specific data
    """
    success: bool = True
    intent: Optional[str] = None
    confidence: float = 0.0
    response: Optional[str] = None
    model_used: Optional[str] = None
    tier_used: Optional[str] = None
    stl_signal: Optional[Dict[str, Any]] = None
    semantic_signal: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "intent": self.intent,
            "confidence": self.confidence,
            "response": self.response,
            "model_used": self.model_used,
            "tier_used": self.tier_used,
            "stl_signal": self.stl_signal,
            "semantic_signal": self.semantic_signal,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }


class BaseEngine(ABC):
    """
    Abstract base class for all engine tiers.

    All engines must implement:
    - classify(): Intent classification
    - capabilities: List of supported operations
    """

    @property
    @abstractmethod
    def tier_name(self) -> str:
        """Return the tier name."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> Tuple[EngineCapability, ...]:
        """Return supported capabilities."""
        pass

    @abstractmethod
    def classify(self, query: str) -> EngineResult:
        """
        Classify the intent of a query.

        All tiers support this operation.

        Args:
            query: Input text to classify

        Returns:
            EngineResult with intent and confidence
        """
        pass

    def generate(self, query: str) -> EngineResult:
        """
        Generate a response to a query.

        Not all tiers support this. Override in subclasses that do.

        Args:
            query: Input query/prompt

        Returns:
            EngineResult with generated response
        """
        return EngineResult(
            success=False,
            response=None,
            tier_used=self.tier_name,
            metadata={"error": f"Generation not supported by {self.tier_name}"},
        )

    def search(self, query: str, candidates: List[str]) -> EngineResult:
        """
        Search/rank candidates by relevance to query.

        Args:
            query: Search query
            candidates: List of candidate documents/items

        Returns:
            EngineResult with ranked candidates in metadata
        """
        return EngineResult(
            success=False,
            tier_used=self.tier_name,
            metadata={"error": f"Search not supported by {self.tier_name}"},
        )

    def has_capability(self, cap: EngineCapability) -> bool:
        """Check if engine has a capability."""
        return cap in self.capabilities
