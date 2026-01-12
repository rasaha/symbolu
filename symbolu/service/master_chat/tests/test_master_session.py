"""
Tests for master session store.
"""

import pytest
import asyncio
from datetime import datetime

from symbolu.service.master_chat.bucket_models import (
    BucketCategory,
    BucketEntry,
    MessageSignals,
)
from symbolu.service.master_chat.master_session import (
    MasterSession,
    MasterSessionStore,
    TurnContext,
)


class TestMasterSession:
    """Tests for MasterSession dataclass."""

    def test_create_session(self):
        """Can create master session."""
        session = MasterSession(user_id="user123")

        assert session.user_id == "user123"
        assert session.session_id == "user123"  # Same as user_id for master
        assert session.turn_count == 0
        assert len(session.buckets) > 0  # Default buckets created

    def test_session_creates_default_buckets(self):
        """Session automatically creates default buckets."""
        session = MasterSession(user_id="user123")

        assert "preferences" in session.buckets
        assert "learning" in session.buckets
        assert "actions" in session.buckets

    def test_session_record_turn(self):
        """Recording turn updates count and timestamp."""
        session = MasterSession(user_id="user123")
        initial_time = session.last_activity

        session.record_turn()

        assert session.turn_count == 1
        assert session.last_activity >= initial_time

    def test_session_add_entry(self):
        """Can add entry to bucket."""
        session = MasterSession(user_id="user123")

        entry = BucketEntry(
            entry_id="e1",
            content="Test entry",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )

        result = session.add_entry("learning", entry)

        assert result is True
        assert session.total_entries == 1
        assert session.buckets["learning"].total_entries == 1

    def test_session_add_entry_invalid_bucket(self):
        """Adding to invalid bucket returns False."""
        session = MasterSession(user_id="user123")

        entry = BucketEntry(
            entry_id="e1",
            content="Test",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )

        result = session.add_entry("nonexistent", entry)
        assert result is False

    def test_session_get_bucket_summary(self):
        """Can get bucket summary."""
        session = MasterSession(user_id="user123")

        # Add some entries
        for i in range(3):
            entry = BucketEntry(
                entry_id=f"e{i}",
                content=f"Test {i}",
                source_turn_id="t1",
                timestamp=datetime.utcnow(),
            )
            session.add_entry("learning", entry)

        summary = session.get_bucket_summary()

        assert "learning" in summary
        assert summary["learning"]["total_entries"] == 3

    def test_session_to_dict(self):
        """Session can be serialized."""
        session = MasterSession(user_id="user123")
        session.record_turn()

        data = session.to_dict()

        assert data["user_id"] == "user123"
        assert data["turn_count"] == 1
        assert "bucket_summary" in data


