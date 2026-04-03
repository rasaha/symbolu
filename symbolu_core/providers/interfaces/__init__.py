"""
Provider Interfaces
====================

Abstract base classes for pluggable embedding, routing, filtering, and
matching providers. These interfaces enable the Single Codebase + Pluggable
Providers architecture, allowing Symbol-U to support both Enterprise (symbolic)
and Consumer (pre-trained) modes via a unified orchestrator.
"""

from symbolu_core.providers.interfaces.embedding_provider import EmbeddingProvider
from symbolu_core.providers.interfaces.router_provider import (
    RouterProvider,
    RoutingDecision,
    ModelType,
)
from symbolu_core.providers.interfaces.filter_provider import (
    FilterProvider,
    FilterResult,
)
from symbolu_core.providers.interfaces.match_provider import (
    MatchProvider,
    MatchResult,
    BatchMatchResult,
    MatchMode,
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
    # Match (Canonical C × R × S)
    "MatchProvider",
    "MatchResult",
    "BatchMatchResult",
    "MatchMode",
]
