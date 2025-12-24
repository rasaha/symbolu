"""Tests for v2.7 experimental rules and signals.

Tests the v2.7 experimental features:
- V27ExperimentalSignals: EMA and Bayesian modes
- V2.7 rules: unreliable_estimate, regressing_state, concept_unstable, low_utility_streak
- Switch behavior: rules only fire when v2.7 is enabled
"""

import pytest
from symbolu.presentation import (
    DeliveryMode,
    ConfidenceIndicator,
    VrittiDistribution,
    SessionContext,
    SignalBundle,
    V27ExperimentalSignals,
    PresentationEngine,
    CONSUMER_CONFIG,
    ENTERPRISE_CHAT_CONFIG,
)
from symbolu.presentation.rules import build_rules


class TestV27ExperimentalSignals:
    """Tests for V27ExperimentalSignals dataclass."""

    def test_disabled_by_default(self):
        """Default signals should have v27 disabled."""
        signals = V27ExperimentalSignals()
        assert signals.v27_enabled is False
        assert signals.bayesian_mode is False
        assert signals.is_available is False

    def test_disabled_factory(self):
        """disabled() factory should create disabled signals."""
        signals = V27ExperimentalSignals.disabled()
        assert signals.is_available is False
        assert signals.has_bayesian_signals is False

    def test_ema_mode(self):
        """EMA mode should have v27 enabled but no Bayesian signals."""
        signals = V27ExperimentalSignals.ema_mode(
            cognitive_state="thriving",
            concept_readiness=0.8,
        )
        assert signals.is_available is True
        assert signals.has_bayesian_signals is False
        assert signals.bayesian_confidence is None
        assert signals.cognitive_state == "thriving"

    def test_bayesian_mode(self):
        """Bayesian mode should have both v27 and Bayesian signals."""
        signals = V27ExperimentalSignals.bayesian_mode_signals(
            bayesian_confidence=0.85,
            credible_interval_width=0.1,
            cognitive_state="stable",
        )
        assert signals.is_available is True
        assert signals.has_bayesian_signals is True
        assert signals.bayesian_confidence == 0.85
        assert signals.is_estimate_reliable is True

    def test_is_estimate_reliable_low_confidence(self):
        """Low Bayesian confidence should be unreliable."""
        signals = V27ExperimentalSignals.bayesian_mode_signals(
            bayesian_confidence=0.4,
        )
        assert signals.is_estimate_reliable is False

    def test_is_estimate_reliable_no_bayesian(self):
        """Without Bayesian mode, assume reliable."""
        signals = V27ExperimentalSignals.ema_mode()
        assert signals.is_estimate_reliable is True

    def test_is_regressing(self):
        """Regressing/unstable states should be detected."""
        for state in ["regressing", "unstable"]:
            signals = V27ExperimentalSignals.ema_mode(cognitive_state=state)
            assert signals.is_regressing is True

    def test_is_not_regressing(self):
        """Non-regressing states should not be flagged."""
        for state in ["thriving", "striving", "stable", "neutral"]:
            signals = V27ExperimentalSignals.ema_mode(cognitive_state=state)
            assert signals.is_regressing is False

    def test_is_concept_stable(self):
        """Concept stability check."""
        high = V27ExperimentalSignals.ema_mode(concept_readiness=0.8)
        low = V27ExperimentalSignals.ema_mode(concept_readiness=0.3)
        assert high.is_concept_stable is True
        assert low.is_concept_stable is False

    def test_validation_cognitive_state(self):
        """Invalid cognitive state should raise error."""
        with pytest.raises(ValueError):
            V27ExperimentalSignals(v27_enabled=True, cognitive_state="invalid")

    def test_validation_concept_readiness_level(self):
        """Invalid concept readiness level should raise error."""
        with pytest.raises(ValueError):
            V27ExperimentalSignals(v27_enabled=True, concept_readiness_level="invalid")


