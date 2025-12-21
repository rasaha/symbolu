"""
Symbolu Engine
==============

Unified engine factory supporting multiple deployment tiers with AGI capabilities.

Enterprise Tier 1 (Pure STL):
    - Search/classification only
    - No LLM, no AGI
    - Use case: Intent detection, filtering, retrieval

Enterprise Tier 2 (STL + 7B + Light AGI):
    - STL routes to specialized 7B models
    - Light AGI: Persona tracking, cross-domain retrieval
    - 25x parameter savings vs 175B
    - Use case: Specialized chat with cost optimization

Consumer (STL + 768D + LLM + Full AGI):
    - STL + 768D semantic embeddings
    - Full AGI: Event tagging, balance checking, insight generation
    - Cascades to 7B (high confidence) or 175B (low confidence)
    - Use case: Full capability with cross-domain reasoning

AGI Capabilities:
    - Event tagging (conflict, destruction, formation, etc.)
    - 10D mirror pair balance checking
    - Persona query tracking
    - Cross-domain experiential retrieval
    - Insight generation (structurally-validated, not advertising)

Usage:
    from symbolu.engine import create_engine, EngineTier, AGILevel

    # Enterprise Tier 1: Pure STL
    engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)
    result = engine.classify("Deploy the K8s cluster")

    # Enterprise Tier 2: STL + 7B + Light AGI
    engine = create_engine(tier=EngineTier.ENTERPRISE_CHAT, persona_id="user_123")
    response = engine.generate("Explain quantum physics")

    # Consumer: Full capability with AGI
    engine = create_engine(tier=EngineTier.CONSUMER, persona_id="user_123")
    response = engine.generate("My startup co-founders disagree")
    print(response.agi_signal)  # Events, balance, cross-domain matches
    insights = engine.get_insights()  # Cross-domain insights
"""

from symbolu.engine.factory import create_engine, EngineTier
from symbolu.engine.base import BaseEngine, EngineResult, EngineCapability
from symbolu.engine.enterprise_search import EnterpriseSearchEngine
from symbolu.engine.enterprise_chat import EnterpriseChatEngine
from symbolu.engine.consumer import ConsumerEngine
from symbolu.engine.agi_context import AGIContext, AGILevel, AGISignal

__all__ = [
    # Factory
    "create_engine",
    "EngineTier",
    # Base classes
    "BaseEngine",
    "EngineResult",
    "EngineCapability",
    # Engines
    "EnterpriseSearchEngine",
    "EnterpriseChatEngine",
    "ConsumerEngine",
    # AGI
    "AGIContext",
    "AGILevel",
    "AGISignal",
]
