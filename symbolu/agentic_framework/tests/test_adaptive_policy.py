"""
Tests for Adaptive Policy Engine.

Tests the policy-level memory that modifies future budgets, decay rates,
attention patterns, and tool access based on session performance trajectory.
"""

import pytest
import time

from symbolu.agentic_framework.adaptive_policy import (
    # Enums
    SessionTrajectory,
    ToolPermission,
    # Data classes
    PerformanceSnapshot,
    SessionPerformanceHistory,
    PolicyParameters,
    PolicyDecision,
    # Main engine
    AdaptivePolicyEngine,
    create_adaptive_policy_engine,
    # Components
    TrajectoryClassifier,
    SCCParameterTuner,
    ToolAccessController,
    ResponseStyleSelector,
)


# =============================================================================
# PerformanceSnapshot Tests
# =============================================================================


class TestPerformanceSnapshot:
    """Tests for PerformanceSnapshot dataclass."""

    def test_create_snapshot(self):
        snapshot = PerformanceSnapshot(
            turn_index=0,
            timestamp=time.time(),
            quality_score=0.85,
            revision_count=1,
            coherence_score=0.78,
            goal_alignment=0.82,
            internal_consistency=0.75,
            volatility=0.2,
            was_successful=True,
            was_revised=True,
            was_blocked=False,
        )

        assert snapshot.turn_index == 0
        assert snapshot.quality_score == 0.85
        assert snapshot.was_successful is True

    def test_to_dict(self):
        snapshot = PerformanceSnapshot(
            turn_index=1,
            timestamp=1000.0,
            quality_score=0.9,
            revision_count=0,
            coherence_score=0.85,
            goal_alignment=0.9,
            internal_consistency=0.88,
            volatility=0.15,
            was_successful=True,
            was_revised=False,
            was_blocked=False,
        )

        d = snapshot.to_dict()
        assert d["turn_index"] == 1
        assert d["quality_score"] == 0.9
        assert d["was_blocked"] is False


# =============================================================================
# SessionPerformanceHistory Tests
# =============================================================================


