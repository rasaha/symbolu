"""
Symbolu Engine
==============

Unified engine factory supporting multiple deployment tiers:

Enterprise Tier 1 (Pure STL):
    - Search/classification only
    - No LLM, fastest option
    - Use case: Intent detection, filtering, retrieval

Enterprise Tier 2 (STL + 7B):
    - STL routes to specialized 7B models
    - 25x parameter savings vs 175B
    - Use case: Specialized chat with cost optimization

Consumer (STL + 768D + LLM):
    - STL + 768D semantic embeddings
    - Cascades to 7B (high confidence) or 175B (low confidence)
    - Use case: Full capability with smart routing

Usage:
    from symbolu.engine import create_engine, EngineTier

    # Enterprise Tier 1: Pure STL
    engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)
    result = engine.classify("Deploy the K8s cluster")

    # Enterprise Tier 2: STL + 7B
    engine = create_engine(tier=EngineTier.ENTERPRISE_CHAT)
    response = engine.generate("Explain quantum physics")

    # Consumer: Full capability
    engine = create_engine(tier=EngineTier.CONSUMER)
    response = engine.generate("Complex edge case query")
"""

from symbolu.engine.factory import create_engine, EngineTier
from symbolu.engine.base import BaseEngine, EngineResult
from symbolu.engine.enterprise_search import EnterpriseSearchEngine
from symbolu.engine.enterprise_chat import EnterpriseChatEngine
from symbolu.engine.consumer import ConsumerEngine

__all__ = [
    "create_engine",
    "EngineTier",
    "BaseEngine",
    "EngineResult",
    "EnterpriseSearchEngine",
    "EnterpriseChatEngine",
    "ConsumerEngine",
]
