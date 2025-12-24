"""Tests for session state manager.

Part 7.2: Session State Manager
"""

import pytest
from symbolu.presentation import (
    VrittiDistribution,
    SessionContext,
)
from symbolu.presentation.session import SessionStateManager


class TestSessionStateManager:
    """Tests for SessionStateManager."""

    def test_initial_state(self):
        """Initial state should be empty."""
        mgr = SessionStateManager()
        ctx = mgr.get_context()

        assert ctx.turn_count == 0
        assert ctx.consecutive_low_scores == 0
        assert ctx.consecutive_high_scores == 0
        assert ctx.consecutive_low_motion == 0
        assert ctx.previous_dominant_vritti is None
        assert ctx.accumulated_smrti == 0.0

    def test_update_increments_turn(self):
        """Each update should increment turn count."""
        mgr = SessionStateManager()

        ctx1 = mgr.update(score=0.5, motion=0.2, dominant_vritti="pramana")
        assert ctx1.turn_count == 1

        ctx2 = mgr.update(score=0.6, motion=0.3, dominant_vritti="pramana")
        assert ctx2.turn_count == 2

    def test_consecutive_low_scores(self):
        """Should track consecutive low scores."""
        mgr = SessionStateManager()

        # High scores
        mgr.update(score=0.9, motion=0.5, dominant_vritti="pramana")
        mgr.update(score=0.85, motion=0.5, dominant_vritti="pramana")

        ctx = mgr.get_context()
        assert ctx.consecutive_low_scores == 0
        assert ctx.consecutive_high_scores == 2

        # Now low scores
        mgr.update(score=0.3, motion=0.5, dominant_vritti="viparyaya")
        mgr.update(score=0.2, motion=0.5, dominant_vritti="viparyaya")

        ctx = mgr.get_context()
        assert ctx.consecutive_low_scores == 2
        assert ctx.consecutive_high_scores == 0

    def test_consecutive_low_motion(self):
        """Should track consecutive low motion."""
        mgr = SessionStateManager()

        mgr.update(score=0.5, motion=0.05, dominant_vritti="smrti")
        mgr.update(score=0.5, motion=0.03, dominant_vritti="smrti")
        mgr.update(score=0.5, motion=0.08, dominant_vritti="smrti")

        ctx = mgr.get_context()
        assert ctx.consecutive_low_motion == 3

        # Break the streak
        mgr.update(score=0.5, motion=0.5, dominant_vritti="pramana")
        ctx = mgr.get_context()
        assert ctx.consecutive_low_motion == 0

    def test_previous_dominant_vritti(self):
        """Should track previous dominant vritti."""
        mgr = SessionStateManager()

        mgr.update(score=0.5, motion=0.2, dominant_vritti="pramana")
        ctx = mgr.get_context()
        assert ctx.previous_dominant_vritti is None  # Only 1 turn

        mgr.update(score=0.5, motion=0.2, dominant_vritti="vikalpa")
        ctx = mgr.get_context()
        assert ctx.previous_dominant_vritti == "pramana"

        mgr.update(score=0.5, motion=0.2, dominant_vritti="smrti")
        ctx = mgr.get_context()
        assert ctx.previous_dominant_vritti == "vikalpa"

    def test_accumulated_smrti(self):
        """Should track accumulated smrti from vritti."""
        mgr = SessionStateManager()

        vritti = VrittiDistribution(smrti=0.3)
        ctx = mgr.update(
            score=0.5,
            motion=0.2,
            dominant_vritti="smrti",
            vritti=vritti,
        )
        assert ctx.accumulated_smrti == 0.3

    def test_reset_clears_state(self):
        """Reset should clear all state."""
        mgr = SessionStateManager()

        mgr.update(score=0.3, motion=0.1, dominant_vritti="viparyaya")
        mgr.update(score=0.2, motion=0.05, dominant_vritti="viparyaya")
        assert mgr.turn_count == 2

        mgr.reset()

        assert mgr.turn_count == 0
        ctx = mgr.get_context()
        assert ctx.turn_count == 0
        assert ctx.consecutive_low_scores == 0

    def test_history_window_limit(self):
        """History should be limited to window size."""
        mgr = SessionStateManager(history_window=5)

        # Add more than window size
        for i in range(10):
            mgr.update(score=0.3, motion=0.05, dominant_vritti="test")

        assert mgr.turn_count == 10
        # Internal history should be trimmed
        # We can verify via consecutive counts
        ctx = mgr.get_context()
        assert ctx.consecutive_low_scores == 5  # Limited by window

    def test_streak_breaks_correctly(self):
        """Streaks should break when threshold crossed."""
        mgr = SessionStateManager()

        # Build a streak of 3 low scores
        mgr.update(score=0.2, motion=0.5, dominant_vritti="test")
        mgr.update(score=0.3, motion=0.5, dominant_vritti="test")
        mgr.update(score=0.1, motion=0.5, dominant_vritti="test")

        ctx = mgr.get_context()
        assert ctx.consecutive_low_scores == 3

        # Add high score to break streak
        mgr.update(score=0.7, motion=0.5, dominant_vritti="test")
        ctx = mgr.get_context()
        assert ctx.consecutive_low_scores == 0

        # Add another low score
        mgr.update(score=0.4, motion=0.5, dominant_vritti="test")
        ctx = mgr.get_context()
        assert ctx.consecutive_low_scores == 1


class TestSessionStateProperties:
    """Tests for SessionStateManager properties."""

    def test_turn_count_property(self):
        """turn_count property should match internal state."""
        mgr = SessionStateManager()
        assert mgr.turn_count == 0

        mgr.update(score=0.5, motion=0.2, dominant_vritti="test")
        assert mgr.turn_count == 1

    def test_history_window_property(self):
        """history_window property should return configured value."""
        mgr = SessionStateManager(history_window=15)
        assert mgr.history_window == 15
