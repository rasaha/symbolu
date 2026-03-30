"""Tests for L6 → L4 Feedback Loop.

Tests cover:
- Signal computation: BOOST/DAMPEN/NEUTRAL from verdict counts
- Parameter adjustments: G_base, k_dv, k_dc, b_p, G_max
- Rate limiting and bounds clamping
- Minimum sample size gating
- Enable/disable toggle
- Replay buffer entry generation
- Engine integration: process_feedback() wiring
"""

import time
import pytest

from symbolu.cloud_controller.action.feedback import (
    FeedbackConfig,
    FeedbackLoop,
    FeedbackSignal,
)
from symbolu.cloud_controller.action.outcome import (
    OutcomeConfig,
    OutcomeRecord,
    OutcomeTracker,
    OutcomeVerdict,
)
from symbolu.cloud_controller.action.rollback import (
    RollbackVerdict,
    RollbackWatch,
)
from symbolu.cloud_controller.shadow.divergence import (
    DivergenceRecord,
    DivergenceType,
    Verdict,
)
from symbolu.cloud_controller.controller import Controller
from symbolu.cloud_controller.action.k8s_actuator import ActuatorConfig, ActuatorMode
from symbolu.cloud_controller.action.policy import PolicyConfig
from symbolu.cloud_controller.action.rollback import RollbackConfig
from symbolu.cloud_controller.recommend.engine import (
    RecommendConfig,
    RecommendEngine,
)
from symbolu.cloud_controller.recommend.confidence import ConfidenceConfig


# ============================================================
# Helpers
# ============================================================

def _make_outcome(verdict, rec_id="rec-1", delta=2, priority=0.5):
    return OutcomeRecord(
        recommendation_id=rec_id,
        deployment="api-gw",
        namespace="prod",
        action_delta=delta,
        action_timestamp=time.time() - 400,
        pre_action_metrics={"latency_p99": 0.3, "cpu": 0.5},
        verdict=verdict,
        verdict_timestamp=time.time(),
        priority_score=priority,
    )


def _make_rollback(verdict, rec_id="rec-1"):
    return RollbackWatch(
        recommendation_id=rec_id,
        deployment="api-gw",
        namespace="prod",
        pre_action_replicas=5,
        post_action_replicas=7,
        pre_action_metrics={"latency_p99": 0.3},
        action_timestamp=time.time() - 200,
        verdict=verdict,
        verdict_timestamp=time.time(),
    )


def _make_divergence(verdict, ctrl_delta=2, hpa_delta=0):
    return DivergenceRecord(
        timestamp=time.time() - 300,
        divergence_type=DivergenceType.CONTROLLER_SCALES_HPA_HOLDS,
        controller_recommendation="scale_out",
        controller_delta=ctrl_delta,
        controller_action_score=0.7,
        controller_pressure=0.6,
        controller_coherence=0.8,
        controller_explanation="test",
        hpa_current=5,
        hpa_desired=5,
        hpa_delta=hpa_delta,
        metrics_snapshot={"cpu": 0.7},
        verdict=verdict,
        verdict_timestamp=time.time(),
    )


# ============================================================
# Signal Computation
# ============================================================