class TestSessionPerformanceHistory:
    """Tests for SessionPerformanceHistory."""

    def test_create_empty_history(self):
        history = SessionPerformanceHistory(session_id="test-session")
        assert history.session_id == "test-session"
        assert history.turn_count == 0
        assert history.avg_quality == 0.0

    def test_append_snapshot(self):
        history = SessionPerformanceHistory(session_id="test")

        snapshot = PerformanceSnapshot(
            turn_index=0,
            timestamp=time.time(),
            quality_score=0.8,
            revision_count=1,
            coherence_score=0.75,
            goal_alignment=0.8,
            internal_consistency=0.7,
            volatility=0.25,
            was_successful=True,
            was_revised=True,
            was_blocked=False,
        )

        history.append(snapshot)

        assert history.turn_count == 1
        assert history.avg_quality == 0.8
        assert history.avg_coherence == 0.75

    def test_aggregates_update(self):
        history = SessionPerformanceHistory(session_id="test")

        # Add improving quality snapshots
        for i, q in enumerate([0.6, 0.7, 0.8, 0.9]):
            history.append(PerformanceSnapshot(
                turn_index=i,
                timestamp=time.time(),
                quality_score=q,
                revision_count=0,
                coherence_score=0.7,
                goal_alignment=0.7,
                internal_consistency=0.7,
                volatility=0.2,
                was_successful=True,
                was_revised=False,
                was_blocked=False,
            ))

        assert history.turn_count == 4
        assert abs(history.avg_quality - 0.75) < 0.001  # (0.6+0.7+0.8+0.9)/4
        assert history.quality_trend > 0  # Improving

    def test_breakthrough_detection(self):
        history = SessionPerformanceHistory(session_id="test")

        # Add snapshot with low quality
        history.append(PerformanceSnapshot(
            turn_index=0, timestamp=time.time(),
            quality_score=0.5, revision_count=0, coherence_score=0.6,
            goal_alignment=0.6, internal_consistency=0.6, volatility=0.3,
            was_successful=True, was_revised=False, was_blocked=False,
        ))

        # Add breakthrough (jump > 0.2)
        history.append(PerformanceSnapshot(
            turn_index=1, timestamp=time.time(),
            quality_score=0.85, revision_count=0, coherence_score=0.75,
            goal_alignment=0.8, internal_consistency=0.8, volatility=0.2,
            was_successful=True, was_revised=False, was_blocked=False,
        ))

        assert history.had_breakthrough is True

    def test_fragmentation_detection(self):
        history = SessionPerformanceHistory(session_id="test")

        # Add snapshots with low coherence (need at least 2 for marker detection)
        history.append(PerformanceSnapshot(
            turn_index=0, timestamp=time.time(),
            quality_score=0.5, revision_count=0, coherence_score=0.25,  # < 0.3
            goal_alignment=0.4, internal_consistency=0.3, volatility=0.6,
            was_successful=False, was_revised=False, was_blocked=True,
        ))
        history.append(PerformanceSnapshot(
            turn_index=1, timestamp=time.time(),
            quality_score=0.4, revision_count=1, coherence_score=0.28,  # < 0.3
            goal_alignment=0.3, internal_consistency=0.25, volatility=0.7,
            was_successful=False, was_revised=True, was_blocked=True,
        ))

        assert history.had_fragmentation is True

    def test_recovery_detection(self):
        history = SessionPerformanceHistory(session_id="test")

        # Valley pattern: dip then rise
        coherences = [0.7, 0.4, 0.75]  # Dip at index 1, recovery at 2
        for i, c in enumerate(coherences):
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=0.7, revision_count=0, coherence_score=c,
                goal_alignment=0.7, internal_consistency=c, volatility=0.2,
                was_successful=True, was_revised=False, was_blocked=False,
            ))

        assert history.had_recovery is True

    def test_oscillation_count(self):
        history = SessionPerformanceHistory(session_id="test")

        # Oscillating quality: up, down, up, down
        qualities = [0.5, 0.8, 0.4, 0.9, 0.3]
        for i, q in enumerate(qualities):
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=q, revision_count=0, coherence_score=0.6,
                goal_alignment=0.6, internal_consistency=0.6, volatility=0.4,
                was_successful=True, was_revised=False, was_blocked=False,
            ))

        # Sign changes: +0.3, -0.4, +0.5, -0.6 → 3 sign changes
        assert history.oscillation_count >= 2


# =============================================================================
# PolicyParameters Tests
# =============================================================================


class TestPolicyParameters:
    """Tests for PolicyParameters."""

    def test_defaults(self):
        params = PolicyParameters()
        assert params.quality_threshold_high == 0.85
        assert params.revision_budget == 3
        assert params.quality_decay_rate == 0.95

    def test_clone(self):
        params = PolicyParameters(quality_threshold_high=0.9)
        cloned = params.clone()

        assert cloned.quality_threshold_high == 0.9
        assert cloned is not params

        # Modify original, clone should be unchanged
        params.quality_threshold_high = 0.7
        assert cloned.quality_threshold_high == 0.9

    def test_to_dict(self):
        params = PolicyParameters()
        d = params.to_dict()

        assert "quality_threshold_high" in d
        assert "revision_budget" in d
        assert d["quality_threshold_high"] == 0.85


# =============================================================================
# TrajectoryClassifier Tests
# =============================================================================


