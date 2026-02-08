"""
Tests for Coherence Tracker Component

Tests the 7-metric coherence monitoring system:
- CoherenceMetrics dataclass
- CoherenceState management
- CoherenceEngine operations
- Intervention detection
- Drift tracking
"""

import pytest

from symbolu.agentic_framework.coherence_tracker import (
    CoherenceMetrics,
    CoherenceState,
    CoherenceEngine,
    create_initial_state,
    create_initial_metrics,
)
from symbolu.agentic_framework.memory_store import create_turn_snapshot


class TestCoherenceMetrics:
    """Tests for CoherenceMetrics dataclass."""

    def test_coherence_metrics_creation(self):
        """Test basic CoherenceMetrics creation."""
        metrics = CoherenceMetrics(
            internal_consistency=0.9,
            prediction_reversal_risk=0.1,
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.88,
        )
        assert metrics.internal_consistency == 0.9
        assert metrics.identity_stability == 0.95
        assert metrics.overall_coherence == 0.88

    def test_coherence_metrics_to_dict(self):
        """Test CoherenceMetrics serialization."""
        metrics = CoherenceMetrics(
            internal_consistency=0.85,
            prediction_reversal_risk=0.15,
            volatility_index=0.1,
            goal_alignment=0.8,
            factual_alignment=0.85,
            identity_stability=0.9,
            drift_magnitude=0.05,
            drift_direction="stable",
            overall_coherence=0.85,
        )
        d = metrics.to_dict()

        assert d["internal_consistency"] == 0.85
        assert d["overall_coherence"] == 0.85
        assert "drift_direction" in d

    def test_create_initial_metrics(self):
        """Test initial metrics creation."""
        metrics = create_initial_metrics()

        assert metrics.internal_consistency == 0.8
        assert metrics.prediction_reversal_risk == 0.2
        assert metrics.drift_direction == "stable"
        assert metrics.overall_coherence == 0.75


class TestCoherenceState:
    """Tests for CoherenceState dataclass."""

    def test_coherence_state_creation(self):
        """Test basic CoherenceState creation."""
        state = create_initial_state("test-session")
        assert state.session_id == "test-session"
        assert state.current_turn == 0
        assert len(state.overall_coherence_history) == 0

    def test_coherence_state_with_metrics(self):
        """Test CoherenceState with current metrics."""
        metrics = create_initial_metrics()
        state = CoherenceState(
            session_id="test",
            current_turn=5,
            current_metrics=metrics,
        )
        assert state.current_turn == 5
        assert state.current_metrics.overall_coherence == 0.75

    def test_window_trim(self):
        """Test window trimming."""
        state = create_initial_state("test")

        # Add many entries
        for i in range(15):
            state.overall_coherence_history.append(0.8 + i * 0.01)

        state.window_trim(window=10)

        assert len(state.overall_coherence_history) == 10

    def test_get_average_coherence(self):
        """Test average coherence calculation."""
        state = create_initial_state("test")
        state.overall_coherence_history = [0.7, 0.8, 0.9]

        avg = state.get_average_coherence()
        assert abs(avg - 0.8) < 0.01

    def test_get_average_coherence_empty(self):
        """Test average coherence with empty history."""
        state = create_initial_state("test")
        assert state.get_average_coherence() == 0.0

    def test_get_recent_trend(self):
        """Test recent trend detection."""
        state = create_initial_state("test")

        # Improving trend
        state.overall_coherence_history = [0.6, 0.7, 0.8]
        assert state.get_recent_trend() == "improving"

        # Degrading trend
        state.overall_coherence_history = [0.8, 0.7, 0.6]
        assert state.get_recent_trend() == "degrading"

        # Stable trend
        state.overall_coherence_history = [0.75, 0.76, 0.75]
        assert state.get_recent_trend() == "stable"

    def test_to_dict(self):
        """Test CoherenceState serialization."""
        state = create_initial_state("test")
        state.overall_coherence_history = [0.7, 0.8, 0.9]

        d = state.to_dict()

        assert d["session_id"] == "test"
        assert d["current_turn"] == 0
        assert "average_coherence" in d
        assert "recent_trend" in d


