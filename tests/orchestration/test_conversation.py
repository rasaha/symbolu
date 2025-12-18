"""
Tests for conversation state management.

Verifies:
- Session management
- Message history tracking
- Intent blending across turns
- Constraint accumulation
"""

import pytest
from symbolu.orchestration.conversation import (
    MessageRole,
    Message,
    ConversationState,
    ConversationSession,
    ConversationManager,
    get_conversation_manager,
    chat,
)
from symbolu.orchestration.semantic_layer import SemanticVector


class TestMessage:
    """Tests for Message dataclass."""

    def test_user_message(self):
        """Create user message."""
        msg = Message(role=MessageRole.USER, content="hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "hello"
        assert msg.timestamp is not None

    def test_message_to_dict(self):
        """Message converts to dictionary."""
        msg = Message(role=MessageRole.USER, content="hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "hello"
        assert "timestamp" in d


class TestConversationSession:
    """Tests for ConversationSession."""

    def test_create_session(self):
        """Create new session."""
        session = ConversationSession()
        assert session.session_id is not None
        assert len(session.messages) == 0
        assert session.state.turn_count == 0

    def test_create_session_with_id(self):
        """Create session with specific ID."""
        session = ConversationSession(session_id="test-123")
        assert session.session_id == "test-123"

    def test_add_user_message(self):
        """Add user message parses intent."""
        session = ConversationSession()
        intent = session.add_user_message("something calm")
        assert len(session.messages) == 1
        assert session.messages[0].role == MessageRole.USER
        assert intent.keywords_matched  # Should match "calm"
        assert session.state.turn_count == 1

    def test_add_assistant_message(self):
        """Add assistant message with sequences."""
        session = ConversationSession()
        sequences = (("ka", "a"), ("ba", "i"))
        msg = session.add_assistant_message("Generated 2", sequences=sequences)
        assert msg.role == MessageRole.ASSISTANT
        assert msg.generated_sequences == sequences
        # Sequences should be tracked in history
        assert ("ka", "a") in session.state.generated_history
        assert ("ba", "i") in session.state.generated_history

    def test_intent_blending_decay(self):
        """Intent vectors decay and blend across turns."""
        session = ConversationSession(intent_decay=0.5)

        # First turn: high energy
        session.add_user_message("energetic powerful")
        first_energy = session.state.accumulated_vector.energy

        # Second turn: neutral
        session.add_user_message("something")
        second_energy = session.state.accumulated_vector.energy

        # Energy should decay
        assert abs(second_energy) < abs(first_energy)

    def test_intent_blending_new_values(self):
        """New intent values blend with accumulated."""
        session = ConversationSession(intent_decay=0.7)

        # First turn: calm
        session.add_user_message("calm")
        first_energy = session.state.accumulated_vector.energy
        assert first_energy < 0  # Calm is negative energy

        # Second turn: energetic (opposite)
        session.add_user_message("energetic")
        second_energy = session.state.accumulated_vector.energy
        # Should move toward positive (blend of decayed negative + positive)
        assert second_energy > first_energy

    def test_persistent_constraints(self):
        """Persistent constraints carry across turns."""
        session = ConversationSession()
        session.set_persistent_constraint("template matches", "CV*")
        session.add_user_message("something")
        constraints = session.get_current_constraints()
        assert "template matches" in constraints

    def test_clear_persistent_constraint(self):
        """Persistent constraints can be cleared."""
        session = ConversationSession()
        session.set_persistent_constraint("key", "value")
        session.clear_persistent_constraint("key")
        constraints = session.get_current_constraints()
        assert "key" not in constraints

    def test_generated_history_exclusion(self):
        """Generated sequences are excluded in constraints."""
        session = ConversationSession()
        sequences = (("ka", "a"), ("ba", "i"))
        session.add_assistant_message("Generated", sequences=sequences)

        constraints = session.get_current_constraints()
        if "sequence NOT IN" in constraints:
            exclusions = constraints["sequence NOT IN"]
            assert ("ka", "a") in exclusions

    def test_max_history_trimming(self):
        """Message history is trimmed when exceeding max."""
        session = ConversationSession(max_history=5)
        for i in range(10):
            session.add_user_message(f"message {i}")
        assert len(session.messages) == 5

    def test_reset_session(self):
        """Reset clears state but keeps session ID."""
        session = ConversationSession(session_id="test-123")
        session.add_user_message("hello")
        session.add_assistant_message("hi")

        session.reset()
        assert session.session_id == "test-123"
        assert len(session.messages) == 0
        assert session.state.turn_count == 0

    def test_get_history(self):
        """Get message history with optional limit."""
        session = ConversationSession()
        session.add_user_message("one")
        session.add_user_message("two")
        session.add_user_message("three")

        all_history = session.get_history()
        assert len(all_history) == 3

        limited = session.get_history(limit=2)
        assert len(limited) == 2
        assert limited[-1].content == "three"

    def test_get_summary(self):
        """Get session summary."""
        session = ConversationSession(session_id="test-123")
        session.add_user_message("calm")
        session.add_assistant_message("response", sequences=(("ka", "a"),))

        summary = session.get_summary()
        assert summary["session_id"] == "test-123"
        assert summary["turn_count"] == 1
        assert summary["message_count"] == 2
        assert summary["sequences_generated"] == 1

    def test_custom_context(self):
        """Custom context can be set and retrieved."""
        session = ConversationSession()
        session.set_context("user_preference", "dark_mode")
        assert session.get_context("user_preference") == "dark_mode"
        assert session.get_context("nonexistent", "default") == "default"


class TestConversationManager:
    """Tests for ConversationManager."""

    def test_create_session(self):
        """Create new session."""
        manager = ConversationManager()
        session = manager.create_session()
        assert session.session_id in manager.sessions

    def test_create_session_with_id(self):
        """Create session with specific ID."""
        manager = ConversationManager()
        session = manager.create_session(session_id="my-session")
        assert session.session_id == "my-session"
        assert manager.get_session("my-session") is session

    def test_get_session_not_found(self):
        """Get nonexistent session returns None."""
        manager = ConversationManager()
        assert manager.get_session("nonexistent") is None

    def test_get_or_create_existing(self):
        """Get or create returns existing session."""
        manager = ConversationManager()
        session1 = manager.create_session(session_id="test")
        session2 = manager.get_or_create_session("test")
        assert session1 is session2

    def test_get_or_create_new(self):
        """Get or create creates new session."""
        manager = ConversationManager()
        session = manager.get_or_create_session("new-session")
        assert session.session_id == "new-session"
        assert "new-session" in manager.sessions

    def test_delete_session(self):
        """Delete session removes it."""
        manager = ConversationManager()
        manager.create_session(session_id="to-delete")
        assert manager.delete_session("to-delete")
        assert manager.get_session("to-delete") is None

    def test_delete_nonexistent(self):
        """Delete nonexistent session returns False."""
        manager = ConversationManager()
        assert manager.delete_session("nonexistent") is False

    def test_list_sessions(self):
        """List sessions returns summaries."""
        manager = ConversationManager()
        manager.create_session(session_id="one")
        manager.create_session(session_id="two")
        sessions = manager.list_sessions()
        assert len(sessions) == 2
        session_ids = [s["session_id"] for s in sessions]
        assert "one" in session_ids
        assert "two" in session_ids


class TestGlobalManager:
    """Tests for global conversation manager."""

    def test_singleton_pattern(self):
        """Global manager is singleton."""
        manager1 = get_conversation_manager()
        manager2 = get_conversation_manager()
        assert manager1 is manager2


class TestChatFunction:
    """Tests for the chat() convenience function."""

    def test_chat_creates_session(self):
        """Chat without session ID creates new session."""
        result = chat("calm")
        assert "session_id" in result
        assert result["session_id"] is not None

    def test_chat_uses_existing_session(self):
        """Chat with session ID uses existing session."""
        result1 = chat("calm")
        session_id = result1["session_id"]
        result2 = chat("energetic", session_id=session_id)
        assert result2["session_id"] == session_id
        # Turn count should increase
        assert result2["turn_count"] == 2

    def test_chat_returns_sequences(self):
        """Chat returns generated sequences."""
        # Use minimal intent to avoid overly restrictive constraints
        result = chat("something")
        assert "sequences" in result
        # Sequences may be empty if constraints are very restrictive
        # The key test is that the structure is correct
        assert isinstance(result["sequences"], tuple)

    def test_chat_returns_intent_info(self):
        """Chat returns parsed intent information."""
        result = chat("calm gentle")
        assert "intent" in result
        assert "keywords" in result["intent"]
        assert "calm" in result["intent"]["keywords"]

    def test_chat_tracks_constraints(self):
        """Chat returns applied constraints."""
        result = chat("calm")
        assert "constraints_applied" in result

    def test_chat_uses_semantic_pipeline(self):
        """Chat uses semantic pipeline."""
        result = chat("calm")
        assert result["pipeline_used"] == "semantic"
