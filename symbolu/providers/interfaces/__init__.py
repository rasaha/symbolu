"""
Provider Interfaces
====================

Abstract base classes for pluggable embedding, routing, and filtering providers.
These interfaces enable the Single Codebase + Pluggable Providers architecture,
allowing Symbol-U to support both Enterprise (symbolic) and Consumer (pre-trained)
modes via a unified orchestrator.
"""

from symbolu.providers.interfaces.embedding_provider import EmbeddingProvider
from symbolu.providers.interfaces.router_provider import (
    RouterProvider,
    RoutingDecision,
    ModelType,
)
from symbolu.providers.interfaces.filter_provider import (
    FilterProvider,
    FilterResult,
)

__all__ = [
    # Embedding
    "EmbeddingProvider",
    # Router
    "RouterProvider",
    "RoutingDecision",
    "ModelType",
    # Filter
    "FilterProvider",
    "FilterResult",
]
