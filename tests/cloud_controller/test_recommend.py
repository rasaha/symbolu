"""Unit tests for Stage 4 — Recommend Mode (Human-in-the-Loop).

Tests cover:
- ConfidenceScorer: threshold evaluation, level classification
- SafetyBounds: clamping, min replicas, cooldown
- WebhookDispatcher: formatting, sending, filtering
- ApprovalManager: lifecycle (pending → approved/dismissed/expired)
- RecommendEngine: end-to-end pipeline
"""

import time
import json
import pytest
from unittest.mock import MagicMock, patch

from symbolu.cloud_controller.controller import Controller, ActionResult
from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.recommend.confidence import (
    ConfidenceConfig,
    ConfidenceLevel,
    ConfidenceScorer,
    ConfidenceResult,
)
from symbolu.cloud_controller.recommend.safety import (
    SafetyConfig,
    SafetyBounds,
    SafetyResult,
)
from symbolu.cloud_controller.recommend.webhook import (
    WebhookConfig,
    WebhookTarget,
    WebhookDispatcher,
    SlackFormatter,
    PagerDutyFormatter,
    OpsGenieFormatter,
)
from symbolu.cloud_controller.recommend.approval import (
    ApprovalState,
    ApprovalManager,
    Recommendation,
)
from symbolu.cloud_controller.recommend.engine import (
    RecommendConfig,
    RecommendEngine,
    RecommendCycleResult,
)


# ============================================================
# Helpers
# ============================================================

def _make_action(delta=0, score=0.0, pressure=0.0, coherence=0.7,
                 recommendation="no_action"):
    """Create an ActionResult for testing."""
    ctrl = Controller()
    result = ctrl.step(
        metrics={"cpu": 0.5, "memory": 0.5, "latency_p99": 0.5, "error_rate": 0.5},
        current_replicas=5,
    )
    result.replica_delta = delta
    result.action_score = score
    result.pressure = pressure
    result.recommendation = recommendation
    if result.coherence is not None:
        result.coherence.coherence = coherence
    return result


# ============================================================
# Confidence Scorer
# ============================================================

class TestConfidenceScorer:
    def test_no_action_no_recommendation(self):
        """delta=0 should never recommend."""
        scorer = ConfidenceScorer()
        action = _make_action(delta=0, score=0.8, coherence=0.9)
        result = scorer.evaluate(action)
        assert result.level == ConfidenceLevel.NONE
        assert result.should_recommend is False

    def test_below_action_threshold(self):
        """Score below threshold should not recommend."""
        scorer = ConfidenceScorer(ConfidenceConfig(action_threshold=0.5))
        action = _make_action(delta=1, score=0.3, coherence=0.9)
        result = scorer.evaluate(action)
        assert result.level == ConfidenceLevel.NONE
        assert result.should_recommend is False
        assert "below threshold" in result.reason

    def test_below_coherence_threshold(self):
        """Coherence below threshold should not recommend."""
        scorer = ConfidenceScorer(ConfidenceConfig(coherence_threshold=0.6))
        action = _make_action(delta=1, score=0.8, coherence=0.4)
        result = scorer.evaluate(action)
        assert result.level == ConfidenceLevel.NONE
        assert result.should_recommend is False
        assert "Coherence" in result.reason

    def test_low_confidence(self):
        """Marginal score/coherence → LOW."""
        scorer = ConfidenceScorer(ConfidenceConfig(
            action_threshold=0.3,
            coherence_threshold=0.5,
            medium_action_threshold=0.5,
            medium_coherence_threshold=0.65,
        ))
        action = _make_action(delta=1, score=0.35, coherence=0.55)
        result = scorer.evaluate(action)
        assert result.level == ConfidenceLevel.LOW
        assert result.should_recommend is True

    def test_medium_confidence(self):
        """Solid score/coherence → MEDIUM."""
        scorer = ConfidenceScorer(ConfidenceConfig(
            medium_action_threshold=0.5,
            medium_coherence_threshold=0.65,
            high_action_threshold=0.7,
            high_coherence_threshold=0.8,
        ))
        action = _make_action(delta=1, score=0.6, coherence=0.7)
        result = scorer.evaluate(action)
        assert result.level == ConfidenceLevel.MEDIUM
        assert result.should_recommend is True

    def test_high_confidence(self):
        """Strong score/coherence → HIGH."""
        scorer = ConfidenceScorer(ConfidenceConfig(
            high_action_threshold=0.7,
            high_coherence_threshold=0.8,
        ))
        action = _make_action(delta=2, score=0.85, coherence=0.92)
        result = scorer.evaluate(action)
        assert result.level == ConfidenceLevel.HIGH
        assert result.should_recommend is True

    def test_negative_action_score_uses_abs(self):
        """Negative action score (scale-in) should use absolute value."""
        scorer = ConfidenceScorer(ConfidenceConfig(action_threshold=0.3))
        action = _make_action(delta=-1, score=-0.5, coherence=0.7)
        result = scorer.evaluate(action)
        assert result.should_recommend is True
        assert result.action_score == 0.5