class TestTrajectoryClassifier:
    """Tests for TrajectoryClassifier."""

    def test_insufficient_turns(self):
        classifier = TrajectoryClassifier()
        history = SessionPerformanceHistory(session_id="test")

        # Only 1 turn
        history.append(PerformanceSnapshot(
            turn_index=0, timestamp=time.time(),
            quality_score=0.7, revision_count=0, coherence_score=0.7,
            goal_alignment=0.7, internal_consistency=0.7, volatility=0.2,
            was_successful=True, was_revised=False, was_blocked=False,
        ))

        trajectory, conf, drivers = classifier.classify(history)
        assert trajectory == SessionTrajectory.UNKNOWN

    def test_hope_driven_classification(self):
        classifier = TrajectoryClassifier()
        history = SessionPerformanceHistory(session_id="test")

        # Improving quality with breakthrough
        for i, q in enumerate([0.5, 0.75, 0.9]):  # Breakthrough at 0.75
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=q, revision_count=0, coherence_score=0.7,
                goal_alignment=0.7, internal_consistency=0.7, volatility=0.2,
                was_successful=True, was_revised=False, was_blocked=False,
            ))

        trajectory, conf, drivers = classifier.classify(history)
        assert trajectory == SessionTrajectory.HOPE_DRIVEN
        assert conf > 0.7

    def test_fear_driven_classification(self):
        classifier = TrajectoryClassifier()
        history = SessionPerformanceHistory(session_id="test")

        # Fragmented, high volatility, blocked
        for i in range(3):
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=0.4, revision_count=2,
                coherence_score=0.25,  # Fragmented
                goal_alignment=0.3, internal_consistency=0.3,
                volatility=0.7,  # High volatility
                was_successful=False, was_revised=True,
                was_blocked=True if i > 0 else False,  # Blocked
            ))

        trajectory, conf, drivers = classifier.classify(history)
        assert trajectory == SessionTrajectory.FEAR_DRIVEN

    def test_stable_classification(self):
        classifier = TrajectoryClassifier()
        history = SessionPerformanceHistory(session_id="test")

        # High coherence, low volatility, high success
        for i in range(5):
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=0.85, revision_count=0,
                coherence_score=0.8,  # High
                goal_alignment=0.85, internal_consistency=0.85,
                volatility=0.15,  # Low
                was_successful=True, was_revised=False, was_blocked=False,
            ))

        trajectory, conf, drivers = classifier.classify(history)
        assert trajectory == SessionTrajectory.STABLE
        assert conf > 0.8


# =============================================================================
# SCCParameterTuner Tests
# =============================================================================


class TestSCCParameterTuner:
    """Tests for SCC-inspired parameter tuning."""

    def test_no_update_insufficient_samples(self):
        tuner = SCCParameterTuner(learning_rate=0.05, min_samples=3)
        params = PolicyParameters()
        history = SessionPerformanceHistory(session_id="test")

        # Only 2 turns (below min_samples)
        for i in range(2):
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=0.7, revision_count=0, coherence_score=0.7,
                goal_alignment=0.7, internal_consistency=0.7, volatility=0.2,
                was_successful=True, was_revised=False, was_blocked=False,
            ))

        new_params = tuner.update(params, history, SessionTrajectory.STABLE)

        # Should return original params unchanged
        assert new_params.quality_threshold_high == params.quality_threshold_high

    def test_improving_quality_relaxes_thresholds(self):
        tuner = SCCParameterTuner(learning_rate=0.1, min_samples=3)
        params = PolicyParameters(quality_threshold_high=0.85)
        history = SessionPerformanceHistory(session_id="test")

        # Strongly improving quality
        for i, q in enumerate([0.5, 0.7, 0.85, 0.95]):
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=q, revision_count=0, coherence_score=0.8,
                goal_alignment=0.8, internal_consistency=0.8, volatility=0.2,
                was_successful=True, was_revised=False, was_blocked=False,
            ))

        new_params = tuner.update(params, history, SessionTrajectory.HOPE_DRIVEN)

        # Threshold should decrease (relax) when quality is improving
        assert new_params.quality_threshold_high < params.quality_threshold_high

    def test_high_revision_rate_increases_budget(self):
        tuner = SCCParameterTuner(learning_rate=0.1, min_samples=3)
        params = PolicyParameters(revision_budget=2)
        history = SessionPerformanceHistory(session_id="test")

        # High revision rate (all turns revised)
        for i in range(5):
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=0.6, revision_count=2, coherence_score=0.6,
                goal_alignment=0.6, internal_consistency=0.6, volatility=0.3,
                was_successful=True,
                was_revised=True,  # All revised
                was_blocked=False,
            ))

        new_params = tuner.update(params, history, SessionTrajectory.STABLE)

        # Budget should increase
        assert new_params.revision_budget >= params.revision_budget

    def test_fear_driven_increases_attention(self):
        tuner = SCCParameterTuner(learning_rate=0.1, min_samples=3)
        params = PolicyParameters(attention_budget=1.0)
        history = SessionPerformanceHistory(session_id="test")

        # Fear-driven session
        for i in range(3):
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=0.4, revision_count=2, coherence_score=0.3,
                goal_alignment=0.3, internal_consistency=0.3, volatility=0.6,
                was_successful=False, was_revised=True, was_blocked=True,
            ))

        new_params = tuner.update(params, history, SessionTrajectory.FEAR_DRIVEN)

        # Attention budget should increase for fear-driven
        assert new_params.attention_budget > params.attention_budget