class TestFeedbackSignal:
    def test_positive_outcomes_produce_boost(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(3)]
        result = loop.process(ctrl, outcomes=outcomes)
        assert result.signal == FeedbackSignal.BOOST

    def test_negative_outcomes_produce_dampen(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        outcomes = [_make_outcome(OutcomeVerdict.NEGATIVE) for _ in range(3)]
        result = loop.process(ctrl, outcomes=outcomes)
        assert result.signal == FeedbackSignal.DAMPEN

    def test_mixed_outcomes_produce_neutral(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        outcomes = [
            _make_outcome(OutcomeVerdict.POSITIVE),
            _make_outcome(OutcomeVerdict.NEGATIVE),
        ]
        result = loop.process(ctrl, outcomes=outcomes)
        assert result.signal == FeedbackSignal.NEUTRAL

    def test_oscillations_strongly_dampen(self):
        """Oscillations count as -2 per verdict."""
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        outcomes = [
            _make_outcome(OutcomeVerdict.POSITIVE),
            _make_outcome(OutcomeVerdict.OSCILLATION),
        ]
        result = loop.process(ctrl, outcomes=outcomes)
        # +1 (positive) - 2 (oscillation) = -1, normalized = -0.5 → DAMPEN
        assert result.signal == FeedbackSignal.DAMPEN

    def test_controller_correct_boosts(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        divergences = [
            _make_divergence(Verdict.CONTROLLER_CORRECT) for _ in range(3)
        ]
        result = loop.process(ctrl, divergences=divergences)
        assert result.signal == FeedbackSignal.BOOST

    def test_hpa_correct_dampens(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        divergences = [
            _make_divergence(Verdict.HPA_CORRECT) for _ in range(3)
        ]
        result = loop.process(ctrl, divergences=divergences)
        assert result.signal == FeedbackSignal.DAMPEN

    def test_rollback_dampens(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        rollbacks = [
            _make_rollback(RollbackVerdict.DEGRADED),
            _make_rollback(RollbackVerdict.ROLLED_BACK),
        ]
        result = loop.process(ctrl, rollbacks=rollbacks)
        assert result.signal == FeedbackSignal.DAMPEN

    def test_stable_rollbacks_boost(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        rollbacks = [_make_rollback(RollbackVerdict.STABLE) for _ in range(3)]
        result = loop.process(ctrl, rollbacks=rollbacks)
        assert result.signal == FeedbackSignal.BOOST


# ============================================================
# Parameter Adjustments
# ============================================================

class TestFeedbackAdjustments:
    def test_boost_increases_g_base(self):
        loop = FeedbackLoop(FeedbackConfig(
            min_verdicts_for_adjustment=1,
            gain_boost_step=0.05,
        ))
        ctrl = Controller()
        original_g = ctrl.adaptive_gain.G_base

        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(3)]
        result = loop.process(ctrl, outcomes=outcomes)

        assert result.applied is True
        assert ctrl.adaptive_gain.G_base > original_g

    def test_dampen_decreases_g_base(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        original_g = ctrl.adaptive_gain.G_base

        outcomes = [_make_outcome(OutcomeVerdict.NEGATIVE) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        assert ctrl.adaptive_gain.G_base < original_g

    def test_dampen_increases_k_dv(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        original_k = ctrl.damping.k_dv

        outcomes = [_make_outcome(OutcomeVerdict.NEGATIVE) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        assert ctrl.damping.k_dv > original_k

    def test_dampen_increases_k_dc(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        original_k = ctrl.damping.k_dc

        outcomes = [_make_outcome(OutcomeVerdict.NEGATIVE) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        assert ctrl.damping.k_dc > original_k

    def test_oscillation_reduces_g_max(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        original_gmax = ctrl.adaptive_gain.G_max

        outcomes = [_make_outcome(OutcomeVerdict.OSCILLATION) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        assert ctrl.adaptive_gain.G_max < original_gmax

    def test_boost_opens_plasticity_gate(self):
        """Boost should increase b_p (less negative = more open)."""
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        original_bp = ctrl.plasticity_gate.b_p

        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        assert ctrl.plasticity_gate.b_p > original_bp

    def test_dampen_closes_plasticity_gate(self):
        """Dampen should decrease b_p (more negative = more closed)."""
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        original_bp = ctrl.plasticity_gate.b_p

        outcomes = [_make_outcome(OutcomeVerdict.NEGATIVE) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        assert ctrl.plasticity_gate.b_p < original_bp


# ============================================================
# Rate Limiting and Bounds
# ============================================================

class TestFeedbackRateLimits:
    def test_rate_limited(self):
        """Adjustment should not exceed max_adjustment_rate of current value."""
        loop = FeedbackLoop(FeedbackConfig(
            min_verdicts_for_adjustment=1,
            max_adjustment_rate=0.10,
            gain_boost_step=1.0,  # Huge step — should be rate limited
        ))
        ctrl = Controller()
        original_g = ctrl.adaptive_gain.G_base  # 1.0

        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(5)]
        result = loop.process(ctrl, outcomes=outcomes)

        # Max change = 10% of 1.0 = 0.1
        delta = ctrl.adaptive_gain.G_base - original_g
        assert delta <= original_g * 0.10 + 1e-8

    def test_bounds_clamped(self):
        """Parameters should never exceed configured bounds."""
        loop = FeedbackLoop(FeedbackConfig(
            min_verdicts_for_adjustment=1,
            g_base_bounds=(0.5, 1.5),
        ))
        ctrl = Controller()
        ctrl.adaptive_gain.G_base = 1.48  # Near upper bound

        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(5)]
        loop.process(ctrl, outcomes=outcomes)

        assert ctrl.adaptive_gain.G_base <= 1.5

    def test_no_adjustment_below_min(self):
        """G_base should not go below configured minimum."""
        loop = FeedbackLoop(FeedbackConfig(
            min_verdicts_for_adjustment=1,
            g_base_bounds=(0.5, 3.0),
        ))
        ctrl = Controller()
        ctrl.adaptive_gain.G_base = 0.52  # Near lower bound

        outcomes = [_make_outcome(OutcomeVerdict.NEGATIVE) for _ in range(5)]
        loop.process(ctrl, outcomes=outcomes)

        assert ctrl.adaptive_gain.G_base >= 0.5


# ============================================================
# Gating: min verdicts, enable/disable
# ============================================================

class TestFeedbackGating:
    def test_insufficient_verdicts_skips(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=5))
        ctrl = Controller()
        original_g = ctrl.adaptive_gain.G_base

        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(2)]
        result = loop.process(ctrl, outcomes=outcomes)

        assert result.applied is False
        assert "Insufficient" in result.skip_reason
        assert ctrl.adaptive_gain.G_base == original_g

    def test_disabled_skips(self):
        loop = FeedbackLoop(FeedbackConfig(
            enabled=False,
            min_verdicts_for_adjustment=1,
        ))
        ctrl = Controller()
        original_g = ctrl.adaptive_gain.G_base

        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(5)]
        result = loop.process(ctrl, outcomes=outcomes)

        assert result.applied is False
        assert "disabled" in result.skip_reason.lower()
        assert ctrl.adaptive_gain.G_base == original_g

    def test_neutral_signal_no_adjustments(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()

        outcomes = [
            _make_outcome(OutcomeVerdict.POSITIVE),
            _make_outcome(OutcomeVerdict.NEGATIVE),
        ]
        result = loop.process(ctrl, outcomes=outcomes)

        assert result.signal == FeedbackSignal.NEUTRAL
        assert len(result.adjustments) == 0


# ============================================================
# Verdict Window Pruning
# ============================================================

class TestFeedbackWindowPruning:
    def test_old_verdicts_pruned(self):
        """Verdicts outside the window should be ignored."""
        loop = FeedbackLoop(FeedbackConfig(
            min_verdicts_for_adjustment=1,
            verdict_window_seconds=600,
        ))
        ctrl = Controller()

        # Old outcome (outside window)
        old_outcome = _make_outcome(OutcomeVerdict.POSITIVE)
        old_outcome.verdict_timestamp = time.time() - 1000

        # Recent outcome
        new_outcome = _make_outcome(OutcomeVerdict.NEGATIVE)
        new_outcome.verdict_timestamp = time.time()

        result = loop.process(ctrl, outcomes=[old_outcome, new_outcome])
        # Only the recent one should count
        assert result.positive_count == 0  # Old one pruned
        assert result.negative_count == 1


# ============================================================
# Replay Buffer Entry Generation
# ============================================================

class TestFeedbackReplayEntries:
    def test_meaningful_outcomes_converted(self):
        outcomes = [
            _make_outcome(OutcomeVerdict.POSITIVE),
            _make_outcome(OutcomeVerdict.NEGATIVE),
            _make_outcome(OutcomeVerdict.OSCILLATION),
            _make_outcome(OutcomeVerdict.OVERRIDDEN),
        ]
        entries = FeedbackLoop.to_replay_entries(outcomes)
        assert len(entries) == 4

    def test_neutral_excluded(self):
        outcomes = [
            _make_outcome(OutcomeVerdict.NEUTRAL),
            _make_outcome(OutcomeVerdict.POSITIVE),
        ]
        entries = FeedbackLoop.to_replay_entries(outcomes)
        assert len(entries) == 1

    def test_empty_outcomes(self):
        entries = FeedbackLoop.to_replay_entries([])
        assert entries == []


# ============================================================
# History and Reset
# ============================================================

class TestFeedbackHistory:
    def test_history_recorded(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        assert len(loop.history) == 1
        assert loop.total_adjustments > 0

    def test_adjustment_history(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        adjs = loop.adjustment_history
        assert len(adjs) > 0
        assert adjs[0].signal == "boost"

    def test_reset_clears_all(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        loop.reset()
        assert len(loop.history) == 0
        assert loop.total_adjustments == 0


# ============================================================
# Format Log
# ============================================================

class TestFeedbackAdjustmentFormat:
    def test_format_log(self):
        loop = FeedbackLoop(FeedbackConfig(min_verdicts_for_adjustment=1))
        ctrl = Controller()
        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(3)]
        loop.process(ctrl, outcomes=outcomes)

        adj = loop.adjustment_history[0]
        log = adj.format_log()
        assert "FEEDBACK" in log
        assert "boost" in log


# ============================================================
# Engine Integration
# ============================================================

class TestEngineFeedbackIntegration:
    def _make_engine(self):
        return RecommendEngine(RecommendConfig(
            service="api-gw",
            namespace="prod",
            confidence=ConfidenceConfig(
                action_threshold=0.1,
                coherence_threshold=0.1,
            ),
            actuator=ActuatorConfig(mode=ActuatorMode.DRY_RUN),
            feedback=FeedbackConfig(min_verdicts_for_adjustment=1),
            outcome=OutcomeConfig(evaluation_window_seconds=300),
            rollback=RollbackConfig(execute_rollback=False),
        ))

    def test_process_feedback_returns_result(self):
        engine = self._make_engine()
        ctrl = Controller()
        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(3)]
        result = engine.process_feedback(ctrl, outcomes=outcomes)

        assert result is not None
        assert result["signal"] == "boost"
        assert result["applied"] is True

    def test_process_feedback_not_configured(self):
        engine = RecommendEngine(RecommendConfig(service="svc"))
        ctrl = Controller()
        result = engine.process_feedback(ctrl, outcomes=[])
        assert result is None

    def test_process_feedback_feeds_replay_buffer(self):
        engine = self._make_engine()
        ctrl = Controller()
        outcomes = [
            _make_outcome(OutcomeVerdict.NEGATIVE, priority=0.8),
        ]
        engine.process_feedback(ctrl, outcomes=outcomes)

        # Replay buffer should have an entry
        assert len(ctrl.replay_buffer.buffer) == 1
        assert ctrl.replay_buffer.buffer[0]["verdict"] == "negative"

    def test_reset_clears_feedback(self):
        engine = self._make_engine()
        ctrl = Controller()
        outcomes = [_make_outcome(OutcomeVerdict.POSITIVE) for _ in range(3)]
        engine.process_feedback(ctrl, outcomes=outcomes)

        engine.reset()
        assert len(engine.feedback.history) == 0
