"""
Tests for CoherenceState and CoherenceEngine.

Validates:
- State creation and updates
- Window trimming behavior
- Coherence score computation
- Integration of all coherence components
"""

import pytest
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.core.coherence.coherence_engine import CoherenceEngine


class MockRoutingPlan:
    """Mock RoutingPlan for testing."""

    def __init__(self, tier="hybrid", domain="general", tension=0.5):
        self.tier = tier
        self.domain = domain
        self.long_arc_tension = tension


class TestCoherenceState:
    """Test CoherenceState dataclass behavior."""

    def test_creation_with_defaults(self):
        """Test CoherenceState creation with default values."""
        state = CoherenceState(convo_id="test_convo", turn_index=0)

        assert state.convo_id == "test_convo"
        assert state.turn_index == 0
        assert len(state.tier_history) == 0
        assert len(state.domain_history) == 0
        assert state.coherence_score == 0.0
        assert state.persona_drift_score == 0.0
        assert state.semantic_stability_score == 0.0

    def test_window_trim_maintains_recent_entries(self):
        """Test that window_trim keeps only most recent entries."""
        state = CoherenceState(convo_id="test", turn_index=10)

        # Add 15 entries
        state.tier_history = ["lower"] * 15
        state.domain_history = ["task"] * 15
        state.mapper_profile_history = [{"arc_mode": "none"}] * 15

        # Trim to window of 10
        state.window_trim(window=10)

        assert len(state.tier_history) == 10
        assert len(state.domain_history) == 10
        assert len(state.mapper_profile_history) == 10

    def test_window_trim_no_truncation_when_under_limit(self):
        """Test window_trim doesn't truncate when history is within limit."""
        state = CoherenceState(convo_id="test", turn_index=5)

        state.tier_history = ["lower"] * 5
        state.domain_history = ["task"] * 5

        state.window_trim(window=10)

        assert len(state.tier_history) == 5
        assert len(state.domain_history) == 5

    def test_get_history_length(self):
        """Test get_history_length returns correct count."""
        state = CoherenceState(convo_id="test", turn_index=3)

        state.domain_history = ["task", "finance", "therapy"]

        assert state.get_history_length() == 3


