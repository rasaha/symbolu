"""Tests for tier-specific configurations.

Part 5: Tier-Specific Behavior
Tests that each tier behaves according to its design philosophy.
"""

import pytest
from symbolu.presentation import (
    DeliveryMode,
    ConfidenceIndicator,
    VrittiDistribution,
    SessionContext,
    SignalBundle,
    PresentationEngine,
    PresentationTier,
    CONSUMER_CONFIG,
    ENTERPRISE_SEARCH_CONFIG,
    ENTERPRISE_CHAT_CONFIG,
    DEVELOPMENT_CONFIG,
    get_config_for_tier,
)


class TestTierLookup:
    """Tests for get_config_for_tier function."""

    def test_all_tiers_mapped(self):
        """All tier enums should return configs."""
        for tier in PresentationTier:
            config = get_config_for_tier(tier)
            assert config is not None

    def test_correct_configs_returned(self):
        """Correct config should be returned for each tier."""
        assert get_config_for_tier(PresentationTier.CONSUMER) == CONSUMER_CONFIG
        assert (
            get_config_for_tier(PresentationTier.ENTERPRISE_SEARCH)
            == ENTERPRISE_SEARCH_CONFIG
        )
        assert (
            get_config_for_tier(PresentationTier.ENTERPRISE_CHAT)
            == ENTERPRISE_CHAT_CONFIG
        )
        assert get_config_for_tier(PresentationTier.DEVELOPMENT) == DEVELOPMENT_CONFIG


class TestEnterpriseSearchTier:
    """Tests for Enterprise Search tier behavior.

    Philosophy: Strictest, classification-focused. Minimal UX.
    """

    def test_strict_viparyaya_threshold(self):
        """Should have lowest viparyaya threshold (most sensitive)."""
        assert ENTERPRISE_SEARCH_CONFIG.viparyaya_critical_threshold == 0.2

    def test_triggers_earlier_than_consumer(self):
        """Should trigger viparyaya at lower values than consumer."""
        enterprise_engine = PresentationEngine(ENTERPRISE_SEARCH_CONFIG)
        consumer_engine = PresentationEngine(CONSUMER_CONFIG)

        # Value between thresholds: 0.25 (Enterprise triggers, Consumer doesn't)
        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.25),
        )

        enterprise_dir = enterprise_engine.compute(bundle)
        consumer_dir = consumer_engine.compute(bundle)

        assert enterprise_dir.triggered_rule == "critical_viparyaya"
        assert consumer_dir.triggered_rule != "critical_viparyaya"

    def test_allows_silent_mode(self):
        """Should allow SILENT mode for uncertain classifications."""
        assert ENTERPRISE_SEARCH_CONFIG.allow_silent_mode is True

    def test_includes_diagnostics(self):
        """Should include diagnostics for audit trail."""
        assert ENTERPRISE_SEARCH_CONFIG.include_diagnostics is True

    def test_terse_language(self):
        """Should use terse, tag-like language."""
        assert "[Uncertain]" in ENTERPRISE_SEARCH_CONFIG.hedging_phrases


class TestEnterpriseChatTier:
    """Tests for Enterprise Chat tier behavior.

    Philosophy: Strict but conversational. Flag uncertainty, maintain flow.
    """

    def test_moderate_thresholds(self):
        """Should have thresholds between Search and Consumer."""
        assert (
            ENTERPRISE_SEARCH_CONFIG.viparyaya_critical_threshold
            < ENTERPRISE_CHAT_CONFIG.viparyaya_critical_threshold
            < CONSUMER_CONFIG.viparyaya_critical_threshold
        )

    def test_disallows_silent_mode(self):
        """Chat must always respond - no SILENT mode."""
        assert ENTERPRISE_CHAT_CONFIG.allow_silent_mode is False

    def test_enables_escalation(self):
        """Should enable escalation to human review."""
        assert ENTERPRISE_CHAT_CONFIG.escalate_to_human is True

    def test_shows_reasoning_by_default(self):
        """Should show reasoning for transparency."""
        assert ENTERPRISE_CHAT_CONFIG.show_reasoning_by_default is True

    def test_professional_language(self):
        """Should use professional language."""
        assert any(
            "confidence" in phrase.lower()
            for phrase in ENTERPRISE_CHAT_CONFIG.hedging_phrases
        )