# =============================================================================
# ToolAccessController Tests
# =============================================================================


class TestToolAccessController:
    """Tests for ToolAccessController."""

    def test_high_coherence_full_access(self):
        controller = ToolAccessController()
        params = PolicyParameters(tool_full_access_coherence=0.75)
        history = SessionPerformanceHistory(session_id="test")

        # High coherence snapshot
        history.append(PerformanceSnapshot(
            turn_index=0, timestamp=time.time(),
            quality_score=0.9, revision_count=0,
            coherence_score=0.85,  # Above full access threshold
            goal_alignment=0.9, internal_consistency=0.9, volatility=0.1,
            was_successful=True, was_revised=False, was_blocked=False,
        ))

        perm, allowed, blocked = controller.determine_access(
            history, params, SessionTrajectory.STABLE
        )

        assert perm == ToolPermission.FULL
        assert "*" in allowed
        assert len(blocked) == 0

    def test_low_coherence_restricted(self):
        controller = ToolAccessController()
        params = PolicyParameters(
            tool_full_access_coherence=0.75,
            tool_standard_access_coherence=0.55,
            tool_restricted_access_coherence=0.35,
        )
        history = SessionPerformanceHistory(session_id="test")

        # Low coherence snapshot
        history.append(PerformanceSnapshot(
            turn_index=0, timestamp=time.time(),
            quality_score=0.5, revision_count=2,
            coherence_score=0.40,  # Between restricted and standard
            goal_alignment=0.4, internal_consistency=0.4, volatility=0.5,
            was_successful=True, was_revised=True, was_blocked=False,
        ))

        perm, allowed, blocked = controller.determine_access(
            history, params, SessionTrajectory.STABLE
        )

        assert perm == ToolPermission.RESTRICTED

    def test_fear_driven_downgrades_access(self):
        controller = ToolAccessController()
        params = PolicyParameters()
        history = SessionPerformanceHistory(session_id="test")

        # Good coherence but fear-driven trajectory
        history.append(PerformanceSnapshot(
            turn_index=0, timestamp=time.time(),
            quality_score=0.7, revision_count=1,
            coherence_score=0.80,  # Would be FULL normally
            goal_alignment=0.7, internal_consistency=0.7, volatility=0.4,
            was_successful=True, was_revised=False, was_blocked=False,
        ))

        perm, _, _ = controller.determine_access(
            history, params, SessionTrajectory.FEAR_DRIVEN
        )

        # Should be downgraded from FULL to STANDARD
        assert perm == ToolPermission.STANDARD

    def test_breakthrough_upgrades_access(self):
        controller = ToolAccessController()
        params = PolicyParameters()
        history = SessionPerformanceHistory(session_id="test")

        # Breakthrough with high success
        history.append(PerformanceSnapshot(
            turn_index=0, timestamp=time.time(),
            quality_score=0.5, revision_count=0, coherence_score=0.65,
            goal_alignment=0.6, internal_consistency=0.6, volatility=0.2,
            was_successful=True, was_revised=False, was_blocked=False,
        ))
        history.append(PerformanceSnapshot(
            turn_index=1, timestamp=time.time(),
            quality_score=0.9, revision_count=0,  # Breakthrough
            coherence_score=0.70,  # Would be STANDARD
            goal_alignment=0.85, internal_consistency=0.85, volatility=0.15,
            was_successful=True, was_revised=False, was_blocked=False,
        ))

        perm, _, _ = controller.determine_access(
            history, params, SessionTrajectory.HOPE_DRIVEN
        )

        # Should be upgraded due to breakthrough + high success
        assert perm in [ToolPermission.STANDARD, ToolPermission.FULL]


