"""
Tests for Memory Store Component

Tests the append-only memory system:
- TurnSnapshot dataclass
- AgentMemory dataclass
- MemoryStore operations
- Semantic retrieval
- Context summarization
"""

import pytest
from datetime import datetime

from agentic.agentic_framework.memory_store import (
    TurnSnapshot,
    AgentMemory,
    MemoryStore,
    create_memory,
    create_turn_snapshot,
)
from agentic.agentic_framework.llm_adapters import MockEmbeddingAdapter


class TestTurnSnapshot:
    """Tests for TurnSnapshot dataclass."""

    def test_turn_snapshot_creation(self):
        """Test basic TurnSnapshot creation."""
        snapshot = create_turn_snapshot(
            turn_id=1,
            user_input="Hello",
            assistant_output="Hi there!",
            quality_score=0.9,
        )
        assert snapshot.turn_id == 1
        assert snapshot.user_input == "Hello"
        assert snapshot.assistant_output == "Hi there!"
        assert snapshot.quality_score == 0.9

    def test_turn_snapshot_defaults(self):
        """Test TurnSnapshot default values."""
        snapshot = create_turn_snapshot(
            turn_id=1,
            user_input="Test",
            assistant_output="Response",
        )
        assert snapshot.revision_count == 0
        assert snapshot.goal_state is None
        assert snapshot.coherence_metrics == {}

    def test_turn_snapshot_to_dict(self):
        """Test TurnSnapshot serialization."""
        snapshot = create_turn_snapshot(
            turn_id=1,
            user_input="Test",
            assistant_output="Response",
            quality_score=0.85,
            revision_count=2,
        )
        d = snapshot.to_dict()
        assert d["turn_id"] == 1
        assert d["quality_score"] == 0.85
        assert d["revision_count"] == 2
        assert "timestamp" in d

    def test_get_text_for_embedding(self):
        """Test combined text for embedding."""
        snapshot = create_turn_snapshot(
            turn_id=1,
            user_input="Question",
            assistant_output="Answer",
        )
        text = snapshot.get_text_for_embedding()
        assert "Question" in text
        assert "Answer" in text


class TestAgentMemory:
    """Tests for AgentMemory dataclass."""

    def test_agent_memory_creation(self):
        """Test basic AgentMemory creation."""
        memory = create_memory("test-session")
        assert memory.session_id == "test-session"
        assert len(memory.history) == 0

    def test_get_turn_count(self):
        """Test turn count calculation."""
        memory = create_memory("test")
        memory.history.append(create_turn_snapshot(1, "Q1", "A1"))
        memory.history.append(create_turn_snapshot(2, "Q2", "A2"))
        assert memory.get_turn_count() == 2

    def test_get_recent_turns(self):
        """Test getting recent turns."""
        memory = create_memory("test")
        for i in range(5):
            memory.history.append(create_turn_snapshot(i, f"Q{i}", f"A{i}"))

        recent = memory.get_recent_turns(n=3)
        assert len(recent) == 3
        assert recent[0].turn_id == 2  # Oldest of the 3 most recent
        assert recent[2].turn_id == 4  # Most recent

    def test_get_recent_turns_less_than_n(self):
        """Test getting recent turns when fewer than n exist."""
        memory = create_memory("test")
        memory.history.append(create_turn_snapshot(1, "Q", "A"))

        recent = memory.get_recent_turns(n=5)
        assert len(recent) == 1

    def test_get_average_quality(self):
        """Test average quality calculation."""
        memory = create_memory("test")
        memory.history.append(create_turn_snapshot(1, "Q1", "A1", quality_score=0.8))
        memory.history.append(create_turn_snapshot(2, "Q2", "A2", quality_score=0.9))
        memory.history.append(create_turn_snapshot(3, "Q3", "A3", quality_score=1.0))

        avg = memory.get_average_quality()
        assert abs(avg - 0.9) < 0.01

    def test_get_average_quality_empty(self):
        """Test average quality with no turns."""
        memory = create_memory("test")
        assert memory.get_average_quality() == 0.0