# ============================================================
# Safety Bounds
# ============================================================

class TestSafetyBounds:
    def test_no_delta_passes_through(self):
        """Zero delta should pass through unchanged."""
        bounds = SafetyBounds()
        result = bounds.check(current_replicas=10, proposed_delta=0)
        assert result.clamped_delta == 0
        assert result.was_clamped is False

    def test_scale_out_within_bounds(self):
        """Scale-out within 50% should pass through."""
        bounds = SafetyBounds()
        result = bounds.check(current_replicas=10, proposed_delta=4)
        assert result.clamped_delta == 4
        assert result.was_clamped is False
        assert result.target_replicas == 14

    def test_scale_out_clamped(self):
        """Scale-out exceeding 50% should be clamped."""
        bounds = SafetyBounds()
        result = bounds.check(current_replicas=10, proposed_delta=8)
        assert result.clamped_delta == 5  # 50% of 10
        assert result.was_clamped is True
        assert result.target_replicas == 15
        assert "clamped" in result.clamp_reason.lower()

    def test_scale_in_within_bounds(self):
        """Scale-in within 25% should pass through."""
        bounds = SafetyBounds()
        result = bounds.check(current_replicas=10, proposed_delta=-2)
        assert result.clamped_delta == -2
        assert result.was_clamped is False

    def test_scale_in_clamped(self):
        """Scale-in exceeding 25% should be clamped."""
        bounds = SafetyBounds()
        result = bounds.check(current_replicas=10, proposed_delta=-5)
        assert result.clamped_delta == -2  # 25% of 10
        assert result.was_clamped is True

    def test_min_replicas_enforced(self):
        """Should never go below min_replicas."""
        bounds = SafetyBounds(SafetyConfig(min_replicas=3))
        result = bounds.check(current_replicas=4, proposed_delta=-2)
        # 4 - 2 = 2, below min of 3 → clamp
        assert result.target_replicas >= 3

    def test_min_replicas_at_boundary(self):
        """At min_replicas, scale-in should be zero."""
        bounds = SafetyBounds(SafetyConfig(min_replicas=5))
        result = bounds.check(current_replicas=5, proposed_delta=-1)
        assert result.clamped_delta == 0 or result.target_replicas >= 5

    def test_cooldown_detected(self):
        """Should detect cooldown after recorded action."""
        bounds = SafetyBounds(SafetyConfig(cooldown_seconds=60.0))
        now = time.time()
        bounds.record_action(now)
        result = bounds.check(current_replicas=10, proposed_delta=2, current_time=now + 10)
        assert result.in_cooldown is True
        assert result.cooldown_remaining == pytest.approx(50.0, abs=1.0)

    def test_cooldown_expired(self):
        """Should not be in cooldown after cooldown period."""
        bounds = SafetyBounds(SafetyConfig(cooldown_seconds=60.0))
        now = time.time()
        bounds.record_action(now)
        result = bounds.check(current_replicas=10, proposed_delta=2, current_time=now + 61)
        assert result.in_cooldown is False

    def test_reset_clears_cooldown(self):
        """Reset should clear cooldown."""
        bounds = SafetyBounds()
        bounds.record_action()
        bounds.reset()
        assert bounds.last_action_time is None

    def test_small_replica_count_min_delta_one(self):
        """With few replicas, max delta should be at least 1."""
        bounds = SafetyBounds()
        # 50% of 1 = 0.5, int = 0, but max(1, ...) ensures at least 1
        result = bounds.check(current_replicas=1, proposed_delta=3)
        assert result.clamped_delta >= 1