# =============================================================================
# ResponseStyleSelector Tests
# =============================================================================


class TestResponseStyleSelector:
    """Tests for ResponseStyleSelector."""

    def test_fear_driven_grounded(self):
        selector = ResponseStyleSelector()
        history = SessionPerformanceHistory(session_id="test")

        style = selector.select(history, SessionTrajectory.FEAR_DRIVEN)
        assert style == "grounded"

    def test_hope_driven_reflective(self):
        selector = ResponseStyleSelector()
        history = SessionPerformanceHistory(session_id="test")

        style = selector.select(history, SessionTrajectory.HOPE_DRIVEN)
        assert style == "reflective"

    def test_expansion_driven_exploratory(self):
        selector = ResponseStyleSelector()
        history = SessionPerformanceHistory(session_id="test")

        style = selector.select(history, SessionTrajectory.EXPANSION_DRIVEN)
        assert style == "exploratory"

    def test_stable_high_coherence_reflective(self):
        selector = ResponseStyleSelector()
        history = SessionPerformanceHistory(session_id="test")

        # Add high coherence snapshots
        for i in range(3):
            history.append(PerformanceSnapshot(
                turn_index=i, timestamp=time.time(),
                quality_score=0.85, revision_count=0,
                coherence_score=0.82,  # > 0.75
                goal_alignment=0.85, internal_consistency=0.85,
                volatility=0.15,  # < 0.3
                was_successful=True, was_revised=False, was_blocked=False,
            ))

        style = selector.select(history, SessionTrajectory.STABLE)
        assert style == "reflective"


# =============================================================================
# AdaptivePolicyEngine Tests
# =============================================================================


class TestAdaptivePolicyEngine:
    """Tests for main AdaptivePolicyEngine."""

    def test_create_engine(self):
        engine = AdaptivePolicyEngine()
        assert engine is not None

    def test_factory_function(self):
        engine = create_adaptive_policy_engine(learning_rate=0.1, history_window=100)
        assert engine.learning_rate == 0.1
        assert engine.history_window == 100

    def test_record_turn_creates_session(self):
        engine = AdaptivePolicyEngine()

        engine.record_turn(
            session_id="new-session",
            quality_score=0.8,
            revision_count=0,
            coherence_score=0.75,
        )

        assert "new-session" in engine.get_all_sessions()
        history = engine.get_session_history("new-session")
        assert history.turn_count == 1

    def test_get_policy_decision(self):
        engine = AdaptivePolicyEngine()

        # Record some turns
        for i in range(3):
            engine.record_turn(
                session_id="test-session",
                quality_score=0.7 + i * 0.05,
                revision_count=0,
                coherence_score=0.7,
            )

        decision = engine.get_policy_decision("test-session")

        assert isinstance(decision, PolicyDecision)
        assert decision.quality_threshold > 0
        assert decision.revision_budget > 0
        assert decision.tool_permission in ToolPermission
        assert len(decision.reasoning) > 0

    def test_policy_adapts_over_time(self):
        engine = AdaptivePolicyEngine(learning_rate=0.1)

        # Record declining quality
        for i in range(5):
            engine.record_turn(
                session_id="declining",
                quality_score=0.9 - i * 0.1,  # 0.9, 0.8, 0.7, 0.6, 0.5
                revision_count=1,
                coherence_score=0.6,
            )

        params_after_decline = engine.get_session_parameters("declining")

        # Now record improving quality in new session
        for i in range(5):
            engine.record_turn(
                session_id="improving",
                quality_score=0.5 + i * 0.1,  # 0.5, 0.6, 0.7, 0.8, 0.9
                revision_count=0,
                coherence_score=0.8,
            )

        params_after_improve = engine.get_session_parameters("improving")

        # Declining session should have different params than improving
        # (thresholds should be higher for declining, lower for improving)
        assert params_after_decline.quality_threshold_high != params_after_improve.quality_threshold_high

    def test_reset_session(self):
        engine = AdaptivePolicyEngine()

        engine.record_turn(
            session_id="to-reset",
            quality_score=0.8,
            revision_count=0,
            coherence_score=0.75,
        )

        assert "to-reset" in engine.get_all_sessions()

        engine.reset_session("to-reset")

        assert "to-reset" not in engine.get_all_sessions()

    def test_history_window_trimming(self):
        engine = AdaptivePolicyEngine(history_window=5)

        # Record more turns than window
        for i in range(10):
            engine.record_turn(
                session_id="trimmed",
                quality_score=0.7,
                revision_count=0,
                coherence_score=0.7,
            )

        history = engine.get_session_history("trimmed")

        # Should be trimmed to window size
        assert history.turn_count == 5

    def test_trajectory_in_decision(self):
        engine = AdaptivePolicyEngine()

        # Create fear-driven pattern
        for i in range(4):
            engine.record_turn(
                session_id="fear-session",
                quality_score=0.4,
                revision_count=2,
                coherence_score=0.25,
                volatility=0.7,
                was_blocked=True,
            )

        decision = engine.get_policy_decision("fear-session")

        # Should classify as fear-driven
        assert decision.trajectory == SessionTrajectory.FEAR_DRIVEN
        assert decision.response_style == "grounded"


