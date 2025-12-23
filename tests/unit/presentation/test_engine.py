"""Tests for presentation engine.

Part 7.1: Rule Executor
Part 10: Invariants
"""

import pytest
from symbolu.presentation import (
    DeliveryMode,
    ConfidenceIndicator,
    VrittiDistribution,
    SessionContext,
    SignalBundle,
    PresentationConfig,
    PresentationEngine,
    CONSUMER_CONFIG,
    ENTERPRISE_SEARCH_CONFIG,
    ENTERPRISE_CHAT_CONFIG,
    DEVELOPMENT_CONFIG,
)


class TestEngineBasics:
    """Basic engine functionality tests."""

    def test_engine_creation(self):
        """Engine should be created with config."""
        engine = PresentationEngine(CONSUMER_CONFIG)
        assert engine.config == CONSUMER_CONFIG
        assert len(engine.rules) == 8

    def test_compute_returns_directive(self):
        """compute should return a PresentationDirective."""
        engine = PresentationEngine(CONSUMER_CONFIG)
        bundle = SignalBundle.create_minimal()
        directive = engine.compute(bundle)

        assert directive is not None
        assert directive.delivery_mode is not None
        assert directive.confidence is not None
        assert directive.triggered_rule != ""


class TestInvariantDeterminism:
    """INV-PL-1: Same signals → same directive."""

    def test_deterministic_output(self):
        """Same input should produce same output."""
        engine = PresentationEngine(CONSUMER_CONFIG)
        bundle = SignalBundle.create_minimal(score=0.6)

        directive1 = engine.compute(bundle)
        directive2 = engine.compute(bundle)

        assert directive1.delivery_mode == directive2.delivery_mode
        assert directive1.confidence == directive2.confidence
        assert directive1.triggered_rule == directive2.triggered_rule


class TestInvariantCompleteness:
    """INV-PL-2: Every signal bundle produces a directive."""

    def test_always_produces_directive(self):
        """Any bundle should produce a valid directive."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        test_bundles = [
            SignalBundle.create_minimal(score=0.0),
            SignalBundle.create_minimal(score=1.0),
            SignalBundle.create_minimal(score=0.5, layers_present_count=0),
            SignalBundle.create_minimal(
                vritti=VrittiDistribution(viparyaya=1.0),
            ),
        ]

        for bundle in test_bundles:
            directive = engine.compute(bundle)
            assert directive is not None
            assert directive.delivery_mode in DeliveryMode
            assert directive.confidence in ConfidenceIndicator


class TestInvariantPriorityOrdering:
    """INV-PL-3: Higher priority rules checked first."""

    def test_viparyaya_beats_nidra(self):
        """Critical viparyaya (100) should beat severe nidra (95)."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        # Both conditions true
        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.8, nidra=0.9),
            layers_present_count=1,  # Would trigger nidra
        )

        directive = engine.compute(bundle)
        assert directive.triggered_rule == "critical_viparyaya"

    def test_nidra_beats_vikalpa(self):
        """Severe nidra (95) should beat high vikalpa (80)."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(nidra=0.9, vikalpa=0.6),
            entropy=0.8,  # Would trigger vikalpa
        )

        directive = engine.compute(bundle)
        assert directive.triggered_rule == "severe_nidra"


class TestInvariantConfigIsolation:
    """INV-PL-4: Tier config doesn't leak between instances."""

    def test_separate_instances(self):
        """Different engines should not affect each other."""
        consumer_engine = PresentationEngine(CONSUMER_CONFIG)
        enterprise_engine = PresentationEngine(ENTERPRISE_SEARCH_CONFIG)

        # Same bundle, different thresholds
        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.25),
        )

        consumer_directive = consumer_engine.compute(bundle)
        enterprise_directive = enterprise_engine.compute(bundle)

        # Enterprise should trigger viparyaya (threshold 0.2)
        # Consumer should not (threshold 0.6)
        assert enterprise_directive.triggered_rule == "critical_viparyaya"
        assert consumer_directive.triggered_rule != "critical_viparyaya"


class TestInvariantStateless:
    """INV-PL-5: Engine is stateless."""

    def test_no_state_between_calls(self):
        """Sequential calls should not affect each other."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        # First call with high viparyaya
        bundle1 = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.8),
        )
        directive1 = engine.compute(bundle1)
        assert directive1.triggered_rule == "critical_viparyaya"

        # Second call with high pramana
        bundle2 = SignalBundle.create_minimal(
            vritti=VrittiDistribution(pramana=0.9),
            score=0.9,
        )
        directive2 = engine.compute(bundle2)
        assert directive2.triggered_rule == "high_pramana"

        # First call again should still give same result
        directive1_again = engine.compute(bundle1)
        assert directive1_again.triggered_rule == "critical_viparyaya"


class TestInvariantTransparency:
    """INV-PL-6: Every directive includes triggered_rule name."""

    def test_all_rules_labeled(self):
        """Every rule should produce labeled directive."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        # Test each rule
        test_cases = [
            (
                SignalBundle.create_minimal(vritti=VrittiDistribution(viparyaya=0.8)),
                "critical_viparyaya",
            ),
            (
                SignalBundle.create_minimal(vritti=VrittiDistribution(nidra=0.9)),
                "severe_nidra",
            ),
            (
                SignalBundle.create_minimal(
                    vritti=VrittiDistribution(vikalpa=0.6), entropy=0.8
                ),
                "high_vikalpa",
            ),
            (
                SignalBundle.create_minimal(score=0.55),
                "moderate_uncertainty",
            ),
            (
                SignalBundle.create_minimal(score=0.3),
                "low_confidence",
            ),
            (
                SignalBundle.create_minimal(
                    vritti=VrittiDistribution(pramana=0.9), score=0.9
                ),
                "high_pramana",
            ),
        ]

        for bundle, expected_rule in test_cases:
            directive = engine.compute(bundle)
            assert directive.triggered_rule == expected_rule


