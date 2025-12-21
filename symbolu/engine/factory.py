"""
Engine Factory
==============

Factory for creating engine instances by tier.
"""

from enum import Enum
from typing import Optional, Dict, Any

from symbolu.engine.base import BaseEngine
from symbolu.engine.enterprise_search import EnterpriseSearchEngine
from symbolu.engine.enterprise_chat import EnterpriseChatEngine
from symbolu.engine.consumer import ConsumerEngine
from symbolu.hybrid.vocabulary import CustomVocabulary, VocabularyLoader


class EngineTier(Enum):
    """Available engine tiers."""

    # Enterprise Tier 1: Pure STL for search/classification
    ENTERPRISE_SEARCH = "enterprise_search"

    # Enterprise Tier 2: STL + 7B for specialized chat
    ENTERPRISE_CHAT = "enterprise_chat"

    # Consumer: STL + 768D + cascading LLM
    CONSUMER = "consumer"


def create_engine(
    tier: EngineTier = EngineTier.ENTERPRISE_SEARCH,
    vocabulary: Optional[CustomVocabulary] = None,
    vocabulary_file: Optional[str] = None,
    persona_id: Optional[str] = None,
    enable_agi: bool = True,
    **kwargs: Any,
) -> BaseEngine:
    """
    Create an engine instance for the specified tier.

    Args:
        tier: Which engine tier to create
        vocabulary: Pre-loaded CustomVocabulary
        vocabulary_file: Path to vocabulary JSON file
        persona_id: User/session ID for AGI persona tracking
        enable_agi: Whether to enable AGI capabilities
        **kwargs: Tier-specific configuration

    Returns:
        Configured engine instance

    Examples:
        # Enterprise Tier 1: Pure STL (no AGI)
        engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)
        result = engine.classify("Deploy the cluster")

        # Enterprise Tier 2: STL + 7B + Light AGI
        engine = create_engine(
            tier=EngineTier.ENTERPRISE_CHAT,
            persona_id="user_123"
        )
        result = engine.generate("Explain quantum physics")

        # Consumer: Full capability with Full AGI
        engine = create_engine(
            tier=EngineTier.CONSUMER,
            persona_id="user_123"
        )
        result = engine.generate("My startup co-founders disagree")
        print(result.agi_signal)  # Cross-domain insights

        # With custom vocabulary
        engine = create_engine(
            tier=EngineTier.ENTERPRISE_SEARCH,
            vocabulary_file="company_terms.json"
        )
    """
    # Load vocabulary if file path provided
    if vocabulary_file and not vocabulary:
        vocabulary = VocabularyLoader.from_file(vocabulary_file)

    # Create appropriate engine
    if tier == EngineTier.ENTERPRISE_SEARCH:
        # No AGI for Enterprise Search
        return EnterpriseSearchEngine(
            vocabulary=vocabulary,
            confidence_threshold=kwargs.get("confidence_threshold", 0.3),
        )

    elif tier == EngineTier.ENTERPRISE_CHAT:
        # Light AGI for Enterprise Chat
        return EnterpriseChatEngine(
            vocabulary=vocabulary,
            confidence_threshold=kwargs.get("confidence_threshold", 0.3),
            model_handlers=kwargs.get("model_handlers"),
            model_names=kwargs.get("model_names"),
            persona_id=persona_id,
            enable_agi=enable_agi,
        )

    elif tier == EngineTier.CONSUMER:
        # Full AGI for Consumer
        return ConsumerEngine(
            vocabulary=vocabulary,
            stl_confidence_threshold=kwargs.get("stl_confidence_threshold", 0.8),
            cascade_threshold=kwargs.get("cascade_threshold", 0.8),
            embedder=kwargs.get("embedder"),
            persona_id=persona_id,
            enable_agi=enable_agi,
        )

    else:
        raise ValueError(f"Unknown tier: {tier}")


# Convenience aliases
def create_search_engine(**kwargs: Any) -> EnterpriseSearchEngine:
    """Create Enterprise Search Engine (Tier 1)."""
    return create_engine(tier=EngineTier.ENTERPRISE_SEARCH, **kwargs)


def create_chat_engine(**kwargs: Any) -> EnterpriseChatEngine:
    """Create Enterprise Chat Engine (Tier 2)."""
    return create_engine(tier=EngineTier.ENTERPRISE_CHAT, **kwargs)


def create_consumer_engine(**kwargs: Any) -> ConsumerEngine:
    """Create Consumer Engine."""
    return create_engine(tier=EngineTier.CONSUMER, **kwargs)
