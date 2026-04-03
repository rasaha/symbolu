"""
Master Session Store for Single-User Continuous Chat
=====================================================

Manages the persistent master chat session per user with
bucket-based context retrieval.

Key Features:
- Single continuous session per user (no session boundaries)
- Automatic knowledge harvesting after each turn
- Signal-based bucket routing for context retrieval
- Seamless integration with existing MLCR/TTOR infrastructure

Architecture:
    User → MasterSessionStore → BucketRouter → Context → ChatService
                    ↓
            KnowledgeHarvester → BucketStore

Version: 1.0
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Dict, List, Optional, Any, Callable
from uuid import uuid4

from .bucket_models import (
    Bucket,
    BucketCategory,
    BucketEntry,
    ActivatedBucket,
    MessageSignals,
    create_default_buckets,
)
from .bucket_router import (
    BucketRouter,
    ContextAssembler,
    RouterConfig,
)
from .knowledge_harvester import (
    KnowledgeHarvester,
    HarvestedFact,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Master Session
# =============================================================================

@dataclass
class MasterSession:
    """
    A single user's master chat session.

    Contains all buckets, conversation history summary,
    and session-level statistics.

    Attributes:
        user_id: Unique user identifier
        session_id: Session identifier (same as user_id for master sessions)
        created_at: Session creation timestamp
        last_activity: Last interaction timestamp
        buckets: Knowledge buckets for this user
        turn_count: Total number of conversation turns
        total_entries: Total knowledge entries harvested
        metadata: Additional session metadata
    """
    user_id: str
    session_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    buckets: Dict[str, Bucket] = field(default_factory=dict)
    turn_count: int = 0
    total_entries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.session_id:
            self.session_id = self.user_id

        if not self.buckets:
            self.buckets = create_default_buckets()

    def record_turn(self) -> None:
        """Record a new conversation turn."""
        self.turn_count += 1
        self.last_activity = datetime.utcnow()

    def add_entry(self, bucket_id: str, entry: BucketEntry) -> bool:
        """Add an entry to a specific bucket."""
        if bucket_id not in self.buckets:
            return False

        self.buckets[bucket_id].add_entry(entry)
        self.total_entries += 1
        return True

    def get_bucket_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all buckets."""
        return {
            bucket_id: {
                "display_name": bucket.display_name,
                "total_entries": bucket.total_entries,
                "access_count": bucket.access_count,
                "last_accessed": bucket.last_accessed.isoformat() if bucket.last_accessed else None,
            }
            for bucket_id, bucket in self.buckets.items()
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session state (without full bucket contents)."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "turn_count": self.turn_count,
            "total_entries": self.total_entries,
            "bucket_summary": self.get_bucket_summary(),
            "metadata": self.metadata,
        }


# =============================================================================
# Turn Context
# =============================================================================

@dataclass
class TurnContext:
    """
    Context assembled for a conversation turn.

    Contains activated buckets and formatted context for LLM injection.

    Attributes:
        turn_id: Unique turn identifier
        activated_buckets: List of activated buckets with entries
        context_text: Formatted context for LLM
        signals: Ontological signals for this turn
        routing_metadata: Debug info about routing decisions
    """
    turn_id: str
    activated_buckets: List[ActivatedBucket]
    context_text: str
    signals: Optional[MessageSignals] = None
    routing_metadata: Dict[str, Any] = field(default_factory=dict)

    def has_context(self) -> bool:
        """Check if any context was activated."""
        return len(self.activated_buckets) > 0 and len(self.context_text) > 0


# =============================================================================
# Master Session Store
# =============================================================================

