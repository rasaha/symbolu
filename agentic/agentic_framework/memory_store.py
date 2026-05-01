"""
Memory Store Component

Maintains persistent conversation state external to LLM context window.
Inspired by Phase 36 Identity Resonance Memory Store (append-only, deterministic).

MEMORY RULES:
- Append new TurnSnapshot per turn
- Never delete prior snapshots
- Never overwrite history
- Deterministic computation only

INVARIANTS:
- INV-MEM-1: Memory is append-only
- INV-MEM-2: History never mutated in place
- INV-MEM-3: Sliding window creates new list
- INV-MEM-4: Deterministic retrieval
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple


from agentic.agentic_framework.memory_retention import MemoryRetentionPolicy


class EmbeddingModel(Protocol):
    """Protocol for embedding model interface."""

    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        ...


@dataclass
class TurnSnapshot:
    """
    Immutable snapshot of a single turn.

    Captures all relevant information from a conversation turn
    for memory and analysis.
    """

    turn_id: int
    timestamp: datetime

    # Input/Output
    user_input: str
    assistant_output: str

    # Goal state (optional)
    goal_state: Optional[Any] = None  # GoalState
    actions_taken: List[Any] = field(default_factory=list)  # List[ActionItem]

    # Quality metrics
    quality_score: float = 0.0
    revision_count: int = 0

    # Coherence metrics (computed externally)
    coherence_metrics: Dict[str, float] = field(default_factory=dict)

    # Embedding for retrieval (computed lazily)
    embedding: Optional[List[float]] = None

    def get_text_for_embedding(self) -> str:
        """Get combined text for embedding computation."""
        return f"{self.user_input} {self.assistant_output}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "turn_id": self.turn_id,
            "timestamp": self.timestamp.isoformat(),
            "user_input": self.user_input,
            "assistant_output": self.assistant_output,
            "quality_score": self.quality_score,
            "revision_count": self.revision_count,
            "coherence_metrics": self.coherence_metrics,
        }


@dataclass
class AgentMemory:
    """
    Append-only memory store for agent state.

    MEMORY RULES (from Phase 36):
    - Append new TurnSnapshot per turn
    - Never delete prior snapshots
    - Never overwrite history
    - Deterministic computation only
    """

    session_id: str
    created_at: datetime

    # Append-only history
    history: List[TurnSnapshot] = field(default_factory=list)

    # Sliding window size for context
    window_size: int = 20

    # Embedding cache for retrieval (turn_id -> embedding)
    embedding_cache: Dict[int, List[float]] = field(default_factory=dict)

    # Operational metadata, populated by MemoryRetentionPolicy (v2.5).
    # Maps turn_id to the wall-clock UTC datetime that turn was last
    # returned by any memory read.  Used by ``idle_ttl_s`` cleanup
    # in ``MemoryStore``.  This is the only mutable field on
    # AgentMemory: history and TurnSnapshot remain immutable.  Until
    # M3 wires read/write paths, the dict stays empty in practice.
    last_accessed_at: Dict[int, datetime] = field(default_factory=dict)

    def get_recent_turns(self, n: int = 5) -> List[TurnSnapshot]:
        """Get n most recent turns."""
        return self.history[-n:] if self.history else []

    def get_turn_count(self) -> int:
        """Get total number of turns."""
        return len(self.history)

    def get_average_quality(self) -> float:
        """Get average quality score across all turns."""
        if not self.history:
            return 0.0
        return sum(t.quality_score for t in self.history) / len(self.history)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary.

        The ``operational`` key carries metadata that is *not* part of
        the immutable conversation history (e.g.
        ``last_accessed_at`` populated by ``MemoryRetentionPolicy``
        cleanup).  Operators inspecting durable session state should
        rely on ``history`` for what was said and on ``operational`` for
        how the runtime has been treating it.
        """
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "turn_count": len(self.history),
            "window_size": self.window_size,
            "history": [t.to_dict() for t in self.history],
            "operational": {
                "last_accessed_at": {
                    str(turn_id): ts.isoformat()
                    for turn_id, ts in self.last_accessed_at.items()
                },
            },
        }


