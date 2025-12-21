"""
Symbol-U Providers
==================

Pluggable provider architecture for Symbol-U.
Supports both Enterprise (symbolic) and Consumer (pre-trained) modes.

Usage:
    from symbolu.providers import (
        get_embedding_provider,
        get_router_provider,
        get_filter_provider,
    )

    # Get enterprise providers (symbolic)
    embedding = get_embedding_provider("enterprise")
    router = get_router_provider("enterprise")
    filter = get_filter_provider("enterprise")

    # Get consumer providers (pre-trained)
    embedding = get_embedding_provider("consumer")
    router = get_router_provider("consumer")
    filter = get_filter_provider("consumer")
"""

from typing import Literal, Optional, Dict, Any

from symbolu.providers.interfaces import (
    EmbeddingProvider,
    RouterProvider,
    FilterProvider,
    RoutingDecision,
    FilterResult,
    ModelType,
)

__all__ = [
    # Provider factory functions
    "get_embedding_provider",
    "get_router_provider",
    "get_filter_provider",
    # Interfaces
    "EmbeddingProvider",
    "RouterProvider",
    "FilterProvider",
    # Data types
    "RoutingDecision",
    "FilterResult",
    "ModelType",
]


def get_embedding_provider(
    mode: Literal["enterprise", "consumer"],
    config: Optional[Dict[str, Any]] = None,
) -> EmbeddingProvider:
    """
    Get an embedding provider for the specified mode.

    Args:
        mode: Provider mode - "enterprise" or "consumer"
        config: Optional provider-specific configuration
            For consumer mode:
                - model_path: Path to trained embedding model

    Returns:
        EmbeddingProvider instance for the mode

    Examples:
        >>> provider = get_embedding_provider("enterprise")
        >>> vec = provider.embed("hello world")
        >>> len(vec)
        256

        >>> provider = get_embedding_provider("consumer")
        >>> vec = provider.embed("hello world")
        >>> len(vec)
        768

        >>> provider = get_embedding_provider("consumer", {"model_path": "model.json"})
        >>> provider.is_model_loaded()
        True
    """
    config = config or {}

    if mode == "enterprise":
        from symbolu.providers.enterprise.hash_embedding import HashEmbeddingProvider
        return HashEmbeddingProvider()
    elif mode == "consumer":
        from symbolu.providers.consumer.learned_embedding import (
            LearnedEmbeddingProvider,
        )
        model_path = config.get("model_path")
        return LearnedEmbeddingProvider(model_path=model_path)
    else:
        raise ValueError(f"Invalid mode: {mode}. Must be 'enterprise' or 'consumer'")


def get_router_provider(
    mode: Literal["enterprise", "consumer"],
    config: Optional[Dict[str, Any]] = None,
    embedding_provider: Optional[EmbeddingProvider] = None,
) -> RouterProvider:
    """
    Get a router provider for the specified mode.

    Args:
        mode: Provider mode - "enterprise" or "consumer"
        config: Optional provider-specific configuration
            For enterprise mode:
                - confidence_threshold: Routing confidence threshold
            For consumer mode:
                - model_path: Path to trained router model
        embedding_provider: Optional embedding provider (for consumer mode)

    Returns:
        RouterProvider instance for the mode

    Examples:
        >>> provider = get_router_provider("enterprise")
        >>> decision = provider.route("How do atoms bond?")
        >>> decision.model_type
        ModelType.LOGIC

        >>> provider = get_router_provider("consumer")
        >>> decision = provider.route("How do atoms bond?")
        >>> decision.model_type
        ModelType.GENERAL  # Fallback when no model loaded

        >>> provider = get_router_provider("consumer", {"model_path": "router.json"})
        >>> provider.is_model_loaded()
        True
    """
    config = config or {}

    if mode == "enterprise":
        from symbolu.providers.enterprise.phoneme_router import PhonemeRouterProvider
        return PhonemeRouterProvider(
            confidence_threshold=config.get("confidence_threshold", 0.3),
        )
    elif mode == "consumer":
        from symbolu.providers.consumer.trained_router import TrainedRouterProvider
        from symbolu.providers.consumer.learned_embedding import LearnedEmbeddingProvider
        model_path = config.get("model_path")
        # Use provided embedder or create default
        embedder = embedding_provider if isinstance(embedding_provider, LearnedEmbeddingProvider) else None
        return TrainedRouterProvider(model_path=model_path, embedder=embedder)
    else:
        raise ValueError(f"Invalid mode: {mode}. Must be 'enterprise' or 'consumer'")


def get_filter_provider(
    mode: Literal["enterprise", "consumer"],
    config: Optional[Dict[str, Any]] = None,
) -> FilterProvider:
    """
    Get a filter provider for the specified mode.

    Args:
        mode: Provider mode - "enterprise" or "consumer"
        config: Optional provider-specific configuration

    Returns:
        FilterProvider instance for the mode

    Examples:
        >>> provider = get_filter_provider("enterprise")
        >>> result = provider.filter(("apple", "banana", "atom"), "chemistry")
        >>> result.filtered_texts
        ('atom',)

        >>> provider = get_filter_provider("consumer")
        >>> result = provider.filter(("apple", "banana", "atom"), "chemistry")
        >>> len(result.filtered_texts) <= 10
        True
    """
    config = config or {}

    if mode == "enterprise":
        from symbolu.providers.enterprise.resonance_filter import (
            ResonanceFilterProvider,
        )
        return ResonanceFilterProvider(
            threshold=config.get("threshold", 0.5),
        )
    elif mode == "consumer":
        from symbolu.providers.consumer.attention_filter import AttentionFilterProvider
        return AttentionFilterProvider()
    else:
        raise ValueError(f"Invalid mode: {mode}. Must be 'enterprise' or 'consumer'")