class TestSignalBundleV27:
    """Tests for SignalBundle with v2.7 signals."""

    def test_default_no_v27(self):
        """Default bundle should not have v2.7 signals."""
        bundle = SignalBundle.create_minimal()
        assert bundle.v27 is None
        assert bundle.has_v27_signals is False
        assert bundle.has_bayesian_signals is False

    def test_with_v27_ema(self):
        """Bundle with EMA v2.7 signals."""
        v27 = V27ExperimentalSignals.ema_mode(cognitive_state="thriving")
        bundle = SignalBundle.create_with_v27(v27)
        assert bundle.has_v27_signals is True
        assert bundle.has_bayesian_signals is False

    def test_with_v27_bayesian(self):
        """Bundle with Bayesian v2.7 signals."""
        v27 = V27ExperimentalSignals.bayesian_mode_signals(bayesian_confidence=0.9)
        bundle = SignalBundle.create_with_v27(v27)
        assert bundle.has_v27_signals is True
        assert bundle.has_bayesian_signals is True


class TestV27RulesBuildRules:
    """Tests for v2.7 rule inclusion in build_rules."""

    def test_v27_rules_included_by_default(self):
        """V2.7 rules should be included by default."""
        rules = build_rules(CONSUMER_CONFIG)
        rule_names = [r.name for r in rules]
        assert "unreliable_estimate_v27" in rule_names
        assert "regressing_state_v27" in rule_names
        assert "concept_unstable_v27" in rule_names
        assert "low_utility_streak_v27" in rule_names

    def test_v27_rules_excluded_when_disabled(self):
        """V2.7 rules should be excluded when include_v27_rules=False."""
        rules = build_rules(CONSUMER_CONFIG, include_v27_rules=False)
        rule_names = [r.name for r in rules]
        assert "unreliable_estimate_v27" not in rule_names
        assert "regressing_state_v27" not in rule_names
        assert "concept_unstable_v27" not in rule_names
        assert "low_utility_streak_v27" not in rule_names

    def test_rule_count_with_v27(self):
        """Should have 12 rules with v2.7 (8 core + 4 v2.7)."""
        rules = build_rules(CONSUMER_CONFIG, include_v27_rules=True)
        assert len(rules) == 12

    def test_rule_count_without_v27(self):
        """Should have 8 rules without v2.7."""
        rules = build_rules(CONSUMER_CONFIG, include_v27_rules=False)
        assert len(rules) == 8


class TestV27RulesDoNotFireWithoutSignals:
    """Tests that v2.7 rules don't fire when v2.7 signals are absent."""

    def test_unreliable_estimate_needs_bayesian(self):
        """unreliable_estimate should not fire without Bayesian signals."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "unreliable_estimate_v27")

        # No v27 signals at all
        bundle_no_v27 = SignalBundle.create_minimal()
        assert rule.condition(bundle_no_v27, CONSUMER_CONFIG) is False

        # EMA mode (no Bayesian)
        v27_ema = V27ExperimentalSignals.ema_mode()
        bundle_ema = SignalBundle.create_with_v27(v27_ema)
        assert rule.condition(bundle_ema, CONSUMER_CONFIG) is False

    def test_regressing_state_needs_v27(self):
        """regressing_state should not fire without v2.7 signals."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "regressing_state_v27")

        bundle_no_v27 = SignalBundle.create_minimal()
        assert rule.condition(bundle_no_v27, CONSUMER_CONFIG) is False

    def test_concept_unstable_needs_v27(self):
        """concept_unstable should not fire without v2.7 signals."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "concept_unstable_v27")

        bundle_no_v27 = SignalBundle.create_minimal()
        assert rule.condition(bundle_no_v27, CONSUMER_CONFIG) is False

    def test_low_utility_streak_needs_v27(self):
        """low_utility_streak should not fire without v2.7 signals."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "low_utility_streak_v27")

        bundle_no_v27 = SignalBundle.create_minimal()
        assert rule.condition(bundle_no_v27, CONSUMER_CONFIG) is False