class TestCoherenceEngine:
    """Tests for CoherenceEngine class."""

    def test_engine_creation(self):
        """Test CoherenceEngine creation."""
        engine = CoherenceEngine()
        assert engine.window == 10

    def test_engine_custom_window(self):
        """Test CoherenceEngine with custom window."""
        engine = CoherenceEngine(window=20)
        assert engine.window == 20

    def test_update_metrics(self):
        """Test updating coherence metrics."""
        engine = CoherenceEngine()
        state = create_initial_state("test")

        turn = create_turn_snapshot(1, "Question?", "Response.", quality_score=0.85)
        new_state = engine.update(state, turn)

        assert new_state.current_turn == 1
        assert new_state.current_metrics is not None
        assert len(new_state.overall_coherence_history) == 1

    def test_multiple_updates(self):
        """Test multiple metric updates."""
        engine = CoherenceEngine()
        state = create_initial_state("test")

        for i in range(5):
            turn = create_turn_snapshot(
                i + 1,
                f"Question {i}",
                f"Response {i}",
                quality_score=0.8 + i * 0.02,
            )
            state = engine.update(state, turn)

        assert state.current_turn == 5
        assert len(state.overall_coherence_history) == 5

    def test_window_enforcement(self):
        """Test that window size is enforced."""
        engine = CoherenceEngine(window=3)
        state = create_initial_state("test")

        for i in range(5):
            turn = create_turn_snapshot(i + 1, f"Q{i}", f"A{i}", quality_score=0.8)
            state = engine.update(state, turn)

        # Only last 3 should be in history
        assert len(state.overall_coherence_history) == 3

    def test_immutability(self):
        """Test that update returns new state, doesn't modify original."""
        engine = CoherenceEngine()
        state = create_initial_state("test")

        turn = create_turn_snapshot(1, "Q", "A", quality_score=0.8)
        new_state = engine.update(state, turn)

        # Original unchanged
        assert state.current_turn == 0
        # New state updated
        assert new_state.current_turn == 1

    def test_should_intervene_healthy(self):
        """Test intervention check for healthy state."""
        engine = CoherenceEngine()
        state = create_initial_state("test")

        # Update with good quality turns
        for i in range(3):
            turn = create_turn_snapshot(i + 1, f"Q{i}", f"A{i}", quality_score=0.9)
            state = engine.update(state, turn)

        should_intervene, reason = engine.should_intervene(state)
        assert should_intervene is False

    def test_should_intervene_low_coherence(self):
        """Test intervention triggered by low coherence."""
        engine = CoherenceEngine()
        state = create_initial_state("test")

        # Manually set low coherence
        state.overall_coherence_history = [0.3, 0.25, 0.2]
        state.current_metrics = CoherenceMetrics(
            internal_consistency=0.3,
            prediction_reversal_risk=0.8,
            volatility_index=0.7,
            goal_alignment=0.3,
            factual_alignment=0.4,
            identity_stability=0.4,
            drift_magnitude=0.5,
            drift_direction="degrading",
            overall_coherence=0.3,
        )

        should_intervene, reason = engine.should_intervene(state)
        assert should_intervene is True
        assert "too low" in reason.lower() or "coherence" in reason.lower()

    def test_get_summary(self):
        """Test getting coherence summary."""
        engine = CoherenceEngine()
        state = create_initial_state("test")

        for i in range(3):
            turn = create_turn_snapshot(i + 1, f"Q{i}", f"A{i}", quality_score=0.8)
            state = engine.update(state, turn)

        summary = engine.get_summary(state)

        assert "session_id" in summary
        assert "current_turn" in summary
        assert "current_coherence" in summary


class TestCoherenceEngineIntegration:
    """Integration tests for CoherenceEngine."""

    def test_full_conversation_tracking(self):
        """Test tracking a full conversation."""
        engine = CoherenceEngine()
        state = create_initial_state("conv-001")

        # Simulate a conversation
        turns = [
            ("What is Python?", "Python is a programming language.", 0.9),
            ("What makes it readable?", "Python uses indentation for blocks.", 0.85),
            ("Is it good for beginners?", "Yes, Python is great for beginners.", 0.88),
        ]

        for i, (user, assistant, quality) in enumerate(turns):
            turn = create_turn_snapshot(i + 1, user, assistant, quality_score=quality)
            state = engine.update(state, turn)

        # Check state
        assert state.current_turn == 3
        assert len(state.overall_coherence_history) == 3
        assert state.get_average_coherence() > 0.5

    def test_quality_degradation_tracking(self):
        """Test tracking quality degradation."""
        engine = CoherenceEngine()
        state = create_initial_state("test")

        # Start with good quality
        state = engine.update(state, create_turn_snapshot(1, "Q1", "Detailed response.", 0.9))
        state = engine.update(state, create_turn_snapshot(2, "Q2", "Another good response.", 0.85))

        # Quality drops
        state = engine.update(state, create_turn_snapshot(3, "Q3", "ok", 0.4))
        state = engine.update(state, create_turn_snapshot(4, "Q4", ".", 0.2))

        # Should show declining trend in history
        assert len(state.overall_coherence_history) == 4