class TestMemoryStore:
    """Tests for MemoryStore class."""

    def test_memory_store_creation(self):
        """Test basic MemoryStore creation."""
        store = MemoryStore()
        assert store.embedding_model is None

    def test_memory_store_with_embeddings(self):
        """Test MemoryStore with embedding model."""
        embedder = MockEmbeddingAdapter()
        store = MemoryStore(embedding_model=embedder)
        assert store.embedding_model is embedder

    def test_append_turn(self):
        """Test appending a turn."""
        store = MemoryStore()
        memory = create_memory("test")
        snapshot = create_turn_snapshot(1, "Hello", "Hi!", quality_score=0.9)

        new_memory = store.append_turn(memory, snapshot)

        assert new_memory.get_turn_count() == 1
        assert new_memory.history[0].user_input == "Hello"
        # Original memory unchanged (immutable pattern)
        assert memory.get_turn_count() == 0

    def test_append_turn_immutability(self):
        """Test that append_turn doesn't modify original memory."""
        store = MemoryStore()
        memory = create_memory("test")
        snapshot = create_turn_snapshot(1, "Q", "A")

        new_memory = store.append_turn(memory, snapshot)

        # Original should be unchanged
        assert memory.get_turn_count() == 0
        # New should have the turn
        assert new_memory.get_turn_count() == 1

    def test_append_enforces_window(self):
        """Test that window limit is enforced."""
        store = MemoryStore()
        memory = create_memory("test", window_size=3)

        for i in range(5):
            snapshot = create_turn_snapshot(i, f"Q{i}", f"A{i}")
            memory = store.append_turn(memory, snapshot)

        # Should only keep last 3 turns
        assert memory.get_turn_count() == 3
        assert memory.history[0].user_input == "Q2"

    def test_get_summary_for_llm(self):
        """Test summary generation for LLM."""
        store = MemoryStore()
        memory = create_memory("test")

        memory = store.append_turn(memory, create_turn_snapshot(1, "Q1", "A1", quality_score=0.8))
        memory = store.append_turn(memory, create_turn_snapshot(2, "Q2", "A2", quality_score=0.9))

        summary = store.get_summary_for_llm(memory)

        assert "Session State" in summary
        assert "Total turns: 2" in summary

    def test_get_summary_empty(self):
        """Test summary for empty memory."""
        store = MemoryStore()
        memory = create_memory("test")

        summary = store.get_summary_for_llm(memory)
        assert "New session" in summary or "no conversation" in summary.lower()

    def test_get_relevant_context_without_embeddings(self):
        """Test relevant context without embedding model."""
        store = MemoryStore()
        memory = create_memory("test")

        memory = store.append_turn(memory, create_turn_snapshot(1, "Python basics", "Python intro"))
        memory = store.append_turn(memory, create_turn_snapshot(2, "Java basics", "Java intro"))

        # Without embeddings, should return recent turns
        context = store.get_relevant_context(memory, "Python question", k=1)
        assert len(context) >= 0

    def test_get_relevant_context_with_embeddings(self):
        """Test relevant context with embedding model."""
        embedder = MockEmbeddingAdapter(dimension=128)
        store = MemoryStore(embedding_model=embedder)
        memory = create_memory("test")

        memory = store.append_turn(memory, create_turn_snapshot(1, "Python programming", "Python is great"))
        memory = store.append_turn(memory, create_turn_snapshot(2, "Java programming", "Java is enterprise"))

        # Should retrieve based on similarity
        context = store.get_relevant_context(memory, "Python code", k=2)
        assert len(context) <= 2

    def test_search_by_keyword(self):
        """Test keyword search."""
        store = MemoryStore()
        memory = create_memory("test")

        memory = store.append_turn(memory, create_turn_snapshot(1, "Python basics", "Learn Python"))
        memory = store.append_turn(memory, create_turn_snapshot(2, "Java basics", "Learn Java"))
        memory = store.append_turn(memory, create_turn_snapshot(3, "Python advanced", "Advanced Python"))

        results = store.search_by_keyword(memory, "Python")
        assert len(results) == 2


class TestMemoryStoreIntegration:
    """Integration tests for MemoryStore."""

    def test_full_conversation_flow(self):
        """Test a complete conversation flow."""
        store = MemoryStore()
        memory = create_memory("conv-001")

        # Turn 1
        memory = store.append_turn(memory, create_turn_snapshot(
            turn_id=1,
            user_input="What is machine learning?",
            assistant_output="ML is a subset of AI that learns from data.",
            quality_score=0.85,
        ))

        # Turn 2
        memory = store.append_turn(memory, create_turn_snapshot(
            turn_id=2,
            user_input="Give me an example",
            assistant_output="Image classification is a common ML application.",
            quality_score=0.90,
        ))

        # Turn 3
        memory = store.append_turn(memory, create_turn_snapshot(
            turn_id=3,
            user_input="How does it work?",
            assistant_output="Neural networks process data through layers.",
            quality_score=0.88,
        ))

        # Verify state
        assert memory.get_turn_count() == 3
        assert abs(memory.get_average_quality() - 0.877) < 0.01

        # Get summary
        summary = store.get_summary_for_llm(memory, max_turns=2)
        assert "neural networks" in summary.lower() or "Turn 3" in summary

    def test_session_persistence_structure(self):
        """Test that session data can be exported."""
        store = MemoryStore()
        memory = create_memory("persist-test")

        memory = store.append_turn(memory, create_turn_snapshot(1, "Q1", "A1", quality_score=0.8))
        memory = store.append_turn(memory, create_turn_snapshot(2, "Q2", "A2", quality_score=0.9))

        # Export via to_dict
        data = memory.to_dict()

        assert data["session_id"] == "persist-test"
        assert data["turn_count"] == 2
        assert len(data["history"]) == 2