class TestConsumerTier:
    """Tests for Consumer tier behavior.

    Philosophy: Maximize flow, minimize interruption. Tolerant.
    """

    def test_highest_thresholds(self):
        """Should have highest thresholds (most tolerant)."""
        assert CONSUMER_CONFIG.viparyaya_critical_threshold == 0.6
        assert CONSUMER_CONFIG.nidra_severe_threshold == 0.8

    def test_disallows_silent_mode(self):
        """Consumer should never suppress output."""
        assert CONSUMER_CONFIG.allow_silent_mode is False

    def test_disables_escalation(self):
        """Consumer should handle issues internally."""
        assert CONSUMER_CONFIG.escalate_to_human is False

    def test_no_diagnostics(self):
        """Consumer should not see debug info."""
        assert CONSUMER_CONFIG.include_diagnostics is False

    def test_conversational_language(self):
        """Should use conversational language."""
        assert "I think" in CONSUMER_CONFIG.hedging_phrases

    def test_smooth_flow_in_moderate_uncertainty(self):
        """Should hedge but continue in moderate uncertainty."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        bundle = SignalBundle.create_minimal(score=0.55)
        directive = engine.compute(bundle)

        assert directive.delivery_mode == DeliveryMode.HEDGED
        assert directive.confidence == ConfidenceIndicator.MEDIUM


class TestDevelopmentTier:
    """Tests for Development tier behavior.

    Philosophy: All features, maximum verbosity for debugging.
    """

    def test_strict_thresholds_like_enterprise_search(self):
        """Should match Enterprise Search thresholds for accuracy testing."""
        assert (
            DEVELOPMENT_CONFIG.viparyaya_critical_threshold
            == ENTERPRISE_SEARCH_CONFIG.viparyaya_critical_threshold
        )
        assert (
            DEVELOPMENT_CONFIG.score_confident_threshold
            == ENTERPRISE_SEARCH_CONFIG.score_confident_threshold
        )

    def test_all_features_enabled(self):
        """Should have all features enabled."""
        assert DEVELOPMENT_CONFIG.allow_silent_mode is True
        assert DEVELOPMENT_CONFIG.escalate_to_human is True
        assert DEVELOPMENT_CONFIG.show_reasoning_by_default is True
        assert DEVELOPMENT_CONFIG.include_diagnostics is True

    def test_dev_tagged_language(self):
        """Should use DEV-tagged language for testing."""
        assert any("[DEV:" in phrase for phrase in DEVELOPMENT_CONFIG.hedging_phrases)


class TestCrossierComparison:
    """Compare behavior across tiers for same input."""

    def test_same_input_different_sensitivity(self):
        """Same input should produce different results based on tier."""
        bundle = SignalBundle.create_minimal(
            score=0.65,
            vritti=VrittiDistribution(viparyaya=0.35),
        )

        consumer_engine = PresentationEngine(CONSUMER_CONFIG)
        enterprise_engine = PresentationEngine(ENTERPRISE_CHAT_CONFIG)

        consumer_dir = consumer_engine.compute(bundle)
        enterprise_dir = enterprise_engine.compute(bundle)

        # Enterprise should catch the viparyaya (0.35 > 0.3 threshold)
        # Consumer should not (0.35 < 0.6 threshold)
        assert enterprise_dir.triggered_rule == "critical_viparyaya"
        assert consumer_dir.triggered_rule != "critical_viparyaya"

    def test_high_confidence_same_across_tiers(self):
        """Very high confidence should be confident across all tiers."""
        bundle = SignalBundle.create_minimal(
            score=0.95,
            coherence=0.98,
            vritti=VrittiDistribution(pramana=0.9),
        )

        for config in [
            CONSUMER_CONFIG,
            ENTERPRISE_SEARCH_CONFIG,
            ENTERPRISE_CHAT_CONFIG,
            DEVELOPMENT_CONFIG,
        ]:
            engine = PresentationEngine(config)
            directive = engine.compute(bundle)
            assert directive.triggered_rule == "high_pramana"
            assert directive.delivery_mode == DeliveryMode.CONFIDENT

    def test_severe_problem_caught_across_tiers(self):
        """Very high viparyaya should be caught by all tiers."""
        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.8),
        )

        for config in [
            CONSUMER_CONFIG,
            ENTERPRISE_SEARCH_CONFIG,
            ENTERPRISE_CHAT_CONFIG,
            DEVELOPMENT_CONFIG,
        ]:
            engine = PresentationEngine(config)
            directive = engine.compute(bundle)
            assert directive.triggered_rule == "critical_viparyaya"