class TestTurnContext:
    """Tests for TurnContext dataclass."""

    def test_turn_context_has_context(self):
        """Check if context was activated."""
        from symbolu.service.master_chat.bucket_models import (
            Bucket,
            ActivatedBucket,
            SignalProfile,
        )

        bucket = Bucket(
            bucket_id="test",
            category=BucketCategory.LEARNING,
            display_name="Test",
            description="Test",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        entry = BucketEntry(
            entry_id="e1",
            content="Test",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )

        activated = ActivatedBucket(
            bucket=bucket,
            activation_score=0.8,
            retrieved_entries=[entry],
            activation_reason="Test",
        )

        context = TurnContext(
            turn_id="turn123",
            activated_buckets=[activated],
            context_text="[Test]\n- Test",
        )

        assert context.has_context() is True

    def test_turn_context_no_context(self):
        """Context without activations."""
        context = TurnContext(
            turn_id="turn123",
            activated_buckets=[],
            context_text="",
        )

        assert context.has_context() is False


class TestMasterSessionStore:
    """Tests for MasterSessionStore class."""

    @pytest.fixture
    def store(self):
        """Create store instance."""
        return MasterSessionStore()

    def test_store_get_or_create_new(self, store):
        """Get or create returns new session."""
        session = store.get_or_create("new_user")

        assert session is not None
        assert session.user_id == "new_user"

    def test_store_get_or_create_existing(self, store):
        """Get or create returns existing session."""
        session1 = store.get_or_create("user123")
        session1.record_turn()  # Modify to verify same instance

        session2 = store.get_or_create("user123")

        assert session2.turn_count == 1  # Same session
        assert session1 is session2

    def test_store_get_nonexistent(self, store):
        """Get returns None for nonexistent user."""
        session = store.get("nonexistent")
        assert session is None

    def test_store_delete(self, store):
        """Can delete session."""
        store.get_or_create("user123")

        result = store.delete("user123")

        assert result is True
        assert store.get("user123") is None

    def test_store_delete_nonexistent(self, store):
        """Delete nonexistent returns False."""
        result = store.delete("nonexistent")
        assert result is False

    def test_store_list_users(self, store):
        """List all users with sessions."""
        store.get_or_create("user1")
        store.get_or_create("user2")
        store.get_or_create("user3")

        users = store.list_users()

        assert len(users) == 3
        assert "user1" in users
        assert "user2" in users

    def test_store_get_context(self, store):
        """Get context for a message."""
        store.get_or_create("user123")

        context = store.get_context(
            user_id="user123",
            message="How is my project going?",
        )

        assert context is not None
        assert context.turn_id
        assert "buckets_activated" in context.routing_metadata

    def test_store_get_context_with_signals(self, store):
        """Get context with signals."""
        store.get_or_create("user123")

        signals = MessageSignals(
            ontology_layers={5: 0.8},
            normalized_entropy=0.5,
        )

        context = store.get_context(
            user_id="user123",
            message="What did I learn?",
            signals=signals,
        )

        assert context.signals is not None

    def test_store_get_context_for_system_prompt(self, store):
        """Get context formatted for system prompt."""
        store.get_or_create("user123")

        prompt = store.get_context_for_system_prompt(
            user_id="user123",
            message="Test message",
        )

        # May be empty if no context, but shouldn't raise
        assert isinstance(prompt, str)

    @pytest.mark.asyncio
    async def test_store_harvest_turn(self, store):
        """Harvest knowledge from turn."""
        store.get_or_create("user123")

        user_msg = "I am a Python developer. I prefer clean code."
        assistant_msg = "Great! Clean code is important."

        facts = await store.harvest_turn(
            user_id="user123",
            user_message=user_msg,
            assistant_response=assistant_msg,
        )

        assert facts >= 0  # May or may not harvest depending on patterns

    def test_store_harvest_turn_sync(self, store):
        """Synchronous harvest."""
        store.get_or_create("user123")

        facts = store.harvest_turn_sync(
            user_id="user123",
            user_message="I decided to use PostgreSQL.",
            assistant_response="Good choice!",
        )

        assert facts >= 0

    def test_store_search_buckets(self, store):
        """Search across buckets."""
        session = store.get_or_create("user123")

        # Add some entries
        entry = BucketEntry(
            entry_id="e1",
            content="I learned Python programming",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )
        session.add_entry("learning", entry)

        results = store.search_buckets(
            user_id="user123",
            query="Python",
        )

        assert len(results) >= 1
        assert "Python" in results[0].content

    def test_store_get_bucket_entries(self, store):
        """Get entries from specific bucket."""
        session = store.get_or_create("user123")

        # Add entries
        for i in range(5):
            entry = BucketEntry(
                entry_id=f"e{i}",
                content=f"Learning entry {i}",
                source_turn_id="t1",
                timestamp=datetime.utcnow(),
                importance_score=i * 0.2,
            )
            session.add_entry("learning", entry)

        # Get by recency
        recent = store.get_bucket_entries(
            user_id="user123",
            bucket_id="learning",
            limit=3,
            sort_by="recency",
        )
        assert len(recent) == 3

        # Get by importance
        important = store.get_bucket_entries(
            user_id="user123",
            bucket_id="learning",
            limit=2,
            sort_by="importance",
        )
        assert len(important) == 2
        assert important[0].importance_score >= important[1].importance_score

    def test_store_get_stats(self, store):
        """Get session statistics."""
        session = store.get_or_create("user123")
        session.record_turn()

        entry = BucketEntry(
            entry_id="e1",
            content="Test",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )
        session.add_entry("learning", entry)

        stats = store.get_stats("user123")

        assert stats["user_id"] == "user123"
        assert stats["turn_count"] == 1
        assert stats["total_entries"] == 1
        assert "entries_by_bucket" in stats

    def test_store_get_stats_nonexistent(self, store):
        """Stats for nonexistent user is empty."""
        stats = store.get_stats("nonexistent")
        assert stats == {}


class TestMasterSessionStoreThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_get_or_create(self):
        """Concurrent get_or_create is thread-safe."""
        import threading

        store = MasterSessionStore()
        results = []

        def worker(user_id):
            session = store.get_or_create(user_id)
            results.append(session.user_id)

        threads = [
            threading.Thread(target=worker, args=(f"user{i}",))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert len(set(results)) == 10  # All unique

    def test_concurrent_same_user(self):
        """Concurrent access to same user is safe."""
        import threading

        store = MasterSessionStore()
        results = []

        def worker():
            session = store.get_or_create("shared_user")
            session.record_turn()
            results.append(session.turn_count)

        threads = [
            threading.Thread(target=worker)
            for _ in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should access same session
        final_session = store.get("shared_user")
        assert final_session.turn_count == 10
