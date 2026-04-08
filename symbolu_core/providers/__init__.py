"""
Symbol-U Providers
==================

Pluggable provider architecture for Symbol-U.
Supports both Enterprise (symbolic) and Consumer (pre-trained) modes.

Usage:
    from symbolu_core.providers import (
        get_embedding_provider,
        get_router_provider,
        get_filter_provider,
        get_match_provider,
    )

    # Get enterprise providers (symbolic)
    embedding = get_embedding_provider("enterprise")
    router = get_router_provider("enterprise")
    filter = get_filter_provider("enterprise")
    match = get_match_provider("enterprise")

    # Get consumer providers (pre-trained)
    embedding = get_embedding_provider("consumer")
    router = get_router_provider("consumer")
    filter = get_filter_provider("consumer")

    # Canonical matching (C × R × S framework)
    match = get_match_provider("enterprise")
    result = match.match("king", "queen")
    print(f"Match score: {result.match_score}")

    # Coherence-enhanced filtering
    filter = get_filter_provider("enterprise", {"with_coherence": True})
    result = filter.filter(candidates, query)
    print(result.stats["coherence_checks"])
"""

from typing import Literal, Optional, Dict, Any

from symbolu_core.providers.interfaces import (
    EmbeddingProvider,
    RouterProvider,
    FilterProvider,
    RoutingDecision,
    FilterResult,
    ModelType,
    MatchProvider,
    MatchResult,
    BatchMatchResult,
    MatchMode,
)

__all__ = [
    # Provider factory functions
    "get_embedding_provider",
    "get_router_provider",
    "get_filter_provider",
    "get_match_provider",
    # Interfaces
    "EmbeddingProvider",
    "RouterProvider",
    "FilterProvider",
    "MatchProvider",
    # Data types
    "RoutingDecision",
    "FilterResult",
    "ModelType",
    "MatchResult",
    "BatchMatchResult",
    "MatchMode",
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
        from symbolu_core.providers.enterprise.hash_embedding import HashEmbeddingProvider
        return HashEmbeddingProvider()
    elif mode == "consumer":
        from symbolu_core.providers.consumer.learned_embedding import (
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
        from symbolu_core.providers.enterprise.phoneme_router import PhonemeRouterProvider
        return PhonemeRouterProvider(
            confidence_threshold=config.get("confidence_threshold", 0.3),
        )
    elif mode == "consumer":
        from symbolu_core.providers.consumer.trained_router import TrainedRouterProvider
        from symbolu_core.providers.consumer.learned_embedding import LearnedEmbeddingProvider
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
            For enterprise mode:
                - threshold: Minimum phoneme similarity to pass (default 0.5)
                - with_coherence: If True, use CoherenceFilterProvider with
                  C × R × S diagnostics (default False)
                - compute_pairwise: If True, compute pairwise coherence (default True)
                - max_pairwise_checks: Max pairwise checks (default 20)

    Returns:
        FilterProvider instance for the mode

    Examples:
        >>> provider = get_filter_provider("enterprise")
        >>> result = provider.filter(("apple", "banana", "atom"), "chemistry")
        >>> result.filtered_texts
        ('atom',)

        >>> provider = get_filter_provider("enterprise", {"with_coherence": True})
        >>> result = provider.filter(("sun", "light", "table"), "energy")
        >>> "coherence_checks" in result.stats
        True

        >>> provider = get_filter_provider("consumer")
        >>> result = provider.filter(("apple", "banana", "atom"), "chemistry")
        >>> len(result.filtered_texts) <= 10
        True
    """
    config = config or {}

    if mode == "enterprise":
        # Check if coherence-enhanced filtering is requested
        if config.get("with_coherence", False):
            from symbolu_core.providers.enterprise.coherence_filter import (
                CoherenceFilterProvider,
            )
            return CoherenceFilterProvider(
                threshold=config.get("threshold", 0.5),
                compute_pairwise=config.get("compute_pairwise", True),
                max_pairwise_checks=config.get("max_pairwise_checks", 20),
            )
        else:
            from symbolu_core.providers.enterprise.resonance_filter import (
                ResonanceFilterProvider,
            )
            return ResonanceFilterProvider(
                threshold=config.get("threshold", 0.5),
            )
    elif mode == "consumer":
        from symbolu_core.providers.consumer.attention_filter import AttentionFilterProvider
        return AttentionFilterProvider()
    else:
        raise ValueError(f"Invalid mode: {mode}. Must be 'enterprise' or 'consumer'")


def get_match_provider(
    mode: Literal["enterprise"],
    config: Optional[Dict[str, Any]] = None,
) -> MatchProvider:
    """
    Get a match provider for canonical matching (C × R × S framework).

    The canonical matching formula: MATCH = C × R × S

    Where:
    - C = Constraint feasibility (phonemic → ontology)
    - R = Realization strength (phonemic → experience)
    - S = Referential coherence (NON-phonemic, source-independent)

    Args:
        mode: Provider mode - currently only "enterprise" is supported
        config: Optional provider-specific configuration
            - c_threshold: Threshold for "high" constraint score (default 0.6)
            - r_threshold: Threshold for "high" realization score (default 0.5)
            - s_threshold: Threshold for referent coherence (default 0.2)

    Returns:
        MatchProvider instance

    Examples:
        >>> provider = get_match_provider("enterprise")
        >>> result = provider.match("king", "queen")
        >>> result.match_score > 0.5
        True
        >>> result.mode
        MatchMode.TRUE_MATCH

        >>> result = provider.match("king", "banana")
        >>> result.match_score < 0.1
        True
        >>> result.mode
        MatchMode.REFERENT_MISMATCH

        >>> # Batch matching
        >>> results = provider.match_batch([("sun", "light"), ("fire", "water")])
        >>> len(results.results)
        2

        >>> # One-to-many matching
        >>> results = provider.match_one_to_many("energy", ("sun", "fire", "table"), top_k=2)
        >>> len(results.results) <= 2
        True
    """
    config = config or {}

    if mode == "enterprise":
        from symbolu_core.providers.enterprise.canonical_match import (
            CanonicalMatchProvider,
        )
        return CanonicalMatchProvider(
            c_threshold=config.get("c_threshold", 0.6),
            r_threshold=config.get("r_threshold", 0.5),
            s_threshold=config.get("s_threshold", 0.2),
        )
    else:
        raise ValueError(
            f"Invalid mode: {mode}. Match provider currently only supports 'enterprise'"
        )