# ============================================================
# Webhook Formatters
# ============================================================

class TestWebhookFormatters:
    def test_slack_format(self):
        """Slack formatter should produce text field."""
        fmt = SlackFormatter()
        payload = fmt.format_recommendation(
            service="api-gw", namespace="prod",
            current_replicas=5, recommended_delta=2, target_replicas=7,
            confidence="high", signals={"cpu": 0.84, "latency_p99": 0.92},
            explanation="test", recommendation_id="abc123",
        )
        assert "text" in payload
        assert "api-gw" in payload["text"]
        assert "HIGH" in payload["text"]
        assert "+2" in payload["text"]

    def test_pagerduty_format(self):
        """PagerDuty formatter should produce Events API v2 structure."""
        fmt = PagerDutyFormatter()
        payload = fmt.format_recommendation(
            service="api-gw", namespace="prod",
            current_replicas=5, recommended_delta=2, target_replicas=7,
            confidence="high", signals={"cpu": 0.84},
            explanation="test", recommendation_id="abc123",
        )
        assert "routing_key" in payload
        assert "payload" in payload
        assert payload["payload"]["severity"] == "warning"
        assert "abc123" in payload["dedup_key"]

    def test_pagerduty_info_severity_for_non_high(self):
        """PagerDuty should use 'info' severity for non-high confidence."""
        fmt = PagerDutyFormatter()
        payload = fmt.format_recommendation(
            service="api-gw", namespace="prod",
            current_replicas=5, recommended_delta=2, target_replicas=7,
            confidence="medium", signals={},
            explanation="test", recommendation_id="abc123",
        )
        assert payload["payload"]["severity"] == "info"

    def test_opsgenie_format(self):
        """OpsGenie formatter should produce Alert API structure."""
        fmt = OpsGenieFormatter()
        payload = fmt.format_recommendation(
            service="api-gw", namespace="prod",
            current_replicas=5, recommended_delta=-1, target_replicas=4,
            confidence="low", signals={},
            explanation="test", recommendation_id="abc123",
        )
        assert "message" in payload
        assert "Scale In" in payload["message"]
        assert payload["priority"] == "P4"
        assert "abc123" in payload["alias"]

    def test_opsgenie_high_confidence_priority(self):
        """OpsGenie should use P3 for high confidence."""
        fmt = OpsGenieFormatter()
        payload = fmt.format_recommendation(
            service="api-gw", namespace="prod",
            current_replicas=5, recommended_delta=2, target_replicas=7,
            confidence="high", signals={},
            explanation="test", recommendation_id="abc123",
        )
        assert payload["priority"] == "P3"


