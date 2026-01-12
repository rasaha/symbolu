"""
Master Chat Module - Single User Continuous Chat with Bucket-Based Context
===========================================================================

This module implements a master chat system where each user has a single
continuous conversation session. Knowledge is automatically harvested
and organized into semantic buckets based on ontological signals
(12D layers, Kosha, Vritti, Guna).

When the user sends a message, relevant buckets are activated based on
signal matching, and context from those buckets is injected to provide
continuity across topics.

Components:
    - bucket_models: Data models for buckets, entries, and signals
    - bucket_router: Signal-based routing to activate relevant buckets
    - knowledge_harvester: Extracts facts from conversation turns
    - master_session: Main session store integrating all components

Usage:
    from symbolu.service.master_chat import (
        get_master_session_store,
        MessageSignals,
    )

    # Get the store
    store = get_master_session_store()

    # Get context for a message
    context = store.get_context(
        user_id="user123",
        message="How is my trading bot project going?",
        signals=signals,  # From MLCR/pipeline
    )

    # Use context.context_text in your LLM call
    response = await chat_service.generate(
        message=user_message,
        context=context.context_text,
    )

    # Harvest knowledge after the turn
    await store.harvest_turn(
        user_id="user123",
        user_message=user_message,
        assistant_response=response,
        signals=signals,
    )

Version: 1.0
"""

from .bucket_models import (
    # Enums
    BucketCategory,
    # Data classes
    SignalProfile,
    BucketEntry,
    Bucket,
    ActivatedBucket,
    MessageSignals,
    # Constants
    LAYER_TO_BUCKET,
    BUCKET_SIGNAL_PROFILES,
    # Factory
    create_default_buckets,
)

from .bucket_router import (
    # Configuration
    RouterConfig,
    DEFAULT_ROUTER_CONFIG,
    # Classes
    BucketRouter,
    ContextAssembler,
)

from .knowledge_harvester import (
    KnowledgeHarvester,
    HarvestedFact,
)

from .master_session import (
    MasterSession,
    MasterSessionStore,
    TurnContext,
    get_master_session_store,
)

# API router (optional import - only when FastAPI is available)
try:
    from .api import router as master_chat_router
except ImportError:
    master_chat_router = None


__all__ = [
    # Bucket Models
    "BucketCategory",
    "SignalProfile",
    "BucketEntry",
    "Bucket",
    "ActivatedBucket",
    "MessageSignals",
    "LAYER_TO_BUCKET",
    "BUCKET_SIGNAL_PROFILES",
    "create_default_buckets",
    # Router
    "RouterConfig",
    "DEFAULT_ROUTER_CONFIG",
    "BucketRouter",
    "ContextAssembler",
    # Harvester
    "KnowledgeHarvester",
    "HarvestedFact",
    # Session
    "MasterSession",
    "MasterSessionStore",
    "TurnContext",
    "get_master_session_store",
    # API
    "master_chat_router",
]