class MemoryStore:
    """
    Operations on agent memory.

    All operations are pure functions that return new objects
    rather than mutating in place (functional/immutable pattern).
    """

    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        memory_retention_policy: Optional[MemoryRetentionPolicy] = None,
    ):
        """
        Initialize memory store.

        Args:
            embedding_model: Optional model for computing embeddings.
                If None, falls back to recency-based retrieval.
            memory_retention_policy: Optional ``MemoryRetentionPolicy``
                governing time- and size-based eviction of memory items.
                ``None`` (default) preserves the existing append-only +
                positional sliding-window behaviour.

                When the policy is active (any field set), the
                append-only invariant is *opt-in* relaxed: turns may be
                evicted on read or on write.  ``TurnSnapshot`` objects
                themselves remain immutable; the relaxation applies to
                the ``AgentMemory.history`` list and to operational
                metadata (``embedding_cache``, ``last_accessed_at``).
        """
        self.embedding_model = embedding_model
        self.memory_retention_policy = memory_retention_policy

    # ------------------------------------------------------------------
    # Eviction (v2.5)
    # ------------------------------------------------------------------

    def _evict(
        self,
        memory: "AgentMemory",
    ) -> Tuple["AgentMemory", int]:
        """Compute the post-eviction memory state.

        Pure: never mutates *memory*.  Returns the same instance when
        no eviction was needed (count == 0) so callers can short-circuit.

        Eviction order (load-bearing):
          1. ``item_ttl_s`` against ``TurnSnapshot.timestamp`` (created_at).
          2. ``idle_ttl_s`` against ``memory.last_accessed_at[turn_id]``,
             falling back to ``turn.timestamp`` for turns that have
             never been read (a never-accessed turn behaves as if its
             last access were its creation).
          3. ``max_items`` applied positionally to the post-TTL set,
             keeping the most recent ``max_items`` turns.

        ``embedding_cache`` and ``last_accessed_at`` are pruned for
        every evicted ``turn_id``.
        """
        policy = self.memory_retention_policy
        if policy is None or not policy.is_active():
            return memory, 0

        now = datetime.utcnow()
        evicted_ids: set[int] = set()
        survivors: List[TurnSnapshot] = []
        for turn in memory.history:
            # 1. item_ttl_s
            if (
                policy.item_ttl_s is not None
                and (now - turn.timestamp).total_seconds() > policy.item_ttl_s
            ):
                evicted_ids.add(turn.turn_id)
                continue
            # 2. idle_ttl_s — fall back to created_at when never accessed
            if policy.idle_ttl_s is not None:
                last_seen = memory.last_accessed_at.get(
                    turn.turn_id, turn.timestamp,
                )
                if (now - last_seen).total_seconds() > policy.idle_ttl_s:
                    evicted_ids.add(turn.turn_id)
                    continue
            survivors.append(turn)

        # 3. max_items applied AFTER TTL cleanup
        if (
            policy.max_items is not None
            and len(survivors) > policy.max_items
        ):
            dropped = survivors[: -policy.max_items]
            for turn in dropped:
                evicted_ids.add(turn.turn_id)
            survivors = survivors[-policy.max_items :]

        if not evicted_ids:
            return memory, 0

        new_cache = {
            tid: emb
            for tid, emb in memory.embedding_cache.items()
            if tid not in evicted_ids
        }
        new_last = {
            tid: ts
            for tid, ts in memory.last_accessed_at.items()
            if tid not in evicted_ids
        }
        new_memory = AgentMemory(
            session_id=memory.session_id,
            created_at=memory.created_at,
            history=survivors,
            window_size=memory.window_size,
            embedding_cache=new_cache,
            last_accessed_at=new_last,
        )
        return new_memory, len(evicted_ids)

    def _apply_eviction(self, memory: "AgentMemory") -> int:
        """Apply ``_evict`` to *memory* in place and return the count.

        Used by read paths to keep their existing API contract
        (``-> List[TurnSnapshot]``).  Mutates ``memory.history``,
        ``memory.embedding_cache``, and ``memory.last_accessed_at``
        if and only if eviction occurred.

        This is the single in-place mutation surface introduced by
        v2.5 for read paths; ``TurnSnapshot`` objects themselves are
        never mutated.
        """
        new_mem, count = self._evict(memory)
        if count == 0:
            return 0
        memory.history[:] = new_mem.history
        memory.embedding_cache.clear()
        memory.embedding_cache.update(new_mem.embedding_cache)
        memory.last_accessed_at.clear()
        memory.last_accessed_at.update(new_mem.last_accessed_at)
        return count

    def _touch(self, memory: "AgentMemory", turn_ids: List[int]) -> None:
        """Update ``last_accessed_at`` for *turn_ids* to ``utcnow()``.

        Called by read paths after they decide which turns to return.
        Mutates ``memory.last_accessed_at`` in place.

        No-op when no ``MemoryRetentionPolicy`` is configured or the
        policy is inactive — read paths preserve their pre-v2.5
        behaviour exactly when retention is not opted in.
        """
        policy = self.memory_retention_policy
        if policy is None or not policy.is_active():
            return
        if not turn_ids:
            return
        now = datetime.utcnow()
        for tid in turn_ids:
            memory.last_accessed_at[tid] = now

    def append_turn(
        self,
        memory: AgentMemory,
        turn: TurnSnapshot,
    ) -> AgentMemory:
        """
        Append turn to memory.

        Returns a new ``AgentMemory`` with the turn appended.  Never
        mutates *memory* (the input).  When ``MemoryRetentionPolicy`` is
        active the order is:

          1. evict expired turns from the existing history
          2. append the new turn
          3. apply ``max_items`` (when set) or ``window_size``
             (otherwise) to the post-append history; the newly
             appended turn counts toward the cap
          4. set ``last_accessed_at[new_turn.turn_id]`` to *now*

        Args:
            memory: Current memory state
            turn: New turn to append

        Returns:
            New AgentMemory with turn appended
        """
        # 1. Evict from the existing history under policy (pure).
        evicted_memory, _evicted_count = self._evict(memory)

        # 2. Append the new turn.
        new_history = list(evicted_memory.history)
        new_history.append(turn)

        # 3. Apply max_items if configured, otherwise window_size.
        policy = self.memory_retention_policy
        cap = (
            policy.max_items
            if (policy is not None and policy.max_items is not None)
            else memory.window_size
        )
        dropped_by_cap: List[int] = []
        if cap is not None and len(new_history) > cap:
            dropped = new_history[:-cap]
            dropped_by_cap = [t.turn_id for t in dropped]
            new_history = new_history[-cap:]

        # Compute embedding for the new turn.
        new_cache = dict(evicted_memory.embedding_cache)
        if self.embedding_model is not None:
            try:
                embedding = self.embedding_model.embed(turn.get_text_for_embedding())
                new_cache[turn.turn_id] = embedding
            except Exception:
                pass  # Embedding computation failed, continue without

        # Prune any turns dropped by the cap from the caches.
        new_last = dict(evicted_memory.last_accessed_at)
        for tid in dropped_by_cap:
            new_cache.pop(tid, None)
            new_last.pop(tid, None)

        # 4. Stamp last_accessed_at for the newly appended turn.
        new_last[turn.turn_id] = datetime.utcnow()

        return AgentMemory(
            session_id=memory.session_id,
            created_at=memory.created_at,
            history=new_history,
            window_size=memory.window_size,
            embedding_cache=new_cache,
            last_accessed_at=new_last,
        )

    def get_relevant_context(
        self,
        memory: AgentMemory,
        query: str,
        k: int = 5,
    ) -> List[TurnSnapshot]:
        """
        Retrieve k most relevant turns for query.

        Uses cosine similarity on embeddings if available,
        otherwise falls back to most recent turns.

        When ``MemoryRetentionPolicy`` is active, eviction runs *before*
        selection (mutates *memory* in place) and ``last_accessed_at``
        is updated for each returned turn.

        Args:
            memory: Memory to search
            query: Query string
            k: Number of turns to retrieve

        Returns:
            List of k most relevant TurnSnapshots
        """
        self._apply_eviction(memory)

        if not memory.history:
            return []

        # Fall back to recent if no embedding model
        if self.embedding_model is None:
            picked = memory.history[-k:]
            self._touch(memory, [t.turn_id for t in picked])
            return picked

        # Compute query embedding
        try:
            query_emb = self.embedding_model.embed(query)
        except Exception:
            picked = memory.history[-k:]
            self._touch(memory, [t.turn_id for t in picked])
            return picked

        # Compute similarities
        scores: List[Tuple[TurnSnapshot, float]] = []
        for turn in memory.history:
            if turn.turn_id in memory.embedding_cache:
                emb = memory.embedding_cache[turn.turn_id]
                sim = _cosine_similarity(query_emb, emb)
                scores.append((turn, sim))
            else:
                # No embedding, use low score
                scores.append((turn, 0.0))

        # Sort by similarity, return top k
        scores.sort(key=lambda x: -x[1])
        picked = [turn for turn, _ in scores[:k]]
        self._touch(memory, [t.turn_id for t in picked])
        return picked

    def get_summary_for_llm(
        self,
        memory: AgentMemory,
        max_turns: int = 5,
    ) -> str:
        """
        Generate compressed summary for LLM context injection.

        Instead of raw history, returns:
        - Session statistics
        - Recent turn summaries
        - Coherence trajectory

        Args:
            memory: Memory to summarize
            max_turns: Maximum recent turns to include

        Returns:
            Formatted summary string
        """
        self._apply_eviction(memory)

        if not memory.history:
            return "New session, no conversation history."

        recent = memory.history[-max_turns:]
        self._touch(memory, [t.turn_id for t in recent])

        # Compute statistics
        total_turns = len(memory.history)
        avg_quality = memory.get_average_quality()

        # Get coherence trend
        coherence_trend = self._compute_coherence_trend(recent)

        # Build summary
        summary_parts = [
            f"Session State:",
            f"- Total turns: {total_turns}",
            f"- Average quality: {avg_quality:.2f}",
            f"- Coherence trend: {coherence_trend}",
            "",
            "Recent conversation:",
        ]

        for turn in recent:
            # Truncate long content
            user_preview = turn.user_input[:80] + ("..." if len(turn.user_input) > 80 else "")
            assistant_preview = turn.assistant_output[:120] + (
                "..." if len(turn.assistant_output) > 120 else ""
            )

            summary_parts.append(f"- Turn {turn.turn_id}:")
            summary_parts.append(f"  User: {user_preview}")
            summary_parts.append(f"  Assistant: {assistant_preview}")
            summary_parts.append(f"  Quality: {turn.quality_score:.2f}")

        return "\n".join(summary_parts)

    def _compute_coherence_trend(self, recent_turns: List[TurnSnapshot]) -> str:
        """Compute coherence trend from recent turns."""
        if len(recent_turns) < 2:
            return "stable"

        coherence_values = []
        for turn in recent_turns:
            if "overall_coherence" in turn.coherence_metrics:
                coherence_values.append(turn.coherence_metrics["overall_coherence"])
            elif "internal_consistency" in turn.coherence_metrics:
                coherence_values.append(turn.coherence_metrics["internal_consistency"])

        if len(coherence_values) < 2:
            return "stable"

        # Compare first and last
        first = coherence_values[0]
        last = coherence_values[-1]

        if last > first + 0.1:
            return "improving"
        elif last < first - 0.1:
            return "degrading"
        return "stable"

    def search_by_keyword(
        self,
        memory: AgentMemory,
        keyword: str,
        max_results: int = 10,
    ) -> List[TurnSnapshot]:
        """
        Search memory by keyword.

        Simple keyword matching for when embeddings aren't available.

        Args:
            memory: Memory to search
            keyword: Keyword to search for
            max_results: Maximum results to return

        Returns:
            List of matching TurnSnapshots
        """
        self._apply_eviction(memory)

        keyword_lower = keyword.lower()
        matches = []

        for turn in memory.history:
            if keyword_lower in turn.user_input.lower() or keyword_lower in turn.assistant_output.lower():
                matches.append(turn)

            if len(matches) >= max_results:
                break

        self._touch(memory, [t.turn_id for t in matches])
        return matches


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def create_memory(
    session_id: str,
    window_size: int = 20,
) -> AgentMemory:
    """
    Create new empty agent memory.

    Args:
        session_id: Unique session identifier
        window_size: Maximum history size

    Returns:
        New AgentMemory instance
    """
    return AgentMemory(
        session_id=session_id,
        created_at=datetime.utcnow(),
        history=[],
        window_size=window_size,
        embedding_cache={},
        last_accessed_at={},
    )


def create_turn_snapshot(
    turn_id: int,
    user_input: str,
    assistant_output: str,
    quality_score: float = 0.0,
    revision_count: int = 0,
    coherence_metrics: Optional[Dict[str, float]] = None,
) -> TurnSnapshot:
    """
    Create a new turn snapshot.

    Args:
        turn_id: Unique turn identifier
        user_input: User's input text
        assistant_output: Assistant's response text
        quality_score: Quality score from critic
        revision_count: Number of revisions made
        coherence_metrics: Coherence metrics dict

    Returns:
        New TurnSnapshot instance
    """
    return TurnSnapshot(
        turn_id=turn_id,
        timestamp=datetime.utcnow(),
        user_input=user_input,
        assistant_output=assistant_output,
        quality_score=quality_score,
        revision_count=revision_count,
        coherence_metrics=coherence_metrics or {},
    )