class TestWebhookDispatcher:
    def test_no_configs_returns_zero(self):
        """Dispatcher with no configs should send nothing."""
        dispatcher = WebhookDispatcher()
        sent = dispatcher.send(
            service="api-gw", namespace="prod",
            current_replicas=5, recommended_delta=2, target_replicas=7,
            confidence="high", signals={},
            explanation="test", recommendation_id="abc123",
        )
        assert sent == 0

    def test_min_confidence_filtering(self):
        """Should skip webhooks when confidence is below min_confidence."""
        config = WebhookConfig(
            target=WebhookTarget.SLACK,
            url="http://localhost:9999/webhook",
            min_confidence="high",
        )
        dispatcher = WebhookDispatcher([config])

        with patch.object(WebhookDispatcher, '_post', return_value=True) as mock_post:
            sent = dispatcher.send(
                service="api-gw", namespace="prod",
                current_replicas=5, recommended_delta=2, target_replicas=7,
                confidence="medium", signals={},
                explanation="test", recommendation_id="abc123",
            )
            assert sent == 0
            mock_post.assert_not_called()

    def test_sends_when_confidence_meets_minimum(self):
        """Should send when confidence meets min_confidence."""
        config = WebhookConfig(
            target=WebhookTarget.SLACK,
            url="http://localhost:9999/webhook",
            min_confidence="medium",
        )
        dispatcher = WebhookDispatcher([config])

        with patch.object(WebhookDispatcher, '_post', return_value=True) as mock_post:
            sent = dispatcher.send(
                service="api-gw", namespace="prod",
                current_replicas=5, recommended_delta=2, target_replicas=7,
                confidence="high", signals={},
                explanation="test", recommendation_id="abc123",
            )
            assert sent == 1
            mock_post.assert_called_once()

    def test_post_failure_returns_zero(self):
        """Failed webhook should not count as sent."""
        config = WebhookConfig(
            target=WebhookTarget.SLACK,
            url="http://localhost:9999/webhook",
        )
        dispatcher = WebhookDispatcher([config])

        with patch.object(WebhookDispatcher, '_post', return_value=False):
            sent = dispatcher.send(
                service="api-gw", namespace="prod",
                current_replicas=5, recommended_delta=2, target_replicas=7,
                confidence="high", signals={},
                explanation="test", recommendation_id="abc123",
            )
            assert sent == 0

    def test_generic_target_sends_raw(self):
        """Generic target should send raw JSON payload."""
        config = WebhookConfig(
            target=WebhookTarget.GENERIC,
            url="http://localhost:9999/webhook",
        )
        dispatcher = WebhookDispatcher([config])

        with patch.object(WebhookDispatcher, '_post', return_value=True) as mock_post:
            dispatcher.send(
                service="api-gw", namespace="prod",
                current_replicas=5, recommended_delta=2, target_replicas=7,
                confidence="high", signals={"cpu": 0.8},
                explanation="test", recommendation_id="abc123",
            )
            payload = mock_post.call_args[0][1]
            assert payload["service"] == "api-gw"
            assert payload["recommended_delta"] == 2


# ============================================================
# Approval Manager
# ============================================================

def _make_confidence_result(level=ConfidenceLevel.HIGH, should_recommend=True):
    return ConfidenceResult(
        level=level, action_score=0.8, coherence=0.9,
        should_recommend=should_recommend, reason="test",
    )


def _make_safety_result(original=2, clamped=2, target=7):
    return SafetyResult(
        original_delta=original, clamped_delta=clamped,
        target_replicas=target, was_clamped=False,
        clamp_reason="", in_cooldown=False, cooldown_remaining=0.0,
    )