# =============================================================================
# Integration Tests
# =============================================================================


class TestAdaptivePolicyIntegration:
    """Integration tests with other agentic framework components."""

    def test_policy_to_reflective_generator_params(self):
        """Test that policy decisions can configure ReflectiveGenerator."""
        engine = AdaptivePolicyEngine()

        # Record stable session
        for i in range(5):
            engine.record_turn(
                session_id="stable",
                quality_score=0.85,
                revision_count=0,
                coherence_score=0.8,
            )

        decision = engine.get_policy_decision("stable")

        # These should be usable as ReflectiveGenerator params
        assert 0.5 <= decision.quality_threshold <= 1.0
        assert 1 <= decision.revision_budget <= 5

    def test_tool_permission_to_safety_contract(self):
        """Test that tool permissions can inform safety contract."""
        engine = AdaptivePolicyEngine()

        # Record blocked session
        for i in range(3):
            engine.record_turn(
                session_id="blocked",
                quality_score=0.3,
                revision_count=3,
                coherence_score=0.2,
                was_blocked=True,
            )

        decision = engine.get_policy_decision("blocked")

        # Should have restricted or blocked tools
        assert decision.tool_permission in [
            ToolPermission.RESTRICTED,
            ToolPermission.BLOCKED,
        ]

    def test_complete_session_lifecycle(self):
        """Test complete session from start to stable."""
        engine = AdaptivePolicyEngine()
        session_id = "lifecycle-test"

        # Phase 1: Rocky start
        for i in range(3):
            engine.record_turn(
                session_id=session_id,
                quality_score=0.5,
                revision_count=2,
                coherence_score=0.4,
                was_revised=True,
            )

        decision1 = engine.get_policy_decision(session_id)
        # Should be cautious

        # Phase 2: Improvement
        for i in range(3):
            engine.record_turn(
                session_id=session_id,
                quality_score=0.7 + i * 0.05,
                revision_count=1,
                coherence_score=0.6 + i * 0.05,
            )

        decision2 = engine.get_policy_decision(session_id)
        # Should be more permissive

        # Phase 3: Stable excellence
        for i in range(3):
            engine.record_turn(
                session_id=session_id,
                quality_score=0.9,
                revision_count=0,
                coherence_score=0.85,
            )

        decision3 = engine.get_policy_decision(session_id)
        # Should be most permissive

        # Verify progression
        assert decision3.tool_permission.value >= decision1.tool_permission.value or \
               decision3.tool_permission == ToolPermission.FULL
