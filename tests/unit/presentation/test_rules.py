"""Tests for presentation rules.

Part 4: Rule Definitions
Tests each of the 8 prioritized rules.
"""

import pytest
from symbolu.presentation import (
    DeliveryMode,
    ConfidenceIndicator,
    VrittiDistribution,
    SessionContext,
    SignalBundle,
    PresentationConfig,
    CONSUMER_CONFIG,
    ENTERPRISE_SEARCH_CONFIG,
)
from symbolu.presentation.rules import build_rules


class TestRulePriorities:
    """Test rule priority ordering."""

    def test_rules_sorted_by_priority(self):
        """Rules should be sorted in descending priority order."""
        rules = build_rules(CONSUMER_CONFIG)
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_critical_viparyaya_highest(self):
        """Critical viparyaya should have highest priority."""
        rules = build_rules(CONSUMER_CONFIG)
        assert rules[0].name == "critical_viparyaya"
        assert rules[0].priority == 100

    def test_default_lowest(self):
        """Default rule should have lowest priority."""
        rules = build_rules(CONSUMER_CONFIG)
        assert rules[-1].name == "default"
        assert rules[-1].priority == 0


class TestCriticalViparyayaRule:
    """Tests for Rule 1: Critical Viparyaya (Priority 100)."""

    def test_high_viparyaya_triggers(self):
        """High viparyaya alone should trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "critical_viparyaya")

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.7),
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_moderate_viparyaya_with_high_confidence_triggers(self):
        """Moderate viparyaya with high confidence should trigger."""
        # Consumer tier: threshold * 0.6 = 0.6 * 0.6 = 0.36
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "critical_viparyaya")

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.4),
            confidence=0.9,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_low_viparyaya_does_not_trigger(self):
        """Low viparyaya should not trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "critical_viparyaya")

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.2),
            confidence=0.5,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is False

    def test_directive_output(self):
        """Directive should have correct structure."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "critical_viparyaya")

        bundle = SignalBundle.create_minimal()
        directive = rule.directive(bundle, CONSUMER_CONFIG)

        assert directive.delivery_mode == DeliveryMode.ACKNOWLEDGING
        assert directive.confidence == ConfidenceIndicator.LOW
        assert directive.behaviors.show_alternatives is True
        assert directive.triggered_rule == "critical_viparyaya"


class TestSevereNidraRule:
    """Tests for Rule 2: Severe Nidrā (Priority 95)."""

    def test_high_nidra_triggers(self):
        """High nidra should trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "severe_nidra")

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(nidra=0.9),
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_few_layers_triggers(self):
        """Less than 2 layers should trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "severe_nidra")

        bundle = SignalBundle.create_minimal(
            layers_present_count=1,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_normal_state_does_not_trigger(self):
        """Normal state should not trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "severe_nidra")

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(nidra=0.2),
            layers_present_count=4,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is False


class TestHighVikalpaRule:
    """Tests for Rule 3: High Vikalpa (Priority 80)."""

    def test_high_vikalpa_with_entropy_triggers(self):
        """High vikalpa with high entropy should trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "high_vikalpa")

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(vikalpa=0.6),
            entropy=0.7,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_high_vikalpa_low_entropy_does_not_trigger(self):
        """High vikalpa with low entropy should not trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "high_vikalpa")

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(vikalpa=0.6),
            entropy=0.3,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is False


class TestElevatedSmrtiRule:
    """Tests for Rule 4: Elevated Smṛti (Priority 70)."""

    def test_high_smrti_with_low_motion_streak_triggers(self):
        """High smrti with low motion streak should trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "elevated_smrti")

        session = SessionContext(consecutive_low_motion=5)
        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(smrti=0.7),
            session=session,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_high_smrti_without_streak_does_not_trigger(self):
        """High smrti without low motion streak should not trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "elevated_smrti")

        session = SessionContext(consecutive_low_motion=1)
        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(smrti=0.7),
            session=session,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is False


class TestModerateUncertaintyRule:
    """Tests for Rule 5: Moderate Uncertainty (Priority 60)."""

    def test_moderate_score_triggers(self):
        """Score in moderate range should trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "moderate_uncertainty")

        # Consumer: score_moderate=0.4, score_confident=0.7
        bundle = SignalBundle.create_minimal(score=0.55)
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_low_score_does_not_trigger(self):
        """Score below moderate threshold should not trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "moderate_uncertainty")

        bundle = SignalBundle.create_minimal(score=0.3)
        assert rule.condition(bundle, CONSUMER_CONFIG) is False


class TestLowConfidenceRule:
    """Tests for Rule 6: Low Confidence (Priority 55)."""

    def test_low_score_triggers(self):
        """Score below moderate threshold should trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "low_confidence")

        bundle = SignalBundle.create_minimal(score=0.3)
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_moderate_score_does_not_trigger(self):
        """Score at or above moderate threshold should not trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "low_confidence")

        bundle = SignalBundle.create_minimal(score=0.5)
        assert rule.condition(bundle, CONSUMER_CONFIG) is False


class TestHighPramanaRule:
    """Tests for Rule 7: High Pramāṇa (Priority 50)."""

    def test_high_pramana_with_high_score_triggers(self):
        """High pramana with high score should trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "high_pramana")

        # Consumer: pramana_high=0.6, score_confident=0.7
        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(pramana=0.8),
            score=0.85,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_high_pramana_low_score_does_not_trigger(self):
        """High pramana with low score should not trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "high_pramana")

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(pramana=0.8),
            score=0.5,
        )
        assert rule.condition(bundle, CONSUMER_CONFIG) is False


class TestDefaultRule:
    """Tests for Rule 8: Default (Priority 0)."""

    def test_always_triggers(self):
        """Default rule should always trigger."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "default")

        bundle = SignalBundle.create_minimal()
        assert rule.condition(bundle, CONSUMER_CONFIG) is True

    def test_directive_is_hedged(self):
        """Default directive should be hedged delivery."""
        rules = build_rules(CONSUMER_CONFIG)
        rule = next(r for r in rules if r.name == "default")

        bundle = SignalBundle.create_minimal()
        directive = rule.directive(bundle, CONSUMER_CONFIG)

        assert directive.delivery_mode == DeliveryMode.HEDGED
        assert directive.confidence == ConfidenceIndicator.MEDIUM