class TestV27RulesFireWithSignals:
    """Tests that v2.7 rules fire correctly when signals are present."""

    def test_unreliable_estimate_fires(self):
        """unreliable_estimate should fire with low Bayesian confidence."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "unreliable_estimate_v27")

        v27 = V27ExperimentalSignals.bayesian_mode_signals(bayesian_confidence=0.3)
        bundle = SignalBundle.create_with_v27(v27)
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_unreliable_estimate_no_fire_high_confidence(self):
        """unreliable_estimate should not fire with high Bayesian confidence."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "unreliable_estimate_v27")

        v27 = V27ExperimentalSignals.bayesian_mode_signals(bayesian_confidence=0.8)
        bundle = SignalBundle.create_with_v27(v27)
        assert rule.condition(bundle, CONSUMER_CONFIG) is False

    def test_regressing_state_fires(self):
        """regressing_state should fire when cognitive state is regressing."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "regressing_state_v27")

        for state in ["regressing", "unstable"]:
            v27 = V27ExperimentalSignals.ema_mode(cognitive_state=state)
            bundle = SignalBundle.create_with_v27(v27)
            assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_regressing_state_no_fire_stable(self):
        """regressing_state should not fire when cognitive state is stable."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "regressing_state_v27")

        v27 = V27ExperimentalSignals.ema_mode(cognitive_state="thriving")
        bundle = SignalBundle.create_with_v27(v27)
        assert rule.condition(bundle, CONSUMER_CONFIG) is False

    def test_concept_unstable_fires(self):
        """concept_unstable should fire with low concept readiness."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "concept_unstable_v27")

        v27 = V27ExperimentalSignals.ema_mode(
            concept_readiness=0.2,
            concept_readiness_level="emerging",
        )
        bundle = SignalBundle.create_with_v27(v27)
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_concept_unstable_no_fire_high(self):
        """concept_unstable should not fire with high concept readiness."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "concept_unstable_v27")

        v27 = V27ExperimentalSignals.ema_mode(concept_readiness=0.8)
        bundle = SignalBundle.create_with_v27(v27)
        assert rule.condition(bundle, CONSUMER_CONFIG) is False

    def test_low_utility_streak_fires(self):
        """low_utility_streak should fire with streak >= 5."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "low_utility_streak_v27")

        v27 = V27ExperimentalSignals.ema_mode(low_utility_streak=6)
        bundle = SignalBundle.create_with_v27(v27)
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_low_utility_streak_no_fire_low(self):
        """low_utility_streak should not fire with streak < 5."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "low_utility_streak_v27")

        v27 = V27ExperimentalSignals.ema_mode(low_utility_streak=3)
        bundle = SignalBundle.create_with_v27(v27)
        assert rule.condition(bundle, CONSUMER_CONFIG) is False


class TestEngineWithV27:
    """Integration tests for PresentationEngine with v2.7 signals."""

    def test_engine_with_v27_disabled(self):
        """Engine should work normally without v2.7 signals."""
        engine = PresentationEngine(CONSUMER_CONFIG)
        bundle = SignalBundle.create_minimal(score=0.55)
        directive = engine.compute(bundle)

        # Should fall through to moderate_uncertainty (no v2.7 rules fire)
        assert directive.triggered_rule == "moderate_uncertainty"

    def test_engine_with_v27_ema_regressing(self):
        """Engine should detect regressing state in EMA mode."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        v27 = V27ExperimentalSignals.ema_mode(cognitive_state="regressing")
        bundle = SignalBundle.create_with_v27(v27, score=0.7)
        directive = engine.compute(bundle)

        assert directive.triggered_rule == "regressing_state_v27"
        assert directive.delivery_mode == DeliveryMode.CLARIFYING

    def test_engine_with_v27_bayesian_low_confidence(self):
        """Engine should detect low Bayesian confidence."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        v27 = V27ExperimentalSignals.bayesian_mode_signals(bayesian_confidence=0.3)
        bundle = SignalBundle.create_with_v27(v27, score=0.7)
        directive = engine.compute(bundle)

        assert directive.triggered_rule == "unreliable_estimate_v27"
        assert directive.confidence == ConfidenceIndicator.LOW

    def test_engine_v27_rules_have_correct_priority(self):
        """V2.7 rules should have correct priority ordering."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        # Both unreliable_estimate (98) and regressing_state (88) could fire
        # unreliable_estimate should win due to higher priority
        v27 = V27ExperimentalSignals.bayesian_mode_signals(
            bayesian_confidence=0.2,
            cognitive_state="regressing",
        )
        bundle = SignalBundle.create_with_v27(v27)
        directive = engine.compute(bundle)

        assert directive.triggered_rule == "unreliable_estimate_v27"

    def test_core_rules_still_take_precedence(self):
        """Core rules with higher priority should still win."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        # critical_viparyaya (100) > unreliable_estimate (98)
        v27 = V27ExperimentalSignals.bayesian_mode_signals(bayesian_confidence=0.3)
        bundle = SignalBundle.create_with_v27(
            v27,
            vritti=VrittiDistribution(viparyaya=0.8),
        )
        directive = engine.compute(bundle)

        assert directive.triggered_rule == "critical_viparyaya"