class MasterSessionStore:
    """
    Central store for managing master chat sessions.

    Provides:
    - Single session per user (get_or_create pattern)
    - Context retrieval via bucket routing
    - Automatic knowledge harvesting
    - Thread-safe operations

    Usage:
        store = MasterSessionStore()
        session = store.get_or_create(user_id)
        context = store.get_context(user_id, message, signals)
        # ... use context in chat ...
        await store.harvest_turn(user_id, message, response, signals)
    """

    def __init__(
        self,
        router_config: Optional[RouterConfig] = None,
        embedding_provider: Optional[Callable[[str], List[float]]] = None,
    ):
        """
        Initialize the master session store.

        Args:
            router_config: Configuration for bucket routing
            embedding_provider: Optional function to compute embeddings
                               Signature: (text: str) -> List[float]
        """
        self._sessions: Dict[str, MasterSession] = {}
        self._lock = RLock()

        self.router = BucketRouter(config=router_config)
        self.assembler = ContextAssembler()
        self.harvester = KnowledgeHarvester()
        self.embedding_provider = embedding_provider

        logger.info("MasterSessionStore initialized")

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    def get_or_create(self, user_id: str) -> MasterSession:
        """
        Get existing session or create new one for user.

        Args:
            user_id: Unique user identifier

        Returns:
            User's master session
        """
        with self._lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = MasterSession(user_id=user_id)
                logger.info(f"Created new master session for user: {user_id}")

            return self._sessions[user_id]

    def get(self, user_id: str) -> Optional[MasterSession]:
        """
        Get session if it exists.

        Args:
            user_id: User identifier

        Returns:
            Session or None
        """
        with self._lock:
            return self._sessions.get(user_id)

    def delete(self, user_id: str) -> bool:
        """
        Delete a user's session (use with caution).

        Args:
            user_id: User identifier

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if user_id in self._sessions:
                del self._sessions[user_id]
                logger.info(f"Deleted master session for user: {user_id}")
                return True
            return False

    def list_users(self) -> List[str]:
        """List all users with active sessions."""
        with self._lock:
            return list(self._sessions.keys())

    # -------------------------------------------------------------------------
    # Context Retrieval
    # -------------------------------------------------------------------------

    def get_context(
        self,
        user_id: str,
        message: str,
        signals: Optional[MessageSignals] = None,
    ) -> TurnContext:
        """
        Get context for a user message by activating relevant buckets.

        Args:
            user_id: User identifier
            message: User's message text
            signals: Optional ontological signals (from MLCR/pipeline)

        Returns:
            TurnContext with activated buckets and formatted context
        """
        turn_id = str(uuid4())

        # Get or create session
        session = self.get_or_create(user_id)

        # Default signals if not provided
        if signals is None:
            signals = MessageSignals()

        # Compute query embedding if provider available
        query_embedding = None
        if self.embedding_provider:
            try:
                query_embedding = self.embedding_provider(message)
            except Exception as e:
                logger.warning(f"Failed to compute embedding: {e}")

        # Route to buckets
        activated_buckets = self.router.route(
            signals=signals,
            buckets=session.buckets,
            query_embedding=query_embedding,
        )

        # Assemble context
        context_text = self.assembler.assemble(activated_buckets)

        # Build routing metadata
        routing_metadata = {
            "buckets_activated": len(activated_buckets),
            "buckets_checked": len(session.buckets),
            "has_embedding": query_embedding is not None,
            "activated_names": [ab.bucket.display_name for ab in activated_buckets],
            "activation_scores": {
                ab.bucket.bucket_id: ab.activation_score
                for ab in activated_buckets
            },
        }

        return TurnContext(
            turn_id=turn_id,
            activated_buckets=activated_buckets,
            context_text=context_text,
            signals=signals,
            routing_metadata=routing_metadata,
        )

    def get_context_for_system_prompt(
        self,
        user_id: str,
        message: str,
        signals: Optional[MessageSignals] = None,
    ) -> str:
        """
        Get context formatted for system prompt injection.

        Convenience method that returns just the context string.

        Args:
            user_id: User identifier
            message: User's message
            signals: Optional ontological signals

        Returns:
            Formatted context string (empty if no relevant context)
        """
        turn_context = self.get_context(user_id, message, signals)
        return self.assembler.assemble_for_system_prompt(
            turn_context.activated_buckets
        )

    # -------------------------------------------------------------------------
    # Knowledge Harvesting
    # -------------------------------------------------------------------------

    async def harvest_turn(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str,
        signals: Optional[MessageSignals] = None,
        turn_id: Optional[str] = None,
    ) -> int:
        """
        Harvest knowledge from a completed conversation turn.

        This should be called after each turn to extract and store
        knowledge nuggets in appropriate buckets.

        Args:
            user_id: User identifier
            user_message: User's message text
            assistant_response: Assistant's response text
            signals: Ontological signals for the turn
            turn_id: Optional turn identifier

        Returns:
            Number of facts harvested
        """
        turn_id = turn_id or str(uuid4())

        # Get session
        session = self.get_or_create(user_id)
        session.record_turn()

        # Harvest facts
        facts = self.harvester.harvest_turn(
            user_message=user_message,
            assistant_response=assistant_response,
            signals=signals,
            turn_id=turn_id,
        )

        if not facts:
            return 0

        # Process each fact
        entries_added = 0

        for fact in facts:
            # Classify to bucket
            bucket_category = self.harvester.classify_to_bucket(fact, signals)
            bucket_id = bucket_category.value

            # Compute embedding if provider available
            embedding = None
            if self.embedding_provider:
                try:
                    embedding = self.embedding_provider(fact.content)
                except Exception as e:
                    logger.warning(f"Failed to compute embedding for fact: {e}")

            # Create entry
            entry = self.harvester.create_bucket_entry(
                fact=fact,
                bucket_category=bucket_category,
                signals=signals,
                embedding=embedding,
            )
            entry.source_turn_id = turn_id

            # Add to bucket
            if session.add_entry(bucket_id, entry):
                entries_added += 1
                logger.debug(
                    f"Added entry to {bucket_id}: {fact.content[:50]}..."
                )

        logger.info(
            f"Harvested {entries_added} facts for user {user_id} "
            f"(turn {session.turn_count})"
        )

        return entries_added

    def harvest_turn_sync(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str,
        signals: Optional[MessageSignals] = None,
        turn_id: Optional[str] = None,
    ) -> int:
        """
        Synchronous version of harvest_turn.

        For use in non-async contexts.
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.harvest_turn(
                    user_id=user_id,
                    user_message=user_message,
                    assistant_response=assistant_response,
                    signals=signals,
                    turn_id=turn_id,
                )
            )
        finally:
            loop.close()

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def search_buckets(
        self,
        user_id: str,
        query: str,
        bucket_ids: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[BucketEntry]:
        """
        Search for entries across buckets.

        Args:
            user_id: User identifier
            query: Search query
            bucket_ids: Optional list of bucket IDs to search (all if None)
            limit: Maximum entries to return

        Returns:
            List of matching entries
        """
        session = self.get(user_id)
        if not session:
            return []

        # Get query embedding
        query_embedding = None
        if self.embedding_provider:
            try:
                query_embedding = self.embedding_provider(query)
            except Exception:
                pass

        results: List[BucketEntry] = []
        buckets_to_search = bucket_ids or list(session.buckets.keys())

        for bucket_id in buckets_to_search:
            bucket = session.buckets.get(bucket_id)
            if not bucket:
                continue

            for entry in bucket.entries:
                # Simple keyword matching if no embeddings
                if query_embedding is None:
                    query_lower = query.lower()
                    content_lower = entry.content.lower()
                    if query_lower in content_lower:
                        results.append(entry)
                else:
                    # Semantic similarity
                    if entry.embedding:
                        sim = self.router._cosine_similarity(
                            query_embedding,
                            entry.embedding,
                        )
                        if sim > 0.5:
                            results.append(entry)

        # Sort by importance and return top results
        results.sort(key=lambda e: e.importance_score, reverse=True)
        return results[:limit]

    def get_bucket_entries(
        self,
        user_id: str,
        bucket_id: str,
        limit: int = 20,
        sort_by: str = "recency",
    ) -> List[BucketEntry]:
        """
        Get entries from a specific bucket.

        Args:
            user_id: User identifier
            bucket_id: Bucket to get entries from
            limit: Maximum entries
            sort_by: Sort order ("recency" or "importance")

        Returns:
            List of bucket entries
        """
        session = self.get(user_id)
        if not session:
            return []

        bucket = session.buckets.get(bucket_id)
        if not bucket:
            return []

        if sort_by == "importance":
            return bucket.get_important_entries(limit)
        else:
            return bucket.get_recent_entries(limit)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a user's session."""
        session = self.get(user_id)
        if not session:
            return {}

        return {
            "user_id": user_id,
            "turn_count": session.turn_count,
            "total_entries": session.total_entries,
            "buckets_with_entries": sum(
                1 for b in session.buckets.values() if b.total_entries > 0
            ),
            "most_active_bucket": max(
                session.buckets.values(),
                key=lambda b: b.access_count,
            ).bucket_id if session.buckets else None,
            "entries_by_bucket": {
                b.bucket_id: b.total_entries
                for b in session.buckets.values()
            },
            "session_age_hours": (
                datetime.utcnow() - session.created_at
            ).total_seconds() / 3600,
        }


# =============================================================================
# Convenience Factory
# =============================================================================

_global_store: Optional[MasterSessionStore] = None


def get_master_session_store(
    router_config: Optional[RouterConfig] = None,
    embedding_provider: Optional[Callable[[str], List[float]]] = None,
) -> MasterSessionStore:
    """
    Get or create the global master session store.

    This provides a singleton-like access pattern for the store.

    Args:
        router_config: Router configuration (only used on first call)
        embedding_provider: Embedding function (only used on first call)

    Returns:
        Global MasterSessionStore instance
    """
    global _global_store

    if _global_store is None:
        _global_store = MasterSessionStore(
            router_config=router_config,
            embedding_provider=embedding_provider,
        )

    return _global_store


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Main classes
    "MasterSession",
    "MasterSessionStore",
    "TurnContext",
    # Factory
    "get_master_session_store",
]