class TestCoherenceEngine:
    """Test CoherenceEngine behavior."""

    def test_engine_initialization(self):
        """Test CoherenceEngine initialization."""
        engine = CoherenceEngine(window=10)

        assert engine.window == 10

    def test_update_state_first_turn(self):
        """Test update_state with no previous state (first turn)."""
        engine = CoherenceEngine(window=10)

        routing_plan = MockRoutingPlan(tier="lower", domain="task", tension=0.3)
        mapper_profile = {
            "resolution_level": "high",
            "arc_mode": "none",
            "detail_bias": 0.7,
            "practical_bias": 0.8,
            "reflective_bias": 0.3,
        }
        temporal_summary = {
            "bhava_id": 5,
            "bhava_direction": "upward",
            "smi": 0.6,
            "flags": {
                "recovery_trajectory": True,
                "tension_corridor": False,
            },
        }
        semantic_signature = {
            "has_symbolic": True,
            "has_practical": True,
            "has_mirror": False,
        }

        state = engine.update_state(
            prev_state=None,
            convo_id="test_convo",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        assert state.convo_id == "test_convo"
        assert state.turn_index == 0
        assert len(state.tier_history) == 1
        assert state.tier_history[0] == "lower"
        assert state.domain_history[0] == "task"
        assert state.bhava_id_history[0] == 5
        assert state.coherence_score >= 0.0
        assert state.coherence_score <= 1.0

    def test_update_state_accumulates_history(self):
        """Test that update_state accumulates history across turns."""
        engine = CoherenceEngine(window=10)

        # First turn
        routing_plan_1 = MockRoutingPlan(tier="lower", domain="task", tension=0.3)
        mapper_profile_1 = {
            "resolution_level": "high",
            "arc_mode": "none",
            "detail_bias": 0.7,
            "practical_bias": 0.8,
            "reflective_bias": 0.3,
        }
        temporal_summary_1 = {
            "bhava_id": 5,
            "bhava_direction": "upward",
            "smi": 0.6,
            "flags": {"recovery_trajectory": True},
        }
        semantic_sig_1 = {"has_symbolic": True}

        state_1 = engine.update_state(
            prev_state=None,
            convo_id="test",
            turn_index=0,
            routing_plan=routing_plan_1,
            mapper_profile=mapper_profile_1,
            temporal_summary=temporal_summary_1,
            semantic_signature=semantic_sig_1,
        )

        # Second turn
        routing_plan_2 = MockRoutingPlan(tier="hybrid", domain="finance", tension=0.5)
        mapper_profile_2 = {
            "resolution_level": "medium",
            "arc_mode": "temporal",
            "detail_bias": 0.5,
            "practical_bias": 0.6,
            "reflective_bias": 0.5,
        }
        temporal_summary_2 = {
            "bhava_id": 6,
            "bhava_direction": "upward",
            "smi": 0.7,
            "flags": {"recovery_trajectory": True},
        }
        semantic_sig_2 = {"has_symbolic": True}

        state_2 = engine.update_state(
            prev_state=state_1,
            convo_id="test",
            turn_index=1,
            routing_plan=routing_plan_2,
            mapper_profile=mapper_profile_2,
            temporal_summary=temporal_summary_2,
            semantic_signature=semantic_sig_2,
        )

        assert len(state_2.tier_history) == 2
        assert state_2.tier_history == ["lower", "hybrid"]
        assert state_2.domain_history == ["task", "finance"]
        assert state_2.bhava_id_history == [5, 6]

    def test_coherence_score_decreases_with_high_drift(self):
        """Test that coherence score decreases with high persona drift."""
        engine = CoherenceEngine(window=10)

        # Create scenario with high drift: rapid domain changes
        state = None
        domains = ["task", "therapy", "finance", "identity", "task", "spiritual"]

        for i, domain in enumerate(domains):
            routing_plan = MockRoutingPlan(tier="hybrid", domain=domain, tension=0.5)
            mapper_profile = {
                "resolution_level": "medium",
                "arc_mode": "none" if i % 2 == 0 else "identity",
                "detail_bias": 0.5,
                "practical_bias": 0.5,
                "reflective_bias": 0.5,
            }
            temporal_summary = {
                "bhava_id": i,
                "bhava_direction": "upward" if i % 2 == 0 else "downward",
                "smi": 0.5,
                "flags": {},
            }
            semantic_sig = {"has_symbolic": True}

            state = engine.update_state(
                prev_state=state,
                convo_id="test",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_sig,
            )

        # High drift should result in lower coherence
        assert state.persona_drift_score > 0.3  # Significant drift
        assert state.coherence_score < 0.8  # Lower coherence due to drift

    def test_coherence_score_increases_with_stability(self):
        """Test that coherence score increases with stable patterns."""
        engine = CoherenceEngine(window=10)

        # Create scenario with low drift: stable domain, bhava, mapper
        state = None

        for i in range(6):
            routing_plan = MockRoutingPlan(tier="hybrid", domain="task", tension=0.5)
            mapper_profile = {
                "resolution_level": "medium",
                "arc_mode": "none",
                "detail_bias": 0.5,
                "practical_bias": 0.5,
                "reflective_bias": 0.5,
            }
            temporal_summary = {
                "bhava_id": 5,
                "bhava_direction": "stable",
                "smi": 0.5,
                "flags": {"recovery_trajectory": True},
            }
            semantic_sig = {"has_symbolic": True}

            state = engine.update_state(
                prev_state=state,
                convo_id="test",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_sig,
            )

        # Low drift should result in higher coherence
        assert state.persona_drift_score < 0.3  # Low drift
        assert state.coherence_score > 0.5  # Higher coherence

    def test_window_trimming_in_update_state(self):
        """Test that engine respects window size during updates."""
        engine = CoherenceEngine(window=5)

        state = None

        # Add 10 turns
        for i in range(10):
            routing_plan = MockRoutingPlan(tier="hybrid", domain="task", tension=0.5)
            mapper_profile = {"resolution_level": "medium", "arc_mode": "none"}
            temporal_summary = {"bhava_id": i, "bhava_direction": "stable"}
            semantic_sig = {"has_symbolic": True}

            state = engine.update_state(
                prev_state=state,
                convo_id="test",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_sig,
            )

        # Should only retain last 5 turns
        assert len(state.tier_history) == 5
        assert len(state.domain_history) == 5
        assert len(state.bhava_id_history) == 5

    def test_coherence_score_bounds(self):
        """Test that all coherence scores remain in [0, 1] bounds."""
        engine = CoherenceEngine(window=10)

        state = None

        # Create extreme scenarios
        for i in range(10):
            routing_plan = MockRoutingPlan(
                tier="lower" if i % 3 == 0 else "upper",
                domain=["task", "therapy", "finance"][i % 3],
                tension=float(i % 10) / 10.0,
            )
            mapper_profile = {
                "resolution_level": ["low", "medium", "high"][i % 3],
                "arc_mode": ["none", "identity", "temporal"][i % 3],
                "detail_bias": float(i % 10) / 10.0,
                "practical_bias": float(9 - i % 10) / 10.0,
                "reflective_bias": 0.5,
            }
            temporal_summary = {
                "bhava_id": i % 10,
                "bhava_direction": ["upward", "downward", "stable"][i % 3],
                "smi": float(i % 10) / 10.0,
                "flags": {
                    "tension_corridor": i % 2 == 0,
                    "recovery_trajectory": i % 3 == 0,
                },
            }
            semantic_sig = {
                "has_symbolic": i % 2 == 0,
                "has_practical": i % 3 == 0,
            }

            state = engine.update_state(
                prev_state=state,
                convo_id="test",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_sig,
            )

        # All scores must be in [0, 1]
        assert 0.0 <= state.coherence_score <= 1.0
        assert 0.0 <= state.persona_drift_score <= 1.0
        assert 0.0 <= state.semantic_stability_score <= 1.0
        assert 0.0 <= state.mapper_volatility_score <= 1.0
        assert 0.0 <= state.temporal_arc_score <= 1.0