class TestApprovalManager:
    def test_create_recommendation(self):
        """Should create a pending recommendation."""
        manager = ApprovalManager()
        action = _make_action(delta=2, score=0.8)
        rec = manager.create(
            service="api-gw", namespace="prod",
            current_replicas=5, original_delta=2,
            clamped_delta=2, target_replicas=7,
            confidence=_make_confidence_result(),
            safety=_make_safety_result(),
            action=action, explanation="test",
        )
        assert rec.state == ApprovalState.PENDING
        assert rec.is_pending
        assert manager.pending_count == 1

    def test_approve_recommendation(self):
        """Should transition pending → approved."""
        manager = ApprovalManager()
        action = _make_action(delta=2, score=0.8)
        rec = manager.create(
            service="api-gw", namespace="prod",
            current_replicas=5, original_delta=2,
            clamped_delta=2, target_replicas=7,
            confidence=_make_confidence_result(),
            safety=_make_safety_result(),
            action=action, explanation="test",
        )

        approved = manager.approve(rec.id, by="ops-team")
        assert approved is not None
        assert approved.state == ApprovalState.APPROVED
        assert approved.resolved_by == "ops-team"
        assert approved.resolved_at is not None

    def test_dismiss_recommendation(self):
        """Should transition pending → dismissed."""
        manager = ApprovalManager()
        action = _make_action(delta=2, score=0.8)
        rec = manager.create(
            service="api-gw", namespace="prod",
            current_replicas=5, original_delta=2,
            clamped_delta=2, target_replicas=7,
            confidence=_make_confidence_result(),
            safety=_make_safety_result(),
            action=action, explanation="test",
        )

        dismissed = manager.dismiss(rec.id, by="ops-team", reason="spike ending")
        assert dismissed is not None
        assert dismissed.state == ApprovalState.DISMISSED
        assert dismissed.resolve_reason == "spike ending"

    def test_approve_nonexistent_returns_none(self):
        """Approving unknown ID should return None."""
        manager = ApprovalManager()
        assert manager.approve("nonexistent") is None

    def test_approve_already_approved_returns_none(self):
        """Double-approve should return None."""
        manager = ApprovalManager()
        action = _make_action(delta=2, score=0.8)
        rec = manager.create(
            service="api-gw", namespace="prod",
            current_replicas=5, original_delta=2,
            clamped_delta=2, target_replicas=7,
            confidence=_make_confidence_result(),
            safety=_make_safety_result(),
            action=action, explanation="test",
        )
        manager.approve(rec.id)
        assert manager.approve(rec.id) is None

    def test_expire_stale(self):
        """Recommendations past TTL should expire."""
        manager = ApprovalManager(ttl_seconds=60.0)
        action = _make_action(delta=2, score=0.8)
        rec = manager.create(
            service="api-gw", namespace="prod",
            current_replicas=5, original_delta=2,
            clamped_delta=2, target_replicas=7,
            confidence=_make_confidence_result(),
            safety=_make_safety_result(),
            action=action, explanation="test",
        )

        # Not expired yet
        expired = manager.expire_stale(current_time=rec.created_at + 30)
        assert len(expired) == 0

        # Expired
        expired = manager.expire_stale(current_time=rec.created_at + 61)
        assert len(expired) == 1
        assert expired[0].state == ApprovalState.EXPIRED

    def test_history_tracks_resolved(self):
        """History should contain all resolved recommendations."""
        manager = ApprovalManager()
        action = _make_action(delta=2, score=0.8)

        rec1 = manager.create(
            service="svc1", namespace="prod",
            current_replicas=5, original_delta=2,
            clamped_delta=2, target_replicas=7,
            confidence=_make_confidence_result(),
            safety=_make_safety_result(),
            action=action, explanation="test",
        )
        rec2 = manager.create(
            service="svc2", namespace="prod",
            current_replicas=5, original_delta=2,
            clamped_delta=2, target_replicas=7,
            confidence=_make_confidence_result(),
            safety=_make_safety_result(),
            action=action, explanation="test",
        )

        manager.approve(rec1.id)
        manager.dismiss(rec2.id)
        assert len(manager.history) == 2

    def test_format_summary(self):
        """Recommendation should produce readable summary."""
        manager = ApprovalManager()
        action = _make_action(delta=2, score=0.8)
        rec = manager.create(
            service="api-gw", namespace="prod",
            current_replicas=5, original_delta=2,
            clamped_delta=2, target_replicas=7,
            confidence=_make_confidence_result(),
            safety=_make_safety_result(),
            action=action, explanation="test",
        )
        summary = rec.format_summary()
        assert "api-gw" in summary
        assert "SCALE OUT" in summary
        assert "+2" in summary

    def test_reset_clears_all(self):
        """Reset should clear all state."""
        manager = ApprovalManager()
        action = _make_action(delta=2, score=0.8)
        manager.create(
            service="api-gw", namespace="prod",
            current_replicas=5, original_delta=2,
            clamped_delta=2, target_replicas=7,
            confidence=_make_confidence_result(),
            safety=_make_safety_result(),
            action=action, explanation="test",
        )
        manager.reset()
        assert manager.pending_count == 0
        assert len(manager.history) == 0


# ============================================================
# Recommend Engine (Integration)
# ============================================================