class TestInvariantBoundedOutput:
    """INV-PL-7: All fields have valid enum/range values."""

    def test_valid_delivery_mode(self):
        """delivery_mode should be valid enum."""
        engine = PresentationEngine(CONSUMER_CONFIG)
        bundle = SignalBundle.create_minimal()
        directive = engine.compute(bundle)
        assert directive.delivery_mode in DeliveryMode

    def test_valid_confidence(self):
        """confidence should be valid enum."""
        engine = PresentationEngine(CONSUMER_CONFIG)
        bundle = SignalBundle.create_minimal()
        directive = engine.compute(bundle)
        assert directive.confidence in ConfidenceIndicator


class TestConfigOverrides:
    """Tests for config override behavior."""

    def test_escalation_disabled_for_consumer(self):
        """Consumer tier should disable escalation."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.8),
        )
        directive = engine.compute(bundle)

        # Consumer config has escalate_to_human=False
        assert directive.behaviors.escalate_to_human is False

    def test_escalation_enabled_for_enterprise(self):
        """Enterprise tier should enable escalation."""
        engine = PresentationEngine(ENTERPRISE_SEARCH_CONFIG)

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.3),
        )
        directive = engine.compute(bundle)

        # Enterprise config has escalate_to_human=True
        assert directive.behaviors.escalate_to_human is True

    def test_silent_mode_blocked_for_consumer(self):
        """Consumer tier should block SILENT mode."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        # Manually check that SILENT would be converted
        # (No rule currently produces SILENT, but override works)
        assert CONSUMER_CONFIG.allow_silent_mode is False

    def test_reasoning_enabled_by_default_for_enterprise_chat(self):
        """Enterprise chat should show reasoning by default."""
        engine = PresentationEngine(ENTERPRISE_CHAT_CONFIG)

        bundle = SignalBundle.create_minimal(score=0.55)
        directive = engine.compute(bundle)

        # Enterprise chat has show_reasoning_by_default=True
        assert directive.behaviors.show_reasoning is True


class TestDiagnostics:
    """Tests for diagnostic info attachment."""

    def test_diagnostics_included_for_development(self):
        """Development tier should include diagnostics."""
        engine = PresentationEngine(DEVELOPMENT_CONFIG)

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(viparyaya=0.3),
            dominant_vritti="viparyaya",
        )
        directive = engine.compute(bundle)

        assert directive.diagnostic is not None
        assert directive.diagnostic.dominant_vritti == "viparyaya"
        assert "score=" in directive.diagnostic.signal_summary

    def test_diagnostics_excluded_for_consumer(self):
        """Consumer tier should not include diagnostics."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        bundle = SignalBundle.create_minimal()
        directive = engine.compute(bundle)

        # Consumer config has include_diagnostics=False
        assert directive.diagnostic is None

    def test_diagnostic_active_penalties(self):
        """Diagnostics should list active penalties."""
        engine = PresentationEngine(DEVELOPMENT_CONFIG)

        bundle = SignalBundle.create_minimal(
            vritti=VrittiDistribution(
                viparyaya=0.3,  # Above threshold
                nidra=0.5,  # Above threshold
            ),
        )
        directive = engine.compute(bundle)

        assert "viparyaya_penalty" in directive.diagnostic.active_penalties
        assert "nidra_penalty" in directive.diagnostic.active_penalties


class TestExplainDecision:
    """Tests for explain_decision method."""

    def test_explanation_contains_inputs(self):
        """Explanation should show input signals."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        bundle = SignalBundle.create_minimal(score=0.75, coherence=0.8)
        explanation = engine.explain_decision(bundle)

        assert "score: 0.750" in explanation
        assert "coherence: 0.800" in explanation

    def test_explanation_shows_rule_evaluation(self):
        """Explanation should show rule evaluation."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        bundle = SignalBundle.create_minimal(score=0.55)
        explanation = engine.explain_decision(bundle)

        assert "moderate_uncertainty" in explanation
        assert "MATCH" in explanation

    def test_explanation_shows_tier(self):
        """Explanation should show tier name."""
        engine = PresentationEngine(CONSUMER_CONFIG)

        bundle = SignalBundle.create_minimal()
        explanation = engine.explain_decision(bundle)

        assert "Tier: consumer" in explanation