class TestRecommendEngine:
    def test_no_action_no_recommendation(self):
        """No controller action should produce no recommendation."""
        engine = RecommendEngine()
        action = _make_action(delta=0, score=0.0)
        result = engine.evaluate(action, current_replicas=5)
        assert result.recommendation is None
        assert result.suppressed is True

    def test_low_score_suppressed(self):
        """Below-threshold score should suppress recommendation."""
        engine = RecommendEngine(RecommendConfig(
            confidence=ConfidenceConfig(action_threshold=0.5),
        ))
        action = _make_action(delta=1, score=0.2, coherence=0.8)
        result = engine.evaluate(action, current_replicas=5)
        assert result.recommendation is None
        assert result.suppressed is True

    def test_high_confidence_creates_recommendation(self):
        """High confidence should create a recommendation."""
        engine = RecommendEngine(RecommendConfig(
            service="api-gw", namespace="prod",
        ))
        action = _make_action(
            delta=2, score=0.85, coherence=0.9,
            recommendation="scale_out_2",
        )
        result = engine.evaluate(action, current_replicas=5)
        assert result.recommendation is not None
        assert result.recommendation.state == ApprovalState.PENDING
        assert result.recommendation.clamped_delta == 2
        assert result.recommendation.target_replicas == 7
        assert result.suppressed is False

    def test_safety_clamps_delta(self):
        """Safety bounds should clamp excessive scale-out."""
        engine = RecommendEngine(RecommendConfig(
            safety=SafetyConfig(max_scale_out_fraction=0.5),
            confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1),
        ))
        action = _make_action(delta=10, score=0.8, coherence=0.9)
        result = engine.evaluate(action, current_replicas=4)
        assert result.recommendation is not None
        # 50% of 4 = 2
        assert result.recommendation.clamped_delta == 2
        assert result.safety.was_clamped is True

    def test_cooldown_suppresses(self):
        """Recommendation during cooldown should be suppressed."""
        engine = RecommendEngine(RecommendConfig(
            safety=SafetyConfig(cooldown_seconds=300.0),
            confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1),
        ))
        # First recommendation
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        result1 = engine.evaluate(action, current_replicas=5)
        assert result1.recommendation is not None

        # Approve → starts cooldown
        engine.approve(result1.recommendation.id, by="test")

        # Second recommendation during cooldown
        result2 = engine.evaluate(action, current_replicas=7)
        assert result2.recommendation is None
        assert result2.suppressed is True
        assert "cooldown" in result2.suppress_reason.lower()

    def test_approve_starts_cooldown(self):
        """Approving a recommendation should start the cooldown."""
        engine = RecommendEngine(RecommendConfig(
            safety=SafetyConfig(cooldown_seconds=120.0),
            confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1),
        ))
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        result = engine.evaluate(action, current_replicas=5)

        engine.approve(result.recommendation.id)
        assert engine.safety.last_action_time is not None

    def test_dismiss_does_not_start_cooldown(self):
        """Dismissing a recommendation should not start cooldown."""
        engine = RecommendEngine(RecommendConfig(
            confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1),
        ))
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        result = engine.evaluate(action, current_replicas=5)

        engine.dismiss(result.recommendation.id)
        assert engine.safety.last_action_time is None

    def test_expiry_in_evaluate_cycle(self):
        """Stale recommendations should be expired during evaluate."""
        engine = RecommendEngine(RecommendConfig(
            approval_ttl_seconds=0.01,
            confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1),
        ))
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        result1 = engine.evaluate(action, current_replicas=5)
        assert result1.recommendation is not None

        time.sleep(0.02)

        # Next evaluate should expire the stale one
        action2 = _make_action(delta=0, score=0.0)
        result2 = engine.evaluate(action2, current_replicas=5)
        assert len(result2.expired) >= 1
        assert result2.expired[0].state == ApprovalState.EXPIRED

    def test_reset_clears_engine(self):
        """Reset should clear all engine state."""
        engine = RecommendEngine(RecommendConfig(
            confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1),
        ))
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        engine.evaluate(action, current_replicas=5)
        assert engine.pending_count == 1

        engine.reset()
        assert engine.pending_count == 0
        assert engine.safety.last_action_time is None

    def test_webhook_integration(self):
        """Webhooks should be dispatched when recommendation is created."""
        config = RecommendConfig(
            service="api-gw",
            namespace="prod",
            confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1),
            webhooks=[
                WebhookConfig(target=WebhookTarget.SLACK, url="http://localhost:9999"),
            ],
        )
        engine = RecommendEngine(config)

        with patch.object(WebhookDispatcher, '_post', return_value=True):
            action = _make_action(delta=2, score=0.8, coherence=0.9)
            result = engine.evaluate(action, current_replicas=5)
            assert result.recommendation is not None
            assert result.recommendation.webhooks_sent == 1

    def test_pending_list(self):
        """Should track multiple pending recommendations."""
        engine = RecommendEngine(RecommendConfig(
            confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1),
            safety=SafetyConfig(cooldown_seconds=0),  # No cooldown
        ))
        for _ in range(3):
            action = _make_action(delta=1, score=0.5, coherence=0.7)
            engine.evaluate(action, current_replicas=5)

        assert engine.pending_count == 3
        assert len(engine.pending) == 3
